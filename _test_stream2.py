import httpx
import json

BASE = "http://localhost:8001"

print("=== STREAMING CHAT ===")
try:
    with httpx.stream("POST", f"{BASE}/api/chat/stream", json={"message": "Say hello in one sentence", "session_id": "debug_test_3"}, timeout=120) as resp:
        print("Status:", resp.status_code)
        for line in resp.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    print("GOT [DONE]")
                    break
                try:
                    evt = json.loads(data)
                    print(f"  EVENT: {json.dumps(evt)[:300]}")
                except json.JSONDecodeError:
                    print(f"  RAW: {data[:200]}")
except Exception as e:
    print("EXCEPTION:", e)
