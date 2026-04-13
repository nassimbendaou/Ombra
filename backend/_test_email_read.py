import pymongo, asyncio
db = pymongo.MongoClient("mongodb://localhost:27017")["ombra_dev"]

# Test read_emails tool
import sys
sys.path.insert(0, "/home/azureuser/Ombra/backend")
from agent_tools import execute_tool

async def test():
    result = await execute_tool("read_emails", {"count": 3, "unread_only": False}, db)
    print("Success:", result.get("success"))
    print("Output:", result.get("output", "")[:800])
    print("Count:", result.get("count"))

asyncio.run(test())
