"""
Ombra GitHub Integration
========================
GitHub API wrapper for PR creation, code review, issue management,
branch operations, and repository interactions.
Uses httpx async client with the GitHub REST API.
"""

import os
import json
import asyncio
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    httpx = None


GITHUB_API = "https://api.github.com"


@dataclass
class GitHubConfig:
    token: str = ""
    default_owner: str = ""
    default_repo: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            token=os.environ.get("GITHUB_TOKEN", ""),
            default_owner=os.environ.get("GITHUB_OWNER", ""),
            default_repo=os.environ.get("GITHUB_REPO", ""),
        )


class GitHubClient:
    """Async GitHub API client for common operations."""

    def __init__(self, config: GitHubConfig = None):
        self.config = config or GitHubConfig.from_env()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> "httpx.AsyncClient":
        if not httpx:
            raise RuntimeError("httpx not installed. pip install httpx")
        if not self.config.token:
            raise RuntimeError("GITHUB_TOKEN not set")
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    def _repo_parts(self, owner: str = None, repo: str = None):
        o = owner or self.config.default_owner
        r = repo or self.config.default_repo
        if not o or not r:
            raise ValueError("owner and repo are required (set GITHUB_OWNER/GITHUB_REPO or pass explicitly)")
        return o, r

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Repository ────────────────────────────────────────────────────────────

    async def get_repo(self, owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(f"/repos/{o}/{r}")
        resp.raise_for_status()
        data = resp.json()
        return {
            "name": data["full_name"],
            "description": data.get("description", ""),
            "default_branch": data["default_branch"],
            "stars": data["stargazers_count"],
            "open_issues": data["open_issues_count"],
            "language": data.get("language", ""),
            "private": data["private"],
        }

    # ── Branches ──────────────────────────────────────────────────────────────

    async def list_branches(self, owner: str = None, repo: str = None,
                            limit: int = 30) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(f"/repos/{o}/{r}/branches", params={"per_page": limit})
        resp.raise_for_status()
        return [{"name": b["name"], "sha": b["commit"]["sha"]} for b in resp.json()]

    async def create_branch(self, branch_name: str, from_branch: str = None,
                            owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()

        # Get SHA of source branch
        if not from_branch:
            repo_info = await self.get_repo(o, r)
            from_branch = repo_info["default_branch"]

        ref_resp = await client.get(f"/repos/{o}/{r}/git/refs/heads/{from_branch}")
        ref_resp.raise_for_status()
        sha = ref_resp.json()["object"]["sha"]

        # Create the new branch
        resp = await client.post(f"/repos/{o}/{r}/git/refs", json={
            "ref": f"refs/heads/{branch_name}",
            "sha": sha,
        })
        resp.raise_for_status()
        return {"branch": branch_name, "sha": sha, "from": from_branch}

    # ── Pull Requests ─────────────────────────────────────────────────────────

    async def create_pr(self, title: str, body: str, head: str, base: str = None,
                        draft: bool = False, owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()

        if not base:
            repo_info = await self.get_repo(o, r)
            base = repo_info["default_branch"]

        resp = await client.post(f"/repos/{o}/{r}/pulls", json={
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        })
        resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "url": data["html_url"],
            "title": data["title"],
            "state": data["state"],
            "head": data["head"]["ref"],
            "base": data["base"]["ref"],
        }

    async def list_prs(self, state: str = "open", owner: str = None,
                       repo: str = None, limit: int = 20) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(f"/repos/{o}/{r}/pulls", params={
            "state": state, "per_page": limit
        })
        resp.raise_for_status()
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": pr["user"]["login"],
                "head": pr["head"]["ref"],
                "base": pr["base"]["ref"],
                "url": pr["html_url"],
                "created_at": pr["created_at"],
            }
            for pr in resp.json()
        ]

    async def get_pr(self, number: int, owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(f"/repos/{o}/{r}/pulls/{number}")
        resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "body": data.get("body", ""),
            "state": data["state"],
            "mergeable": data.get("mergeable"),
            "author": data["user"]["login"],
            "head": data["head"]["ref"],
            "base": data["base"]["ref"],
            "additions": data.get("additions", 0),
            "deletions": data.get("deletions", 0),
            "changed_files": data.get("changed_files", 0),
            "url": data["html_url"],
        }

    async def get_pr_diff(self, number: int, owner: str = None, repo: str = None) -> str:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(
            f"/repos/{o}/{r}/pulls/{number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        resp.raise_for_status()
        return resp.text

    async def review_pr(self, number: int, body: str, event: str = "COMMENT",
                        owner: str = None, repo: str = None) -> dict:
        """Submit a PR review. event: APPROVE, REQUEST_CHANGES, COMMENT."""
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.post(f"/repos/{o}/{r}/pulls/{number}/reviews", json={
            "body": body,
            "event": event,
        })
        resp.raise_for_status()
        data = resp.json()
        return {"review_id": data["id"], "state": data["state"], "url": data["html_url"]}

    async def merge_pr(self, number: int, method: str = "squash",
                       owner: str = None, repo: str = None) -> dict:
        """Merge a PR. method: merge, squash, rebase."""
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.put(f"/repos/{o}/{r}/pulls/{number}/merge", json={
            "merge_method": method,
        })
        resp.raise_for_status()
        data = resp.json()
        return {"merged": data.get("merged", False), "sha": data.get("sha", ""), "message": data.get("message", "")}

    # ── Issues ────────────────────────────────────────────────────────────────

    async def list_issues(self, state: str = "open", labels: str = "",
                          owner: str = None, repo: str = None,
                          limit: int = 20) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        params = {"state": state, "per_page": limit}
        if labels:
            params["labels"] = labels
        resp = await client.get(f"/repos/{o}/{r}/issues", params=params)
        resp.raise_for_status()
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "labels": [l["name"] for l in i["labels"]],
                "author": i["user"]["login"],
                "created_at": i["created_at"],
                "url": i["html_url"],
            }
            for i in resp.json()
            if "pull_request" not in i  # Filter out PRs
        ]

    async def create_issue(self, title: str, body: str = "",
                           labels: list[str] = None, assignees: list[str] = None,
                           owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        payload = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        resp = await client.post(f"/repos/{o}/{r}/issues", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "number": data["number"],
            "title": data["title"],
            "url": data["html_url"],
        }

    async def comment_on_issue(self, number: int, body: str,
                               owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.post(f"/repos/{o}/{r}/issues/{number}/comments", json={
            "body": body,
        })
        resp.raise_for_status()
        data = resp.json()
        return {"comment_id": data["id"], "url": data["html_url"]}

    # ── Files ─────────────────────────────────────────────────────────────────

    async def get_file_content(self, path: str, ref: str = None,
                               owner: str = None, repo: str = None) -> dict:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        params = {}
        if ref:
            params["ref"] = ref
        resp = await client.get(f"/repos/{o}/{r}/contents/{path}", params=params)
        resp.raise_for_status()
        data = resp.json()

        import base64
        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")

        return {
            "path": data["path"],
            "size": data.get("size", 0),
            "sha": data["sha"],
            "content": content,
        }

    async def search_code(self, query: str, owner: str = None,
                          repo: str = None, limit: int = 10) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get("/search/code", params={
            "q": f"{query} repo:{o}/{r}",
            "per_page": limit,
        })
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "path": item["path"],
                "name": item["name"],
                "url": item["html_url"],
                "score": item.get("score", 0),
            }
            for item in data.get("items", [])
        ]

    # ── Commits ───────────────────────────────────────────────────────────────

    async def list_commits(self, branch: str = None, path: str = None,
                           owner: str = None, repo: str = None,
                           limit: int = 10) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        params = {"per_page": limit}
        if branch:
            params["sha"] = branch
        if path:
            params["path"] = path
        resp = await client.get(f"/repos/{o}/{r}/commits", params=params)
        resp.raise_for_status()
        return [
            {
                "sha": c["sha"][:8],
                "message": c["commit"]["message"].split("\n")[0],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            }
            for c in resp.json()
        ]

    # ── Actions / Workflows ───────────────────────────────────────────────────

    async def list_workflow_runs(self, owner: str = None, repo: str = None,
                                 limit: int = 10) -> list[dict]:
        o, r = self._repo_parts(owner, repo)
        client = await self._get_client()
        resp = await client.get(f"/repos/{o}/{r}/actions/runs", params={"per_page": limit})
        resp.raise_for_status()
        runs = resp.json().get("workflow_runs", [])
        return [
            {
                "id": run["id"],
                "name": run["name"],
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "branch": run["head_branch"],
                "created_at": run["created_at"],
                "url": run["html_url"],
            }
            for run in runs
        ]


# ── Global instance ───────────────────────────────────────────────────────────
github_client = GitHubClient()
