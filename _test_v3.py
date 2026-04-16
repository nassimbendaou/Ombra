#!/usr/bin/env python3
"""Streaming test v3: correct event handling."""
import requests, json

BASE = "http://localhost:8001"

print("=== Streaming Test ===")
try:
    r = requests.post(f"{BASE}/api/chat/stream", json={
        "message": "What is 2+2? Answer briefly.",
        "conversation_id": "test_v3_stream",
        "model": "gpt-4o"
    }, stream=True, timeout=60)
    content = ""
    model_used = ""
    provider = ""
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            evt = json.loads(payload)
            etype = evt.get("type", "")
            print(f"  Event: {etype} -> {json.dumps(evt)[:200]}")
            if etype == "token":
                content += evt.get("token", "")
            elif etype == "done":
                model_used = evt.get("model", "")
                provider = evt.get("provider", "")
            elif etype == "error":
                print(f"  ERROR: {evt.get('message', '')}")
        except:
            pass
    print(f"\nModel: {model_used}")
    print(f"Provider: {provider}")
    print(f"Content: {content[:300]}")
    if not content:
        print("WARNING: No content!")
    else:
        print("OK: Got content!")
except Exception as e:
    print(f"ERROR: {e}")
