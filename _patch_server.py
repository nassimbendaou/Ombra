import re

with open('/home/azureuser/Ombra/backend/server.py', 'r') as f:
    content = f.read()

# Fix 1: Done event hardcoded provider/model
old1 = """yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'provider': 'openai', 'model': 'gpt-4o', 'tool_calls': tool_calls_made, 'iterations': event.get('iterations', 1), 'duration_ms': event.get('duration_ms', 0)})}\\n\\n\""""
new1 = """yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'provider': event.get('provider', 'anthropic'), 'model': event.get('model', 'claude-sonnet-4-5-20250929'), 'tool_calls': tool_calls_made, 'iterations': event.get('iterations', 1), 'duration_ms': event.get('duration_ms', 0)})}\\n\\n\""""

assert old1 in content, "Could not find done event line"
content = content.replace(old1, new1)

# Fix 2: Conversation storage hardcoded provider/model
old2 = """"provider": "openai", "model": "gpt-4o", "tool_calls": tool_calls_made or None}"""
new2 = """"provider": "anthropic" if actual_stream_model.startswith("claude") else "openai", "model": actual_stream_model, "tool_calls": tool_calls_made or None}"""

assert old2 in content, "Could not find conversation storage line"
content = content.replace(old2, new2)

# Add actual_stream_model variable tracking - insert after tool_calls_log init
# We need to capture the model from the done event
old3 = """        full_response = ""
        tool_calls_made = []

        if AGENT_LOOP_AVAILABLE and use_tools_stream and EMERGENT_KEY:"""
new3 = """        full_response = ""
        tool_calls_made = []
        actual_stream_model = "claude-sonnet-4-5-20250929"

        if AGENT_LOOP_AVAILABLE and use_tools_stream and EMERGENT_KEY:"""

assert old3 in content, "Could not find full_response init"
content = content.replace(old3, new3)

# Also capture model from done event
old4 = """                elif event["type"] == "done":
                    tool_calls_made = event.get("tool_calls", [])"""
new4 = """                elif event["type"] == "done":
                    tool_calls_made = event.get("tool_calls", [])
                    actual_stream_model = event.get("model", actual_stream_model)"""

assert old4 in content, "Could not find done event handler"
content = content.replace(old4, new4)

with open('/home/azureuser/Ombra/backend/server.py', 'w') as f:
    f.write(content)

print("All 4 patches applied successfully!")
