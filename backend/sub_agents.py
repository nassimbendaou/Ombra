"""
Ombra Sub-Agent System
======================
Spawns parallel sub-agents that work on independent sub-tasks
concurrently and report results back to the orchestrator.
"""

import os
import json
import asyncio
import time
import uuid
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from openai import AsyncOpenAI


@dataclass
class SubTask:
    """A sub-task assigned to a sub-agent."""
    id: str
    description: str
    status: str = "pending"     # pending, running, completed, failed
    result: str = ""
    tool_calls: list = field(default_factory=list)
    agent_type: str = "general"
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    error: str = ""


@dataclass
class SubAgentPlan:
    """A plan decomposed into parallel sub-tasks."""
    id: str
    original_task: str
    subtasks: list[SubTask] = field(default_factory=list)
    status: str = "planning"     # planning, running, completed, failed
    final_synthesis: str = ""
    created_at: str = ""
    completed_at: str = ""


class SubAgentOrchestrator:
    """
    Decomposes complex tasks into parallel sub-tasks, spawns independent
    agent loops for each, then synthesizes results.
    """

    def __init__(self, max_concurrent: int = 4, max_iterations_per_sub: int = 6):
        self.max_concurrent = max_concurrent
        self.max_iterations_per_sub = max_iterations_per_sub
        self._active_plans: dict[str, SubAgentPlan] = {}

    async def decompose_task(self, task: str, model: str = "gpt-4o") -> list[dict]:
        """
        Use the LLM to decompose a complex task into independent sub-tasks.
        Returns a list of sub-task descriptions.
        """
        client = self._get_client()
        if not client:
            return [{"description": task, "agent_type": "general"}]

        decompose_prompt = """You are a task decomposition expert. Break the following task into 2-5 independent sub-tasks that can be executed in parallel. Each sub-task should be:
1. Self-contained (doesn't depend on other sub-tasks' results)
2. Clearly scoped
3. Actionable

Return a JSON array of objects with "description" and "agent_type" fields.
Agent types: "coder" (code tasks), "researcher" (web lookup), "analyst" (data analysis), "general" (everything else).

If the task is simple and doesn't need decomposition, return a single-element array.

Task: """ + task

        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": decompose_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            subtasks = data if isinstance(data, list) else data.get("subtasks", data.get("tasks", [data]))
            if not subtasks:
                subtasks = [{"description": task, "agent_type": "general"}]
            return subtasks[:5]  # Cap at 5
        except Exception:
            return [{"description": task, "agent_type": "general"}]

    async def execute_plan(self, task: str, *,
                           system_prompt: str = "",
                           model: str = "gpt-4o",
                           session_id: str = "",
                           db=None,
                           tools_enabled: bool = True,
                           on_subtask_complete=None) -> SubAgentPlan:
        """
        Decompose a task, run sub-agents in parallel, synthesize results.

        on_subtask_complete: async callback(subtask) called when each finishes.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        plan = SubAgentPlan(
            id=plan_id,
            original_task=task,
            status="planning",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._active_plans[plan_id] = plan

        # Decompose
        subtask_specs = await self.decompose_task(task, model)
        for i, spec in enumerate(subtask_specs):
            plan.subtasks.append(SubTask(
                id=f"{plan_id}_sub{i}",
                description=spec.get("description", task),
                agent_type=spec.get("agent_type", "general"),
            ))

        # Run sub-agents in parallel (bounded concurrency)
        plan.status = "running"
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_subtask(subtask: SubTask):
            async with semaphore:
                subtask.status = "running"
                subtask.started_at = datetime.now(timezone.utc).isoformat()
                start = time.time()

                try:
                    result = await self._run_sub_agent(
                        task=subtask.description,
                        agent_type=subtask.agent_type,
                        system_prompt=system_prompt,
                        model=model,
                        session_id=f"{session_id}_{subtask.id}",
                        db=db,
                        tools_enabled=tools_enabled,
                    )
                    subtask.status = "completed"
                    subtask.result = result.get("response", "")
                    subtask.tool_calls = result.get("tool_calls", [])
                except Exception as e:
                    subtask.status = "failed"
                    subtask.error = str(e)

                subtask.duration_ms = int((time.time() - start) * 1000)
                subtask.completed_at = datetime.now(timezone.utc).isoformat()

                if on_subtask_complete:
                    await on_subtask_complete(subtask)

        await asyncio.gather(*(run_subtask(st) for st in plan.subtasks))

        # Synthesize results
        plan.final_synthesis = await self._synthesize_results(plan, model)
        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc).isoformat()

        return plan

    async def _run_sub_agent(self, task: str, agent_type: str,
                             system_prompt: str, model: str,
                             session_id: str, db, tools_enabled: bool) -> dict:
        """Run a single sub-agent with the agent loop."""
        try:
            from agent_loop import run_agent_loop
        except ImportError:
            return {"response": f"Agent loop not available. Task: {task}", "tool_calls": []}

        # Customize system prompt based on agent type
        type_prompts = {
            "coder": "\nYou are a focused coding agent. Write clean, working code. Test it before considering the task done.",
            "researcher": "\nYou are a research agent. Search the web, gather facts, and synthesize findings. Cite sources.",
            "analyst": "\nYou are a data analysis agent. Use python_exec for calculations. Present findings clearly.",
            "general": "\nYou are a versatile agent. Use the appropriate tools to complete the task efficiently.",
        }
        sub_prompt = system_prompt + type_prompts.get(agent_type, type_prompts["general"])
        sub_prompt += f"\n\nYour specific task: {task}\nComplete this task independently. Be thorough but concise."

        return await run_agent_loop(
            message=task,
            system_prompt=sub_prompt,
            model=model,
            session_id=session_id,
            db=db,
            tools_enabled=tools_enabled,
            max_iterations=self.max_iterations_per_sub,
        )

    async def _synthesize_results(self, plan: SubAgentPlan, model: str) -> str:
        """Use the LLM to synthesize results from all sub-agents."""
        client = self._get_client()
        if not client:
            # Simple concatenation fallback
            parts = []
            for st in plan.subtasks:
                parts.append(f"## {st.description}\n{st.result}" if st.status == "completed"
                             else f"## {st.description}\n[FAILED: {st.error}]")
            return "\n\n".join(parts)

        sub_results = []
        for st in plan.subtasks:
            if st.status == "completed":
                sub_results.append(f"Sub-task: {st.description}\nResult: {st.result}")
            else:
                sub_results.append(f"Sub-task: {st.description}\nStatus: FAILED - {st.error}")

        synthesis_prompt = f"""You were asked to complete this task: {plan.original_task}

It was broken into sub-tasks. Here are the results:

{chr(10).join(sub_results)}

Synthesize these results into a single coherent response for the user. Be concise but complete."""

        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": synthesis_prompt}],
                temperature=0.5,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"Synthesis failed: {e}\n\n" + "\n\n".join(
                f"**{st.description}**: {st.result}" for st in plan.subtasks if st.status == "completed"
            )

    def _get_client(self) -> Optional[AsyncOpenAI]:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY") or ""
        return AsyncOpenAI(api_key=api_key) if api_key else None

    def get_plan_status(self, plan_id: str) -> dict | None:
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None
        return {
            "id": plan.id,
            "task": plan.original_task,
            "status": plan.status,
            "subtasks": [
                {
                    "id": st.id,
                    "description": st.description,
                    "status": st.status,
                    "agent_type": st.agent_type,
                    "duration_ms": st.duration_ms,
                    "result_preview": st.result[:200] if st.result else "",
                    "error": st.error,
                }
                for st in plan.subtasks
            ],
            "final_synthesis": plan.final_synthesis[:500] if plan.final_synthesis else "",
            "created_at": plan.created_at,
            "completed_at": plan.completed_at,
        }

    def list_plans(self) -> list[dict]:
        return [self.get_plan_status(pid) for pid in self._active_plans]


# ── Global instance ───────────────────────────────────────────────────────────
sub_agent_orchestrator = SubAgentOrchestrator()
