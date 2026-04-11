"""
Ombra Creative Exploration Engine
- Internal context-based idea generation
- Learning from user acceptance/rejection patterns
- Safe-by-default (no external calls, no auto-execution)
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional


class CreativeExplorer:
    """Proactive idea generation based on internal context."""

    def __init__(self, db, ollama_url, emergent_key):
        self.db = db
        self.ollama_url = ollama_url
        self.emergent_key = emergent_key
        self.enabled = False
        self.cadence_ticks = 5  # Generate ideas every N ticks (default: 5 ticks)
        self.draft_tasks_auto = False  # Require user approval by default
        self.tick_counter = 0
        
        self.stats = {
            "ideas_generated": 0,
            "ideas_accepted": 0,
            "ideas_ignored": 0,
            "tasks_drafted": 0,
            "last_run_at": None
        }

    def _gather_context(self):
        """Gather internal context for idea generation."""
        context = {
            "recent_topics": [],
            "pinned_memories": [],
            "active_tasks": [],
            "completed_tasks_today": 0
        }

        # Recent conversation topics
        recent_convos = list(self.db["conversations"].find().sort("updated_at", -1).limit(3))
        for conv in recent_convos:
            turns = conv.get("turns", [])
            user_turns = [t for t in turns if t["role"] == "user"]
            if user_turns:
                context["recent_topics"].append(user_turns[-1]["content"][:150])

        # Pinned memories
        pinned = list(self.db["memories"].find({"pinned": True}).limit(5))
        context["pinned_memories"] = [m.get("content", "")[:100] for m in pinned]

        # Active tasks
        active = list(self.db["tasks"].find({
            "status": {"$in": ["pending", "in_progress", "planned"]}
        }).limit(5))
        context["active_tasks"] = [t.get("title", "") for t in active]

        # Completed tasks today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = self.db["tasks"].count_documents({
            "status": "completed",
            "completed_at": {"$gte": today_start.isoformat()}
        })
        context["completed_tasks_today"] = completed_today

        return context

    def _score_suggestion(self, suggestion_text):
        """Score a suggestion based on historical acceptance patterns."""
        # Simple heuristic: count keywords from previously accepted suggestions
        # In a real system, this would use more sophisticated ML
        accepted_suggestions = list(self.db["memories"].find({
            "type": "creative_idea",
            "accepted": True
        }).limit(10))

        # Extract common keywords from accepted ideas
        score = 0.5  # Base score
        for accepted in accepted_suggestions:
            content = accepted.get("content", "").lower()
            if any(word in suggestion_text.lower() for word in content.split()[:5]):
                score += 0.1

        return min(1.0, score)

    async def generate_idea(self):
        """Generate a single creative idea from internal context."""
        context = self._gather_context()

        # Check if we have enough context
        if not context["recent_topics"] and not context["pinned_memories"] and not context["active_tasks"]:
            return None

        # Build prompt
        prompt_parts = ["Based on the following context, generate ONE creative, actionable suggestion or idea:\n"]
        
        if context["recent_topics"]:
            prompt_parts.append(f"Recent topics discussed: {'; '.join(context['recent_topics'])}")
        
        if context["pinned_memories"]:
            prompt_parts.append(f"Important memories: {'; '.join(context['pinned_memories'])}")
        
        if context["active_tasks"]:
            prompt_parts.append(f"Active tasks: {'; '.join(context['active_tasks'])}")
        
        prompt_parts.append(f"Completed tasks today: {context['completed_tasks_today']}")
        prompt_parts.append("\nRespond with a single creative suggestion (1-2 sentences):")

        prompt = "\n".join(prompt_parts)

        # Try local model first (mistral preferred for creativity)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{self.ollama_url}/api/generate", json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 150,
                        "temperature": 0.9,  # Higher temp for creativity
                        "top_p": 0.95
                    }
                })
                
                if resp.status_code == 200:
                    idea = resp.json().get("response", "").strip()
                    
                    if idea and len(idea) > 20:  # Minimum viable idea length
                        # Score the idea
                        score = self._score_suggestion(idea)
                        
                        # Store as memory
                        memory_id = self.db["memories"].insert_one({
                            "type": "creative_idea",
                            "content": idea[:500],
                            "source": "creative_explorer",
                            "utility_score": score,
                            "access_count": 0,
                            "pinned": False,
                            "accepted": None,  # Track if user acts on it
                            "decay_rate": 0.05,
                            "context": context,
                            "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).inserted_id
                        
                        self.stats["ideas_generated"] += 1
                        self.stats["last_run_at"] = datetime.now(timezone.utc).isoformat()
                        
                        return {
                            "idea_id": str(memory_id),
                            "content": idea,
                            "score": score,
                            "context_summary": {
                                "topics": len(context["recent_topics"]),
                                "memories": len(context["pinned_memories"]),
                                "tasks": len(context["active_tasks"])
                            }
                        }
        
        except Exception as e:
            print(f"Creative idea generation error: {e}")
            return None

    async def tick(self):
        """Periodic tick for creative exploration."""
        if not self.enabled:
            return {"action": "skipped", "reason": "disabled"}

        self.tick_counter += 1

        # Only run every N ticks
        if self.tick_counter % self.cadence_ticks != 0:
            return {"action": "skipped", "reason": "not_due"}

        # Generate idea
        idea = await self.generate_idea()
        
        if idea:
            # Log activity
            self.db["activity_log"].insert_one({
                "type": "creativity",
                "details": {
                    "idea_id": idea["idea_id"],
                    "score": idea["score"],
                    "content_preview": idea["content"][:100]
                },
                "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "action": "generated",
                "idea": idea
            }
        
        return {"action": "no_idea", "reason": "insufficient_context"}

    def update_settings(self, enabled=None, cadence_ticks=None, draft_tasks_auto=None):
        """Update creative explorer settings."""
        if enabled is not None:
            self.enabled = enabled
        if cadence_ticks is not None:
            self.cadence_ticks = max(1, cadence_ticks)
        if draft_tasks_auto is not None:
            self.draft_tasks_auto = draft_tasks_auto

    def mark_idea_accepted(self, idea_id):
        """Mark an idea as accepted (user acted on it)."""
        self.db["memories"].update_one(
            {"_id": idea_id},
            {"$set": {"accepted": True, "accepted_at": datetime.now(timezone.utc).isoformat()}}
        )
        self.stats["ideas_accepted"] += 1

    def mark_idea_ignored(self, idea_id):
        """Mark an idea as ignored."""
        self.db["memories"].update_one(
            {"_id": idea_id},
            {"$set": {"accepted": False, "ignored_at": datetime.now(timezone.utc).isoformat()}}
        )
        self.stats["ideas_ignored"] += 1

    def get_status(self):
        """Get creative explorer status."""
        return {
            "enabled": self.enabled,
            "cadence_ticks": self.cadence_ticks,
            "draft_tasks_auto": self.draft_tasks_auto,
            "tick_counter": self.tick_counter,
            "stats": self.stats
        }
