#!/usr/bin/env python3
"""Fix _call_llm: always continue to next model on ANY error, and prioritize OpenAI over Claude."""
import re

FILEPATH = "/home/azureuser/Ombra/backend/agent_loop.py"

with open(FILEPATH, "r") as f:
    code = f.read()

# Replace the entire _call_llm function
old_func_pattern = r'async def _call_llm\(messages: list, model: str, tools: list, stream: bool = False\):.*?raise last_error or RuntimeError\("All models failed \(Ollama \+ cloud\)"\)'

new_func = '''async def _call_llm(messages: list, model: str, tools: list, stream: bool = False):
    """Call LLM with Advisor strategy.
    
    Strategy: Local Ollama = Executor (tool calling, every turn)
              Cloud LLM = Advisor/Thinker (complex reasoning, on-demand)
    
    Fallback: Ollama -> OpenAI (gpt-4o) -> OpenAI (gpt-4o-mini) -> Claude
    """
    # --- Executor path: try local Ollama first for tool execution ---
    try:
        result = await _call_ollama(messages, OLLAMA_MODEL, tools, stream=False)
        return result, f"ollama/{OLLAMA_MODEL}"
    except Exception:
        pass  # Fall through to cloud models

    # --- Cloud fallback: OpenAI first (working), then Claude ---
    cloud_models = ["gpt-4o", "gpt-4o-mini"]
    if _get_anthropic_key():
        cloud_models.append("claude-sonnet-4-5-20250929")
    
    last_error = None
    for m in cloud_models:
        try:
            if m.startswith("claude"):
                return await _call_anthropic(messages, m, tools, stream=False), m
            else:
                result = await _call_openai(messages, m, tools, stream=stream)
                return result, m
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                await asyncio.sleep(2)
            continue  # ALWAYS continue to next model

    raise last_error or RuntimeError("All models failed (Ollama + cloud)")'''

result = re.sub(old_func_pattern, new_func, code, flags=re.DOTALL)
if result == code:
    print("[FAIL] Pattern not found — _call_llm may have changed")
else:
    with open(FILEPATH, "w") as f:
        f.write(result)
    print("[OK] _call_llm fixed: OpenAI prioritized, always-continue on errors")
