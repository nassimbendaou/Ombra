#!/usr/bin/env python3
"""Quick test: verify Claude is the primary model."""
import httpx, json, asyncio

async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post("http://localhost:8001/api/chat", json={
            "message": "Say hello in one sentence. What model are you?",
            "session_id": "test-claude-primary-2"
        })
        data = resp.json()
        print("provider:", data.get("provider"))
        print("model:", data.get("model"))
        print("routing:", data.get("routing"))
        print("response:", (data.get("response") or "")[:300])

asyncio.run(main())
