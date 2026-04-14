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
- browser_research: Control a real browser page (navigate/search/click)
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

# Track auto-started preview servers so we don't spawn duplicates.
_PREVIEW_SERVERS: dict[int, int] = {}  # port -> pid


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
    """Return a proxy-based preview URL.  Auto-starts a file server on a free port
    so that multi-file apps (HTML + CSS + JS) resolve relative imports correctly."""
    if not path:
        return None
    real = os.path.realpath(path)
    if not any(real.startswith(d) for d in PREVIEW_DIRS):
        return None
    ext = os.path.splitext(real)[1].lower()
    if ext not in PREVIEWABLE_EXT and ext not in APP_ASSET_EXT:
        return None

    # Find the entry HTML file
    target_html = None
    if ext in PREVIEWABLE_EXT and os.path.isfile(real):
        target_html = real
    elif ext in APP_ASSET_EXT:
        cur = os.path.dirname(real)
        for _ in range(6):
            idx = os.path.join(cur, "index.html")
            if os.path.isfile(idx):
                target_html = os.path.realpath(idx)
                break
            parent = os.path.dirname(cur)
            if parent == cur or not any(parent.startswith(d) for d in PREVIEW_DIRS):
                break
            cur = parent
    if not target_html:
        return None

    # Serve from WORK_DIR so relative paths work
    rel_path = os.path.relpath(target_html, WORK_DIR).replace("\\", "/")

    # Auto-start a static file server if one isn't already running
    port = _ensure_preview_server()
    return _proxy_preview_url(port, f"/{rel_path}")


def _ensure_preview_server(base_port: int = 9500) -> int:
    """Ensure a background http.server is running on WORK_DIR. Returns the port."""
    # Check if an existing server is still alive
    for port, pid in list(_PREVIEW_SERVERS.items()):
        try:
            os.kill(pid, 0)  # Check if process exists
            return port
        except OSError:
            del _PREVIEW_SERVERS[port]

    # Find a free port starting from base_port
    import socket
    port = base_port
    for _ in range(20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                break
        except OSError:
            port += 1
    else:
        port = base_port  # fallback

    # Start http.server in background
    try:
        cmd = f"nohup python3 -m http.server {port} --bind 127.0.0.1 > /dev/null 2>&1 & echo $!"
        result = subprocess.run(
            ["/bin/bash", "-c", cmd], capture_output=True, text=True,
            timeout=5, cwd=WORK_DIR
        )
        pid_str = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
        if pid_str.isdigit():
            _PREVIEW_SERVERS[port] = int(pid_str)
    except Exception:
        pass
    return port


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
        # Parse actual port from command (e.g. python -m http.server 8001 --bind 0.0.0.0)
        m = re.search(r'http\.server\b[^|;&]*?\b(\d{2,5})\b', cmd)
        return m.group(1) if m else "8000"
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
        r'http\.server\b[^|;&]*?\b(\d{2,5})\b',
        r'serve.*-l\s+(\d{2,5})',
        r':(?:port|PORT)\s*=?\s*(\d{2,5})',
        r'uvicorn\b[^|;&]*?:(\d{2,5})',
        r'gunicorn\b[^|;&]*?:(\d{2,5})',
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
            "name": "browser_research",
            "description": "Use a real headless browser for web research and interaction. Can navigate, optionally fill search fields, click selectors, and return rendered text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                    "query": {"type": "string", "description": "Optional search phrase to type into detected search input"},
                    "click_selector": {"type": "string", "description": "Optional CSS selector to click after page load"},
                    "timeout": {"type": "integer", "description": "Timeout seconds (default 30, max 120)", "default": 30}
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
    },
    {
        "type": "function",
        "function": {
            "name": "install_packages",
            "description": "Install packages using pip, npm, or apt. Use this tool whenever you need to install dependencies for a project. Supports pip (Python), npm (Node.js), and apt (system packages).",
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {"type": "string", "description": "Space-separated list of package names to install, e.g. 'flask requests numpy' or 'express react'"},
                    "manager": {"type": "string", "description": "Package manager: pip, npm, or apt (default: pip)", "default": "pip"},
                    "cwd": {"type": "string", "description": "Working directory for npm install (default: project workspace)"}
                },
                "required": ["packages"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_video",
            "description": "Generate a short video with text overlay and optional TTS narration. Useful for creating video responses, demos, or explanations. Returns the path to the generated .mp4 file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to display in the video and narrate via TTS"},
                    "duration": {"type": "integer", "description": "Video duration in seconds (default: auto from TTS, max 60)", "default": 10},
                    "title": {"type": "string", "description": "Optional title shown at the top of the video"},
                    "bg_color": {"type": "string", "description": "Background color hex (default: #1a1a2e)", "default": "#1a1a2e"},
                    "text_color": {"type": "string", "description": "Text color hex (default: #ffffff)", "default": "#ffffff"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of any URL (web page, preview link, localhost app) and return it as an image. The screenshot is automatically sent to Telegram. Use this whenever the user asks to 'see' something, wants a screenshot, or asks you to show them what something looks like.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to screenshot. For local apps, use http://127.0.0.1:<port>/<path>"},
                    "full_page": {"type": "boolean", "description": "Whether to capture the full page (default: false, captures viewport only)", "default": False},
                    "width": {"type": "integer", "description": "Viewport width in pixels (default: 1280)", "default": 1280},
                    "height": {"type": "integer", "description": "Viewport height in pixels (default: 720)", "default": 720}
                },
                "required": ["url"]
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

        elif name == "browser_research":
            return await _tool_browser_research(
                args.get("url", ""),
                args.get("query", ""),
                args.get("click_selector", ""),
                args.get("timeout", 30),
            )

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

        elif name == "install_packages":
            return _tool_install_packages(
                args.get("packages", ""), args.get("manager", "pip"),
                args.get("cwd", WORK_DIR)
            )

        elif name == "generate_video":
            return await _tool_generate_video(
                args.get("text", ""), args.get("duration", 10),
                args.get("title", ""), args.get("bg_color", "#1a1a2e"),
                args.get("text_color", "#ffffff")
            )

        elif name == "screenshot":
            return await _tool_screenshot(
                args.get("url", ""), args.get("full_page", False),
                args.get("width", 1280), args.get("height", 720)
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


def _tool_install_packages(packages: str, manager: str = "pip", cwd: str = WORK_DIR) -> dict:
    """Install packages via pip, npm, or apt."""
    if not packages.strip():
        return {"success": False, "output": "No packages specified"}
    manager = (manager or "pip").lower().strip()
    if manager not in ("pip", "npm", "apt"):
        return {"success": False, "output": f"Unsupported package manager: {manager}. Use pip, npm, or apt."}
    # Sanitize: only allow alphanumeric, hyphens, underscores, dots, @, /, =, >, < in package names
    pkg_list = packages.strip().split()
    for pkg in pkg_list:
        if not re.match(r'^[a-zA-Z0-9@_./><=~\[\]-]+$', pkg):
            return {"success": False, "output": f"Invalid package name: {pkg}"}
    safe_pkgs = " ".join(pkg_list)
    if manager == "pip":
        cmd = f"pip install {safe_pkgs}"
    elif manager == "npm":
        cmd = f"npm install {safe_pkgs}"
    else:
        cmd = f"sudo apt-get install -y {safe_pkgs}"
    timeout = 120
    safe_env = {k: v for k, v in os.environ.items()
                if not any(s in k.upper() for s in ["KEY", "SECRET", "PASSWORD", "TOKEN", "PASS"])}
    work_dir = cwd if cwd and os.path.isdir(cwd) else WORK_DIR
    try:
        result = subprocess.run(
            ["/bin/bash", "-lc", cmd], shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=work_dir, env=safe_env
        )
        out = (result.stdout or "") + ("" if not result.stderr else f"\nSTDERR:\n{result.stderr}")
        return {
            "success": result.returncode == 0,
            "output": _truncate(out, 4000) or "(no output)",
            "command": cmd,
            "packages": pkg_list,
            "manager": manager,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"Package install timed out after {timeout}s", "command": cmd}
    except Exception as e:
        return {"success": False, "output": str(e), "command": cmd}


async def _tool_generate_video(text: str, duration: int = 10, title: str = "",
                                bg_color: str = "#1a1a2e", text_color: str = "#ffffff") -> dict:
    """Generate a video with text overlay and TTS narration using ffmpeg."""
    if not text.strip():
        return {"success": False, "output": "No text provided"}
    duration = min(max(int(duration), 2), 60)
    timestamp = int(time.time())
    video_path = os.path.join(WORK_DIR, f"video_{timestamp}.mp4")
    audio_path = os.path.join(WORK_DIR, f"audio_{timestamp}.mp3")
    has_audio = False

    # Try TTS for narration
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    if api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(
                    f"{base_url}/audio/speech",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "tts-1", "input": text[:4096], "voice": "onyx"},
                )
                if resp.status_code == 200 and resp.content:
                    with open(audio_path, "wb") as f:
                        f.write(resp.content)
                    has_audio = True
                    # Get audio duration to match video length
                    probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                        capture_output=True, text=True, timeout=10
                    )
                    if probe.returncode == 0 and probe.stdout.strip():
                        duration = max(int(float(probe.stdout.strip())) + 1, duration)
        except Exception:
            pass

    # Escape text for ffmpeg drawtext
    safe_text = text.replace("'", "\u2019").replace("\\", "\\\\").replace(":", "\\:")
    safe_title = (title or "").replace("'", "\u2019").replace("\\", "\\\\").replace(":", "\\:")

    # Build ffmpeg filter for text overlay
    filters = []
    # Wrap text at ~40 chars per line
    import textwrap
    wrapped = textwrap.fill(safe_text, width=45)
    wrapped_escaped = wrapped.replace("\n", "\\n")

    drawtext_body = (
        f"drawtext=text='{wrapped_escaped}':"
        f"fontcolor={text_color}:fontsize=28:x=(w-text_w)/2:y=(h-text_h)/2:"
        f"font=monospace"
    )
    filters.append(drawtext_body)

    if safe_title:
        drawtext_title = (
            f"drawtext=text='{safe_title}':"
            f"fontcolor={text_color}:fontsize=36:x=(w-text_w)/2:y=60:"
            f"font=monospace"
        )
        filters.append(drawtext_title)

    filter_str = ",".join(filters)

    # Build ffmpeg command
    cmd_parts = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={bg_color}:s=720x480:d={duration}:r=24",
    ]
    if has_audio:
        cmd_parts.extend(["-i", audio_path])
    cmd_parts.extend([
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
    ])
    if has_audio:
        cmd_parts.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
    else:
        cmd_parts.extend(["-an"])
    cmd_parts.append(video_path)

    try:
        result = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=60, cwd=WORK_DIR)
        # Cleanup temp audio
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if result.returncode != 0:
            return {"success": False, "output": f"ffmpeg failed: {(result.stderr or '')[:500]}"}
        if not os.path.exists(video_path):
            return {"success": False, "output": "Video file was not created"}
        size = os.path.getsize(video_path)
        # Also send to Telegram if possible
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        tg_chat = _resolve_telegram_chat_id()
        if tg_token and tg_chat:
            try:
                import httpx
                with open(video_path, "rb") as vf:
                    video_bytes = vf.read()
                async with httpx.AsyncClient(timeout=60) as c:
                    caption = title or text[:200]
                    await c.post(
                        f"https://api.telegram.org/bot{tg_token}/sendVideo",
                        data={"chat_id": str(tg_chat), "caption": caption[:1024]},
                        files={"video": ("response.mp4", video_bytes, "video/mp4")},
                    )
            except Exception:
                pass
        return {
            "success": True,
            "output": f"Video generated: {video_path} ({size} bytes, {duration}s)",
            "path": video_path,
            "duration": duration,
            "has_audio": has_audio,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "Video generation timed out"}
    except Exception as e:
        return {"success": False, "output": f"Video generation error: {str(e)}"}


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


async def _tool_browser_research(url: str, query: str = "", click_selector: str = "", timeout: int = 30) -> dict:
    """Control a real browser page (Playwright) for rendered-web research."""
    if not url:
        return {"success": False, "output": "URL is required"}
    if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
        return {"success": False, "output": "URL must start with http:// or https://", "url": url}

    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {
            "success": False,
            "output": "Playwright is not installed/configured. Install with: pip install playwright && playwright install chromium"
        }

    timeout = max(5, min(int(timeout), 120))
    screenshot_path = os.path.join(WORK_DIR, f"browser_capture_{int(time.time())}.png")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

            if query:
                # Heuristic search-box fill for most sites/search engines.
                search_box = await page.query_selector("input[type='search'], input[name='q'], input[type='text']")
                if search_box:
                    await search_box.fill(query)
                    await search_box.press("Enter")
                    await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)

            if click_selector:
                target = await page.query_selector(click_selector)
                if target:
                    await target.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)

            title = await page.title()
            final_url = page.url
            body_text = await page.inner_text("body")
            await page.screenshot(path=screenshot_path, full_page=True)
            await browser.close()

        preview = _make_preview_url(screenshot_path)
        output = (
            f"Title: {title}\n"
            f"URL: {final_url}\n\n"
            f"Rendered text excerpt:\n{_truncate(body_text, 4000)}"
        )
        result = {
            "success": True,
            "output": output,
            "title": title,
            "url": final_url,
            "screenshot_path": screenshot_path,
        }
        if preview:
            result["preview_url"] = preview
            result["output"] += f"\n\nScreenshot preview: {preview}"
        return result
    except Exception as e:
        return {"success": False, "output": f"Browser research failed: {str(e)}", "url": url}


async def _tool_screenshot(url: str, full_page: bool = False, width: int = 1280, height: int = 720) -> dict:
    """Take a screenshot of a URL and optionally send it to Telegram."""
    if not url:
        return {"success": False, "output": "URL is required"}
    # Allow localhost URLs for local previews
    if not re.match(r"^https?://", url.strip(), re.IGNORECASE):
        # If it looks like a relative path, build a localhost URL
        if url.startswith("/"):
            url = f"http://127.0.0.1:8001{url}"
        else:
            return {"success": False, "output": "URL must start with http:// or https://"}

    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {"success": False, "output": "Playwright is not installed. Run: pip install playwright && playwright install chromium"}

    width = max(320, min(int(width), 1920))
    height = max(240, min(int(height), 1080))
    screenshot_path = os.path.join(WORK_DIR, f"screenshot_{int(time.time())}.png")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            # Small delay to let animations/rendering finish
            await page.wait_for_timeout(1000)
            await page.screenshot(path=screenshot_path, full_page=full_page)
            title = await page.title()
            await browser.close()

        if not os.path.isfile(screenshot_path):
            return {"success": False, "output": "Screenshot file was not created"}

        size = os.path.getsize(screenshot_path)
        preview = _make_preview_url(screenshot_path)

        # Auto-send to Telegram
        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        tg_chat = _resolve_telegram_chat_id()
        if tg_token and tg_chat:
            try:
                import httpx
                with open(screenshot_path, "rb") as f:
                    img_bytes = f.read()
                async with httpx.AsyncClient(timeout=30) as c:
                    await c.post(
                        f"https://api.telegram.org/bot{tg_token}/sendPhoto",
                        data={"chat_id": str(tg_chat), "caption": f"Screenshot: {title or url}"[:1024]},
                        files={"photo": ("screenshot.png", img_bytes, "image/png")},
                    )
            except Exception:
                pass

        result = {
            "success": True,
            "output": f"Screenshot taken: {screenshot_path} ({size} bytes, {width}x{height})",
            "path": screenshot_path,
            "title": title,
            "url": url,
        }
        if preview:
            result["preview_url"] = preview
            result["output"] += f"\nPreview: {preview}"
        return result
    except Exception as e:
        return {"success": False, "output": f"Screenshot failed: {str(e)}", "url": url}


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
