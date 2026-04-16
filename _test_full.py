#!/usr/bin/env python3
"""Quick test: send a simple chat message via the API and print response."""
import requests, json, sys

BASE = "http://localhost:8001"

# Test non-streaming
print("=== Non-Streaming Test ===")
try:
    r = requests.post(f"{BASE}/api/chat", json={
        "message": "Say hello and tell me who you are in one sentence.",
        "conversation_id": "test_advisor_fix",
        "model": "gpt-4o"
    }, timeout=60)
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Model: {data.get('model', 'N/A')}")
    print(f"Provider: {data.get('provider', 'N/A')}")
    resp_text = data.get('response', '')
    print(f"Response: {resp_text[:300]}")
    if not resp_text or resp_text == "I've completed the requested operations.":
        print("WARNING: Empty/fallback response!")
    else:
        print("SUCCESS: Got a real response!")
except Exception as e:
    print(f"ERROR: {e}")

# Test streaming
print("\n=== Streaming Test ===")
try:
    r = requests.post(f"{BASE}/api/chat/stream", json={
        "message": "What is 2+2? Answer briefly.",
        "conversation_id": "test_stream_fix",
        "model": "gpt-4o"
    }, stream=True, timeout=60)
    content = ""
    model_used = ""
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            evt = json.loads(payload)
            if evt.get("type") == "content":
                content += evt.get("content", "")
            elif evt.get("type") == "done":
                model_used = evt.get("model", "")
        except:
            pass
    print(f"Model: {model_used}")
    print(f"Content: {content[:300]}")
    if not content:
        print("WARNING: No content streamed!")
    else:
        print("SUCCESS: Got streamed content!")
except Exception as e:
    print(f"ERROR: {e}")
