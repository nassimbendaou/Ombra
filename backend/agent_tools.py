"""
Ombra Agent Tools
=================
All tool implementations available to the agentic chat loop.
Each tool follows the OpenAI function-calling schema.

Tools:
- terminal        : Run a shell command on the VM
- read_file       : Read a file
- write_file      : Write/create a file
- list_dir        : List a directory
- web_search      : DuckDuckGo search
- fetch_url       : Fetch and read a URL
- python_exec     : Execute a Python snippet and return output
- draft_email     : Draft an email for user review before sending
- git_run         : Run a git command
- memory_store    : Store a memory/note
- create_task     : Add a task to Ombra's queue
- http_request    : Make an arbitrary HTTP request
"""

import os, subprocess, json, asyncio, smtplib, ssl, textwrap, re, time, shlex
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
WORK_DIR_RAW = os.environ.get("AGENT_WORK_DIR", "/tmp/ombra_workspace")
WORK_DIR = os.path.realpath(os.path.expanduser(WORK_DIR_RAW))
# Enforce tmp-only sandbox for autonomous project work.
if not WORK_DIR.startswith("/tmp/"):
    WORK_DIR = "/tmp/ombra_workspace"
os.makedirs(WORK_DIR, exist_ok=True)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", EMAIL_USER)

_PUBLIC_BASE_CACHE = {"value": None, "ts": 0.0}
PUBLIC_BASE_TTL_SEC = 600
_TELEGRAM_CHAT_CACHE = {"value": None, "ts": 0.0}
TELEGRAM_CHAT_TTL_SEC = 300

# Paths the tools may not touch (security)
BLOCKED_PATHS = ["/etc/shadow", "/etc/passwd", "id_rsa", ".ssh/", "/.env", "/home/azureuser/Ombra"]

BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\};\s*:",
    r"\bcurl\b.*\|\s*(sh|bash)",
    r"\bwget\b.*\|\s*(sh|bash)",
    r"\bchmod\s+777\b",
    r">\s*/etc/",
    r"\bchown\s+root\b",
    r"/home/azureuser/ombra",
    r"\.{2}/",
]

BLOCKED_PYTHON_PATTERNS = [
    r"\bimport\s+subprocess\b",
    r"\bimport\s+socket\b",
    r"\bimport\s+ctypes\b",
    r"\bimport\s+resource\b",
    r"\bfrom\s+os\s+import\b",
    r"\bos\.system\(",
    r"\bsubprocess\.",
    r"\beval\(",
    r"\bexec\(",
    r"\bopen\(\s*['\"]/(etc|proc|sys)",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def _safe_path(path: str) -> tuple[bool, str]:
    """Returns (is_safe, resolved_path)."""
    resolved = os.path.realpath(os.path.expanduser(path))
    # Hard sandbox: everything must stay inside WORK_DIR.
    base = WORK_DIR.rstrip("/") + "/"
    if resolved != WORK_DIR and not resolved.startswith(base):
        return False, resolved
    for b in BLOCKED_PATHS:
        if b in resolved:
            return False, resolved
    return True, resolved


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n\n... [{len(text) - limit} chars truncated] ...\n\n" + text[-half:]


def _is_command_blocked(command: str) -> str | None:
    """Return a reason when a shell command is unsafe, otherwise None."""
    lowered = (command or "").lower().strip()
    if not lowered:
        return "empty command"
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, lowered):
            return f"blocked by policy pattern: {pattern}"
    return None


def _is_python_code_blocked(code: str) -> str | None:
    """Return a reason when python snippet is unsafe, otherwise None."""
    text = (code or "")
    for pattern in BLOCKED_PYTHON_PATTERNS:
        if re.search(pattern, text):
            return f"blocked python pattern: {pattern}"
    return None


PREVIEWABLE_EXT = {".html", ".htm", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
APP_ASSET_EXT = {".js", ".css", ".json", ".txt", ".md"}
PREVIEW_DIRS = [WORK_DIR]


def _http_get_text(url: str, headers: dict | None = None, timeout: float = 1.5) -> str | None:
    try:
        req = Request(url, headers=headers or {})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def _resolve_telegram_chat_id() -> str:
    """Resolve default telegram chat id from env first, then DB settings."""
    env_chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if env_chat:
        return env_chat

    now = time.time()
    cached = _TELEGRAM_CHAT_CACHE.get("value")
    ts = _TELEGRAM_CHAT_CACHE.get("ts", 0.0)
    if cached and (now - ts) < TELEGRAM_CHAT_TTL_SEC:
        return cached

    try:
        from pymongo import MongoClient
        mongo = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "ombra_db")
        client = MongoClient(mongo, serverSelectionTimeoutMS=1500)
        doc = client[db_name]["settings"].find_one({"user_id": "default"}, {"telegram_chat_id": 1}) or {}
        chat = str(doc.get("telegram_chat_id") or "").strip()
        if chat:
            _TELEGRAM_CHAT_CACHE["value"] = chat
            _TELEGRAM_CHAT_CACHE["ts"] = now
            return chat
    except Exception:
        pass
    return ""


def _normalize_public_base(raw: str) -> str | None:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return None
    if not value.startswith("http://") and not value.startswith("https://"):
        scheme = os.environ.get("OMBRA_PUBLIC_SCHEME", "http")
        value = f"{scheme}://{value}"
    return value.rstrip("/")


def _legacy_api_base_to_public(raw: str) -> str | None:
    """Backward compatibility: drop :8001 for public links when legacy var is used."""
    base = _normalize_public_base(raw)
    if not base:
        return None
    parsed = urlparse(base)
    if parsed.port == 8001 and parsed.hostname:
        scheme = parsed.scheme or "http"
        return f"{scheme}://{parsed.hostname}"
    return base


def _discover_public_base() -> str:
    # 1) Explicit public base from env (preferred)
    for key in ("OMBRA_PUBLIC_BASE", "PUBLIC_BASE_URL", "PUBLIC_URL", "APP_BASE_URL"):
        v = _normalize_public_base(os.environ.get(key, ""))
        if v:
            return v

    # 2) Backward-compat with legacy env name
    legacy = _legacy_api_base_to_public(os.environ.get("OMBRA_API_BASE", ""))
    if legacy:
        return legacy

    # 3) Azure metadata service (public IP first, then private)
    meta_raw = _http_get_text(
        "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
        headers={"Metadata": "true"},
        timeout=1.5,
    )
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            interfaces = (meta.get("network", {}) or {}).get("interface", [])
            for iface in interfaces:
                for ip_item in ((iface.get("ipv4", {}) or {}).get("ipAddress", []) or []):
                    pub = (ip_item.get("publicIpAddress") or "").strip()
                    if pub:
                        return _normalize_public_base(pub) or "http://127.0.0.1"
        except Exception:
            pass

    # 4) External resolver fallback (works on most VMs)
    for probe in ("http://ifconfig.me", "http://api.ipify.org"):
        ext = _http_get_text(probe, timeout=1.5)
        if ext and re.match(r"^\d+\.\d+\.\d+\.\d+$", ext):
            return _normalize_public_base(ext) or "http://127.0.0.1"

    # 5) Private IP fallback (useful on same VNet)
    if meta_raw:
        try:
            meta = json.loads(meta_raw)
            interfaces = (meta.get("network", {}) or {}).get("interface", [])
            for iface in interfaces:
                for ip_item in ((iface.get("ipv4", {}) or {}).get("ipAddress", []) or []):
                    priv = (ip_item.get("privateIpAddress") or "").strip()
                    if priv:
                        return _normalize_public_base(priv) or "http://127.0.0.1"
        except Exception:
            pass

    # 6) Last resort
    return "http://127.0.0.1"


def _public_api_base() -> str:
    now = time.time()
    cached = _PUBLIC_BASE_CACHE.get("value")
    ts = _PUBLIC_BASE_CACHE.get("ts", 0.0)
    if cached and (now - ts) < PUBLIC_BASE_TTL_SEC:
        return cached
    base = _discover_public_base()
    _PUBLIC_BASE_CACHE["value"] = base
    _PUBLIC_BASE_CACHE["ts"] = now
    return base

def _make_preview_url(path: str) -> str | None:
    """Return a preview URL. For asset/code files, resolve to nearest index.html."""
    if not path:
        return None
    real = os.path.realpath(path)
    if not any(real.startswith(d) for d in PREVIEW_DIRS):
        return None
    ext = os.path.splitext(real)[1].lower()

    # Direct preview for renderable file types
    if ext in PREVIEWABLE_EXT and os.path.isfile(real):
        return f"{_public_api_base()}/api/preview?path={quote(real)}"

    # If user edited app assets (js/css/etc), try to open app entry point instead
    if ext in APP_ASSET_EXT:
        cur = os.path.dirname(real)
        # Walk up to find nearest index.html under allowed roots
        for _ in range(6):
            idx = os.path.join(cur, "index.html")
            if os.path.isfile(idx):
                return f"{_public_api_base()}/api/preview?path={quote(os.path.realpath(idx))}"
            parent = os.path.dirname(cur)
            if parent == cur or not any(parent.startswith(d) for d in PREVIEW_DIRS):
                break
            cur = parent

    return None


def _proxy_preview_url(port: str | int, path: str = "/") -> str:
    safe_path = "/" + (path or "/").lstrip("/")
    return f"{_public_api_base()}/api/preview/proxy/{port}{quote(safe_path, safe='/')}"


def _default_port_from_command(command: str) -> str | None:
    cmd = (command or "").lower()
    if "flask run" in cmd:
        return "5000"
    if "streamlit run" in cmd:
        return "8501"
    if "npm run dev" in cmd or "vite" in cmd:
        return "5173"
    if "npm start" in cmd or "next dev" in cmd or "react-scripts" in cmd:
        return "3000"
    if "python" in cmd and "http.server" in cmd:
        return "8000"
    return None


def _detect_server_port(command: str, output: str) -> str | None:
    """Detect if a command starts a web server and return a proxied preview URL."""
    def _best_proxy_path() -> str:
        # Prefer explicit --directory when provided in http.server commands.
        m = re.search(r"--directory\s+([^\s]+)", command)
        if m:
            raw_dir = m.group(1).strip().strip("\"'")
            full_dir = raw_dir if os.path.isabs(raw_dir) else os.path.join(WORK_DIR, raw_dir)
            idx = os.path.join(full_dir, "index.html")
            if os.path.isfile(idx):
                rel = os.path.relpath(idx, WORK_DIR).replace("\\", "/")
                return f"/{rel}"

        # Otherwise, auto-detect a likely app entry HTML (most recently modified).
        skip_dirs = {".git", "venv", "node_modules", "backend", "frontend", "__pycache__"}
        candidates = []
        root_depth = WORK_DIR.rstrip("/").count("/")
        for cur, dirs, files in os.walk(WORK_DIR):
            # Keep scan bounded for speed/safety.
            depth = cur.rstrip("/").count("/") - root_depth
            if depth > 4:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for name in files:
                lower = name.lower()
                if lower not in ("index.html", "main.html", "app.html") and not lower.endswith(".html"):
                    continue
                full = os.path.join(cur, name)
                try:
                    mtime = os.path.getmtime(full)
                except Exception:
                    continue
                rel = os.path.relpath(full, WORK_DIR).replace("\\", "/")
                score = 0
                rel_lower = rel.lower()
                if lower == "index.html":
                    score += 3
                if "game" in rel_lower or "project" in rel_lower or "app" in rel_lower:
                    score += 2
                candidates.append((score, mtime, rel))

        if candidates:
            # Highest score first, then most recent.
            candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
            return f"/{candidates[0][2]}"

        return "/"

    proxy_path = quote(_best_proxy_path(), safe="/")
    port_patterns = [
        r'(?:--port|--listen|-p)\s+(\d{2,5})',
        r'(?:localhost|0\.0\.0\.0|127\.0\.0\.1):(\d{2,5})',
        r'http\.server\s+(\d{2,5})',
        r'serve.*-l\s+(\d{2,5})',
        r':(?:port|PORT)\s*=?\s*(\d{2,5})',
    ]
    text = command + "\n" + output
    for pat in port_patterns:
        m = re.search(pat, text)
        if m:
            port = m.group(1)
            return _proxy_preview_url(port, proxy_path)
    url_match = re.search(r'https?://(?:localhost|0\.0\.0\.0|127\.0\.0\.1):(\d{2,5})', output)
    if url_match:
        port = url_match.group(1)
        return _proxy_preview_url(port, proxy_path)
    guessed = _default_port_from_command(command)
    if guessed:
        return _proxy_preview_url(guessed, proxy_path)
    return None


def _is_likely_server_command(command: str) -> bool:
    cmd = (command or "").lower()
    server_markers = [
        "http.server", "uvicorn", "flask run", "npm run dev", "npm start",
        "vite", "next dev", "streamlit run", "gradio", "gunicorn", "serve -l",
        "python -m", "node ",
    ]
    if any(marker in cmd for marker in server_markers):
        return True
    return bool(_detect_server_port(command, ""))


def _launch_server_background(command: str, safe_env: dict, server_url: str | None) -> dict:
    log_file = f"/tmp/ombra_server_{int(time.time())}.log"
    wrapped = f"nohup {command} > {shlex.quote(log_file)} 2>&1 & echo $!"
    try:
        bg = subprocess.run(
            ["/bin/bash", "-lc", wrapped],
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=WORK_DIR,
            env=safe_env,
            preexec_fn=_set_subprocess_limits,
        )
        pid = (bg.stdout or "").strip().splitlines()[-1] if (bg.stdout or "").strip() else ""
        res = {
            "success": bool(pid),
            "output": (
                f"Started in background (pid {pid}). Logs: {log_file}. "
                f"If preview fails immediately, wait 2-3 seconds and retry."
            ) if pid else f"Failed to start background process: {(bg.stderr or bg.stdout or '').strip()}",
            "command": command,
            "pid": pid or None,
            "log_file": log_file,
        }
        if server_url:
            res["preview_url"] = server_url
            res["output"] += f"\nServer accessible at: {server_url}"
        return res
    except Exception as e:
        return {
            "success": False,
            "output": f"Failed to launch background server: {str(e)}",
            "command": command,
        }


def _set_subprocess_limits():
    """Best-effort subprocess resource limits for safer execution."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    except Exception:
        pass


# ── Tool definitions for OpenAI function calling ──────────────────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Run a shell command on the server. Use for file operations, running scripts, checking ports, installing packages, etc. Working directory is the Ombra project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30, max 120)", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on the server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or create a file on the server. Overwrites if exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path"},
                    "content": {"type": "string", "description": "File content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories at a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: project root)"},
                    "recursive": {"type": "boolean", "description": "Whether to list recursively", "default": False}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo. Use for current events, documentation, or any information you don't have.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Number of results (default 5)", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the text content of a URL. Use for reading documentation, articles, or any web page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Max characters to return (default 8000)", "default": 8000}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "Execute a Python code snippet and return stdout/stderr. The snippet runs in an isolated subprocess. Use for calculations, data processing, testing code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 15)", "default": 15}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft_email",
            "description": "Draft an email for user review. The email will NOT be sent automatically — the user will review and approve it first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body (plain text or HTML)"},
                    "html": {"type": "boolean", "description": "Whether body is HTML (default false)", "default": False}
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_run",
            "description": "Run a git command in the project directory. Use for status, log, diff, add, commit, push, pull, clone, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {"type": "string", "description": "Git arguments after 'git', e.g. 'status', 'log --oneline -5', 'diff HEAD~1'"},
                    "cwd": {"type": "string", "description": "Working directory (default: project root)"}
                },
                "required": ["args"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Make an HTTP request to any URL. Use for calling APIs, webhooks, or services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL"},
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)", "default": "GET"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "body": {"type": "object", "description": "Request body (will be JSON-encoded)"},
                    "timeout": {"type": "integer", "description": "Timeout seconds (default 15)", "default": 15}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_store",
            "description": "Store an important fact, insight, or note into Ombra's memory for later recall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The fact or insight to remember"},
                    "mem_type": {"type": "string", "description": "Memory type: fact|insight|preference|code|url", "default": "fact"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a background task for Ombra's autonomous daemon to work on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Detailed description of what to do"},
                    "priority": {"type": "string", "description": "Priority: low|normal|high|critical", "default": "normal"}
                },
                "required": ["title", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": "Read emails from the user's inbox. Can list recent emails or search for specific ones. Returns sender, subject, date, and body preview for each email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Mailbox folder (default: INBOX)", "default": "INBOX"},
                    "count": {"type": "integer", "description": "Number of emails to fetch (default 5, max 20)", "default": 5},
                    "unread_only": {"type": "boolean", "description": "Only fetch unread emails", "default": False},
                    "search": {"type": "string", "description": "Search term to filter emails (searches subject and sender)"}
                },
                "required": []
            }
        }
    }
]


# ── Tool executor ─────────────────────────────────────────────────────────────
async def execute_tool(name: str, args: dict, db=None) -> dict:
    """
    Dispatch a tool call and return a result dict.
    Always returns {"success": bool, "output": str, ...}
    """
    try:
        if name == "terminal":
            return _tool_terminal(args.get("command", ""), args.get("timeout", 30))

        elif name == "read_file":
            return _tool_read_file(args.get("path", ""))

        elif name == "write_file":
            return _tool_write_file(args.get("path", ""), args.get("content", ""))

        elif name == "list_dir":
            return _tool_list_dir(args.get("path", WORK_DIR), args.get("recursive", False))

        elif name == "web_search":
            return await _tool_web_search(args.get("query", ""), args.get("max_results", 5))

        elif name == "fetch_url":
            return await _tool_fetch_url(args.get("url", ""), args.get("max_chars", 8000))

        elif name == "python_exec":
            return _tool_python_exec(args.get("code", ""), args.get("timeout", 15))

        elif name == "draft_email":
            return _tool_draft_email(
                args.get("to", ""), args.get("subject", ""),
                args.get("body", ""), args.get("html", False)
            )

        elif name == "git_run":
            return _tool_git_run(args.get("args", ""), args.get("cwd", WORK_DIR))

        elif name == "http_request":
            return await _tool_http_request(
                args.get("url", ""), args.get("method", "GET"),
                args.get("headers"), args.get("body"), args.get("timeout", 15)
            )

        elif name == "memory_store":
            return _tool_memory_store(args.get("content", ""), args.get("mem_type", "fact"), db)

        elif name == "create_task":
            return _tool_create_task(
                args.get("title", ""), args.get("description", ""),
                args.get("priority", "normal"), db
            )

        elif name == "read_emails":
            return _tool_read_emails(
                args.get("folder", "INBOX"), args.get("count", 5),
                args.get("unread_only", False), args.get("search", ""), db
            )

        else:
            return {"success": False, "output": f"Unknown tool: {name}"}

    except Exception as e:
        return {"success": False, "output": f"Tool error: {str(e)}"}


# ── Implementations ───────────────────────────────────────────────────────────

def _tool_terminal(command: str, timeout: int = 30) -> dict:
    if not command.strip():
        return {"success": False, "output": "No command provided"}
    blocked_reason = _is_command_blocked(command)
    if blocked_reason:
        return {"success": False, "output": f"Command rejected: {blocked_reason}", "command": command}
    timeout = min(int(timeout), 120)
    # Redact common secrets
    safe_env = {k: v for k, v in os.environ.items()
                if not any(s in k.upper() for s in ["KEY", "SECRET", "PASSWORD", "TOKEN", "PASS"])}
    # Explicitly expose Telegram credentials for generated programs that need notifications.
    tg_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    tg_chat = _resolve_telegram_chat_id()
    if tg_token:
        safe_env["TELEGRAM_BOT_TOKEN"] = tg_token
    if tg_chat:
        safe_env["TELEGRAM_CHAT_ID"] = tg_chat
    try:
        result = subprocess.run(
            ["/bin/bash", "-lc", command], shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=WORK_DIR, env=safe_env, preexec_fn=_set_subprocess_limits
        )
        out = (result.stdout or "") + ("" if not result.stderr else f"\nSTDERR:\n{result.stderr}")
        res = {
            "success": result.returncode == 0,
            "output": _truncate(out) or "(no output)",
            "return_code": result.returncode,
            "command": command
        }
        # Detect server start or previewable output
        server_url = _detect_server_port(command, out)
        if server_url:
            res["preview_url"] = server_url
            res["output"] += f"\nServer accessible at: {server_url}"
        return res
    except subprocess.TimeoutExpired:
        # subprocess.run() timeout terminates the child; for servers we relaunch detached.
        server_url = _detect_server_port(command, "")
        if _is_likely_server_command(command):
            return _launch_server_background(command, safe_env, server_url)
        return {"success": False, "output": f"Timed out after {timeout}s", "command": command}
    except Exception as e:
        return {"success": False, "output": str(e), "command": command}


def _tool_read_file(path: str) -> dict:
    ok, resolved = _safe_path(path)
    if not ok:
        return {"success": False, "output": f"Blocked path: {resolved}"}
    # Allow relative paths from WORK_DIR
    if not os.path.isabs(path):
        resolved = os.path.realpath(os.path.join(WORK_DIR, path))
    if not os.path.exists(resolved):
        return {"success": False, "output": f"File not found: {resolved}"}
    if os.path.getsize(resolved) > 500_000:
        return {"success": False, "output": "File too large (>500KB). Use terminal with head/tail."}
    try:
        with open(resolved, "r", errors="replace") as f:
            content = f.read()
        return {"success": True, "output": _truncate(content, 8000), "path": resolved, "size": len(content)}
    except Exception as e:
        return {"success": False, "output": str(e)}


def _tool_write_file(path: str, content: str) -> dict:
    if not os.path.isabs(path):
        path = os.path.join(WORK_DIR, path)
    ok, resolved = _safe_path(path)
    if not ok:
        return {"success": False, "output": f"Blocked path: {resolved}"}
    try:
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w") as f:
            f.write(content)
        result = {"success": True, "output": f"Written {len(content)} chars to {resolved}", "path": resolved}
        preview = _make_preview_url(resolved)
        if preview:
            result["preview_url"] = preview
            result["output"] += f"\nPreview: {preview}"
        return result
    except Exception as e:
        return {"success": False, "output": str(e)}


def _tool_list_dir(path: str = WORK_DIR, recursive: bool = False) -> dict:
    if not os.path.isabs(path):
        path = os.path.join(WORK_DIR, path)
    ok, resolved = _safe_path(path)
    if not ok:
        return {"success": False, "output": f"Blocked path: {resolved}"}
    if not os.path.exists(resolved):
        return {"success": False, "output": f"Path not found: {resolved}"}
    try:
        if recursive:
            lines = []
            for root, dirs, files in os.walk(resolved):
                # Skip hidden + common junk
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git', 'venv', 'build')]
                rel = os.path.relpath(root, resolved)
                prefix = rel + "/" if rel != "." else ""
                for f in files:
                    lines.append(prefix + f)
                if len(lines) > 500:
                    lines.append("... (truncated)")
                    break
            return {"success": True, "output": "\n".join(lines) or "(empty)", "path": resolved}
        else:
            entries = os.listdir(resolved)
            lines = []
            for e in sorted(entries):
                full = os.path.join(resolved, e)
                kind = "/" if os.path.isdir(full) else ""
                size = "" if os.path.isdir(full) else f"  ({os.path.getsize(full)} bytes)"
                lines.append(f"{e}{kind}{size}")
            return {"success": True, "output": "\n".join(lines) or "(empty)", "path": resolved}
    except Exception as e:
        return {"success": False, "output": str(e)}


async def _tool_web_search(query: str, max_results: int = 5) -> dict:
    try:
        import httpx
        # Use DuckDuckGo HTML (no API key needed)
        async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0 (compatible; OmbraBot/1.0)"}) as c:
            resp = await c.get("https://html.duckduckgo.com/html/", params={"q": query})
            html = resp.text

        # Parse results using simple regex (avoid dependency on beautifulsoup)
        import re
        results = []
        # Match result links and snippets
        for m in re.finditer(r'class="result__title".*?href="([^"]+)"[^>]*>([^<]+)</a>.*?class="result__snippet"[^>]*>([^<]*(?:<b>[^<]*</b>[^<]*)*)', html, re.DOTALL):
            url = m.group(1)
            title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            snippet = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            if url and title:
                results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break

        if not results:
            return {"success": True, "output": f"No results found for: {query}"}

        lines = [f"{i+1}. {r['title']}\n   {r['url']}\n   {r['snippet']}" for i, r in enumerate(results)]
        return {"success": True, "output": "\n\n".join(lines), "count": len(results)}
    except Exception as e:
        return {"success": False, "output": f"Search failed: {e}"}


async def _tool_fetch_url(url: str, max_chars: int = 8000) -> dict:
    try:
        import httpx, re
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0 (compatible; OmbraBot/1.0)"}) as c:
            resp = await c.get(url)
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                # Strip HTML tags
                text = resp.text
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
            elif "json" in content_type:
                text = json.dumps(resp.json(), indent=2)
            else:
                text = resp.text

        return {"success": True, "output": _truncate(text, max_chars), "url": url, "status": resp.status_code}
    except Exception as e:
        return {"success": False, "output": f"Fetch failed: {e}", "url": url}


def _tool_python_exec(code: str, timeout: int = 15) -> dict:
    if not code.strip():
        return {"success": False, "output": "No code provided"}
    blocked_reason = _is_python_code_blocked(code)
    if blocked_reason:
        return {"success": False, "output": f"Python execution rejected: {blocked_reason}"}
    timeout = min(int(timeout), 60)
    # Write to temp file and run in subprocess (safer than exec())
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        fname = f.name
    try:
        result = subprocess.run(
            ["python3", "-I", "-S", fname], capture_output=True, text=True, timeout=timeout,
            cwd="/tmp", env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"}, preexec_fn=_set_subprocess_limits
        )
        out = result.stdout
        err = result.stderr
        combined = (out + ("\nSTDERR:\n" + err if err else "")).strip()
        return {
            "success": result.returncode == 0,
            "output": _truncate(combined) or "(no output)",
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"Code timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "output": str(e)}
    finally:
        try:
            os.unlink(fname)
        except Exception:
            pass


def _tool_draft_email(to: str, subject: str, body: str, html: bool = False) -> dict:
    """Save an email draft for user review instead of sending directly."""
    if not to or "@" not in to:
        return {"success": False, "output": f"Invalid recipient: {to}"}
    if not subject:
        return {"success": False, "output": "Subject is required"}
    try:
        from pymongo import MongoClient
        from datetime import datetime, timezone
        _mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        _db = _mc[os.environ.get("DB_NAME", "ombra_db")]
        draft = {
            "to": to,
            "subject": subject,
            "body": body,
            "html": html,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = _db["email_drafts"].insert_one(draft)
        return {
            "success": True,
            "output": f"Email draft saved (to: {to}, subject: {subject}). The user will review and approve it before sending.",
            "draft_id": str(result.inserted_id),
        }
    except Exception as e:
        return {"success": False, "output": f"Failed to save draft: {e}"}


def _tool_git_run(args: str, cwd: str = WORK_DIR) -> dict:
    if not os.path.isabs(cwd):
        cwd = os.path.join(WORK_DIR, cwd)
    ok, resolved_cwd = _safe_path(cwd)
    if not ok:
        return {"success": False, "output": f"Blocked path: {resolved_cwd}"}
    cwd = resolved_cwd
    # Safety: only allow specific git subcommands
    safe_cmds = ["status", "log", "diff", "show", "branch", "add", "commit",
                 "push", "pull", "fetch", "clone", "checkout", "stash", "init",
                 "remote", "tag", "describe", "rev-parse", "ls-files", "shortlog"]
    first_arg = args.strip().split()[0] if args.strip() else ""
    if first_arg not in safe_cmds:
        return {"success": False, "output": f"Git subcommand '{first_arg}' not in allowlist"}
    try:
        result = subprocess.run(
            f"git {args}", shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd
        )
        out = (result.stdout or "") + ("" if not result.stderr else f"\n{result.stderr}")
        return {
            "success": result.returncode == 0,
            "output": _truncate(out) or "(no output)",
            "command": f"git {args}"
        }
    except Exception as e:
        return {"success": False, "output": str(e)}


async def _tool_http_request(url: str, method: str = "GET", headers: dict = None,
                              body: dict = None, timeout: int = 15) -> dict:
    try:
        import httpx
        method = method.upper()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            kwargs = {"headers": headers or {}}
            if body is not None:
                kwargs["json"] = body
            resp = await c.request(method, url, **kwargs)
            try:
                output = json.dumps(resp.json(), indent=2)
            except Exception:
                output = _truncate(resp.text, 4000)
        return {"success": True, "output": output, "status": resp.status_code, "url": url}
    except Exception as e:
        return {"success": False, "output": f"Request failed: {e}", "url": url}


def _tool_memory_store(content: str, mem_type: str = "fact", db=None) -> dict:
    if db is None:
        return {"success": False, "output": "No DB connection"}
    try:
        from datetime import datetime, timezone
        db["memories"].insert_one({
            "content": content,
            "type": mem_type,
            "source": "agent_tool",
            "utility_score": 0.5,
            "access_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True, "output": f"Stored {mem_type}: {content[:80]}..."}
    except Exception as e:
        return {"success": False, "output": str(e)}


def _tool_create_task(title: str, description: str, priority: str = "normal", db=None) -> dict:
    if db is None:
        return {"success": False, "output": "No DB connection"}
    try:
        import uuid
        from datetime import datetime, timezone
        task_id = str(uuid.uuid4())
        db["tasks"].insert_one({
            "task_id": task_id,
            "title": title,
            "description": description,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "agent_tool"
        })
        return {"success": True, "output": f"Task created: [{priority}] {title}", "task_id": task_id}
    except Exception as e:
        return {"success": False, "output": str(e)}


# ── IMAP email provider config mapping ────────────────────────────────────────
IMAP_SERVERS = {
    "google": "imap.gmail.com",
    "microsoft": "imap-mail.outlook.com",
    "icloud": "imap.mail.me.com",
}


def _get_email_credentials(db=None):
    """Get email credentials from DB settings."""
    if db is None:
        return None, None, None, None
    settings = db["settings"].find_one({"user_id": "default"}) or {}
    provider = settings.get("email_provider", "")
    email = settings.get("email_provider_email", "") or settings.get("email_user", "")
    password = settings.get("email_provider_pass", "") or settings.get("email_pass", "")
    imap_server = IMAP_SERVERS.get(provider, "")
    if not email or not password or not imap_server:
        return None, None, None, None
    return imap_server, email, password, provider


def _tool_read_emails(folder: str = "INBOX", count: int = 5,
                      unread_only: bool = False, search: str = "", db=None) -> dict:
    """Read emails via IMAP from the user's configured email provider."""
    import imaplib
    import email as email_lib
    from email.header import decode_header
    from datetime import datetime, timezone

    imap_server, email_addr, password, provider = _get_email_credentials(db)
    if not imap_server:
        return {"success": False, "output": "No email provider configured. Go to Settings > Email to connect your account."}

    count = min(max(count, 1), 20)

    try:
        # Connect via IMAP SSL
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email_addr, password)
        mail.select(folder, readonly=True)

        # Build search criteria
        if search:
            # Search by subject OR from
            criteria = f'(OR SUBJECT "{search}" FROM "{search}")'
        elif unread_only:
            criteria = "UNSEEN"
        else:
            criteria = "ALL"

        status, msg_ids = mail.search(None, criteria)
        if status != "OK" or not msg_ids[0]:
            mail.logout()
            return {"success": True, "output": "No emails found matching your criteria.", "count": 0}

        ids = msg_ids[0].split()
        # Get latest N
        selected_ids = ids[-count:]
        selected_ids.reverse()  # newest first

        emails = []
        for mid in selected_ids:
            status, msg_data = mail.fetch(mid, "(RFC822 FLAGS)")
            if status != "OK":
                continue

            raw = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw)

            # Decode subject
            subject_parts = decode_header(msg.get("Subject", ""))
            subject = ""
            for part, enc in subject_parts:
                if isinstance(part, bytes):
                    subject += part.decode(enc or "utf-8", errors="replace")
                else:
                    subject += str(part)

            # Sender
            from_raw = msg.get("From", "")
            from_parts = decode_header(from_raw)
            sender = ""
            for part, enc in from_parts:
                if isinstance(part, bytes):
                    sender += part.decode(enc or "utf-8", errors="replace")
                else:
                    sender += str(part)

            # Date
            date_str = msg.get("Date", "")

            # Flags (read/unread)
            flags_raw = msg_data[0][0] if msg_data[0][0] else b""
            is_read = b"\\Seen" in flags_raw

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
                            break
                    elif ct == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_text = payload.decode(charset, errors="replace")
                            # Simple HTML to text
                            body = re.sub(r'<[^>]+>', '', html_text)
                            body = re.sub(r'\s+', ' ', body).strip()
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")

            # Truncate body preview
            body_preview = body.strip()[:500] if body else "(no text content)"

            emails.append({
                "from": sender[:100],
                "subject": subject[:200],
                "date": date_str[:40],
                "read": is_read,
                "body_preview": body_preview,
            })

        mail.logout()

        # Format output
        lines = []
        for i, em in enumerate(emails, 1):
            status_icon = "📧" if not em["read"] else "📨"
            lines.append(
                f"{status_icon} {i}. From: {em['from']}\n"
                f"   Subject: {em['subject']}\n"
                f"   Date: {em['date']}\n"
                f"   {em['body_preview'][:300]}\n"
            )

        output = f"Found {len(emails)} email(s) in {folder}:\n\n" + "\n".join(lines)
        return {"success": True, "output": _truncate(output, 6000), "count": len(emails)}

    except imaplib.IMAP4.error as e:
        err = str(e)
        if "AUTHENTICATIONFAILED" in err or "Invalid credentials" in err:
            return {"success": False, "output": "Email authentication failed. The app password may be expired. Go to Settings > Email to reconnect."}
        return {"success": False, "output": f"IMAP error: {err}"}
    except Exception as e:
        return {"success": False, "output": f"Failed to read emails: {str(e)}"}
