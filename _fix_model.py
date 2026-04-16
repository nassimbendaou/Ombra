with open('/home/azureuser/Ombra/backend/agent_loop.py', 'r') as f:
    al = f.read()

# Fix 1: Change default Ollama model to mistral (actually available)
al = al.replace(
    'OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")',
    'OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:latest")'
)

# Fix 2: In the streaming path, also inject advisor consultation
# The streaming path checks model.startswith("claude") and calls _call_llm
# which now routes to Ollama first. When Ollama returns empty content,
# we need to consult the advisor.

# Find the streaming "No tool calls - final response" section and add advisor
old_streaming_final = '''            # No tool calls - final response
            if content_buf:
                messages.append({"role": "assistant", "content": content_buf})
            break'''

new_streaming_final = '''            # No tool calls - final response from executor
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

al = al.replace(old_streaming_final, new_streaming_final)

with open('/home/azureuser/Ombra/backend/agent_loop.py', 'w') as f:
    f.write(al)

print("[OK] Fixed Ollama model + streaming advisor fallback")

# Verify syntax
import py_compile
py_compile.compile('/home/azureuser/Ombra/backend/agent_loop.py', doraise=True)
print("[OK] Syntax check passed")
