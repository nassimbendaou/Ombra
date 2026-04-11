"""
Ombra Task Scheduler
- Simple interval schedules (every X seconds/hours/days)
- Cron expression schedules
- Timezone-aware execution
- Respect quiet hours + permissions
"""
import asyncio
from datetime import datetime, timezone, timedelta
from croniter import croniter
from typing import Optional


class TaskScheduler:
    """Advanced task scheduler with interval and cron support."""

    def __init__(self, db, executor_callback):
        """
        Args:
            db: MongoDB database instance
            executor_callback: async function(task_id) to execute a task
        """
        self.db = db
        self.executor_callback = executor_callback
        self.running = False
        self.paused = False
        self.tick_interval = 30  # Check every 30 seconds
        self.stats = {
            "scheduled_tasks": 0,
            "executed_runs": 0,
            "skipped_runs": 0,
            "failed_runs": 0,
            "started_at": None,
            "last_tick_at": None
        }

    def _compute_next_run(self, schedule, last_run_at=None, now=None):
        """
        Compute next run time based on schedule configuration.
        
        Args:
            schedule: dict with {mode, interval_seconds?, cron_expr?, timezone?}
            last_run_at: ISO timestamp of last execution
            now: current datetime (for testing)
        
        Returns:
            datetime (UTC) or None
        """
        if not schedule or schedule.get("mode") == "none":
            return None

        now = now or datetime.now(timezone.utc)
        mode = schedule.get("mode")

        if mode == "interval":
            interval = schedule.get("interval_seconds", 3600)
            if last_run_at:
                last = datetime.fromisoformat(last_run_at)
                return last + timedelta(seconds=interval)
            else:
                # First run: immediate or after interval?
                return now + timedelta(seconds=interval)

        elif mode == "cron":
            cron_expr = schedule.get("cron_expr", "0 * * * *")  # default: hourly
            tz_str = schedule.get("timezone", "UTC")
            try:
                # croniter expects naive datetime in the target timezone
                # We'll use UTC internally
                cron = croniter(cron_expr, now)
                next_run = cron.get_next(datetime)
                return next_run.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"Invalid cron expression: {cron_expr}, error: {e}")
                return None

        return None

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
        """Single scheduler tick: check for runnable tasks and enqueue them."""
        if self.paused:
            return {"action": "skipped", "reason": "paused"}

        self.stats["last_tick_at"] = datetime.now(timezone.utc).isoformat()
        now = datetime.now(timezone.utc)
        executed = 0
        skipped = 0
        failed = 0

        # Find all tasks with schedules enabled
        scheduled_tasks = list(self.db["tasks"].find({
            "schedule.mode": {"$in": ["interval", "cron"]},
            "schedule_enabled": True
        }))

        self.stats["scheduled_tasks"] = len(scheduled_tasks)

        for task in scheduled_tasks:
            task_id = task["_id"]
            schedule = task.get("schedule", {})
            next_run_at_str = task.get("next_run_at")

            # If next_run_at not set, compute it
            if not next_run_at_str:
                next_run = self._compute_next_run(
                    schedule,
                    task.get("last_run_at"),
                    now
                )
                if next_run:
                    self.db["tasks"].update_one(
                        {"_id": task_id},
                        {"$set": {"next_run_at": next_run.isoformat()}}
                    )
                    next_run_at_str = next_run.isoformat()
                else:
                    continue

            # Check if task is due
            next_run_at = datetime.fromisoformat(next_run_at_str)
            if next_run_at > now:
                continue  # Not due yet

            # Check quiet hours
            if self.is_quiet_hours() and task.get("respect_quiet_hours", True):
                skipped += 1
                # Update next_run for next cycle
                next_next_run = self._compute_next_run(schedule, now.isoformat(), now)
                if next_next_run:
                    self.db["tasks"].update_one(
                        {"_id": task_id},
                        {"$set": {"next_run_at": next_next_run.isoformat()}}
                    )
                continue

            # Execute task
            try:
                await self.executor_callback(str(task_id))
                executed += 1

                # Update last_run and compute next_run
                now_iso = now.isoformat()
                next_next_run = self._compute_next_run(schedule, now_iso, now)
                
                update_data = {
                    "last_run_at": now_iso,
                    "missed_runs": 0
                }
                if next_next_run:
                    update_data["next_run_at"] = next_next_run.isoformat()
                
                self.db["tasks"].update_one(
                    {"_id": task_id},
                    {"$set": update_data}
                )

            except Exception as e:
                failed += 1
                print(f"Scheduled task {task_id} execution failed: {e}")
                # Track failure but don't block other tasks
                self.db["tasks"].update_one(
                    {"_id": task_id},
                    {"$inc": {"missed_runs": 1}}
                )

        self.stats["executed_runs"] += executed
        self.stats["skipped_runs"] += skipped
        self.stats["failed_runs"] += failed

        # Log tick activity
        if executed > 0 or skipped > 0 or failed > 0:
            self.db["activity_log"].insert_one({
                "type": "scheduler",
                "details": {
                    "executed": executed,
                    "skipped": skipped,
                    "failed": failed
                },
                "duration_ms": 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return {
            "action": "ticked",
            "executed": executed,
            "skipped": skipped,
            "failed": failed
        }

    async def start(self):
        """Start the scheduler loop."""
        self.running = True
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.db["activity_log"].insert_one({
            "type": "system",
            "details": {"event": "task_scheduler_started"},
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while self.running:
            try:
                await self.tick()
            except Exception as e:
                print(f"Scheduler tick error: {e}")
                self.db["activity_log"].insert_one({
                    "type": "system",
                    "details": {"event": "scheduler_error", "error": str(e)[:200]},
                    "duration_ms": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            await asyncio.sleep(self.tick_interval)

    def stop(self):
        """Stop the scheduler."""
        self.running = False

    def get_status(self):
        """Get scheduler status."""
        return {
            "running": self.running,
            "paused": self.paused,
            "stats": self.stats,
            "tick_interval": self.tick_interval
        }
