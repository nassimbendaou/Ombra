import httpx, json
BASE = "http://localhost:8001"

print("=== QUICK CHAT TEST ===")
r = httpx.post(f"{BASE}/api/chat", json={"message": "hi", "session_id": "quick_test"}, timeout=120)
d = r.json()
print(f"Status: {r.status_code}")
print(f"Model: {d.get('model')}")
print(f"Response: {str(d.get('response',''))[:300]}")

print("\n=== STREAMING TEST ===")
with httpx.stream("POST", f"{BASE}/api/chat/stream", json={"message": "bonjour", "session_id": "quick_test_2"}, timeout=120) as resp:
    print(f"Status: {resp.status_code}")
    tokens = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            try:
                evt = json.loads(line[6:])
                if evt.get("type") == "token":
                    tokens.append(evt.get("token", ""))
                elif evt.get("type") == "done":
                    print(f"Model: {evt.get('model')}")
                    print(f"Provider: {evt.get('provider')}")
            except: pass
    print(f"Response: {''.join(tokens)[:300]}")

print("\n=== PERMS ===")
r = httpx.get(f"{BASE}/api/permissions", timeout=10)
print(r.json())
