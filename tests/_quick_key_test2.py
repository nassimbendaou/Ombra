#!/usr/bin/env python3
"""Quick key check with explicit path."""
import os, sys
from dotenv import load_dotenv
load_dotenv("/home/azureuser/Ombra/backend/.env", override=True)
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
print("ANTHROPIC_API_KEY present:", bool(os.environ.get("ANTHROPIC_API_KEY")))

# Quick OpenAI test
import openai
key = os.environ.get("OPENAI_API_KEY")
if not key:
    print("NO KEY - aborting")
    sys.exit(1)
client = openai.OpenAI(api_key=key)
try:
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":"Say hello in 5 words"}],
        max_tokens=20
    )
    print("OpenAI response:", r.choices[0].message.content)
except Exception as e:
    print("OpenAI error:", e)
