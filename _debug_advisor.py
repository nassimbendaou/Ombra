"""Debug the advisor call chain directly."""
import asyncio, os, sys
sys.path.insert(0, '/home/azureuser/Ombra/backend')

async def test():
    from agent_loop import _call_anthropic, _call_advisor, _call_ollama, _get_anthropic_key, OLLAMA_MODEL
    
    print(f"Ollama model: {OLLAMA_MODEL}")
    print(f"Anthropic key configured: {bool(_get_anthropic_key())}")
    
    # Test 1: Direct Ollama call
    print("\n=== TEST 1: Direct Ollama call ===")
    try:
        result = await _call_ollama(
            [{"role": "user", "content": "Say hello in one sentence"}],
            OLLAMA_MODEL, tools=[], stream=False
        )
        msg = result.choices[0].message
        print(f"  finish_reason: {result.choices[0].finish_reason}")
        print(f"  content: {repr(msg.content)}")
        print(f"  tool_calls: {msg.tool_calls}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 2: Direct Anthropic call
    print("\n=== TEST 2: Direct Anthropic call ===")
    try:
        result = await _call_anthropic(
            [{"role": "system", "content": "You are a helpful assistant."},
             {"role": "user", "content": "Say hello in one sentence"}],
            "claude-sonnet-4-5-20250929", tools=[], stream=False
        )
        msg = result.choices[0].message
        print(f"  finish_reason: {result.choices[0].finish_reason}")
        print(f"  content: {repr(msg.content)}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 3: Advisor call
    print("\n=== TEST 3: Advisor call ===")
    try:
        messages = [
            {"role": "system", "content": "You are Ombra."},
            {"role": "user", "content": "bonjour"},
            {"role": "assistant", "content": ""},  # empty executor response
        ]
        advice = await _call_advisor(messages, "You are the Advisor. Provide a polished response to the user. Be concise.")
        print(f"  advice: {repr(advice[:300])}")
    except Exception as e:
        print(f"  ERROR: {e}")

asyncio.run(test())
