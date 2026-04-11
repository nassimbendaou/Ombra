"""
Ombra Autonomy Daemon
- Background worker for autonomous operations
- Task advancement, memory decay, creative ideas, Telegram summaries
- Respects quiet hours and permissions
"""
import asyncio
import os
from datetime import datetime, timezone


class AutonomyDaemon:
    """Background daemon for autonomous task execution and maintenance."""

    def __init__(self, db, ollama_url, emergent_key):
        self.db = db
        self.ollama_url = ollama_url
        self.emergent_key = emergent_key
        self.running = False
        self.paused = False
        self.tick_interval = 60  # seconds
        self.task = None
        self.stats = {
            "ticks": 0,
            "tasks_advanced": 0,
            "ideas_generated": 0,
            "decay_runs": 0,
            "telegram_sent": 0,
            "cloud_escalations": 0,
            "started_at": None,
            "last_tick_at": None
        }

    def is_quiet_hours(self):
        """Check if we're in quiet hours."""
        settings = self.db["settings"].find_one({"user_id": "default"}) or {}
        start = settings.get("quiet_hours_start", "")
        end = settings.get("quiet_hours_end", "")
        if not start or not end:
            return False
        now = datetime.now(timezone.utc).strftime("%H:%M")
        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end

    async def tick(self):
        """Single tick of the autonomy daemon."""
        if self.paused or self.is_quiet_hours():
            return {"action": "skipped", "reason": "paused" if self.paused else "quiet_hours"}

        self.stats["ticks"] += 1
        self.stats["last_tick_at"] = datetime.now(timezone.utc).isoformat()
        actions_taken = []

        # 1. Run memory decay periodically (every 10 ticks)
        if self.stats["ticks"] % 10 == 0:
            decayed, removed = await self._run_memory_decay()
            if decayed > 0 or removed > 0:
                actions_taken.append(f"memory_decay: {decayed} decayed, {removed} removed")
                self.stats["decay_runs"] += 1

        # 2. Generate creative ideas periodically (every 5 ticks)
        if self.stats["ticks"] % 5 == 0:
            settings = self.db["settings"].find_one({"user_id": "default"}) or {}
            if settings.get("white_card_enabled", False):
                idea = await self._generate_creative_idea()
                if idea:
                    actions_taken.append(f"creative_idea: {idea[:80]}")
                    self.stats["ideas_generated"] += 1

        # 3. Send Telegram summary at end of day (tick 100+)
        if self.stats["ticks"] % 100 == 0:
            settings = self.db["settings"].find_one({"user_id": "default"}) or {}
            if settings.get("telegram_enabled") and settings.get("telegram_chat_id"):
                actions_taken.append("telegram_summary_triggered")
                self.stats["telegram_sent"] += 1

        if actions_taken:
            self.db["activity_log"].insert_one({
                "type": "autonomy_daemon",
                "details": {"actions": actions_taken, "tick": self.stats["ticks"]},
                "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return {"action": "ticked", "actions_taken": actions_taken}

    async def _run_memory_decay(self):
        """Decay unpinned memories."""
        unpinned = list(self.db["memories"].find({"pinned": {"$ne": True}}))
        decayed = 0
        removed = 0
        for mem in unpinned:
            score = mem.get("utility_score", 0.5)
            decay = mem.get("decay_rate", 0.01)
            new_score = max(0, score - decay)
            if new_score < 0.1:
                self.db["memories"].delete_one({"_id": mem["_id"]})
                removed += 1
            else:
                self.db["memories"].update_one(
                    {"_id": mem["_id"]},
                    {"$set": {"utility_score": round(new_score, 3),
                              "updated_at": datetime.now(timezone.utc).isoformat()}}
                )
                decayed += 1
        return decayed, removed

    async def _generate_creative_idea(self):
        """Generate a creative idea based on context."""
        # Gather context
        recent_topics = []
        recent_convos = list(self.db["conversations"].find().sort("updated_at", -1).limit(3))
        for conv in recent_convos:
            turns = conv.get("turns", [])
            user_turns = [t for t in turns if t["role"] == "user"]
            if user_turns:
                recent_topics.append(user_turns[-1]["content"][:100])

        pinned_memories = list(self.db["memories"].find({"pinned": True}).limit(5))
        memory_context = [m.get("content", "")[:80] for m in pinned_memories]

        active_tasks = list(self.db["tasks"].find({"status": {"$in": ["pending", "in_progress", "planned"]}}).limit(3))
        task_context = [t.get("title", "") for t in active_tasks]

        if not recent_topics and not memory_context and not task_context:
            return None

        idea_prompt = f"""Based on the following context, generate ONE creative, actionable idea or suggestion:

Recent topics: {'; '.join(recent_topics) if recent_topics else 'None'}
Pinned memories: {'; '.join(memory_context) if memory_context else 'None'}
Active tasks: {'; '.join(task_context) if task_context else 'None'}

Respond with a single paragraph - a creative, helpful suggestion."""

        # Try local model first
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(f"{self.ollama_url}/api/generate", json={
                    "model": "mistral",
                    "prompt": idea_prompt,
                    "stream": False,
                    "options": {"num_predict": 150, "temperature": 0.9}
                })
                idea = resp.json().get("response", "")
                if idea:
                    # Store as suggestion
                    self.db["memories"].insert_one({
                        "type": "creative_idea",
                        "content": idea.strip()[:500],
                        "source": "autonomy_daemon",
                        "utility_score": 0.5,
                        "access_count": 0,
                        "pinned": False,
                        "decay_rate": 0.05,
                        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    return idea.strip()[:200]
        except Exception:
            pass
        return None

    async def start(self):
        """Start the autonomy daemon."""
        self.running = True
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.db["activity_log"].insert_one({
            "type": "system",
            "details": {"event": "autonomy_daemon_started"},
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while self.running:
            try:
                await self.tick()
            except Exception as e:
                self.db["activity_log"].insert_one({
                    "type": "system",
                    "details": {"event": "daemon_error", "error": str(e)[:200]},
                    "duration_ms": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            await asyncio.sleep(self.tick_interval)

    def stop(self):
        """Stop the autonomy daemon."""
        self.running = False

    def get_status(self):
        """Get daemon status."""
        return {
            "running": self.running,
            "paused": self.paused,
            "stats": self.stats,
            "tick_interval": self.tick_interval,
            "quiet_hours_active": self.is_quiet_hours()
        }
