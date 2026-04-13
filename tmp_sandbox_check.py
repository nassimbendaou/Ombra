import asyncio
import sys
sys.path.insert(0, '/home/azureuser/Ombra/backend')
from agent_tools import execute_tool

async def main():
    r1 = await execute_tool('terminal', {'command': 'rm -rf /tmp/never_do_this'})
    print('terminal_blocked', r1.get('success'), r1.get('output', '')[:140])

    r2 = await execute_tool('python_exec', {'code': 'import subprocess\nprint(123)'})
    print('python_blocked', r2.get('success'), r2.get('output', '')[:140])

asyncio.run(main())
