"""
Ombra Autonomy Daemon — K1 Full Autonomy Mode
- Ombra acts independently: researches topics, creates tasks, improves prompts, notifies the user
- Self-directed goal generation every 20 ticks
- Autonomous action loop every 2 ticks (no user needed)
- Prompt self-improvement using cloud API
- Always notifies user via Telegram + activity log after doing something significant
- Internet learning + memory decay + task advancement as before
"""
import asyncio
import os
import json
import re
import time
import uuid
from datetime import datetime, timezone, timedelta

from agent_tools import execute_tool, TOOL_DEFINITIONS
from agents import BUILTIN_AGENTS, classify_task_for_agent
from agent_loop import run_agent_loop

# Tools safe for autonomous sub-agent use (no terminal, write_file, git_run)
AUTONOMOUS_SAFE_TOOLS = {
    "web_search", "fetch_url", "list_dir", "read_file",
    "python_exec", "create_task", "memory_store", "http_request", "draft_email", "browser_research"
}


class AutonomyDaemon:
    """Background daemon for fully autonomous K1 operation."""

    def __init__(self, db, ollama_url, emergent_key):
        self.db = db
        self.ollama_url = ollama_url
        self.emergent_key = emergent_key
        self.running = False
        self.paused = False
        self.tick_interval = 60  # seconds
        self.task = None
        self._current_goals = []  # K1's self-set goals
        self.stats = {
            "ticks": 0,
            "tasks_advanced": 0,
            "ideas_generated": 0,
            "decay_runs": 0,
            "telegram_sent": 0,
            "cloud_escalations": 0,
            "internet_learns": 0,
            "autonomous_actions": 0,
            "tool_actions": 0,
            "plan_runs": 0,
            "verify_failures": 0,
            "retry_attempts": 0,
            "retry_exhausted": 0,
            "loop_guard_skips": 0,
            "goals_set": 0,
            "prompts_improved": 0,
            "morning_reports_sent": 0,
            "last_morning_report_date": None,
            "started_at": None,
            "last_tick_at": None
        }

    def _normalize_subject(self, text: str) -> str:
        """Normalize a subject so near-duplicates can be compared reliably."""
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        normalized = re.sub(r"[^a-z0-9 ]", "", normalized)
        return normalized[:120]

    def _recent_autonomy_subjects(self, hours: int = 12, limit: int = 20):
        """Return normalized recent subjects used by autonomous actions and tool calls."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        recent = []

        for entry in self.db["activity_log"].find({
            "type": {"$in": ["k1_tool_action", "k1_autonomous_report"]},
            "timestamp": {"$gte": cutoff}
        }).sort("timestamp", -1).limit(limit):
            details = entry.get("details", {}) or {}
            subject = details.get("subject") or details.get("summary") or ""
            normalized = self._normalize_subject(subject)
            if normalized:
                recent.append(normalized)

        for mem in self.db["memories"].find({
            "type": {"$in": ["k1_research", "k1_tool_learn"]},
            "created_at": {"$gte": cutoff}
        }).sort("created_at", -1).limit(limit):
            content = mem.get("content", "")
            normalized = self._normalize_subject(content)
            if normalized:
                recent.append(normalized)

        unique = []
        for item in recent:
            if item not in unique:
                unique.append(item)
        return unique[:limit]

    def _is_subject_recent(self, subject: str, hours: int = 12) -> bool:
        """Check whether a subject is too similar to recent autonomous work."""
        normalized = self._normalize_subject(subject)
        if not normalized:
            return False
        recent = self._recent_autonomy_subjects(hours=hours)
        return any(normalized in item or item in normalized for item in recent)

    def _is_tool_action_repeated(self, tool_name: str, tool_args: dict, hours: int = 8) -> bool:
        """Protect against action loops by checking recent near-identical tool calls."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        key = f"{tool_name}:{json.dumps(tool_args or {}, sort_keys=True)}"[:300]
        count = 0
        for entry in self.db["activity_log"].find({
            "type": "k1_tool_action",
            "timestamp": {"$gte": cutoff}
        }).sort("timestamp", -1).limit(20):
            details = entry.get("details", {}) or {}
            existing_key = f"{details.get('tool', '')}:{json.dumps(details.get('args', {}) or {}, sort_keys=True)}"[:300]
            if existing_key == key:
                count += 1
            if count >= 2:
                return True
        return False

    def _log_observation(self, event_type: str, details: dict, phase: str = "run"):
        """Centralized observability log for autonomous planning/execution/verification."""
        payload = {
            "type": event_type,
            "phase": phase,
            "details": details,
            "duration_ms": details.get("duration_ms", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.db["activity_log"].insert_one(payload)

    def _create_autonomy_task(self, subject: str, reason: str, plan: dict):
        """Create a task document with explicit plan/execute/verify state machine."""
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.db["tasks"].insert_one({
            "task_id": task_id,
            "title": f"[Autonomy] {subject[:120]}",
            "description": reason[:240],
            "status": "planned",
            "state_phase": "plan",
            "state_history": [{"phase": "plan", "at": now, "note": "Plan created"}],
            "plan": plan,
            "source": "k1_state_machine",
            "created_at": now,
            "updated_at": now,
        })
        return task_id

    def _update_task_phase(self, task_id: str, phase: str, note: str, status: str = None, extra: dict = None):
        """Update state machine phase and append structured history entries."""
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "$set": {"state_phase": phase, "updated_at": now},
            "$push": {"state_history": {"phase": phase, "at": now, "note": note}},
        }
        if status:
            update["$set"]["status"] = status
        if extra:
            for k, v in extra.items():
                update["$set"][k] = v
        self.db["tasks"].update_one({"task_id": task_id}, update)

    async def _build_tool_plan(self, subject: str, reason: str) -> dict:
        """Create a concrete multi-step plan with explicit verification criteria."""
        recent_subjects = self._recent_autonomy_subjects(hours=12, limit=8)
        prompt = f"""You are Ombra creating a safe autonomous execution plan.

Objective: {subject}
Reason: {reason}
Recent subjects to avoid repeating: {('; '.join(recent_subjects))[:300] or 'None'}

Return STRICT JSON:
{{
  "goal": "short goal",
  "steps": [
    {{"id": "s1", "tool": "web_search", "args": {{"query": "..."}}, "verify": "what success looks like"}},
    {{"id": "s2", "tool": "memory_store", "args": {{"content": "...", "mem_type": "insight"}}, "verify": "what success looks like"}}
  ]
}}

Rules:
- Use only: web_search, fetch_url, browser_research, list_dir, read_file, python_exec, create_task, memory_store, http_request
- 1 to 3 steps max
- Avoid repeating prior topics
- Keep args minimal and safe
"""

        raw = await self._call_openai(prompt, max_tokens=300) or await self._call_ollama(prompt, max_tokens=220)
        if not raw:
            return {
                "goal": subject,
                "steps": [{"id": "s1", "tool": "web_search", "args": {"query": subject}, "verify": "At least one result is returned"}],
            }

        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return {
                "goal": subject,
                "steps": [{"id": "s1", "tool": "web_search", "args": {"query": subject}, "verify": "At least one result is returned"}],
            }

        try:
            plan = json.loads(match.group())
        except Exception:
            plan = {
                "goal": subject,
                "steps": [{"id": "s1", "tool": "web_search", "args": {"query": subject}, "verify": "At least one result is returned"}],
            }

        steps = plan.get("steps") or []
        filtered = []
        allowed = {"web_search", "fetch_url", "browser_research", "list_dir", "read_file", "python_exec", "create_task", "memory_store", "http_request"}
        for i, step in enumerate(steps[:3]):
            tool = (step.get("tool") or "").strip()
            if tool in allowed:
                filtered.append({
                    "id": step.get("id") or f"s{i+1}",
                    "tool": tool,
                    "args": step.get("args") or {},
                    "verify": (step.get("verify") or "tool success true")[:180],
                })
        if not filtered:
            filtered = [{"id": "s1", "tool": "web_search", "args": {"query": subject}, "verify": "At least one result is returned"}]
        return {"goal": (plan.get("goal") or subject)[:200], "steps": filtered}

    async def _execute_tool_with_retry(self, tool_name: str, tool_args: dict, retries: int = 3) -> tuple[dict, int]:
        """Retry transient tool failures with exponential backoff."""
        attempt = 0
        last_result = {"success": False, "output": "Tool execution did not start"}
        while attempt < retries:
            attempt += 1
            started = time.time()
            result = await execute_tool(tool_name, tool_args, self.db)
            duration_ms = int((time.time() - started) * 1000)
            self._log_observation("k1_tool_attempt", {
                "tool": tool_name,
                "args": tool_args,
                "attempt": attempt,
                "success": result.get("success", False),
                "output_preview": (result.get("output", "") or "")[:220],
                "duration_ms": duration_ms,
            }, phase="execute")

            if result.get("success", False):
                return result, attempt

            last_result = result
            transient = any(x in (result.get("output", "") or "").lower() for x in ["timeout", "temporar", "connection", "rate", "busy", "502", "503"])
            if attempt < retries and transient:
                self.stats["retry_attempts"] += 1
                await asyncio.sleep(min(2 ** (attempt - 1), 5))
            else:
                break

        self.stats["retry_exhausted"] += 1
        return last_result, attempt

    async def _verify_step_outcome(self, goal: str, step: dict, result: dict) -> tuple[bool, str]:
        """Verify each execution step for plan/execute/verify state machine."""
        if not result.get("success", False):
            return False, "tool returned success=false"
        verify_text = step.get("verify", "")
        output = (result.get("output", "") or "")[:700]
        prompt = f"""You are verifying an autonomous task step.

Goal: {goal}
Step verify rule: {verify_text}
Tool output: {output}

Respond only JSON: {{"ok": true/false, "note": "short reason"}}
"""
        raw = await self._call_openai(prompt, max_tokens=120) or await self._call_ollama(prompt, max_tokens=90)
        if not raw:
            return True, "fallback accepted (no verifier response)"
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return True, "fallback accepted (unparseable verifier response)"
        try:
            verdict = json.loads(match.group())
            ok = bool(verdict.get("ok", True))
            note = (verdict.get("note") or "")[:200]
            return ok, note or ("verified" if ok else "not verified")
        except Exception:
            return True, "fallback accepted (verifier parse failed)"

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
        """Single tick of the K1 full autonomy daemon."""
        if self.paused or self.is_quiet_hours():
            return {"action": "skipped", "reason": "paused" if self.paused else "quiet_hours"}

        self.stats["ticks"] += 1
        self.stats["last_tick_at"] = datetime.now(timezone.utc).isoformat()
        actions_taken = []
        significant_actions = []  # things worth notifying user about

        # 1. Memory decay (every 10 ticks)
        if self.stats["ticks"] % 10 == 0:
            decayed, removed = await self._run_memory_decay()
            if decayed > 0 or removed > 0:
                actions_taken.append(f"memory_decay: {decayed} decayed, {removed} removed")
                self.stats["decay_runs"] += 1

        # 2. Set autonomous goals (every 20 ticks ~20 min)
        if self.stats["ticks"] % 20 == 0:
            goals = await self._set_autonomous_goals()
            if goals:
                actions_taken.append(f"new_goals: {len(goals)}")
                self.stats["goals_set"] += len(goals)
                # Goals are internal planning — logged but not pushed to Telegram

        # 3. Autonomous action (every 2 ticks)
        if self.stats["ticks"] % 2 == 0:
            result = await self._autonomous_action()
            if result:
                actions_taken.append(f"autonomous: {result['type']}")
                self.stats["autonomous_actions"] += 1
                significant_actions.append(f"I autonomously {result['description']}")

        # 4. Creative idea (every 5 ticks — always, no gate)
        if self.stats["ticks"] % 5 == 0:
            idea = await self._generate_creative_idea()
            if idea:
                actions_taken.append(f"creative_idea: {idea[:80]}")
                self.stats["ideas_generated"] += 1

        # 5. Learn from internet (configurable cadence, default 30 ticks)
        settings = self.db["settings"].find_one({"user_id": "default"}) or {}
        internet_cadence = max(1, int(settings.get("internet_learning_cadence_ticks", 30) or 30))
        if self.stats["ticks"] % internet_cadence == 0:
            learned = await self._learn_from_internet()
            if learned:
                actions_taken.append(f"internet_learn: {learned}")
                self.stats["internet_learns"] += 1
                # Learning is routine background work — logged but not pushed to Telegram

        # 6. Advance pending tasks (every 3 ticks)
        if self.stats["ticks"] % 3 == 0:
            advanced = await self._advance_tasks()
            if advanced:
                actions_taken.append(f"task_advanced: {advanced}")
                self.stats["tasks_advanced"] += 1

        # 7. Self-improve prompts using OpenAI (every 15 ticks ~15 min)
        if self.stats["ticks"] % 15 == 0:
            improved = await self._self_improve_prompts()
            if improved:
                actions_taken.append(f"prompt_improved: {improved}")
                self.stats["prompts_improved"] += 1
                # Prompt improvements are internal maintenance — logged but not pushed to Telegram

        # 8. Log + notify user if significant things happened
        if actions_taken:
            self.db["activity_log"].insert_one({
                "type": "autonomy_daemon",
                "details": {"actions": actions_taken, "tick": self.stats["ticks"]},
                "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        if significant_actions:
            await self._notify_user(significant_actions)

        # 9. Morning learning digest (clock-based, once per day)
        if self._is_morning_summary_due():
            sent = await self._send_morning_learning_summary()
            if sent:
                actions_taken.append("morning_learning_digest")

        return {"action": "ticked", "actions_taken": actions_taken}

    def _get_best_model(self):
        """Return the smallest available Ollama model."""
        try:
            import httpx, asyncio
            # Use sync call in sync context
            import urllib.request
            with urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=5) as r:
                data = json.loads(r.read())
                models = sorted(data.get("models", []), key=lambda m: m.get("size", 0))
                if models:
                    return models[0]["name"]
        except Exception:
            pass
        return "tinyllama"

    async def _call_openai(self, prompt, system="You are Ombra, an autonomous AI.", max_tokens=400):
        """Call OpenAI API directly for higher-quality tasks."""
        if not self.emergent_key:
            return None
        import httpx
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                resp = await c.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.emergent_key}", "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "messages": messages, "max_tokens": max_tokens, "temperature": 0.7}
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    async def _call_ollama(self, prompt, system="", max_tokens=300):
        """Call Ollama with the best available model."""
        import httpx
        model = self._get_best_model()
        full_prompt = f"{system}\n\nUser: {prompt}\nAssistant:" if system else prompt
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.post(f"{self.ollama_url}/api/generate", json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.7}
                })
                return resp.json().get("response", "").strip()
        except Exception:
            return None

    def _get_user_patterns(self) -> dict:
        """Analyze recent conversations and tasks to detect the user's daily patterns and needs."""
        try:
            # Recent user messages (last 48h)
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
            recent_convos = list(self.db["conversations"].find(
                {"updated_at": {"$gte": cutoff}}
            ).sort("updated_at", -1).limit(10))

            user_topics = []
            user_asks = []
            for conv in recent_convos:
                for turn in conv.get("turns", []):
                    if turn.get("role") == "user":
                        content = turn.get("content", "")[:200]
                        user_topics.append(content)
                        # Detect recurring patterns: requests for reminders, schedules, checks
                        lower = content.lower()
                        if any(w in lower for w in ["remind", "deadline", "tomorrow", "meeting", "schedule"]):
                            user_asks.append(("schedule", content))
                        elif any(w in lower for w in ["email", "mail", "inbox"]):
                            user_asks.append(("email", content))
                        elif any(w in lower for w in ["weather", "rain", "temperature"]):
                            user_asks.append(("weather", content))
                        elif any(w in lower for w in ["price", "cost", "buy", "order", "shop"]):
                            user_asks.append(("shopping", content))
                        elif any(w in lower for w in ["news", "update", "latest"]):
                            user_asks.append(("news", content))
                        elif any(w in lower for w in ["code", "script", "deploy", "server", "bug", "error"]):
                            user_asks.append(("devops", content))

            # Recurring task patterns
            recent_tasks = list(self.db["tasks"].find(
                {"created_at": {"$gte": cutoff}}
            ).sort("created_at", -1).limit(15))
            task_patterns = [t.get("title", "") for t in recent_tasks]

            # User's pinned memories (long-term interests)
            pinned = list(self.db["memories"].find({"pinned": True}).limit(10))
            interests = [m.get("content", "")[:100] for m in pinned]

            return {
                "recent_topics": user_topics[:10],
                "categorized_asks": user_asks[:10],
                "task_patterns": task_patterns[:8],
                "interests": interests[:6],
            }
        except Exception:
            return {"recent_topics": [], "categorized_asks": [], "task_patterns": [], "interests": []}

    async def _set_autonomous_goals(self):
        """K1 sets its own goals — focused on practical daily-life assistance."""
        try:
            # Gather context
            recent_memories = list(self.db["memories"].find().sort("created_at", -1).limit(10))
            recent_tasks = list(self.db["tasks"].find({"status": {"$in": ["pending", "planned"]}}).limit(5))
            last_internet = list(self.db["memories"].find({"type": "internet_knowledge"}).sort("created_at", -1).limit(5))
            user_patterns = self._get_user_patterns()

            mem_ctx = "; ".join(m.get("content", "")[:80] for m in recent_memories)
            task_ctx = "; ".join(t.get("title", "") for t in recent_tasks)
            inet_ctx = "; ".join(m.get("content", "")[:80] for m in last_internet)
            recent_subjects = self._recent_autonomy_subjects(hours=24, limit=8)

            # Build user-pattern context for the prompt
            pattern_ctx_parts = []
            if user_patterns["recent_topics"]:
                pattern_ctx_parts.append(f"User recently talked about: {'; '.join(t[:60] for t in user_patterns['recent_topics'][:5])}")
            if user_patterns["categorized_asks"]:
                categories = set(cat for cat, _ in user_patterns["categorized_asks"])
                pattern_ctx_parts.append(f"User frequently asks about: {', '.join(categories)}")
            if user_patterns["interests"]:
                pattern_ctx_parts.append(f"User interests: {'; '.join(user_patterns['interests'][:4])}")
            pattern_ctx = "\n".join(pattern_ctx_parts) or "No clear patterns yet"

            prompt = f"""You are Ombra, a fully autonomous AI assistant. Your PRIMARY purpose is to help your user's daily life.
Based on context, define 2-3 concrete goals for the next hour. Prioritize PRACTICAL actions that directly help the user.

EXAMPLES of good daily-life goals:
- "Check user's emails and summarize anything urgent"
- "Monitor the deployment server health and fix any issues"
- "Research best deals on [item user mentioned wanting]"
- "Prepare a summary of tomorrow's tasks and deadlines"
- "Create an automation script for [recurring task user keeps doing manually]"
- "Check weather forecast and notify if it affects user's plans"

User behavior patterns:
{pattern_ctx}

Recent memories: {mem_ctx[:300] or 'None'}
Active tasks: {task_ctx[:200] or 'None'}
Recent internet learning: {inet_ctx[:300] or 'None'}
Your current goals: {'; '.join(self._current_goals) or 'None'}
Subjects to avoid repeating: {('; '.join(recent_subjects))[:300] or 'None'}

Respond with a JSON array of goal strings, like: ["goal 1", "goal 2", "goal 3"]
Be specific, actionable, and focused on things that CONCRETELY help the user's daily routine."""

            raw = await self._call_openai(prompt, max_tokens=300) or await self._call_ollama(prompt, max_tokens=200)
            if not raw:
                return []

            # Parse JSON array from response
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                goals = json.loads(match.group())
                goals = [str(g)[:200] for g in goals if g][:3]
            else:
                # Fallback: split by newline
                goals = [line.strip("•- ").strip() for line in raw.split("\n") if line.strip() and len(line.strip()) > 10][:3]

            goals = [goal for goal in goals if not self._is_subject_recent(goal, hours=24)]

            if goals:
                self._current_goals = goals
                # Store as a memory so they persist
                self.db["memories"].insert_one({
                    "type": "k1_goals",
                    "content": "K1 Goals: " + " | ".join(goals),
                    "source": "k1_self",
                    "utility_score": 0.9,
                    "access_count": 0,
                    "pinned": True,
                    "decay_rate": 0.01,
                    "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                return goals
        except Exception:
            pass
        return []

    async def _autonomous_action(self):
        """K1 decides and executes one autonomous action — prioritizes practical daily-life help."""
        try:
            # Build context for decision
            mem_ctx = list(self.db["memories"].find({"pinned": True}).limit(5))
            mem_text = "; ".join(m.get("content", "")[:100] for m in mem_ctx)
            goals_text = "; ".join(self._current_goals) if self._current_goals else "help user with daily tasks"
            active_tasks = list(self.db["tasks"].find({"status": "pending"}).limit(3))
            task_titles = "; ".join(t.get("title", "") for t in active_tasks)
            recent_subjects = self._recent_autonomy_subjects(hours=12, limit=8)
            user_patterns = self._get_user_patterns()

            # Build a daily-life context hint
            daily_hints = []
            ask_categories = set(cat for cat, _ in user_patterns.get("categorized_asks", []))
            if "email" in ask_categories:
                daily_hints.append("User frequently checks emails — consider checking and summarizing inbox")
            if "devops" in ask_categories:
                daily_hints.append("User manages servers — consider health-checking deployments")
            if "schedule" in ask_categories:
                daily_hints.append("User cares about schedules — consider checking upcoming deadlines or reminders")
            if "shopping" in ask_categories:
                daily_hints.append("User has shopping interests — consider price monitoring or deal research")
            daily_hint_text = "; ".join(daily_hints) or "Observe user patterns and find ways to help proactively"

            decision_prompt = f"""You are Ombra, an autonomous AI assistant. Your PRIMARY goal is to take actions that CONCRETELY help your user's daily life.

Your current goals: {goals_text}
Pinned memories: {mem_text[:300] or 'None'}
Pending tasks: {task_titles[:200] or 'None'}
Daily-life hints: {daily_hint_text}
Recently explored subjects to avoid repeating: {('; '.join(recent_subjects))[:300] or 'None'}

Decide ONE action to take right now. PRIORITIZE actions that directly benefit the user. Reply with JSON:
{{
  "action": "<research_topic | create_task | write_insight | analyze_memory | draft_report | use_tool | daily_check | proactive_assist | automate_routine>",
  "subject": "<what to do it about — be specific and practical>",
  "reason": "<why this helps the user's daily life>"
}}

NEW ACTION TYPES:
- daily_check: check something the user cares about (emails, server health, weather, news)
- proactive_assist: do something helpful before the user asks (prepare summaries, organize tasks, create reminders)
- automate_routine: create or run a script/automation for a task the user does repeatedly

Prefer daily_check, proactive_assist, automate_routine over generic research.
Do not repeat subjects from the recent list."""

            raw = await self._call_openai(decision_prompt, max_tokens=200) or await self._call_ollama(decision_prompt, max_tokens=150)
            if not raw:
                return None

            # Parse decision
            match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if not match:
                return None
            decision = json.loads(match.group())
            action = decision.get("action", "")
            subject = decision.get("subject", "")[:200]
            reason = decision.get("reason", "")[:200]
            if not action or not subject:
                return None
            if self._is_subject_recent(subject, hours=12):
                return {
                    "type": "skip_duplicate",
                    "description": f"skipped duplicate autonomous subject '{subject}'"
                }

            result_description = ""

            if action == "research_topic":
                # Research a topic and store as memory
                research = await self._call_openai(
                    f"Research and summarize in 3-5 sentences: {subject}",
                    system="You are an expert researcher. Be factual and concise.",
                    max_tokens=300
                ) or await self._call_ollama(f"Summarize in 3-5 sentences: {subject}", max_tokens=200)
                if research:
                    self.db["memories"].insert_one({
                        "type": "k1_research",
                        "content": f"[K1 Research: {subject}] {research}",
                        "source": "k1_autonomous",
                        "utility_score": 0.85,
                        "access_count": 0,
                        "pinned": False,
                        "decay_rate": 0.02,
                        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    result_description = f"researched '{subject}': {research[:150]}"

            elif action == "create_task":
                # Create a self-directed task
                existing = self.db["tasks"].find_one({"title": {"$regex": subject[:40], "$options": "i"}})
                if not existing:
                    self.db["tasks"].insert_one({
                        "title": subject[:150],
                        "description": f"[K1 autonomous task] {reason}",
                        "status": "planned",
                        "priority": "medium",
                        "source": "k1_autonomous",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
                    result_description = f"created task '{subject}'"

            elif action == "write_insight":
                # Generate an insight and store as memory
                insight = await self._call_openai(
                    f"Write a concise insight about: {subject}. Context: {reason}",
                    system="You are Ombra. Write sharp, useful insights.",
                    max_tokens=200
                ) or await self._call_ollama(f"Write an insight about: {subject}", max_tokens=150)
                if insight:
                    self.db["memories"].insert_one({
                        "type": "k1_insight",
                        "content": f"[K1 Insight] {insight}",
                        "source": "k1_autonomous",
                        "utility_score": 0.8,
                        "access_count": 0,
                        "pinned": False,
                        "decay_rate": 0.015,
                        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    result_description = f"wrote insight about '{subject}'"

            elif action == "analyze_memory":
                # Analyze existing memories and generate synthesis
                mems = list(self.db["memories"].find().sort("utility_score", -1).limit(10))
                mem_list = "\n".join(f"- {m.get('content','')[:120]}" for m in mems)
                synthesis = await self._call_openai(
                    f"Analyze these knowledge items and synthesize ONE key pattern or connection:\n{mem_list}",
                    system="You are Ombra analyzing your own memory. Find non-obvious patterns.",
                    max_tokens=250
                )
                if synthesis:
                    self.db["memories"].insert_one({
                        "type": "k1_synthesis",
                        "content": f"[K1 Memory Synthesis] {synthesis}",
                        "source": "k1_autonomous",
                        "utility_score": 0.9,
                        "access_count": 0,
                        "pinned": True,
                        "decay_rate": 0.005,
                        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    result_description = f"synthesized memory: {synthesis[:120]}"

            elif action == "draft_report":
                # Write a short autonomous status report
                report = await self._call_openai(
                    f"As Ombra, write a 3-sentence autonomous report about: {subject}. Be informative and direct.",
                    max_tokens=200
                )
                if report:
                    self.db["activity_log"].insert_one({
                        "type": "k1_autonomous_report",
                        "details": {"subject": subject, "report": report, "reason": reason},
                        "duration_ms": 0,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    result_description = f"drafted report on '{subject}'"

            elif action == "use_tool":
                tool_result = await self._run_autonomous_tool_action(subject, reason)
                if tool_result:
                    self.stats["tool_actions"] += 1
                    result_description = tool_result

            elif action == "daily_check":
                # Proactively check something the user cares about
                check_result = await self._run_daily_check(subject, reason)
                if check_result:
                    result_description = check_result

            elif action == "proactive_assist":
                # Do something helpful before the user asks
                assist_result = await self._run_proactive_assist(subject, reason)
                if assist_result:
                    result_description = assist_result

            elif action == "automate_routine":
                # Create or run an automation for a recurring user task
                auto_result = await self._run_automate_routine(subject, reason)
                if auto_result:
                    self.stats["tool_actions"] += 1
                    result_description = auto_result

            if result_description:
                return {"type": action, "description": result_description}
        except Exception:
            pass
        return None

    async def _run_daily_check(self, subject: str, reason: str) -> str | None:
        """Proactively check something the user cares about using tools."""
        try:
            # Use the sub-agent loop to perform a focused check
            system_prompt = (
                "You are Ombra performing a daily check for your user. "
                "Be concise and actionable. Only report if you find something noteworthy. "
                "Use tools to gather real data — do not fabricate information. "
                "If checking emails, use read_emails. If checking a server, use http_request or terminal. "
                "If checking weather or news, use web_search. Store key findings with memory_store."
            )
            task_message = (
                f"Daily check: {subject}\n"
                f"Reason: {reason}\n\n"
                f"Perform this check using real tools. Report findings concisely."
            )
            safe_tools = [
                t for t in TOOL_DEFINITIONS
                if t.get("function", {}).get("name") in AUTONOMOUS_SAFE_TOOLS
            ]
            session_id = f"k1_daily_{uuid.uuid4().hex[:8]}"
            loop_result = await run_agent_loop(
                message=task_message,
                system_prompt=system_prompt,
                model="gpt-4o-mini",
                session_id=session_id,
                db=self.db,
                tools_enabled=True,
                max_iterations=5,
                tools_override=safe_tools,
            )
            response = loop_result.get("response", "")
            tool_calls = loop_result.get("tool_calls", [])

            if response:
                # Store as a daily check result
                self.db["memories"].insert_one({
                    "type": "k1_daily_check",
                    "content": f"[Daily Check: {subject}] {response[:400]}",
                    "source": "k1_autonomous",
                    "utility_score": 0.85,
                    "access_count": 0,
                    "pinned": False,
                    "decay_rate": 0.05,  # decay faster — daily checks are time-sensitive
                    "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                # Daily check results stay in activity_log only — no Telegram push
                return f"daily check '{subject}' ({len(tool_calls)} tools): {response[:150]}"
        except Exception:
            pass
        return None

    async def _run_proactive_assist(self, subject: str, reason: str) -> str | None:
        """Do something helpful before the user asks — prepare summaries, organize tasks, create reminders."""
        try:
            system_prompt = (
                "You are Ombra proactively helping your user. "
                "Perform this task WITHOUT the user asking. "
                "Focus on being genuinely useful: organize information, prepare summaries, "
                "create task reminders, or compile relevant data the user will need soon. "
                "Use memory_store to save anything the user should know. "
                "Use create_task for actionable items."
            )
            task_message = (
                f"Proactive assist: {subject}\n"
                f"Why this helps: {reason}\n\n"
                f"Complete this proactively. Store useful outputs for the user."
            )
            safe_tools = [
                t for t in TOOL_DEFINITIONS
                if t.get("function", {}).get("name") in AUTONOMOUS_SAFE_TOOLS
            ]
            session_id = f"k1_assist_{uuid.uuid4().hex[:8]}"
            loop_result = await run_agent_loop(
                message=task_message,
                system_prompt=system_prompt,
                model="gpt-4o-mini",
                session_id=session_id,
                db=self.db,
                tools_enabled=True,
                max_iterations=5,
                tools_override=safe_tools,
            )
            response = loop_result.get("response", "")
            tool_calls = loop_result.get("tool_calls", [])

            if response:
                self.db["memories"].insert_one({
                    "type": "k1_proactive_assist",
                    "content": f"[Proactive: {subject}] {response[:400]}",
                    "source": "k1_autonomous",
                    "utility_score": 0.9,
                    "access_count": 0,
                    "pinned": False,
                    "decay_rate": 0.03,
                    "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                return f"proactive assist '{subject}': {response[:150]}"
        except Exception:
            pass
        return None

    async def _run_automate_routine(self, subject: str, reason: str) -> str | None:
        """Create or run a script/automation for a recurring user task."""
        try:
            system_prompt = (
                "You are Ombra automating a recurring task for your user. "
                "Write a Python script or use tools to automate this task. "
                "If writing a script, use write_file to save it, then python_exec to test it. "
                "The script should be self-contained and use environment variables for secrets. "
                "Available env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, EMERGENT_KEY, MONGODB_URI. "
                "After creating the automation, verify it works with a dry run. "
                "Store the automation details using memory_store so you can run it again later."
            )
            task_message = (
                f"Automate this routine: {subject}\n"
                f"Why: {reason}\n\n"
                f"Create a working automation. Test it. Store details in memory."
            )
            # For automations, allow write_file and python_exec too
            automation_tools = AUTONOMOUS_SAFE_TOOLS | {"write_file"}
            safe_tools = [
                t for t in TOOL_DEFINITIONS
                if t.get("function", {}).get("name") in automation_tools
            ]
            session_id = f"k1_auto_{uuid.uuid4().hex[:8]}"
            loop_result = await run_agent_loop(
                message=task_message,
                system_prompt=system_prompt,
                model="gpt-4o-mini",
                session_id=session_id,
                db=self.db,
                tools_enabled=True,
                max_iterations=8,
                tools_override=safe_tools,
            )
            response = loop_result.get("response", "")
            tool_calls = loop_result.get("tool_calls", [])

            if response:
                self.db["memories"].insert_one({
                    "type": "k1_automation",
                    "content": f"[Automation: {subject}] {response[:400]}",
                    "source": "k1_autonomous",
                    "utility_score": 0.95,
                    "access_count": 0,
                    "pinned": True,  # automations are high-value, keep them
                    "decay_rate": 0.005,
                    "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                # Automation results stay in activity_log only — no Telegram push
                return f"automated '{subject}' ({len(tool_calls)} tools): {response[:150]}"
        except Exception:
            pass
        return None

    async def _assess_importance(self, subject: str, content: str) -> bool:
        """Assess whether a daily check result is important enough to notify the user."""
        prompt = f"""You are deciding whether this daily check result is important enough to notify the user immediately.

Subject: {subject}
Content: {content[:500]}

Only say YES if it requires user attention (urgent email, server down, deadline approaching, significant price change, bad weather warning).
Do NOT notify for routine/normal results.

Respond only: YES or NO"""
        raw = await self._call_openai(prompt, max_tokens=10) or await self._call_ollama(prompt, max_tokens=10)
        if raw and "YES" in (raw or "").upper():
            return True
        return False

    async def _run_autonomous_tool_action(self, subject: str, reason: str):
        """Run autonomous tool workflow by delegating to specialized sub-agents."""
        try:
            if self._is_subject_recent(subject, hours=12):
                self.stats["loop_guard_skips"] += 1
                return f"skipped repeated tool subject '{subject}'"

            started = time.time()

            # ── 1. Pick the best sub-agent for the task ────────────────────
            agent = self._pick_subagent(subject, reason)
            agent_id = agent["agent_id"]
            agent_name = agent["name"]

            # ── 2. Create task record ──────────────────────────────────────
            plan = {"goal": subject, "agent": agent_id, "delegation": True}
            self.stats["plan_runs"] += 1
            task_id = self._create_autonomy_task(subject, reason, plan)

            self._log_observation("k1_subagent_delegated", {
                "task_id": task_id,
                "subject": subject,
                "reason": reason,
                "agent_id": agent_id,
                "agent_name": agent_name,
            }, phase="plan")

            self._update_task_phase(task_id, "execute", f"Delegated to sub-agent {agent_name}", status="in_progress")

            # ── 3. Build system prompt with autonomy context ───────────────
            goals_text = "; ".join(self._current_goals) if self._current_goals else "explore and learn"
            recent_subjects = self._recent_autonomy_subjects(hours=12, limit=6)

            system_prompt = (
                f"{agent['system_prompt']}\n\n"
                f"You are operating autonomously as part of Ombra's K1 daemon.\n"
                f"Current goals: {goals_text}\n"
                f"Avoid repeating these recent topics: {'; '.join(recent_subjects[:4]) or 'None'}\n"
                f"Be efficient — use the minimum tools needed. Store key findings in memory."
            )

            task_message = (
                f"Autonomous task: {subject}\n"
                f"Reason: {reason}\n\n"
                f"Complete this task using the available tools. "
                f"Store any valuable findings using memory_store. Be concise."
            )

            # ── 4. Filter tools to safe subset ─────────────────────────────
            safe_tools = [
                t for t in TOOL_DEFINITIONS
                if t.get("function", {}).get("name") in AUTONOMOUS_SAFE_TOOLS
            ]

            # ── 5. Run the sub-agent loop ──────────────────────────────────
            session_id = f"k1_{agent_id}_{uuid.uuid4().hex[:8]}"
            loop_result = await run_agent_loop(
                message=task_message,
                system_prompt=system_prompt,
                model="gpt-4o-mini",
                session_id=session_id,
                db=self.db,
                tools_enabled=True,
                max_iterations=8,
                tools_override=safe_tools,
            )

            response = loop_result.get("response", "")
            tool_calls = loop_result.get("tool_calls", [])
            iterations = loop_result.get("iterations", 0)
            duration_ms = loop_result.get("duration_ms", 0)

            # ── 6. Log tool calls from the sub-agent ───────────────────────
            for tc in tool_calls:
                self.db["activity_log"].insert_one({
                    "type": "k1_tool_action",
                    "details": {
                        "task_id": task_id,
                        "tool": tc.get("tool", ""),
                        "args": tc.get("args", {}),
                        "success": tc.get("success", False),
                        "subject": subject,
                        "reason": reason,
                        "preview": tc.get("result_preview", "")[:240],
                        "agent_id": agent_id,
                        "via": "subagent",
                    },
                    "duration_ms": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            # ── 7. Verify overall outcome ──────────────────────────────────
            verified, verify_note = await self._verify_subagent_outcome(subject, response, tool_calls)

            self._log_observation("k1_subagent_completed", {
                "task_id": task_id,
                "agent_id": agent_id,
                "iterations": iterations,
                "tool_calls_count": len(tool_calls),
                "verified": verified,
                "verify_note": verify_note,
                "response_preview": response[:300],
                "duration_ms": duration_ms,
            }, phase="verify")

            if not verified:
                self.stats["verify_failures"] += 1
                self._update_task_phase(
                    task_id, "failed",
                    f"Sub-agent {agent_name} verification failed: {verify_note}",
                    status="failed",
                    extra={"agent_id": agent_id, "tool_calls_count": len(tool_calls)}
                )
                return f"sub-agent {agent_name} failed verification for '{subject}'"

            # ── 8. Mark completed & store learning ─────────────────────────
            self._update_task_phase(
                task_id, "completed",
                f"Sub-agent {agent_name} completed in {iterations} iterations",
                status="completed",
                extra={
                    "agent_id": agent_id,
                    "iterations": iterations,
                    "tool_calls_count": len(tool_calls),
                    "duration_ms": duration_ms,
                }
            )

            if response:
                self.db["memories"].insert_one({
                    "type": "k1_tool_learn",
                    "content": f"[SubAgent/{agent_name}] {subject}: {response[:300]}",
                    "source": "k1_autonomous",
                    "utility_score": 0.8,
                    "access_count": 0,
                    "pinned": False,
                    "decay_rate": 0.02,
                    "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })

            return (
                f"sub-agent {agent_name} completed '{subject}' "
                f"({iterations} iters, {len(tool_calls)} tool calls)"
            )

        except Exception:
            return None

    def _pick_subagent(self, subject: str, reason: str) -> dict:
        """Select the best sub-agent for an autonomous task."""
        agent_id = classify_task_for_agent(f"{subject} {reason}")
        for agent in BUILTIN_AGENTS:
            if agent["agent_id"] == agent_id:
                return agent
        # Fallback: Executor (general-purpose)
        return next(a for a in BUILTIN_AGENTS if a["agent_id"] == "executor")

    async def _verify_subagent_outcome(self, goal: str, response: str, tool_calls: list) -> tuple:
        """Verify that a sub-agent accomplished its task."""
        if not response and not tool_calls:
            return False, "sub-agent produced no response and made no tool calls"

        tools_summary = ", ".join(
            f"{tc.get('tool')}({'ok' if tc.get('success') else 'fail'})"
            for tc in tool_calls[:6]
        ) or "no tools used"

        prompt = f"""You are verifying whether an autonomous sub-agent completed its task.

Goal: {goal}
Agent response: {response[:500]}
Tools used: {tools_summary}

Did the agent accomplish the goal? Respond only JSON: {{"ok": true/false, "note": "short reason"}}"""

        raw = await self._call_openai(prompt, max_tokens=120) or await self._call_ollama(prompt, max_tokens=90)
        if not raw:
            return True, "fallback accepted (no verifier response)"
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return True, "fallback accepted (unparseable verifier response)"
        try:
            verdict = json.loads(match.group())
            ok = bool(verdict.get("ok", True))
            note = (verdict.get("note") or "")[:200]
            return ok, note or ("verified" if ok else "not verified")
        except Exception:
            return True, "fallback accepted (verifier parse failed)"

    async def _self_improve_prompts(self):
        """Use OpenAI to generate improved prompt variants for low-performing prompts."""
        if not self.emergent_key:
            return None
        try:
            # Find lowest-performing active prompt
            prompts = list(self.db["k1_prompts"].find({"active": True}).sort("performance_score", 1).limit(1))
            if not prompts:
                # Try default prompts table
                from ombra_k1 import DEFAULT_PROMPTS
                prompts = [min(DEFAULT_PROMPTS, key=lambda p: p.get("performance_score", 0.7))]
                source = "default"
            else:
                source = "db"

            prompt_doc = prompts[0]
            current_prompt = prompt_doc.get("system_prompt", "")
            category = prompt_doc.get("category", "general")
            score = prompt_doc.get("performance_score", 0.7)

            if score >= 0.85:
                return None  # Good enough, skip

            improved = await self._call_openai(
                f"""This system prompt for category '{category}' has performance score {score:.2f}. Improve it.

Current prompt:
{current_prompt}

Write a BETTER version that is clearer, more directive, and will produce higher-quality responses.
Respond with only the improved system prompt — no labels, no explanation.""",
                system="You are a prompt engineer. Create improved system prompts.",
                max_tokens=300
            )

            if not improved or len(improved) < 30:
                return None

            # Insert as new variant
            new_id = f"{category}_v{int(datetime.now(timezone.utc).timestamp())}"
            self.db["k1_prompts"].insert_one({
                "prompt_id": new_id,
                "name": f"{category.title()} (K1 Improved)",
                "category": category,
                "system_prompt": improved,
                "performance_score": 0.72,  # Start slightly above baseline
                "usage_count": 0,
                "success_count": 0,
                "active": True,
                "source": "k1_self_improve",
                "parent_prompt_id": prompt_doc.get("prompt_id", ""),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return new_id
        except Exception:
            pass
        return None

    async def _notify_user(self, significant_actions: list):
        """Log autonomous actions and optionally notify user on Telegram."""
        summary = "\n".join(f"• {a}" for a in significant_actions)
        # Log to activity_log for dashboard visibility
        self.db["activity_log"].insert_one({
            "type": "k1_autonomous_report",
            "details": {
                "summary": summary,
                "actions": significant_actions,
                "tick": self.stats["ticks"]
            },
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Autonomous updates stay in activity_log only — no Telegram push

    async def _send_telegram(self, message: str):
        """Send a Telegram message if bot is configured."""
        try:
            settings = self.db["settings"].find_one({"user_id": "default"}) or {}
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = settings.get("telegram_chat_id", "")
            if not token or not chat_id:
                return
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": message[:4000], "parse_mode": "HTML"}
                )
            self.stats["telegram_sent"] += 1
        except Exception:
            pass

    def _is_morning_summary_due(self):
        """Return True once each day at/after configured morning hour (UTC)."""
        settings = self.db["settings"].find_one({"user_id": "default"}) or {}
        morning_hour = int(settings.get("morning_summary_hour_utc", 8))
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        already_sent = self.stats.get("last_morning_report_date") == today
        return now.hour >= morning_hour and not already_sent

    async def _send_morning_learning_summary(self):
        """Log a morning digest and optionally send it on Telegram."""
        try:
            now = datetime.now(timezone.utc)
            since = (now - timedelta(hours=24)).isoformat()
            settings = self.db["settings"].find_one({"user_id": "default"}) or {}
            learn_types = [
                "internet_knowledge", "k1_research", "k1_insight",
                "k1_synthesis", "creative_idea", "k1_tool_learn"
            ]
            recent = list(self.db["memories"].find({
                "type": {"$in": learn_types},
                "created_at": {"$gte": since}
            }).sort("created_at", -1).limit(12))

            lines = []
            for mem in recent[:8]:
                content = (mem.get("content", "") or "").replace("\n", " ").strip()
                if content:
                    lines.append(f"• {content[:180]}")

            self.db["activity_log"].insert_one({
                "type": "k1_morning_digest",
                "details": {"items": lines, "count": len(recent)},
                "duration_ms": 0,
                "timestamp": now.isoformat()
            })
            self.stats["morning_reports_sent"] += 1
            self.stats["last_morning_report_date"] = now.date().isoformat()

            # Morning digest stays in activity_log only — no Telegram push
            # User can check dashboard or /summary for learning status
            return True
        except Exception:
            return False

    async def _learn_from_internet(self):
        """Fetch fresh knowledge from public internet APIs and store as memories."""
        import httpx
        learned_items = []
        recent_subjects = self._recent_autonomy_subjects(hours=24, limit=12)

        # 1. Hacker News top stories titles (no API key needed)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                top_ids = (await c.get("https://hacker-news.firebaseio.com/v0/topstories.json")).json()
                for story_id in top_ids[:5]:
                    item = (await c.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")).json()
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if not title:
                        continue
                    # Check not already stored
                    exists = self.db["memories"].find_one({"content": {"$regex": title[:60], "$options": "i"}})
                    if exists:
                        continue
                    # Ask Ollama to summarize relevance
                    summary = await self._call_ollama(
                        f"In one sentence, what is this tech news about and why could it matter? Title: '{title}'",
                        max_tokens=80
                    )
                    content = f"[HN] {title}: {summary}" if summary else f"[HN] {title}"
                    self.db["memories"].insert_one({
                        "type": "internet_knowledge",
                        "source": "hacker_news",
                        "content": content[:400],
                        "url": url,
                        "utility_score": 0.6,
                        "access_count": 0,
                        "pinned": False,
                        "decay_rate": 0.03,
                        "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    learned_items.append(title[:60])
        except Exception:
            pass

        # 2. DuckDuckGo instant answer based on recent user topics
        try:
            recent_convos = list(self.db["conversations"].find().sort("updated_at", -1).limit(2))
            topics = []
            for conv in recent_convos:
                turns = [t for t in conv.get("turns", []) if t["role"] == "user"]
                if turns:
                    topic = turns[-1]["content"][:60]
                    if not self._is_subject_recent(topic, hours=24):
                        topics.append(topic)

            deduped_topics = []
            for topic in topics:
                normalized = self._normalize_subject(topic)
                if normalized and normalized not in deduped_topics and all(normalized not in item for item in recent_subjects):
                    deduped_topics.append(normalized)

            for topic in deduped_topics[:2]:
                async with httpx.AsyncClient(timeout=8) as c:
                    resp = await c.get(
                        "https://api.duckduckgo.com/",
                        params={"q": topic, "format": "json", "no_html": "1", "skip_disambig": "1"}
                    )
                    data = resp.json()
                    abstract = data.get("AbstractText", "")
                    if abstract and len(abstract) > 50:
                        exists = self.db["memories"].find_one({"content": {"$regex": abstract[:60], "$options": "i"}})
                        if not exists:
                            self.db["memories"].insert_one({
                                "type": "internet_knowledge",
                                "source": "duckduckgo",
                                "content": f"[DDG on '{topic}']: {abstract[:400]}",
                                "utility_score": 0.7,
                                "access_count": 0,
                                "pinned": False,
                                "decay_rate": 0.02,
                                "last_accessed_at": datetime.now(timezone.utc).isoformat(),
                                "created_at": datetime.now(timezone.utc).isoformat()
                            })
                            learned_items.append(f"ddg:{topic[:40]}")
        except Exception:
            pass

        if learned_items:
            self.db["activity_log"].insert_one({
                "type": "internet_learning",
                "details": {"items": learned_items},
                "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return f"{len(learned_items)} items"
        return None

    async def _advance_tasks(self):
        """Pick a stalled pending task and ask Ollama for next steps."""
        try:
            task = self.db["tasks"].find_one(
                {"status": {"$in": ["pending", "planned"]}},
                sort=[("created_at", 1)]
            )
            if not task:
                return None
            title = task.get("title", "")
            description = task.get("description", "")
            next_step = await self._call_ollama(
                f"Task: {title}. {description}\n\nWhat is ONE concrete next action step to move this forward?",
                system="You are a productivity assistant. Be brief and actionable.",
                max_tokens=100
            )
            if next_step:
                self.db["tasks"].update_one(
                    {"_id": task["_id"]},
                    {"$set": {
                        "status": "in_progress",
                        "next_step": next_step,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                     },
                     "$push": {"notes": {"text": f"[daemon] {next_step}", "at": datetime.now(timezone.utc).isoformat()}}}
                )
                return title[:60]
        except Exception:
            pass
        return None

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
            idea = await self._call_ollama(idea_prompt, max_tokens=150)
            if idea:
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
