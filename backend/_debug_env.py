import os
from dotenv import load_dotenv
load_dotenv()
print("EMERGENT_LLM_KEY:", "YES" if os.environ.get("EMERGENT_LLM_KEY") else "NO")
print("OPENAI_API_KEY:", "YES" if os.environ.get("OPENAI_API_KEY") else "NO")
print("TELEGRAM_BOT_TOKEN:", "YES" if os.environ.get("TELEGRAM_BOT_TOKEN") else "NO")
try:
    from agent_loop import run_agent_loop
    print("agent_loop import: OK")
except Exception as e:
    print("agent_loop import FAILED:", e)
try:
    from agent_tools import TOOL_DEFINITIONS
    print("TOOL_DEFINITIONS count:", len(TOOL_DEFINITIONS))
    for t in TOOL_DEFINITIONS:
        print("  -", t.get("function", {}).get("name"))
except Exception as e:
    print("agent_tools import FAILED:", e)
