"""
Ombra Agent Loop
================
Agentic multi-step loop using OpenAI function calling.
The model is given tools and can call them repeatedly until it
returns a final text answer (finish_reason == "stop").

Entry points:
  run_agent_loop()     - Returns final result dict
  stream_agent_loop()  - Async generator, yields SSE-compatible events

Usage:
  from agent_loop import run_agent_loop, stream_agent_loop

  result = await run_agent_loop(
      message="Build a hello world Flask app",
      system_prompt=SOUL,
      model="gpt-4o",
      session_id="abc123",
      db=db,
      tools_enabled=True
  )
  print(result["response"])
  print(result["tool_calls"])
"""

import os, json, time, asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from agent_tools import TOOL_DEFINITIONS, execute_tool
from mcp_client import mcp_manager

def _get_openai_client():
    """Create the OpenAI client from the same env vars used elsewhere in the backend."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY") or ""
    return AsyncOpenAI(api_key=api_key) if api_key else None


def _get_anthropic_key():
    """Get Anthropic API key if available."""
    return os.environ.get("ANTHROPIC_API_KEY") or ""


# ── Model fallback chain ─────────────────────────────────────────────────────
FALLBACK_CHAINS = {
    "claude-sonnet-4-5-20250929": ["gpt-4o", "gpt-4o-mini"],
    "gpt-4o": ["gpt-4o-mini", "claude-sonnet-4-5-20250929"],
    "gpt-4o-mini": ["gpt-4o", "claude-sonnet-4-5-20250929"],
}


def _assistant_message_to_dict(message):
    """Convert an OpenAI SDK assistant message into a plain dict for replay in later turns."""
    tool_calls = []
    for tool_call in message.tool_calls or []:
        tool_calls.append({
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
        })
    payload = {
        "role": "assistant",
        "content": message.content,
    }
    if tool_calls:
        payload["tool_calls"] = tool_calls
    return payload

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_ITERATIONS = 12

# ── Helper: call Anthropic (Claude) with tool support ─────────────────────────
async def _call_anthropic(messages: list, model: str, tools: list, stream: bool = False):
    """Call Anthropic API with tool support, returns an OpenAI-compatible response object."""
    import httpx
    api_key = _get_anthropic_key()
    if not api_key:
        raise RuntimeError("Anthropic API key not configured")

    # Convert OpenAI message format to Anthropic
    system_msg = ""
    anthropic_msgs = []
    for m in messages:
        if m["role"] == "system":
            system_msg += (m.get("content") or "") + "\n"
        elif m["role"] == "user":
            anthropic_msgs.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            content_parts = []
            if m.get("content"):
                content_parts.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls", []):
                content_parts.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                })
            anthropic_msgs.append({"role": "assistant", "content": content_parts or m.get("content", "")})
        elif m["role"] == "tool":
            anthropic_msgs.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                }]
            })

    # Merge consecutive same-role messages (Anthropic requires alternating)
    merged = []
    for msg in anthropic_msgs:
        if merged and merged[-1]["role"] == msg["role"]:
            prev_content = merged[-1]["content"]
            curr_content = msg["content"]
            if isinstance(prev_content, str):
                prev_content = [{"type": "text", "text": prev_content}]
            if isinstance(curr_content, str):
                curr_content = [{"type": "text", "text": curr_content}]
            merged[-1]["content"] = prev_content + curr_content
        else:
            merged.append(msg)
    anthropic_msgs = merged

    # Convert OpenAI tool definitions to Anthropic format
    anthropic_tools = []
    for t in tools:
        fn = t.get("function", {})
        anthropic_tools.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })

    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system_msg.strip(),
        "messages": anthropic_msgs,
    }
    if anthropic_tools:
        payload["tools"] = anthropic_tools

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Anthropic error: {data['error'].get('message', str(data['error']))}")

    # Convert Anthropic response to OpenAI-compatible format
    return _anthropic_to_openai_response(data)


class _FakeChoice:
    def __init__(self, finish_reason, message):
        self.finish_reason = finish_reason
        self.message = message

class _FakeMessage:
    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls

class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFunction(name, arguments)

class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

class _FakeResponse:
    def __init__(self, choices):
        self.choices = choices


def _anthropic_to_openai_response(data: dict):
    """Convert Anthropic API response to OpenAI-like response object."""
    content_text = ""
    tool_calls = []

    for block in data.get("content", []):
        if block["type"] == "text":
            content_text += block["text"]
        elif block["type"] == "tool_use":
            tool_calls.append(_FakeToolCall(
                id=block["id"],
                name=block["name"],
                arguments=json.dumps(block["input"]),
            ))

    stop_reason = data.get("stop_reason", "end_turn")
    if stop_reason == "tool_use":
        finish_reason = "tool_calls"
    else:
        finish_reason = "stop"

    message = _FakeMessage(
        content=content_text or None,
        tool_calls=tool_calls if tool_calls else None,
    )
    return _FakeResponse(choices=[_FakeChoice(finish_reason=finish_reason, message=message)])


# ── Helper: call LLM with automatic model fallback ───────────────────────────
def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate limit (429) error."""
    err_str = str(e).lower()
    return "429" in err_str or "rate limit" in err_str or "rate_limit" in err_str


async def _call_llm(messages: list, model: str, tools: list, stream: bool = False):
    """Call LLM with automatic fallback on rate limits."""
    models_to_try = [model] + FALLBACK_CHAINS.get(model, [])
    last_error = None

    for m in models_to_try:
        try:
            if m.startswith("claude"):
                if not _get_anthropic_key():
                    continue
                # Claude uses non-streaming internally; caller handles simulation
                return await _call_anthropic(messages, m, tools, stream=False), m
            else:
                result = await _call_openai(messages, m, tools, stream=stream)
                return result, m
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                # Wait briefly then try next model
                await asyncio.sleep(2)
                continue
            else:
                raise

    raise last_error or RuntimeError("All models failed")


# ── Helper: call OpenAI ───────────────────────────────────────────────────────
async def _call_openai(messages: list, model: str, tools: list, stream: bool = False):
    client = _get_openai_client()
    if not client:
        raise RuntimeError("OpenAI API key not configured")
    kwargs = {
        "model": model,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if stream:
        kwargs["stream"] = True
    return await client.chat.completions.create(**kwargs)


async def _execute_tool_with_retry(tool_name: str, tool_args: dict, db=None, retries: int = 2) -> dict:
    """Retry transient tool failures to improve robustness."""
    last_result = {"success": False, "output": "tool execution did not start"}
    for attempt in range(1, retries + 1):
        result = await execute_tool(tool_name, tool_args, db)
        if result.get("success", False):
            if attempt > 1:
                result["recovered_after_attempts"] = attempt
            return result
        last_result = result
        text = (result.get("output", "") or "").lower()
        transient = any(x in text for x in ["timeout", "temporar", "connection", "rate", "busy", "502", "503"])
        if attempt < retries and transient:
            await asyncio.sleep(min(2 ** (attempt - 1), 3))
            continue
        break
    return last_result


# ── Main agentic loop ─────────────────────────────────────────────────────────
async def run_agent_loop(
    message: str,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    session_id: str = "",
    db=None,
    tools_enabled: bool = True,
    max_iterations: int = MAX_ITERATIONS,
    extra_context: list = None,
    tools_override: list = None
) -> dict:
    """
    Run the full agentic loop.
    Returns:
        {
          "response": str,            - Final text answer
          "tool_calls": [list],       - All tool calls made with args + output
          "iterations": int,          - How many loops ran
          "model": str,
          "session_id": str,
          "duration_ms": int
        }
    If tools_override is provided, use those tool definitions instead of the defaults.
    """
    start = time.time()
    tools = tools_override if tools_override is not None else (TOOL_DEFINITIONS if tools_enabled else [])
    # Merge connected MCP server tools
    if tools_enabled and tools_override is None:
        mcp_tools = mcp_manager.get_all_tool_definitions()
        if mcp_tools:
            tools = tools + mcp_tools

    messages = [{"role": "system", "content": system_prompt}]
    if extra_context:
        messages.extend(extra_context)
    messages.append({"role": "user", "content": message})

    tool_calls_log = []
    iterations = 0
    final_response = ""

    for i in range(max_iterations):
        iterations = i + 1
        try:
            resp, actual_model = await _call_llm(messages, model, tools)
            model = actual_model  # Track which model we ended up using
        except Exception as e:
            final_response = f"[Model error: {e}]"
            break

        choice = resp.choices[0]
        msg = choice.message

        # If model wants to call tools
        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            # Append assistant message
            messages.append(_assistant_message_to_dict(msg))

            # Execute each tool call
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                tool_result = await _execute_tool_with_retry(tool_name, tool_args, db, retries=2)
                result_text = json.dumps(tool_result)

                tool_calls_log.append({
                    "id": tc.id,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "result_preview": tool_result.get("output", "")[:300],
                    "success": tool_result.get("success", False),
                    "preview_url": tool_result.get("preview_url"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text
                })

        else:
            # Final text response
            final_response = msg.content or ""
            break

    # If we hit max_iterations with no final response, grab last content
    if not final_response:
        for m in reversed(messages):
            if m.get("role") == "assistant":
                content = m.get("content")
                if isinstance(content, str) and content:
                    final_response = content
                    break
        if not final_response:
            final_response = "I've completed the requested operations. See tool calls above for details."

    duration_ms = int((time.time() - start) * 1000)

    return {
        "response": final_response,
        "tool_calls": tool_calls_log,
        "iterations": iterations,
        "model": model,
        "session_id": session_id,
        "duration_ms": duration_ms
    }


# ── Streaming version ─────────────────────────────────────────────────────────
async def stream_agent_loop(
    message: str,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    session_id: str = "",
    db=None,
    tools_enabled: bool = True,
    max_iterations: int = MAX_ITERATIONS,
    extra_context: list = None
) -> AsyncIterator[dict]:
    """
    Streaming agentic loop.
    Yields event dicts that the caller should serialize to SSE:

      {"type": "tool_start",  "tool": "...", "args": {...}}
      {"type": "tool_result", "tool": "...", "success": bool, "output": "..."}
      {"type": "text_chunk",  "content": "...", "delta": True}
      {"type": "done",        "tool_calls": [...], "iterations": int, "duration_ms": int}
      {"type": "error",       "message": "..."}
    """
    start = time.time()
    tools = TOOL_DEFINITIONS if tools_enabled else []
    # Merge connected MCP server tools
    if tools_enabled:
        mcp_tools = mcp_manager.get_all_tool_definitions()
        if mcp_tools:
            tools = tools + mcp_tools

    messages = [{"role": "system", "content": system_prompt}]
    if extra_context:
        messages.extend(extra_context)
    messages.append({"role": "user", "content": message})

    tool_calls_log = []
    iterations = 0

    for i in range(max_iterations):
        iterations = i + 1

        try:
            # Try with fallback for streaming; if Claude was used, fall back to non-stream wrapper
            if model.startswith("claude"):
                # Claude doesn't support our streaming path yet — use non-streaming
                try:
                    resp_obj, actual_model = await _call_llm(messages, model, tools, stream=False)
                    model = actual_model
                except Exception as e:
                    yield {"type": "error", "message": str(e)}
                    return
                # Simulate streaming from non-streaming response
                choice = resp_obj.choices[0]
                msg = choice.message
                finish_reason = choice.finish_reason
                content_buf = msg.content or ""
                tool_call_bufs = {}
                if msg.tool_calls:
                    for idx_tc, tc in enumerate(msg.tool_calls):
                        tool_call_bufs[idx_tc] = {
                            "id": tc.id,
                            "name": tc.function.name,
                            "args_str": tc.function.arguments,
                        }
                if content_buf:
                    yield {"type": "text_chunk", "content": content_buf, "delta": True}
            else:
                # Normal OpenAI streaming path with fallback
                try:
                    resp, actual_model = await _call_llm(messages, model, tools, stream=True)
                    model = actual_model
                except Exception as e:
                    # If streaming failed (e.g., fallback to Claude), try non-streaming
                    if _is_rate_limit_error(e):
                        try:
                            resp_obj, actual_model = await _call_llm(messages, model, tools, stream=False)
                            model = actual_model
                            choice = resp_obj.choices[0]
                            msg = choice.message
                            finish_reason = choice.finish_reason
                            content_buf = msg.content or ""
                            tool_call_bufs = {}
                            if msg.tool_calls:
                                for idx_tc, tc in enumerate(msg.tool_calls):
                                    tool_call_bufs[idx_tc] = {
                                        "id": tc.id,
                                        "name": tc.function.name,
                                        "args_str": tc.function.arguments,
                                    }
                            if content_buf:
                                yield {"type": "text_chunk", "content": content_buf, "delta": True}
                            yield {"type": "model_switched", "from": "gpt-4o", "to": actual_model}
                            # Skip the streaming block below
                            resp = None
                        except Exception as e2:
                            yield {"type": "error", "message": str(e2)}
                            return
                    else:
                        yield {"type": "error", "message": str(e)}
                        return

                if resp is not None:
                    # Accumulate streaming response
                    content_buf = ""
                    tool_call_bufs = {}  # index -> {id, name, args_str}
                    finish_reason = None

                    async for chunk in resp:
                        c = chunk.choices[0] if chunk.choices else None
                        if not c:
                            continue
                        delta = c.delta
                        finish_reason = c.finish_reason or finish_reason

                        # Text content
                        if delta.content:
                            content_buf += delta.content
                            yield {"type": "text_chunk", "content": delta.content, "delta": True}

                        # Tool calls being streamed
                        if delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                idx = tc_delta.index
                                if idx not in tool_call_bufs:
                                    tool_call_bufs[idx] = {
                                        "id": tc_delta.id or "",
                                        "name": tc_delta.function.name if tc_delta.function else "",
                                        "args_str": ""
                                    }
                                if tc_delta.id:
                                    tool_call_bufs[idx]["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        tool_call_bufs[idx]["name"] = tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        tool_call_bufs[idx]["args_str"] += tc_delta.function.arguments
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        # Build assistant message for history
        if tool_call_bufs:
            # Reconstruct tool calls list (OpenAI format)
            tc_list = []
            for idx in sorted(tool_call_bufs.keys()):
                buf = tool_call_bufs[idx]
                tc_list.append({
                    "id": buf["id"],
                    "type": "function",
                    "function": {"name": buf["name"], "arguments": buf["args_str"]}
                })
            messages.append({
                "role": "assistant",
                "content": content_buf or None,
                "tool_calls": tc_list
            })

            # Execute each tool
            for buf in sorted(tool_call_bufs.values(), key=lambda x: x.get("id", "")):
                tool_name = buf["name"]
                try:
                    tool_args = json.loads(buf["args_str"]) if buf["args_str"] else {}
                except json.JSONDecodeError:
                    tool_args = {}

                yield {"type": "tool_start", "tool": tool_name, "args": tool_args}

                tool_result = await _execute_tool_with_retry(tool_name, tool_args, db, retries=2)

                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "success": tool_result.get("success", False),
                    "output": tool_result.get("output", "")[:500],
                    "preview_url": tool_result.get("preview_url"),
                }

                tc_entry = {
                    "id": buf["id"],
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "result_preview": tool_result.get("output", "")[:300],
                    "success": tool_result.get("success", False),
                    "preview_url": tool_result.get("preview_url"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                tool_calls_log.append(tc_entry)

                messages.append({
                    "role": "tool",
                    "tool_call_id": buf["id"],
                    "content": json.dumps(tool_result)
                })

        else:
            # No tool calls - final response
            if content_buf:
                messages.append({"role": "assistant", "content": content_buf})
            break

    duration_ms = int((time.time() - start) * 1000)
    yield {
        "type": "done",
        "tool_calls": tool_calls_log,
        "iterations": iterations,
        "model": model,
        "duration_ms": duration_ms,
        "session_id": session_id
    }
