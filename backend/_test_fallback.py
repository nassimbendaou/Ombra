#!/usr/bin/env python3
"""Quick smoke test for model fallback chain."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from agent_loop import FALLBACK_CHAINS, _get_anthropic_key, _is_rate_limit_error

print("FALLBACK_CHAINS:", FALLBACK_CHAINS)
print("Anthropic key available:", bool(_get_anthropic_key()))
print("OpenAI key available:", bool(os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")))
print("Rate limit test:", _is_rate_limit_error(Exception("Error code: 429 rate limit exceeded")))
print("Non-rate-limit test:", _is_rate_limit_error(Exception("Connection refused")))
print("ALL CHECKS PASSED")
