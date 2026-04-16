import httpx
import json

BASE = "http://localhost:8001"

# Test non-streaming chat (tests Advisor strategy)
print("=== ADVISOR STRATEGY TEST ===")
try:
    r = httpx.post(f"{BASE}/api/chat", json={"message": "What time is it?", "session_id": "advisor_test_1"}, timeout=120)
    print("Status:", r.status_code)
    d = r.json()
    print("Provider:", d.get("provider"))
    print("Model:", d.get("model"))
    print("Response:", str(d.get("response", ""))[:300])
except Exception as e:
    print("EXCEPTION:", e)

# Test streaming
print("\n=== STREAMING TEST ===")
try:
    with httpx.stream("POST", f"{BASE}/api/chat/stream", json={"message": "say hello", "session_id": "advisor_test_2"}, timeout=120) as resp:
        print("Status:", resp.status_code)
        for line in resp.iter_lines():
            if line.startswith("data: "):
                data = line[6:]
                try:
                    evt = json.loads(data)
                    print(f"  EVENT: {json.dumps(evt)[:300]}")
                except:
                    pass
except Exception as e:
    print("EXCEPTION:", e)

# Test permissions
print("\n=== PERMISSIONS TEST ===")
try:
    r = httpx.get(f"{BASE}/api/permissions", timeout=10)
    print("Permissions:", r.json())
except Exception as e:
    print("EXCEPTION:", e)

# Verify no posthog in frontend
print("\n=== POSTHOG CHECK ===")
import subprocess
result = subprocess.run(["grep", "-c", "posthog", "/home/azureuser/Ombra/frontend/build/index.html"], capture_output=True, text=True)
print("PostHog in build/index.html:", "GONE" if result.stdout.strip() == "0" else f"FOUND ({result.stdout.strip()} matches)")

# Verify no emergent in frontend
result2 = subprocess.run(["grep", "-c", "emergent", "/home/azureuser/Ombra/frontend/build/index.html"], capture_output=True, text=True)
print("Emergent in build/index.html:", "GONE" if result2.stdout.strip() == "0" else f"FOUND ({result2.stdout.strip()} matches)")
