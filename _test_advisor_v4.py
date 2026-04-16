#!/usr/bin/env python3
"""Test: verify advisor is actually polishing responses."""
import requests, json

BASE = "http://localhost:8001"

# Non-streaming test with complex question
print("=== Non-Streaming: Complex Question ===")
r = requests.post(f"{BASE}/api/chat", json={
    "message": "Explain in 2 sentences what Docker is and why developers use it.",
    "conversation_id": "test_advisor_v4",
    "model": "gpt-4o"
}, timeout=90)
data = r.json()
print(f"Model: {data.get('model')}")
print(f"Response: {data.get('response', '')[:400]}")
print(f"Duration: {data.get('duration_ms')}ms")

# Streaming test with complex question
print("\n=== Streaming: Complex Question ===")
r = requests.post(f"{BASE}/api/chat/stream", json={
    "message": "Explain in 2 sentences what Kubernetes is.",
    "conversation_id": "test_advisor_stream_v4",
    "model": "gpt-4o"
}, stream=True, timeout=90)
content = ""
duration = 0
for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data: "):
        continue
    payload = line[6:]
    if payload == "[DONE]":
        break
    try:
        evt = json.loads(payload)
        if evt.get("type") == "token":
            content += evt.get("token", "")
        elif evt.get("type") == "done":
            duration = evt.get("duration_ms", 0)
    except:
        pass
print(f"Duration: {duration}ms")
print(f"Content: {content[:400]}")
