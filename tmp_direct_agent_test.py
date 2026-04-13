import asyncio
import json
import os
import sys

sys.path.insert(0, '/home/azureuser/Ombra/backend')

from agent_loop import run_agent_loop
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/home/azureuser/Ombra/backend/.env')
load_dotenv('/home/azureuser/Ombra/.env')

async def main():
    client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
    db = client[os.environ.get('DB_NAME', 'ombra_db')]
    result = await run_agent_loop(
        message='Use tools to list the files in the backend folder and tell me the first five names only.',
        system_prompt='You are Ombra. Use tools when needed.',
        model='gpt-4o',
        session_id='direct_tool_test',
        db=db,
        tools_enabled=True,
        extra_context=[]
    )
    print(json.dumps(result, indent=2)[:4000])

asyncio.run(main())
