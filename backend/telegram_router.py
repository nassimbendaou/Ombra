"""
Ombra Telegram Inbound Command Router
- Processes incoming Telegram messages
- Routes commands to Ombra actions
- Supports: /status, /summary, /tasks, /run, /pause, /resume, /cancel, /ask
"""
import os
import asyncio
import httpx
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def get_telegram_updates(offset=0, timeout=5):
    """Get updates from Telegram (long polling)."""
    if not TELEGRAM_TOKEN:
        return []
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]}
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
    """Send reply to Telegram."""
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text[:4000],
                "parse_mode": "HTML"
            })
    except Exception:
        pass


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
    """Routes inbound Telegram commands to Ombra actions."""

    def __init__(self, db, route_and_respond_fn, get_summary_fn):
        self.db = db
        self.route_and_respond = route_and_respond_fn
        self.get_summary = get_summary_fn
        self.last_update_id = 0
        self.running = False
        self.allowed_chat_ids = []  # empty = allow all

    def is_authorized(self, chat_id):
        if not self.allowed_chat_ids:
            return True
        return str(chat_id) in [str(x) for x in self.allowed_chat_ids]

    async def handle_command(self, chat_id, command, args):
        """Handle a single command."""
        if not self.is_authorized(chat_id):
            return "Unauthorized. Contact admin."

        self.db["activity_log"].insert_one({
            "type": "telegram_inbound",
            "details": {"command": command, "args": args[:100], "chat_id": str(chat_id)},
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        if command == "status":
            return await self._handle_status()
        elif command == "summary":
            return await self._handle_summary()
        elif command == "tasks":
            return await self._handle_tasks()
        elif command == "run":
            return await self._handle_run(args)
        elif command == "pause":
            return await self._handle_lifecycle(args, "paused")
        elif command == "resume":
            return await self._handle_lifecycle(args, "in_progress")
        elif command == "cancel":
            return await self._handle_lifecycle(args, "cancelled")
        elif command == "ask" or command == "start":
            if not args or command == "start":
                return ("Welcome to Ombra! Available commands:\n"
                        "/status - System status\n"
                        "/summary - Daily summary\n"
                        "/tasks - Active tasks\n"
                        "/run <task_id> - Execute task step\n"
                        "/pause <task_id> - Pause task\n"
                        "/resume <task_id> - Resume task\n"
                        "/cancel <task_id> - Cancel task\n"
                        "Or just type a question!")
            return await self._handle_ask(args)
        elif command == "help":
            return ("Ombra Bot Commands:\n"
                    "/status - System status\n"
                    "/summary - Daily summary\n"
                    "/tasks - Active tasks\n"
                    "/run <task_id> - Execute next step\n"
                    "/pause <task_id> - Pause task\n"
                    "/resume <task_id> - Resume task\n"
                    "/cancel <task_id> - Cancel task\n"
                    "Or just type a question!")
        else:
            # Treat unknown commands as questions
            return await self._handle_ask(f"{command} {args}".strip())

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

        return (f"<b>Ombra Status</b>\n\n"
                f"Ollama: {'Online' if ollama_ok else 'Offline'} ({', '.join(models) if models else 'no models'})\n"
                f"Cloud API: Configured\n"
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

    async def _handle_run(self, args):
        if not args:
            return "Usage: /run <task_id>"
        # This is handled at the server level
        return f"Task execution triggered for: {args.strip()}"

    async def _handle_lifecycle(self, args, new_status):
        if not args:
            return f"Usage: /{new_status.replace('in_progress', 'resume')} <task_id>"
        from bson import ObjectId
        try:
            task_id = args.strip()
            self.db["tasks"].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return f"Task {task_id} set to: {new_status}"
        except Exception as e:
            return f"Error: {str(e)[:100]}"

    async def _handle_ask(self, question):
        try:
            result = await self.route_and_respond(
                message=question,
                system_message="You are Ombra responding via Telegram. Be concise. Max 500 chars."
            )
            response = result.get("response", "Sorry, I couldn't process that.")[:500]
            provider = result.get("provider_used", "unknown")
            return f"{response}\n\n<i>({provider})</i>"
        except Exception as e:
            return f"Error: {str(e)[:100]}"

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
                    text = msg.get("text", "")

                    if chat_id and text:
                        command, args = parse_command(text)
                        reply = await self.handle_command(chat_id, command, args)
                        if reply:
                            await send_reply(chat_id, reply)
            except Exception:
                await asyncio.sleep(5)

            await asyncio.sleep(1)

    def stop(self):
        self.running = False
