"""
Ombra Workspace — Like OpenClaw's workspace/skills system.
Loads SOUL.md, AGENTS.md, and active skill SKILL.md files.
Injects them into system prompts for every request.
"""
import os
from pathlib import Path
from typing import Optional

WORKSPACE_DIR = Path(__file__).parent / "workspace"
SKILLS_DIR = WORKSPACE_DIR / "skills"


def _read(path: Path) -> str:
    """Read a file, return empty string on failure."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_soul() -> str:
    """Load SOUL.md — Ombra's identity & persona."""
    return _read(WORKSPACE_DIR / "SOUL.md")


def load_agents() -> str:
    """Load AGENTS.md — capabilities and instructions."""
    return _read(WORKSPACE_DIR / "AGENTS.md")


def list_skills() -> list[dict]:
    """Return all available skills with their metadata."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        content = _read(skill_md)
        # Parse name from first # heading
        name = skill_dir.name
        for line in content.splitlines():
            if line.startswith("# "):
                name = line[2:].strip()
                break
        # Parse purpose
        purpose = ""
        in_purpose = False
        for line in content.splitlines():
            if line.strip() == "## Purpose":
                in_purpose = True
                continue
            if in_purpose:
                if line.startswith("##"):
                    break
                if line.strip():
                    purpose = line.strip()
                    break
        skills.append({
            "id": skill_dir.name,
            "name": name,
            "purpose": purpose,
            "path": str(skill_md),
        })
    return skills


def load_skill(skill_id: str) -> str:
    """Load a single skill's SKILL.md content."""
    skill_path = SKILLS_DIR / skill_id / "SKILL.md"
    return _read(skill_path)


def install_skill(skill_id: str, content: str) -> bool:
    """Install or update a skill by writing its SKILL.md."""
    try:
        skill_dir = SKILLS_DIR / skill_id
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def delete_skill(skill_id: str) -> bool:
    """Remove a skill directory."""
    import shutil
    try:
        skill_dir = SKILLS_DIR / skill_id
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        return True
    except Exception:
        return False


def build_system_prompt(
    base_prompt: str,
    active_skill_ids: Optional[list[str]] = None,
    include_soul: bool = True,
    include_agents_md: bool = False,
) -> str:
    """
    Build the full system prompt by prepending SOUL.md + active skills.
    This is injected into every request like OpenClaw does with workspace files.
    """
    parts = []

    if include_soul:
        soul = load_soul()
        if soul:
            parts.append(soul)

    if active_skill_ids:
        for skill_id in active_skill_ids:
            skill_content = load_skill(skill_id)
            if skill_content:
                parts.append(f"--- Active Skill: {skill_id} ---\n{skill_content}\n---")

    if base_prompt:
        parts.append(base_prompt)

    return "\n\n".join(parts)


def get_active_skill_ids(db) -> list[str]:
    """Get the list of skill IDs that are active in the database settings."""
    try:
        settings = db["settings"].find_one({"user_id": "default"}) or {}
        return settings.get("active_skills", [])
    except Exception:
        return []


def detect_skills_for_message(message: str) -> list[str]:
    """
    Auto-detect which skills are relevant for a given message.
    Returns a list of skill IDs to activate for this request.
    """
    lower = message.lower()
    activated = []

    # Code review skill
    if any(k in lower for k in ["review", "audit", "check this code", "look at this code",
                                  "what's wrong with", "improve this", "refactor", "bug in"]):
        activated.append("code-review")

    # Research skill
    if any(k in lower for k in ["research", "explain", "what is", "how does", "compare",
                                  "tell me about", "analyze", "study", "explore"]):
        activated.append("research")

    return activated
