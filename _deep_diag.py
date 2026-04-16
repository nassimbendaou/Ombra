#!/usr/bin/env python3
"""Deep diagnostic: test each step of the agent loop pipeline."""
import asyncio, os, sys, json
sys.path.insert(0, "/home/azureuser/Ombra/backend")
os.chdir("/home/azureuser/Ombra/backend")

# Load .env
from dotenv import load_dotenv
load_dotenv("/home/azureuser/Ombra/.env")

async def main():
    from agent_loop import (
        _call_ollama, _call_openai, _call_advisor,
        _call_llm, _get_anthropic_key, OLLAMA_MODEL
    )
    
    print(f"OLLAMA_MODEL = {OLLAMA_MODEL}")
    print(f"ANTHROPIC_KEY present = {bool(_get_anthropic_key())}")
    print(f"OPENAI_KEY present = {bool(os.environ.get('OPENAI_API_KEY'))}")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Respond briefly."},
        {"role": "user", "content": "Say hello in one sentence."}
    ]
    
    # Step 1: Test Ollama directly
    print("\n=== Step 1: _call_ollama ===")
    try:
        result = await _call_ollama(messages, OLLAMA_MODEL, tools=[], stream=False)
        msg = result.choices[0].message
        print(f"  content = {repr(msg.content)}")
        print(f"  tool_calls = {msg.tool_calls}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Step 2: Test OpenAI directly
    print("\n=== Step 2: _call_openai (gpt-4o) ===")
    try:
        result = await _call_openai(messages, "gpt-4o", tools=[], stream=False)
        msg = result.choices[0].message
        print(f"  content = {repr(msg.content[:200])}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Step 3: Test _call_llm (the full fallback chain)
    print("\n=== Step 3: _call_llm ===")
    try:
        result, model_used = await _call_llm(messages, "gpt-4o", tools=[])
        msg = result.choices[0].message
        print(f"  model_used = {model_used}")
        print(f"  content = {repr(msg.content)}")
        print(f"  tool_calls = {msg.tool_calls}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
    
    # Step 4: Test advisor
    print("\n=== Step 4: _call_advisor ===")
    try:
        advice = await _call_advisor(
            messages + [{"role": "assistant", "content": "Hello there!"}],
            "You are an AI advisor. Polish and improve the executor response. Return ONLY the improved response."
        )
        print(f"  advice = {repr(advice[:300])}")
        if advice.startswith("[Advisor unavailable"):
            print("  ADVISOR FAILED!")
        else:
            print("  ADVISOR SUCCESS!")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Step 5: Simulate full non-streaming loop logic
    print("\n=== Step 5: Simulate run_agent_loop logic ===")
    try:
        result, model_used = await _call_llm(messages, "gpt-4o", tools=[])
        msg = result.choices[0].message
        print(f"  model_used = {model_used}")
        print(f"  msg.content = {repr(msg.content)}")
        print(f"  msg.tool_calls = {msg.tool_calls}")
        
        if msg.tool_calls:
            print("  -> Would process tool calls")
        else:
            executor_response = msg.content or ""
            print(f"  executor_response = {repr(executor_response)}")
            print(f"  len(executor_response) = {len(executor_response)}")
            
            # Check advisor condition
            has_key = bool(_get_anthropic_key())
            should_advise = has_key and (len(executor_response) < 50)
            print(f"  has_key = {has_key}, should_advise = {should_advise}")
            
            if should_advise:
                advice = await _call_advisor(
                    messages + [{"role": "assistant", "content": executor_response}],
                    "You are an AI advisor. Polish the response."
                )
                print(f"  advice = {repr(advice[:300])}")
                if advice and not advice.startswith("[Advisor unavailable"):
                    final = advice
                else:
                    final = executor_response
            else:
                final = executor_response
            
            print(f"  final_response = {repr(final[:300])}")
            if not final:
                print("  WARNING: final is empty -> would get fallback message!")
            else:
                print("  OK: Would send this response to user")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(main())
