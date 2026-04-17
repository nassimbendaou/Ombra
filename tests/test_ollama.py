import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=60) as c:
        payload = {"model": "tinyllama", "prompt": "say hello", "stream": False}
        r = await c.post("http://localhost:11434/api/generate", json=payload)
        print("status:", r.status_code)
        print("response:", r.text[:300])

asyncio.run(test())
