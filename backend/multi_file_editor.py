"""
Ombra Multi-File Editor
=======================
Coordinated multi-file editing with atomic rollback support.
Tracks file snapshots, applies diffs, and supports undo.
"""

import os
import time
import uuid
import shutil
import difflib
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class FileSnapshot:
    """Snapshot of a file's content before editing."""
    path: str
    content: str
    exists: bool
    timestamp: str


@dataclass
class FileEdit:
    """A single edit operation on a file."""
    path: str
    operation: str   # "create", "modify", "delete", "rename"
    new_content: str | None = None
    old_path: str | None = None     # For rename
    search: str | None = None       # For search-and-replace
    replace: str | None = None      # For search-and-replace


@dataclass
class EditSession:
    """An atomic editing transaction across multiple files."""
    id: str
    description: str
    edits: list[FileEdit]
    snapshots: dict[str, FileSnapshot] = field(default_factory=dict)
    applied: bool = False
    rolled_back: bool = False
    created_at: str = ""
    applied_at: str | None = None
    results: list[dict] = field(default_factory=list)


class MultiFileEditor:
    """
    Manages coordinated multi-file edits with atomic rollback.
    """

    def __init__(self, work_dir: str = "/tmp/ombra_workspace"):
        self.work_dir = work_dir
        self._sessions: dict[str, EditSession] = {}
        self._max_sessions = 50

    def _resolve_path(self, path: str) -> str:
        """Resolve a path relative to work_dir, preventing traversal."""
        if os.path.isabs(path):
            resolved = os.path.realpath(path)
        else:
            resolved = os.path.realpath(os.path.join(self.work_dir, path))

        # Security: ensure we stay within work_dir
        work_dir_real = os.path.realpath(self.work_dir)
        if not resolved.startswith(work_dir_real):
            raise ValueError(f"Path escapes work directory: {path}")
        return resolved

    def _snapshot_file(self, path: str) -> FileSnapshot:
        """Take a snapshot of a file's current state."""
        resolved = self._resolve_path(path)
        exists = os.path.exists(resolved)
        content = ""
        if exists and os.path.isfile(resolved):
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        return FileSnapshot(
            path=resolved,
            content=content,
            exists=exists,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def create_session(self, description: str, edits: list[dict]) -> str:
        """
        Create a new editing session with a list of edits.
        Each edit dict: {path, operation, new_content?, search?, replace?, old_path?}
        Returns session ID.
        """
        session_id = f"edit_{uuid.uuid4().hex[:8]}"
        file_edits = []
        for e in edits:
            file_edits.append(FileEdit(
                path=e["path"],
                operation=e["operation"],
                new_content=e.get("new_content"),
                old_path=e.get("old_path"),
                search=e.get("search"),
                replace=e.get("replace"),
            ))

        session = EditSession(
            id=session_id,
            description=description,
            edits=file_edits,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Pre-snapshot all affected files
        for edit in file_edits:
            resolved = self._resolve_path(edit.path)
            if resolved not in session.snapshots:
                session.snapshots[resolved] = self._snapshot_file(edit.path)
            if edit.old_path:
                old_resolved = self._resolve_path(edit.old_path)
                if old_resolved not in session.snapshots:
                    session.snapshots[old_resolved] = self._snapshot_file(edit.old_path)

        self._sessions[session_id] = session

        # Evict old sessions
        if len(self._sessions) > self._max_sessions:
            oldest = sorted(self._sessions.values(), key=lambda s: s.created_at)
            for s in oldest[:len(self._sessions) - self._max_sessions]:
                del self._sessions[s.id]

        return session_id

    def apply_session(self, session_id: str) -> dict:
        """
        Apply all edits in a session atomically.
        If any edit fails, rolls back all changes.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "error": f"Session '{session_id}' not found"}
        if session.applied:
            return {"success": False, "error": "Session already applied"}

        results = []
        applied_paths = []

        try:
            for edit in session.edits:
                result = self._apply_edit(edit)
                results.append(result)
                if result["success"]:
                    applied_paths.append(edit.path)
                else:
                    # Rollback all applied edits
                    self._rollback_session(session, applied_paths)
                    session.results = results
                    return {
                        "success": False,
                        "error": f"Edit failed on {edit.path}: {result.get('error', 'unknown')}",
                        "results": results,
                        "rolled_back": True,
                    }

            session.applied = True
            session.applied_at = datetime.now(timezone.utc).isoformat()
            session.results = results

            return {
                "success": True,
                "session_id": session_id,
                "files_modified": len(applied_paths),
                "results": results,
            }

        except Exception as e:
            self._rollback_session(session, applied_paths)
            return {"success": False, "error": str(e), "rolled_back": True}

    def _apply_edit(self, edit: FileEdit) -> dict:
        """Apply a single edit operation."""
        try:
            resolved = self._resolve_path(edit.path)

            if edit.operation == "create":
                os.makedirs(os.path.dirname(resolved), exist_ok=True)
                with open(resolved, "w", encoding="utf-8") as f:
                    f.write(edit.new_content or "")
                return {"success": True, "path": edit.path, "operation": "create"}

            elif edit.operation == "modify":
                if edit.search is not None and edit.replace is not None:
                    # Search-and-replace mode
                    with open(resolved, "r", encoding="utf-8") as f:
                        content = f.read()
                    if edit.search not in content:
                        return {"success": False, "path": edit.path,
                                "error": "Search string not found"}
                    new_content = content.replace(edit.search, edit.replace, 1)
                    with open(resolved, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    return {"success": True, "path": edit.path, "operation": "search_replace"}

                elif edit.new_content is not None:
                    # Full content replacement
                    with open(resolved, "w", encoding="utf-8") as f:
                        f.write(edit.new_content)
                    return {"success": True, "path": edit.path, "operation": "full_replace"}

                else:
                    return {"success": False, "path": edit.path,
                            "error": "Modify requires new_content or search+replace"}

            elif edit.operation == "delete":
                if os.path.exists(resolved):
                    os.remove(resolved)
                return {"success": True, "path": edit.path, "operation": "delete"}

            elif edit.operation == "rename":
                if not edit.old_path:
                    return {"success": False, "path": edit.path, "error": "Rename requires old_path"}
                old_resolved = self._resolve_path(edit.old_path)
                os.makedirs(os.path.dirname(resolved), exist_ok=True)
                shutil.move(old_resolved, resolved)
                return {"success": True, "path": edit.path, "old_path": edit.old_path,
                        "operation": "rename"}

            else:
                return {"success": False, "path": edit.path,
                        "error": f"Unknown operation: {edit.operation}"}

        except Exception as e:
            return {"success": False, "path": edit.path, "error": str(e)}

    def _rollback_session(self, session: EditSession, applied_paths: list[str]):
        """Rollback all applied edits using snapshots."""
        for path in reversed(applied_paths):
            try:
                resolved = self._resolve_path(path)
                snapshot = session.snapshots.get(resolved)
                if snapshot:
                    if snapshot.exists:
                        os.makedirs(os.path.dirname(resolved), exist_ok=True)
                        with open(resolved, "w", encoding="utf-8") as f:
                            f.write(snapshot.content)
                    else:
                        if os.path.exists(resolved):
                            os.remove(resolved)
            except Exception:
                pass  # Best-effort rollback
        session.rolled_back = True

    def rollback(self, session_id: str) -> dict:
        """Manually rollback an applied session."""
        session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "error": f"Session '{session_id}' not found"}
        if not session.applied:
            return {"success": False, "error": "Session was never applied"}
        if session.rolled_back:
            return {"success": False, "error": "Session already rolled back"}

        applied_paths = [e.path for e in session.edits]
        self._rollback_session(session, applied_paths)

        return {
            "success": True,
            "session_id": session_id,
            "files_restored": len(applied_paths),
        }

    def get_diff(self, session_id: str) -> dict:
        """Get a unified diff for all edits in a session."""
        session = self._sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        diffs = []
        for edit in session.edits:
            resolved = self._resolve_path(edit.path)
            snapshot = session.snapshots.get(resolved)
            old_content = snapshot.content if snapshot else ""

            if edit.operation == "create":
                new_content = edit.new_content or ""
            elif edit.operation == "modify":
                if edit.new_content:
                    new_content = edit.new_content
                elif edit.search and edit.replace:
                    new_content = old_content.replace(edit.search, edit.replace, 1)
                else:
                    new_content = old_content
            elif edit.operation == "delete":
                new_content = ""
            else:
                new_content = old_content

            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{edit.path}",
                tofile=f"b/{edit.path}",
            ))
            diffs.append({
                "path": edit.path,
                "operation": edit.operation,
                "diff": "".join(diff_lines),
            })

        return {"success": True, "session_id": session_id, "diffs": diffs}

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List recent editing sessions."""
        sessions = sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)
        return [
            {
                "id": s.id,
                "description": s.description,
                "edit_count": len(s.edits),
                "applied": s.applied,
                "rolled_back": s.rolled_back,
                "created_at": s.created_at,
                "applied_at": s.applied_at,
            }
            for s in sessions[:limit]
        ]


# ── Global instance ───────────────────────────────────────────────────────────
multi_file_editor = MultiFileEditor()
