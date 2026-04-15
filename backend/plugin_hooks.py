"""
Ombra Plugin Hooks System
=========================
Pre/post hooks on tool execution for logging, approval gates,
input/output transformation, and custom side-effects.
"""

import asyncio
import time
import uuid
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class HookPhase(str, Enum):
    PRE = "pre"      # Before tool execution
    POST = "post"    # After tool execution


class HookAction(str, Enum):
    CONTINUE = "continue"   # Proceed normally
    MODIFY = "modify"       # Modify args/result and continue
    BLOCK = "block"         # Block the tool call
    SKIP = "skip"           # Skip this hook, run next


@dataclass
class HookResult:
    """Result of a hook execution."""
    action: HookAction = HookAction.CONTINUE
    modified_args: dict | None = None       # For pre hooks: modified input args
    modified_result: dict | None = None     # For post hooks: modified result
    message: str = ""                       # Optional message for logging
    metadata: dict = field(default_factory=dict)


@dataclass
class Hook:
    """A registered hook."""
    id: str
    name: str
    phase: HookPhase
    tool_pattern: str = "*"          # Tool name pattern (* = all tools)
    priority: int = 100              # Lower = runs first
    enabled: bool = True
    handler: Callable = None         # async fn(tool_name, args_or_result, context) -> HookResult
    description: str = ""
    created_at: str = ""


class HookManager:
    """
    Central hook registry and execution engine.
    Hooks are executed in priority order for each phase.
    """

    def __init__(self):
        self._hooks: dict[str, Hook] = {}
        self._execution_log: list[dict] = []
        self._max_log_size = 1000

    def register(self, name: str, phase: HookPhase, handler: Callable, *,
                 tool_pattern: str = "*", priority: int = 100,
                 description: str = "") -> str:
        """Register a new hook. Returns the hook ID."""
        hook_id = f"hook_{uuid.uuid4().hex[:8]}"
        self._hooks[hook_id] = Hook(
            id=hook_id,
            name=name,
            phase=phase,
            tool_pattern=tool_pattern,
            priority=priority,
            handler=handler,
            description=description,
            enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return hook_id

    def unregister(self, hook_id: str) -> bool:
        """Remove a hook by ID."""
        return self._hooks.pop(hook_id, None) is not None

    def enable(self, hook_id: str) -> bool:
        hook = self._hooks.get(hook_id)
        if hook:
            hook.enabled = True
            return True
        return False

    def disable(self, hook_id: str) -> bool:
        hook = self._hooks.get(hook_id)
        if hook:
            hook.enabled = False
            return True
        return False

    def _matches_tool(self, pattern: str, tool_name: str) -> bool:
        """Check if a tool name matches a hook's tool pattern."""
        if pattern == "*":
            return True
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(tool_name, pattern)
        return pattern == tool_name

    def _get_matching_hooks(self, phase: HookPhase, tool_name: str) -> list[Hook]:
        """Get all enabled hooks matching a phase and tool name, sorted by priority."""
        matching = [
            h for h in self._hooks.values()
            if h.enabled and h.phase == phase and self._matches_tool(h.tool_pattern, tool_name)
        ]
        matching.sort(key=lambda h: h.priority)
        return matching

    async def run_pre_hooks(self, tool_name: str, args: dict,
                            context: dict = None) -> tuple[HookAction, dict]:
        """
        Run all pre-execution hooks for a tool call.
        Returns (action, possibly_modified_args).
        If any hook blocks, returns (BLOCK, original_args).
        """
        hooks = self._get_matching_hooks(HookPhase.PRE, tool_name)
        current_args = dict(args)

        for hook in hooks:
            start = time.time()
            try:
                result = await hook.handler(tool_name, current_args, context or {})
                duration_ms = int((time.time() - start) * 1000)

                self._log_execution(hook, "pre", tool_name, duration_ms, result)

                if result.action == HookAction.BLOCK:
                    return (HookAction.BLOCK, current_args)
                elif result.action == HookAction.MODIFY and result.modified_args:
                    current_args = result.modified_args
                elif result.action == HookAction.SKIP:
                    continue

            except Exception as e:
                self._log_execution(hook, "pre", tool_name, 0, None, error=str(e))

        return (HookAction.CONTINUE, current_args)

    async def run_post_hooks(self, tool_name: str, args: dict, result: dict,
                             context: dict = None) -> dict:
        """
        Run all post-execution hooks for a tool call.
        Returns the (possibly modified) result.
        """
        hooks = self._get_matching_hooks(HookPhase.POST, tool_name)
        current_result = dict(result)

        for hook in hooks:
            start = time.time()
            try:
                hook_result = await hook.handler(
                    tool_name,
                    {"args": args, "result": current_result},
                    context or {}
                )
                duration_ms = int((time.time() - start) * 1000)

                self._log_execution(hook, "post", tool_name, duration_ms, hook_result)

                if hook_result.action == HookAction.MODIFY and hook_result.modified_result:
                    current_result = hook_result.modified_result

            except Exception as e:
                self._log_execution(hook, "post", tool_name, 0, None, error=str(e))

        return current_result

    def _log_execution(self, hook: Hook, phase: str, tool_name: str,
                       duration_ms: int, result: HookResult | None,
                       error: str = ""):
        """Log a hook execution for auditing."""
        entry = {
            "hook_id": hook.id,
            "hook_name": hook.name,
            "phase": phase,
            "tool": tool_name,
            "action": result.action if result else "error",
            "message": result.message if result else error,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._execution_log.append(entry)
        if len(self._execution_log) > self._max_log_size:
            self._execution_log = self._execution_log[-self._max_log_size:]

    def list_hooks(self) -> list[dict]:
        """List all registered hooks."""
        return [
            {
                "id": h.id,
                "name": h.name,
                "phase": h.phase,
                "tool_pattern": h.tool_pattern,
                "priority": h.priority,
                "enabled": h.enabled,
                "description": h.description,
                "created_at": h.created_at,
            }
            for h in sorted(self._hooks.values(), key=lambda h: (h.phase, h.priority))
        ]

    def get_execution_log(self, limit: int = 50) -> list[dict]:
        """Get recent hook execution log entries."""
        return self._execution_log[-limit:]

    def get_stats(self) -> dict:
        return {
            "total_hooks": len(self._hooks),
            "enabled": sum(1 for h in self._hooks.values() if h.enabled),
            "pre_hooks": sum(1 for h in self._hooks.values() if h.phase == HookPhase.PRE),
            "post_hooks": sum(1 for h in self._hooks.values() if h.phase == HookPhase.POST),
            "total_executions": len(self._execution_log),
        }


# ── Built-in Hooks ────────────────────────────────────────────────────────────

async def audit_log_hook(tool_name: str, data: Any, context: dict) -> HookResult:
    """Built-in hook: logs all tool executions for auditing."""
    return HookResult(
        action=HookAction.CONTINUE,
        message=f"Tool '{tool_name}' executed",
        metadata={"tool": tool_name, "timestamp": datetime.now(timezone.utc).isoformat()},
    )


async def sensitive_data_hook(tool_name: str, args: dict, context: dict) -> HookResult:
    """Built-in pre-hook: redacts sensitive data from tool arguments."""
    import re
    sensitive_patterns = [
        (r'(?i)(password|secret|token|api_key)\s*[=:]\s*\S+', r'\1=***REDACTED***'),
        (r'(?i)Bearer\s+\S+', 'Bearer ***REDACTED***'),
    ]

    modified = False
    new_args = dict(args)

    for key, val in new_args.items():
        if isinstance(val, str):
            for pattern, replacement in sensitive_patterns:
                new_val = re.sub(pattern, replacement, val)
                if new_val != val:
                    new_args[key] = new_val
                    modified = True
                    val = new_val

    if modified:
        return HookResult(action=HookAction.MODIFY, modified_args=new_args,
                          message="Sensitive data redacted")
    return HookResult(action=HookAction.CONTINUE)


async def rate_limit_hook(tool_name: str, args: dict, context: dict) -> HookResult:
    """Built-in pre-hook: rate limits tool calls (max 30 per minute)."""
    now = time.time()
    _rate_limit_window = context.get("_rate_limit_calls", [])
    _rate_limit_window = [t for t in _rate_limit_window if now - t < 60]
    if len(_rate_limit_window) >= 30:
        return HookResult(
            action=HookAction.BLOCK,
            message=f"Rate limit exceeded: {len(_rate_limit_window)} calls in the last minute"
        )
    _rate_limit_window.append(now)
    context["_rate_limit_calls"] = _rate_limit_window
    return HookResult(action=HookAction.CONTINUE)


# ── Global instance ───────────────────────────────────────────────────────────
hook_manager = HookManager()


def register_default_hooks():
    """Register the built-in hooks. Called at startup."""
    hook_manager.register(
        name="audit_log",
        phase=HookPhase.POST,
        handler=audit_log_hook,
        tool_pattern="*",
        priority=999,  # Runs last
        description="Logs all tool executions"
    )
    hook_manager.register(
        name="sensitive_data_redaction",
        phase=HookPhase.PRE,
        handler=sensitive_data_hook,
        tool_pattern="*",
        priority=10,  # Runs early
        description="Redacts passwords, tokens, and API keys from tool args"
    )
