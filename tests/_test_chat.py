import httpx
import json

BASE = "http://localhost:8001"

# Test health
r = httpx.get(f"{BASE}/health", timeout=10)
print("=== HEALTH ===")
print(r.status_code, r.json())

# Test non-streaming chat
print("\n=== NON-STREAMING CHAT ===")
try:
    r = httpx.post(f"{BASE}/api/chat", json={"message": "Say hello in one sentence", "session_id": "debug_test_1"}, timeout=120)
    print("Status:", r.status_code)
    d = r.json()
    print("Provider:", d.get("provider"))
    print("Model:", d.get("model"))
    print("Response:", str(d.get("response", ""))[:500])
    if "error" in d:
        print("ERROR:", d["error"])
except Exception as e:
    print("EXCEPTION:", e)

# Test streaming chat
print("\n=== STREAMING CHAT ===")
try:
    with httpx.stream("POST", f"{BASE}/api/chat/stream", json={"message": "Say hi in one word", "session_id": "debug_test_2"}, timeout=120) as resp:
        print("Status:", resp.status_code)
        count = 0
        for line in resp.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    print("GOT [DONE]")
                    break
                try:
                    evt = json.loads(data)
                    if evt.get("type") == "token":
                        count += 1
                        if count <= 5:
                            print(f"  token: {evt.get('content', '')!r}")
                    elif evt.get("type") == "done":
                        print(f"  done event, model={evt.get('model')}, provider={evt.get('provider')}")
                    elif evt.get("type") == "error":
                        print(f"  ERROR event: {evt}")
                    else:
                        print(f"  event type={evt.get('type')}")
                except json.JSONDecodeError:
                    print(f"  raw: {data[:200]}")
        print(f"Total tokens received: {count}")
except Exception as e:
    print("EXCEPTION:", e)
