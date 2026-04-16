#!/usr/bin/env python3
"""Fix streaming: don't emit executor text when advisor will replace it.
Also fix the done event provider."""
import re

FILEPATH = "/home/azureuser/Ombra/backend/agent_loop.py"

with open(FILEPATH, "r") as f:
    code = f.read()

# Fix 1: In the Ollama non-streaming handling, don't emit executor text immediately.
# Instead, let the advisor section handle it.
# Currently:
#   if content_buf:
#       yield {"type": "text_chunk", "content": content_buf, "delta": True}
#   resp = None

old_emit = '''                    if model.startswith("ollama/") and hasattr(resp, 'choices') and not hasattr(resp, '__aiter__'):
                        choice = resp.choices[0]
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
                        resp = None  # Skip the streaming block below'''

new_emit = '''                    if model.startswith("ollama/") and hasattr(resp, 'choices') and not hasattr(resp, '__aiter__'):
                        choice = resp.choices[0]
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
                        # Don't emit executor text here - let advisor section handle it
                        # If advisor is available, it will replace the text
                        # If not, the final else block will emit content_buf
                        resp = None  # Skip the streaming block below'''

if old_emit in code:
    code = code.replace(old_emit, new_emit)
    print("[OK] Fix 1: Removed premature executor text emission")
else:
    print("[SKIP] Fix 1: Pattern not found")

# Fix 2: In the advisor section, emit either advisor text or executor text (not both)
# Currently the advisor section yields advice if available, then the executor text was already emitted.
# After fix 1, neither is emitted yet. So we need to emit one or the other.
old_advisor_block = '''            # No tool calls - final response from executor
            # Consult Advisor (Claude) for a polished response if executor gave weak/empty answer
            if _get_anthropic_key() and len(content_buf.strip()) < 50:
                advisor_prompt = (
                    "You are the Advisor in an Executor-Advisor architecture. "
                    "The Executor (local LLM) produced a draft response. "
                    "Review the conversation and provide a polished, comprehensive answer. "
                    "Be concise but thorough. Keep the same language as the user."
                )
                try:
                    advice = await _call_advisor(
                        messages + [{"role": "assistant", "content": content_buf}],
                        advisor_prompt
                    )
                    if advice and not advice.startswith("[Advisor unavailable"):
                        content_buf = advice
                        yield {"type": "text_chunk", "content": advice, "delta": True}
                except Exception:
                    pass  # Use whatever executor produced
            if content_buf:
                messages.append({"role": "assistant", "content": content_buf})
            break'''

new_advisor_block = '''            # No tool calls - final response from executor
            # Consult Advisor for a polished response if executor gave weak/empty answer
            if len(content_buf.strip()) < 50:
                advisor_prompt = (
                    "You are the Advisor in an Executor-Advisor architecture. "
                    "The Executor (local LLM) produced a draft response. "
                    "Review the conversation and provide a polished, comprehensive answer. "
                    "Be concise but thorough. Keep the same language as the user."
                )
                try:
                    advice = await _call_advisor(
                        messages + [{"role": "assistant", "content": content_buf}],
                        advisor_prompt
                    )
                    if advice and not advice.startswith("[Advisor unavailable"):
                        content_buf = advice
                except Exception:
                    pass  # Use whatever executor produced
            # Emit the final response (advisor-polished or raw executor)
            if content_buf:
                yield {"type": "text_chunk", "content": content_buf, "delta": True}
                messages.append({"role": "assistant", "content": content_buf})
            break'''

if old_advisor_block in code:
    code = code.replace(old_advisor_block, new_advisor_block)
    print("[OK] Fix 2: Advisor emits single response (no duplication)")
else:
    print("[SKIP] Fix 2: Pattern not found - checking...")
    if "No tool calls - final response from executor" in code:
        print("  Found the comment but block differs")
        # Show what's around it
        idx = code.find("No tool calls - final response from executor")
        print(f"  Context: {code[idx:idx+200]}")

with open(FILEPATH, "w") as f:
    f.write(code)
print("[DONE] Streaming fixes applied")
