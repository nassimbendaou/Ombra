#!/usr/bin/env python3
"""Fix stream_agent_loop: handle Ollama non-streaming response in the streaming path."""
import re

FILEPATH = "/home/azureuser/Ombra/backend/agent_loop.py"

with open(FILEPATH, "r") as f:
    code = f.read()

# The problem: in the "else" branch (non-claude model), _call_llm returns a non-streaming
# response from Ollama, but the code expects a streaming async iterator.
# Fix: after _call_llm, check if actual_model starts with "ollama/" and handle non-streaming.

old_block = '''                if resp is not None:
                    # Accumulate streaming response
                    content_buf = ""
                    tool_call_bufs = {}  # index -> {id, name, args_str}
                    finish_reason = None

                    async for chunk in resp:'''

new_block = '''                if resp is not None:
                    # Accumulate streaming response
                    content_buf = ""
                    tool_call_bufs = {}  # index -> {id, name, args_str}
                    finish_reason = None

                    # If Ollama returned a non-streaming response, handle it directly
                    if model.startswith("ollama/") and hasattr(resp, 'choices'):
                        choice = resp.choices[0]
                        msg = choice.message
                        finish_reason = choice.finish_reason
                        content_buf = msg.content or ""
                        if msg.tool_calls:
                            for idx_tc, tc in enumerate(msg.tool_calls):
                                tool_call_bufs[idx_tc] = {
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "args_str": tc.function.arguments,
                                }
                        if content_buf:
                            yield {"type": "text_chunk", "content": content_buf, "delta": True}
                    else:
                      async for chunk in resp:'''

if old_block not in code:
    print("[FAIL] Could not find the target block in stream_agent_loop")
    # Try to find what's there
    import re as re2
    m = re2.search(r'if resp is not None:.*?async for chunk in resp:', code, re2.DOTALL)
    if m:
        print(f"Found at pos {m.start()}: {m.group()[:200]}")
    else:
        print("No match at all")
else:
    # Also need to indent everything inside the else for the async for block
    # Find the end of the async for loop content
    idx = code.find(old_block)
    after_old = code[idx + len(old_block):]
    
    # Find where the tool_call_bufs block ends (at the "else:" associated with "if tool_call_bufs:")
    # The structure is: async for chunk... then "if tool_call_bufs:" ... "else:" (final response)
    # We need to add proper indentation for the else clause
    
    # Simpler approach: wrap the async for content in the else with extra indentation
    # Find from "async for chunk" up to the closing of the streaming block
    
    # Actually, the cleanest approach: after the ollama non-streaming handling,
    # make the async for loop an else clause, and indent its content
    
    # Let's find the full streaming block and add proper indentation
    # The async for loop and its content needs 2 more spaces of indentation
    
    # Find end of streaming block - it ends at the "else:" that's at the same level as "if tool_call_bufs:"
    # which is right after the async for block
    
    # Strategy: find "async for chunk in resp:" and everything until the next unindented block
    # Then indent all of it by 2 more spaces
    
    # Actually, let me use a different approach. Instead of re-indenting everything,
    # I'll handle Ollama non-streaming first, then skip the async for block with a flag.
    
    code2 = code.replace(old_block, new_block)
    
    # Now I need to close the else block. The async for loop content needs to be indented.
    # But that's a LOT of code to re-indent. Let me use a different approach entirely.
    
    # BETTER APPROACH: Don't modify the streaming loop. Instead, make _call_ollama
    # return a fake async generator when stream=True.
    
    # Revert the change
    print("[INFO] Using alternative approach: make _call_ollama support pseudo-streaming")

# BETTER APPROACH: modify _call_ollama to return an async generator when stream=True
# This way the streaming path in stream_agent_loop doesn't need changes.

# But actually the issue is that _call_llm always calls _call_ollama with stream=False.
# Let me fix _call_llm to pass stream through to _call_ollama.

# Actually the SIMPLEST fix: in stream_agent_loop, before entering the streaming loop,
# check if the response is a _FakeResponse (from Ollama) and convert it to the same
# format as the non-streaming Claude handler.

# Let me use a totally different approach: patch the beginning of the "else" (non-claude) branch
# to check if _call_llm returned an Ollama response and handle it like the Claude branch.

# Replace the entire non-streaming check
old_else = '''            else:
                # Normal OpenAI streaming path with fallback
                try:
                    resp, actual_model = await _call_llm(messages, model, tools, stream=True)
                    model = actual_model'''

new_else = '''            else:
                # Try to get response (Ollama returns non-streaming, OpenAI streams)
                try:
                    resp, actual_model = await _call_llm(messages, model, tools, stream=True)
                    model = actual_model
                    # If Ollama returned a non-streaming FakeResponse, convert to Claude-style handling
                    if model.startswith("ollama/") and hasattr(resp, 'choices') and not hasattr(resp, '__aiter__'):
                        choice = resp.choices[0]
                        msg = choice.message
                        finish_reason = choice.finish_reason
                        content_buf = msg.content or ""
                        tool_call_bufs = {}
                        if msg.tool_calls:
                            for idx_tc, tc in enumerate(msg.tool_calls):
                                tool_call_bufs[idx_tc] = {
                                    "id": tc.id,
                                    "name": tc.function.name,
                                    "args_str": tc.function.arguments,
                                }
                        if content_buf:
                            yield {"type": "text_chunk", "content": content_buf, "delta": True}
                        resp = None  # Skip the streaming block below'''

if old_else not in code:
    print("[FAIL] Could not find the else branch")
else:
    code = code.replace(old_else, new_else)
    with open(FILEPATH, "w") as f:
        f.write(code)
    print("[OK] Fixed stream_agent_loop to handle Ollama non-streaming responses")
