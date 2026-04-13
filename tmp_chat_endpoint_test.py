import asyncio
import json
import sys
import traceback

sys.path.insert(0, '/home/azureuser/Ombra/backend')

from server import chat_endpoint, ChatRequest

async def main():
    req = ChatRequest(
        message='Use tools to list the files in the backend folder and tell me the first five names only.',
        session_id='endpoint_tool_test',
        enable_tools=True,
    )
    try:
        result = await chat_endpoint(req)
        print(json.dumps(result, indent=2)[:4000])
    except Exception:
        traceback.print_exc()

asyncio.run(main())
