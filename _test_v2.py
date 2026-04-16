#!/usr/bin/env python3
"""Full test: non-streaming + streaming with proper event handling."""
import requests, json

BASE = "http://localhost:8001"

# Test non-streaming
print("=== Non-Streaming Test ===")
try:
    r = requests.post(f"{BASE}/api/chat", json={
        "message": "Say hello and tell me who you are in one sentence.",
        "conversation_id": "test_v2_nonsream",
        "model": "gpt-4o"
    }, timeout=60)
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Model: {data.get('model', 'N/A')}")
    print(f"Provider: {data.get('provider', 'N/A')}")
    resp_text = data.get('response', '')
    print(f"Response: {resp_text[:300]}")
    if not resp_text or "completed the requested" in resp_text:
        print("WARNING: Empty/fallback response!")
    else:
        print("OK: Got a real response!")
except Exception as e:
    print(f"ERROR: {e}")

# Test streaming
print("\n=== Streaming Test ===")
try:
    r = requests.post(f"{BASE}/api/chat/stream", json={
        "message": "What is 2+2? Answer briefly.",
        "conversation_id": "test_v2_stream",
        "model": "gpt-4o"
    }, stream=True, timeout=60)
    content = ""
    model_used = ""
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            evt = json.loads(payload)
            events.append(evt.get("type", "unknown"))
            if evt.get("type") == "content":
                content += evt.get("content", "")
            elif evt.get("type") == "text_chunk":
                content += evt.get("content", "")
            elif evt.get("type") == "done":
                model_used = evt.get("model", "")
            elif evt.get("type") == "error":
                print(f"  ERROR event: {evt.get('message', '')}")
        except:
            pass
    print(f"Event types: {events}")
    print(f"Model: {model_used}")
    print(f"Content: {content[:300]}")
    if not content:
        print("WARNING: No content streamed!")
    else:
        print("OK: Got streamed content!")
except Exception as e:
    print(f"ERROR: {e}")
