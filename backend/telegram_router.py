"""
Ombra Telegram Inbound Command Router
Full chat parity: agent loop with tools, conversation persistence,
learning, per-chat session state.
Supports: /status, /summary, /tasks, /status_tasks, /run, /pause, /resume, /cancel,
          /tools, /model, /whitecard, /clear, /help, or plain text
"""
import os
import asyncio
import time
import re
import httpx
from datetime import datetime, timezone
from bson import ObjectId
from urllib.parse import urlparse, parse_qs, unquote

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MAX_TG_LEN = 4000  # Telegram message limit (we leave margin from 4096)

# ── Media / STT helpers ────────────────────────────────────────────────────────

async def _download_telegram_file(file_id: str) -> bytes | None:
    """Download a file from Telegram servers by file_id."""
    if not TELEGRAM_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            info = (await c.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
                                params={"file_id": file_id})).json()
            fpath = info.get("result", {}).get("file_path")
            if not fpath:
                return None
            resp = await c.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{fpath}")
            return resp.content if resp.status_code == 200 else None
    except Exception:
        return None


async def _speech_to_text(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio bytes via OpenAI Whisper API."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    if not api_key:
        return ""
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": "whisper-1"},
                files={"file": (filename, audio_bytes)},
            )
            return resp.json().get("text", "")
    except Exception:
        return ""


async def _text_to_speech(text: str) -> bytes | None:
    """Convert text to speech via OpenAI TTS API. Returns mp3 bytes or None."""
    api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    if not api_key:
        return None
    try:
        # Truncate to TTS limit
        snippet = text[:4096]
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{base_url}/audio/speech",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "tts-1", "input": snippet, "voice": "onyx"},
            )
            if resp.status_code == 200:
                return resp.content
    except Exception:
        pass
    return None


async def send_voice_reply(chat_id, audio_bytes: bytes):
    """Send a voice message back to Telegram."""
    if not TELEGRAM_TOKEN or not audio_bytes:
        return
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice",
                data={"chat_id": str(chat_id)},
                files={"voice": ("reply.mp3", audio_bytes, "audio/mpeg")},
            )
    except Exception:
        pass


async def send_video_reply(chat_id, video_bytes: bytes, caption: str = ""):
    """Send a video message back to Telegram."""
    if not TELEGRAM_TOKEN or not video_bytes:
        return
    try:
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption[:1024]
        async with httpx.AsyncClient(timeout=60) as c:
            await c.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data=data,
                files={"video": ("reply.mp4", video_bytes, "video/mp4")},
            )
    except Exception:
        pass


async def _extract_text_from_media(msg: dict) -> tuple[str, str]:
    """Extract text from a Telegram message (voice/audio/video/video_note/text).

    Returns (transcribed_text, media_type).
    media_type is one of: 'text', 'voice', 'audio', 'video', 'video_note'.
    """
    # Voice message
    if msg.get("voice"):
        file_id = msg["voice"].get("file_id")
        data = await _download_telegram_file(file_id) if file_id else None
        if data:
            text = await _speech_to_text(data, "voice.ogg")
            return (text, "voice") if text else ("", "voice")
        return ("", "voice")

    # Audio file (mp3, etc.)
    if msg.get("audio"):
        file_id = msg["audio"].get("file_id")
        fname = msg["audio"].get("file_name", "audio.mp3")
        data = await _download_telegram_file(file_id) if file_id else None
        if data:
            text = await _speech_to_text(data, fname)
            return (text, "audio") if text else ("", "audio")
        return ("", "audio")

    # Video note (round video)
    if msg.get("video_note"):
        file_id = msg["video_note"].get("file_id")
        data = await _download_telegram_file(file_id) if file_id else None
        if data:
            text = await _speech_to_text(data, "video_note.mp4")
            return (text, "video_note") if text else ("", "video_note")
        return ("", "video_note")

    # Video message
    if msg.get("video"):
        file_id = msg["video"].get("file_id")
        data = await _download_telegram_file(file_id) if file_id else None
        if data:
            text = await _speech_to_text(data, "video.mp4")
            return (text, "video") if text else ("", "video")
        return ("", "video")

    # Plain text (caption on media or regular text)
    text = msg.get("caption") or msg.get("text") or ""
    return (text, "text")


async def get_telegram_updates(offset=0, timeout=5):
    """Get updates from Telegram (long polling)."""
    if not TELEGRAM_TOKEN:
        return []
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "edited_message"]}
    try:
        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
    except Exception:
        pass
    return []


async def send_reply(chat_id, text):
    """Send reply to Telegram, splitting long messages."""
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = _split_message(text)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for chunk in chunks:
                await client.post(url, json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "HTML"
                })
    except Exception:
        # Retry without HTML parse mode in case of formatting errors
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                for chunk in chunks:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": chunk,
                    })
        except Exception:
            pass


def _split_message(text: str) -> list:
    """Split text into chunks that fit Telegram's limit."""
    if len(text) <= MAX_TG_LEN:
        return [text]
    chunks = []
    while text:
        if len(text) <= MAX_TG_LEN:
            chunks.append(text)
            break
        # Try to split at newline
        cut = text.rfind("\n", 0, MAX_TG_LEN)
        if cut < MAX_TG_LEN // 2:
            cut = MAX_TG_LEN
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def _normalize_preview_url(url: str) -> str:
    """Normalize preview links to /api/preview/proxy/<port>/<path> format."""
    if not url:
        return url
    try:
        p = urlparse(url)
        # Already path-style proxy link
        if p.path.startswith("/api/preview/proxy/"):
            return url

        # Legacy query-style proxy link
        if p.path.rstrip("/") == "/api/preview/proxy":
            q = parse_qs(p.query)
            port = (q.get("port") or [""])[0]
            path = unquote((q.get("path") or ["/"])[0])
            if port:
                safe_path = "/" + path.lstrip("/")
                base = f"{p.scheme}://{p.netloc}"
                return f"{base}/api/preview/proxy/{port}{safe_path}"

        # Direct server URL (e.g. http://20.67.232.113:8000/)
        if p.scheme in ("http", "https") and p.hostname and p.port and 3000 <= p.port <= 9998:
            safe_path = "/" + (p.path or "/").lstrip("/")
            base = f"{p.scheme}://{p.hostname}"
            return f"{base}/api/preview/proxy/{p.port}{safe_path}"
    except Exception:
        pass
    return url


def _rewrite_legacy_preview_links(text: str) -> str:
    """Rewrite legacy/query/direct preview links found in plain model text."""
    if not text:
        return text
    # Query-style preview links
    pattern_query = r"https?://[^\s<\"]+/api/preview/proxy\?[^\s<\"]+"
    text = re.sub(pattern_query, lambda m: _normalize_preview_url(m.group(0)), text)
    # Direct host:port links that should go through the preview proxy
    pattern_direct = r"https?://[^\s<\")]+:\d{2,5}[^\s<\")]*"
    return re.sub(pattern_direct, lambda m: _normalize_preview_url(m.group(0)), text)


def parse_command(text):
    """Parse a Telegram command."""
    if not text:
        return None, None
    text = text.strip()
    if not text.startswith("/"):
        return "ask", text
    parts = text.split(maxsplit=1)
    command = parts[0].lower().lstrip("/").split("@")[0]
    args = parts[1] if len(parts) > 1 else ""
    return command, args


class TelegramRouter:
    """Routes inbound Telegram commands to Ombra actions — full chat parity."""

    def __init__(self, db, *,
                 route_and_respond_fn,
                 get_summary_fn,
                 run_agent_loop_fn=None,
                 load_soul_fn=None,
                 extract_and_learn_fn=None,
                 prune_conversation_fn=None,
                 get_permissions_fn=None,
                 classify_agent_fn=None,
                 emergent_key: str = ""):
        self.db = db
        self.route_and_respond = route_and_respond_fn
        self.get_summary = get_summary_fn
        self.run_agent_loop = run_agent_loop_fn
        self.load_soul = load_soul_fn
        self.extract_and_learn = extract_and_learn_fn
        self.prune_conversation = prune_conversation_fn
        self.get_permissions = get_permissions_fn
        self.classify_agent = classify_agent_fn
        self.emergent_key = emergent_key

        self.last_update_id = 0
        self.running = False
        self.allowed_chat_ids = []  # empty = allow all
        # Per-chat session state: {chat_id: {tools: bool, whitecard: bool, model: str|None}}
        self._chat_state: dict = {}

    # ── helpers ────────────────────────────────────────────────────────────
    def _now_iso(self):
        return datetime.now(timezone.utc).isoformat()

    def _get_chat_state(self, chat_id):
        cid = str(chat_id)
        if cid not in self._chat_state:
            self._chat_state[cid] = {"tools": True, "whitecard": False, "model": None}
        return self._chat_state[cid]

    def _session_id(self, chat_id):
        return f"telegram_{chat_id}"

    def is_authorized(self, chat_id):
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in [str(x) for x in self.allowed_chat_ids]

    # ── command dispatch ───────────────────────────────────────────────────
    async def handle_command(self, chat_id, command, args):
        """Handle a single command."""
        if not self.is_authorized(chat_id):
            return "Unauthorized. Contact admin."

        self.db["activity_log"].insert_one({
            "type": "telegram_inbound",
            "details": {"command": command, "args": (args or "")[:100], "chat_id": str(chat_id)},
            "duration_ms": 0,
            "timestamp": self._now_iso()
        })

        if command == "status":
            return await self._handle_status()
        elif command == "summary":
            return await self._handle_summary()
        elif command == "tasks":
            return await self._handle_tasks()
        elif command == "status_tasks":
            return await self._handle_status_tasks()
        elif command == "run":
            return await self._handle_run(args)
        elif command == "pause":
            return await self._handle_lifecycle(args, "paused")
        elif command == "resume":
            return await self._handle_lifecycle(args, "in_progress")
        elif command == "cancel":
            return await self._handle_lifecycle(args, "cancelled")
        elif command == "tools":
            return self._handle_tools_toggle(chat_id, args)
        elif command == "model":
            return self._handle_model(chat_id, args)
        elif command == "whitecard":
            return self._handle_whitecard_toggle(chat_id)
        elif command == "clear":
            return self._handle_clear(chat_id)
        elif command == "ask" or command == "start":
            if not args or command == "start":
                return self._help_text()
            return await self._handle_ask(chat_id, args)
        elif command == "help":
            return self._help_text()
        else:
            # Treat unknown commands as questions
            return await self._handle_ask(chat_id, f"{command} {args}".strip())

    # ── settings commands ──────────────────────────────────────────────────
    def _handle_tools_toggle(self, chat_id, args):
        state = self._get_chat_state(chat_id)
        if args.strip().lower() in ("on", "1", "true", "yes"):
            state["tools"] = True
        elif args.strip().lower() in ("off", "0", "false", "no"):
            state["tools"] = False
        else:
            state["tools"] = not state["tools"]
        return f"Tools: {'ON' if state['tools'] else 'OFF'}"

    def _handle_model(self, chat_id, args):
        state = self._get_chat_state(chat_id)
        model = args.strip() if args.strip() else None
        state["model"] = model
        return f"Model override: {model or 'auto'}"

    def _handle_whitecard_toggle(self, chat_id):
        state = self._get_chat_state(chat_id)
        state["whitecard"] = not state["whitecard"]
        return f"White Card mode: {'ON' if state['whitecard'] else 'OFF'}"

    def _handle_clear(self, chat_id):
        session_id = self._session_id(chat_id)
        self.db["conversations"].delete_one({"session_id": session_id})
        return "Conversation cleared."

    def _help_text(self):
        return (
            "<b>Ombra Bot</b> — full chat with tools\n\n"
            "<b>Chat:</b> Just type anything\n"
            "/tools [on|off] — toggle tool use\n"
            "/model [name] — set model (e.g. gpt-4o)\n"
            "/whitecard — toggle proactive mode\n"
            "/clear — reset conversation\n\n"
            "<b>System:</b>\n"
            "/status — system health\n"
            "/summary — daily summary\n"
            "/tasks — active tasks\n"
            "/status_tasks — status of every task\n"
            "/run <id> — execute task step\n"
            "/pause <id> · /resume <id> · /cancel <id>\n"
            "/help — this message"
        )

    # ── core: full chat with agent loop ────────────────────────────────────
    async def _handle_ask(self, chat_id, question):
        """Full chat handler — mirrors /api/chat with agent loop + tools."""
        session_id = self._session_id(chat_id)
        state = self._get_chat_state(chat_id)
        start = time.time()

        # Load conversation context
        conversation = self.db["conversations"].find_one({"session_id": session_id})
        context = ""
        if conversation:
            recent_turns = conversation.get("turns", [])[-6:]
            context = "\n".join([f"{t['role']}: {t['content'][:200]}" for t in recent_turns])

        system_addition = ""
        if state.get("whitecard"):
            system_addition = ("\n\nYou are in 'White Card' mode. Be proactive: suggest ideas, "
                               "improvements, next steps. Explore creative solutions.")

        # Always use agent loop when available — individual tools check their own permissions
        use_tools = state.get("tools", True)
        can_agent = bool(self.run_agent_loop and use_tools and self.emergent_key)

        # Telegram-specific system prompt: tell the model it's autonomous and has tools
        telegram_system = (
            "\n\n## Telegram Mode — You are autonomous. EXECUTE, don't just talk.\n"
            "You are responding via Telegram. You have tools and MUST use them.\n"
            "Your available tools:\n"
            "- read_emails: Read the user's inbox (list, search, unread)\n"
            "- draft_email: Draft an email for user approval\n"
            "- web_search: Search the internet\n"
            "- fetch_url: Read a web page\n"
            "- browser_research: Use a real browser for rendered-page research\n"
            "- terminal: Run shell commands\n"
            "- read_file / write_file / list_dir: File operations\n"
            "- python_exec: Run Python code\n"
            "- memory_store: Save important info\n"
            "- create_task: Create background tasks\n"
            "- http_request: Call APIs\n"
            "- git_run: Git operations\n\n"
            "RULES:\n"
            "1. When asked to do something, USE the tools. Never say 'I don't have access'.\n"
            "2. For emails: use read_emails to check inbox, draft_email to compose.\n"
            "3. For research: use web_search + fetch_url, then summarize findings.\n"
            "3b. If a site needs JS rendering or interactive navigation, use browser_research.\n"
            "4. Report what you DID, not what you COULD do.\n"
            "5. Be concise in Telegram replies.\n"
            "6. For user notifications from generated scripts, use env vars TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.\n"
            "\n## Code Quality Rules\n"
            "When writing code:\n"
            "1. ALWAYS test your code after writing it. Run it with terminal or python_exec and verify it works.\n"
            "2. If a command or script fails, read the error, fix the issue, and re-run until it works.\n"
            "3. Before writing files, read existing files first to understand context.\n"
            "4. Write complete, working code \u2014 never leave placeholders or TODO comments.\n"
            "5. If you\u2019re unsure, research first (web_search / fetch_url) before coding.\n"
        )

        tool_calls_made = []
        try:
            if can_agent:
                # ── Agent loop with tools (same as /api/chat) ──
                soul = (self.load_soul() if self.load_soul else "") or ""
                extra_ctx = []
                if context:
                    extra_ctx = [{"role": "system", "content": f"Conversation context:\n{context}"}]
                model = state.get("model") or "gpt-4o"
                agent_result = await self.run_agent_loop(
                    message=question,
                    system_prompt=soul + system_addition + telegram_system,
                    model=model,
                    session_id=session_id,
                    db=self.db,
                    tools_enabled=True,
                    extra_context=extra_ctx,
                )
                response_text = agent_result["response"]
                provider_used = "openai"
                model_used = model
                routing = {"route": "agent_loop", "iterations": agent_result["iterations"]}
                duration = agent_result["duration_ms"]
                tool_calls_made = agent_result.get("tool_calls", [])
            else:
                # ── Plain LLM (route_and_respond) ──
                agent_id = self.classify_agent(question) if self.classify_agent else None
                result = await self.route_and_respond(
                    message=question,
                    system_message=system_addition,
                    conversation_context=context,
                    force_provider=state.get("model"),
                    agent_id=agent_id,
                )
                response_text = result.get("response", "Sorry, I couldn't process that.")
                provider_used = result.get("provider_used", "unknown")
                model_used = result.get("model_used", "")
                routing = result.get("routing", {})
                duration = int((time.time() - start) * 1000)
        except Exception as e:
            return f"Error processing message: {str(e)[:200]}"

        # ── Persist conversation ──
        user_turn = {"role": "user", "content": question, "timestamp": self._now_iso()}
        assistant_turn = {
            "role": "assistant",
            "content": response_text,
            "timestamp": self._now_iso(),
            "provider": provider_used,
            "model": model_used,
            "routing": routing,
            "tool_calls": tool_calls_made if tool_calls_made else None,
        }

        if conversation:
            existing = conversation.get("turns", [])
            new_turns = existing + [user_turn, assistant_turn]
            if self.prune_conversation:
                new_turns = self.prune_conversation(new_turns)
            self.db["conversations"].update_one(
                {"session_id": session_id},
                {"$set": {"turns": new_turns, "updated_at": self._now_iso()}}
            )
        else:
            self.db["conversations"].insert_one({
                "session_id": session_id,
                "turns": [user_turn, assistant_turn],
                "created_at": self._now_iso(),
                "updated_at": self._now_iso(),
            })

        # ── Learning extraction (fire-and-forget) ──
        if self.extract_and_learn:
            try:
                asyncio.create_task(self.extract_and_learn(question, response_text, session_id))
            except Exception:
                pass

        # ── Format reply ──
        reply = _rewrite_legacy_preview_links(response_text)
        # Append tool call summary if tools were used
        if tool_calls_made:
            tools_summary = ", ".join(tc.get("tool", tc.get("name", "?")) for tc in tool_calls_made[:5])
            reply += f"\n\n<i>Tools used: {tools_summary}</i>"
            # Collect preview URLs from tool results
            preview_urls = []
            for tc in tool_calls_made:
                url = tc.get("preview_url")
                if not url:
                    r = tc.get("result") or {}
                    url = r.get("preview_url")
                url = _normalize_preview_url(url) if url else url
                if url and url not in preview_urls:
                    preview_urls.append(url)
            if preview_urls:
                for url in preview_urls[:3]:
                    reply += f'\n🔗 <a href="{url}">Preview</a>'
        return reply

    # ── existing command handlers ──────────────────────────────────────────
    async def _handle_status(self):
        import httpx as hx
        try:
            async with hx.AsyncClient(timeout=5) as c:
                resp = await c.get("http://localhost:11434/api/tags")
                models = [m["name"] for m in resp.json().get("models", [])]
                ollama_ok = True
        except Exception:
            models = []
            ollama_ok = False

        mem_count = self.db["memories"].count_documents({})
        conv_count = self.db["conversations"].count_documents({})
        active = self.db["tasks"].count_documents({"status": {"$in": ["pending", "in_progress"]}})

        state_info = ""
        perms = self.get_permissions() if self.get_permissions else {}
        tools_available = bool(self.run_agent_loop and self.emergent_key and
                               (perms.get("terminal") or perms.get("filesystem")))

        return (f"<b>Ombra Status</b>\n\n"
                f"Ollama: {'Online' if ollama_ok else 'Offline'} ({', '.join(models) if models else 'no models'})\n"
                f"Cloud API: {'Configured' if self.emergent_key else 'Not configured'}\n"
                f"Agent Loop: {'Available' if tools_available else 'Unavailable'}\n"
                f"Memories: {mem_count}\n"
                f"Conversations: {conv_count}\n"
                f"Active Tasks: {active}")

    async def _handle_summary(self):
        try:
            summary = await self.get_summary()
            from telegram_bot import format_daily_summary
            return format_daily_summary(summary)
        except Exception as e:
            return f"Failed to get summary: {str(e)[:100]}"

    async def _handle_tasks(self):
        tasks = list(self.db["tasks"].find(
            {"status": {"$in": ["pending", "in_progress", "planned", "paused"]}}
        ).sort("created_at", -1).limit(10))

        if not tasks:
            return "No active tasks."

        from telegram_bot import format_task_list
        return format_task_list(tasks)

    async def _handle_status_tasks(self):
        tasks = list(self.db["tasks"].find({}).sort("created_at", -1).limit(100))
        if not tasks:
            return "No tasks found."

        lines = ["<b>All Task Status</b>"]
        for t in tasks:
            tid = str(t.get("_id", ""))[:8]
            title = (t.get("title") or "Untitled").replace("\n", " ")[:80]
            status = (t.get("status") or "unknown")
            lines.append(f"• <code>{tid}</code> [{status}] {title}")
        return "\n".join(lines)

    async def _handle_run(self, args):
        if not args:
            return "Usage: /run <task_id>"
        return f"Task execution triggered for: {args.strip()}"

    async def _handle_lifecycle(self, args, new_status):
        if not args:
            return f"Usage: /{new_status.replace('in_progress', 'resume')} <task_id>"
        try:
            task_id = args.strip()
            self.db["tasks"].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": new_status, "updated_at": self._now_iso()}}
            )
            return f"Task {task_id} set to: {new_status}"
        except Exception as e:
            return f"Error: {str(e)[:100]}"

    # ── polling loop ───────────────────────────────────────────────────────
    async def poll_loop(self):
        """Continuous polling loop for Telegram updates."""
        self.running = True
        while self.running:
            try:
                updates = await get_telegram_updates(offset=self.last_update_id + 1, timeout=10)
                for update in updates:
                    self.last_update_id = update.get("update_id", self.last_update_id)
                    msg = update.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    if not chat_id:
                        continue

                    # Extract text from any format (voice/audio/video/text)
                    text, media_type = await _extract_text_from_media(msg)

                    if not text:
                        if media_type != "text":
                            await send_reply(chat_id, "I received your message but couldn't transcribe the audio. Please try again or send text.")
                        continue

                    command, args = parse_command(text)
                    try:
                        # Prevent silent hangs on long/blocked tool runs.
                        reply = await asyncio.wait_for(
                            self.handle_command(chat_id, command, args),
                            timeout=180
                        )
                    except asyncio.TimeoutError:
                        reply = (
                            "I am still working on your request and it took too long in one step. "
                            "Please retry, or ask me to split the task in smaller steps."
                        )
                        try:
                            self.db["activity_log"].insert_one({
                                "type": "telegram_poll_timeout",
                                "details": {"chat_id": str(chat_id), "command": command},
                                "duration_ms": 180000,
                                "timestamp": self._now_iso()
                            })
                        except Exception:
                            pass

                    if reply:
                        # Respond in same format: voice/audio/video → voice, else text
                        if media_type in ("voice", "audio", "video_note", "video"):
                            audio = await _text_to_speech(reply)
                            if audio:
                                await send_voice_reply(chat_id, audio)
                            else:
                                # Fallback to text if TTS fails
                                await send_reply(chat_id, reply)
                        else:
                            await send_reply(chat_id, reply)
            except Exception as e:
                try:
                    self.db["activity_log"].insert_one({
                        "type": "telegram_poll_error",
                        "details": {"error": str(e)[:300]},
                        "duration_ms": 0,
                        "timestamp": self._now_iso()
                    })
                except Exception:
                    pass
                await asyncio.sleep(5)

            await asyncio.sleep(1)

    def stop(self):
        self.running = False
