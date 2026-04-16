with open('/home/azureuser/Ombra/backend/server.py', 'r') as f:
    sv = f.read()

# Fix the TelegramRouter constructor call  
sv = sv.replace(
    '            emergent_key=EMERGENT_KEY,\n',
    '            api_key=EMERGENT_KEY,\n'
)

# Fix AutonomyDaemon — it takes positional args, check how it's called
# AutonomyDaemon(db, OLLAMA_URL, EMERGENT_KEY) — 3rd positional arg
# The class was patched to rename emergent_key -> api_key internally
# Positional args are fine, but let's verify

# Fix CreativeExplorer — same pattern  
# CreativeExplorer(db, OLLAMA_URL, EMERGENT_KEY) — positional, OK

with open('/home/azureuser/Ombra/backend/server.py', 'w') as f:
    f.write(sv)

print("[OK] Fixed emergent_key= keyword arg in server.py")

# Also verify TelegramRouter __init__ signature
with open('/home/azureuser/Ombra/backend/telegram_router.py', 'r') as f:
    tr = f.read()

import re
init_match = re.search(r'def __init__\(self[^)]+\)', tr)
if init_match:
    print(f"TelegramRouter.__init__ signature: {init_match.group()[:200]}")
