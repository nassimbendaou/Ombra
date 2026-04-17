#!/usr/bin/env python3
"""Quick key check."""
import os, sys
sys.path.insert(0, "/home/azureuser/Ombra/backend")
os.chdir("/home/azureuser/Ombra/backend")
from dotenv import load_dotenv
load_dotenv()
print("OPENAI_API_KEY present:", bool(os.environ.get("OPENAI_API_KEY")))
print("ANTHROPIC_API_KEY present:", bool(os.environ.get("ANTHROPIC_API_KEY")))
print("EMERGENT_LLM_KEY present:", bool(os.environ.get("EMERGENT_LLM_KEY")))

# Quick OpenAI test
import openai
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
try:
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":"Say hello in 5 words"}],
        max_tokens=20
    )
    print("OpenAI response:", r.choices[0].message.content)
except Exception as e:
    print("OpenAI error:", e)
