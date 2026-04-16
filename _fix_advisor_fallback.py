with open('/home/azureuser/Ombra/backend/agent_loop.py', 'r') as f:
    al = f.read()

# Fix _call_advisor to fallback to OpenAI when Claude fails
old_advisor = '''async def _call_advisor(messages: list, advisor_prompt: str) -> str:
    """Call Cloud LLM (Claude) as Advisor/Thinker for complex reasoning."""
    advisor_messages = [
        {"role": "system", "content": advisor_prompt},
    ]
    # Include the shared context (last 6 messages for efficiency)
    for m in messages[-6:]:
        if m["role"] in ("user", "assistant"):
            advisor_messages.append({"role": m["role"], "content": (m.get("content") or "")[:2000]})
        elif m["role"] == "tool":
            advisor_messages.append({"role": "user", "content": f"[Tool result]: {(m.get('content') or '')[:1000]}"})

    try:
        # Use Claude as advisor
        resp = await _call_anthropic(advisor_messages, "claude-sonnet-4-5-20250929", tools=[], stream=False)
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[Advisor unavailable: {e}]"'''

new_advisor = '''async def _call_advisor(messages: list, advisor_prompt: str) -> str:
    """Call Cloud LLM (Claude or OpenAI) as Advisor/Thinker for complex reasoning."""
    advisor_messages = [
        {"role": "system", "content": advisor_prompt},
    ]
    # Include the shared context (last 6 messages for efficiency)
    for m in messages[-6:]:
        if m["role"] in ("user", "assistant"):
            advisor_messages.append({"role": m["role"], "content": (m.get("content") or "")[:2000]})
        elif m["role"] == "tool":
            advisor_messages.append({"role": "user", "content": f"[Tool result]: {(m.get('content') or '')[:1000]}"})

    # Try Claude first, then OpenAI as fallback
    try:
        resp = await _call_anthropic(advisor_messages, "claude-sonnet-4-5-20250929", tools=[], stream=False)
        return resp.choices[0].message.content or ""
    except Exception:
        pass

    # Fallback to OpenAI
    try:
        resp = await _call_openai(advisor_messages, "gpt-4o", tools=[], stream=False)
        return resp.choices[0].message.content or ""
    except Exception:
        pass

    try:
        resp = await _call_openai(advisor_messages, "gpt-4o-mini", tools=[], stream=False)
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[Advisor unavailable: {e}]"'''

assert old_advisor in al, "Could not find _call_advisor"
al = al.replace(old_advisor, new_advisor)

# Also fix _call_llm: when Ollama succeeds for tool calls but Claude fails for text,
# We need the fallback to continue to OpenAI properly.
# The current code already does this, but let's make sure the advisor is always tried.

with open('/home/azureuser/Ombra/backend/agent_loop.py', 'w') as f:
    f.write(al)

import py_compile
py_compile.compile('/home/azureuser/Ombra/backend/agent_loop.py', doraise=True)
print("[OK] Advisor now falls back to OpenAI when Claude credits exhausted")
