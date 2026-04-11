"""
Ombra Telegram Integration
- Bot webhook/polling for incoming messages
- Send messages, daily summaries, notifications
- Quick commands: /summary, /tasks, /status
"""
import os
import asyncio
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def send_telegram_message(chat_id: str, text: str, token: str = None):
    """Send a message via Telegram bot."""
    import httpx
    tk = token or TELEGRAM_TOKEN
    if not tk:
        return {"success": False, "error": "No Telegram bot token configured"}
    
    url = f"https://api.telegram.org/bot{tk}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            return {"success": data.get("ok", False), "result": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_bot_info(token: str = None):
    """Get Telegram bot info to verify token."""
    import httpx
    tk = token or TELEGRAM_TOKEN
    if not tk:
        return {"success": False, "error": "No token"}
    
    url = f"https://api.telegram.org/bot{tk}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
            return {"success": data.get("ok", False), "bot": data.get("result", {})}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_daily_summary(summary: dict) -> str:
    """Format daily summary for Telegram."""
    text = f"<b>Ombra Daily Summary</b>\n"
    text += f"Date: {summary.get('date', 'N/A')}\n\n"
    text += f"Total Interactions: {summary.get('total_interactions', 0)}\n"
    text += f"Tool Executions: {summary.get('tool_executions', 0)}\n"
    text += f"Memory Operations: {summary.get('memory_operations', 0)}\n"
    text += f"Avg Response: {summary.get('avg_response_ms', 0)}ms\n\n"
    
    providers = summary.get('providers_used', {})
    if providers:
        text += "<b>Providers Used:</b>\n"
        for p, c in providers.items():
            text += f"  - {p}: {c} calls\n"
    
    text += f"\n{summary.get('summary', '')}"
    return text


def format_task_list(tasks: list) -> str:
    """Format task list for Telegram."""
    if not tasks:
        return "No active tasks."
    
    text = "<b>Active Tasks:</b>\n\n"
    for i, task in enumerate(tasks, 1):
        status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(task.get("status", "pending"), "⏳")
        text += f"{status_icon} {i}. {task.get('title', 'Untitled')}\n"
        text += f"   Priority: {task.get('priority', 'medium')} | Status: {task.get('status', 'pending')}\n"
    
    return text
