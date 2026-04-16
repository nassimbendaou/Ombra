#!/usr/bin/env python3
"""Add OPENAI_API_KEY to .env by copying value from EMERGENT_LLM_KEY."""
env_path = "/home/azureuser/Ombra/backend/.env"

with open(env_path) as f:
    lines = f.readlines()

openai_key = ""
for line in lines:
    if line.startswith("EMERGENT_LLM_KEY="):
        openai_key = line.strip().split("=", 1)[1]
        break

if not openai_key:
    print("[FAIL] No EMERGENT_LLM_KEY found in .env")
    exit(1)

# Check if OPENAI_API_KEY already exists
has_openai = any(l.startswith("OPENAI_API_KEY=") for l in lines)
if has_openai:
    print("[SKIP] OPENAI_API_KEY already in .env")
else:
    with open(env_path, "a") as f:
        f.write(f"\nOPENAI_API_KEY={openai_key}\n")
    print(f"[OK] Added OPENAI_API_KEY to .env (sk-proj-...{openai_key[-6:]})")
