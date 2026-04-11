"""
Ombra Tool Safety System
- Allowlist/denylist policies
- Secret redaction
- Output scrubbing
- Safe execution profiles
"""
import re
import os

# Default blocked patterns
DEFAULT_DENYLIST = [
    "rm -rf /", "dd if=", "mkfs", ":(){ :|:& };:",
    "chmod -R 777 /", "shutdown", "reboot", "format",
    "curl.*|.*sh", "wget.*|.*bash", "nc -e", "ncat -e",
    "> /dev/sd", "mv /* /dev/null"
]

# Default allowed safe commands
DEFAULT_ALLOWLIST = [
    "ls", "cat", "echo", "pwd", "date", "whoami",
    "python3", "pip", "node", "npm", "yarn",
    "git status", "git log", "git diff",
    "df", "free", "top -bn1", "uname", "wc", "grep",
    "head", "tail", "find", "sort", "cut", "awk"
]

# Secrets to redact in outputs
SECRET_PATTERNS = [
    (r'sk-[a-zA-Z0-9\-]{20,}', '[REDACTED_API_KEY]'),
    (r'[a-zA-Z0-9]{32,}:[A-Za-z0-9\-_]{20,}', '[REDACTED_TOKEN]'),
    (r'(password|passwd|pwd|secret|token|api_key|apikey)\s*[=:]\s*\S+', '[REDACTED_SECRET]'),
    (r'-----BEGIN.*PRIVATE KEY-----[\s\S]*?-----END.*PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]'),
    (r'mongodb(\+srv)?://[^\s]+', '[REDACTED_MONGO_URL]'),
    (r'(EMERGENT_LLM_KEY|TELEGRAM_BOT_TOKEN)\s*=\s*\S+', '[REDACTED_ENV_VAR]'),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive information from output text."""
    if not text:
        return text
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def check_command_policy(command: str, policies: dict = None) -> dict:
    """Check if command is allowed based on policies."""
    policies = policies or {}
    denylist = policies.get("denylist", DEFAULT_DENYLIST)
    allowlist = policies.get("allowlist", [])
    mode = policies.get("mode", "denylist")  # denylist or allowlist

    cmd_lower = command.lower().strip()

    # Always block dangerous patterns
    for pattern in denylist:
        if pattern.lower() in cmd_lower:
            return {"allowed": False, "reason": f"Blocked by deny rule: {pattern}", "severity": "critical"}

    # Check regex denylist
    for pattern in denylist:
        try:
            if re.search(pattern.lower(), cmd_lower):
                return {"allowed": False, "reason": f"Blocked by deny pattern: {pattern}", "severity": "high"}
        except re.error:
            pass

    # If allowlist mode, command must start with an allowed prefix
    if mode == "allowlist" and allowlist:
        cmd_base = cmd_lower.split()[0] if cmd_lower.split() else ""
        is_allowed = any(cmd_base.startswith(a.lower()) for a in allowlist)
        if not is_allowed:
            return {"allowed": False, "reason": f"Not in allowlist. Command: {cmd_base}", "severity": "medium"}

    return {"allowed": True, "reason": "Passed all checks", "severity": "none"}


def create_safe_env():
    """Create a sanitized environment for subprocess execution."""
    safe_env = os.environ.copy()
    # Remove sensitive env vars from subprocess
    for key in list(safe_env.keys()):
        if any(s in key.upper() for s in ["TOKEN", "SECRET", "KEY", "PASSWORD", "PRIVATE"]):
            del safe_env[key]
    return safe_env
