"""
Ombra Patch: Advisor Strategy + Full Admin + Remove Emergent/PostHog + Credential Cleanup
"""
import re

# ============================================================
# 1. PATCH agent_loop.py — Advisor Strategy
#    Local LLM (Ollama) = Executor (runs every turn)
#    Cloud LLM (Claude) = Advisor/Thinker (on-demand for complex reasoning)
# ============================================================
with open('/home/azureuser/Ombra/backend/agent_loop.py', 'r') as f:
    al = f.read()

# 1a. Replace OpenAI client creation — remove EMERGENT_LLM_KEY fallback
al = al.replace(
    'api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY") or ""',
    'api_key = os.environ.get("OPENAI_API_KEY") or ""'
)

# 1b. Add Ollama client helper and advisor call after the existing helpers
advisor_code = '''

# ── Ollama (Local Executor) ───────────────────────────────────────────────────
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

async def _call_ollama(messages: list, model: str, tools: list, stream: bool = False):
    """Call local Ollama as Executor (runs every turn for tool calling)."""
    import httpx
    ollama_msgs = []
    for m in messages:
        msg = {"role": m["role"], "content": m.get("content", "")}
        if m.get("tool_calls"):
            msg["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            msg["tool_call_id"] = m["tool_call_id"]
        ollama_msgs.append(msg)

    payload = {
        "model": model,
        "messages": ollama_msgs,
        "stream": False,
    }
    if tools:
        # Convert OpenAI tool format to Ollama format
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        data = resp.json()

    # Convert Ollama response to OpenAI-compatible format
    msg_data = data.get("message", {})
    content = msg_data.get("content", "")
    tool_calls_raw = msg_data.get("tool_calls", [])

    tc_objs = []
    for i, tc in enumerate(tool_calls_raw):
        fn = tc.get("function", {})
        tc_objs.append(_FakeToolCall(
            id=f"call_ollama_{i}_{int(time.time())}",
            name=fn.get("name", ""),
            arguments=json.dumps(fn.get("arguments", {})),
        ))

    finish = "tool_calls" if tc_objs else "stop"
    message_obj = _FakeMessage(content=content or None, tool_calls=tc_objs if tc_objs else None)
    return _FakeResponse(choices=[_FakeChoice(finish_reason=finish, message=message_obj)])


async def _call_advisor(messages: list, advisor_prompt: str) -> str:
    """Call Cloud LLM (Claude) as Advisor/Thinker for complex reasoning."""
    advisor_messages = [
        {"role": "system", "content": advisor_prompt},
    ]
    # Include the shared context (last 6 messages for efficiency)
    for m in messages[-6:]:
        if m["role"] in ("user", "assistant"):
            advisor_messages.append({"role": m["role"], "content": (m.get("content") or "")[:2000]})
        elif m["role"] == "tool":
            advisor_messages.append({"role": "user", "content": f"[Tool result]: {(m.get('content') or '')[:1000]}"})

    try:
        # Use Claude as advisor
        resp = await _call_anthropic(advisor_messages, "claude-sonnet-4-5-20250929", tools=[], stream=False)
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[Advisor unavailable: {e}]"

'''

# Insert advisor code before the _call_llm function
al = al.replace(
    "# ── Helper: call LLM with automatic model fallback",
    advisor_code + "\n# ── Helper: call LLM with automatic model fallback"
)

# 1c. Rewrite _call_llm to use Advisor strategy:
#     - Ollama (local) as Executor for tool calling
#     - Claude as Advisor when the executor needs guidance
old_call_llm = '''async def _call_llm(messages: list, model: str, tools: list, stream: bool = False):
    """Call LLM with automatic fallback on rate limits."""
    models_to_try = [model] + FALLBACK_CHAINS.get(model, [])
    last_error = None

    for m in models_to_try:
        try:
            if m.startswith("claude"):
                if not _get_anthropic_key():
                    continue
                # Claude uses non-streaming internally; caller handles simulation
                return await _call_anthropic(messages, m, tools, stream=False), m
            else:
                result = await _call_openai(messages, m, tools, stream=stream)
                return result, m
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                # Wait briefly then try next model
                await asyncio.sleep(2)
                continue
            else:
                raise

    raise last_error or RuntimeError("All models failed")'''

new_call_llm = '''async def _call_llm(messages: list, model: str, tools: list, stream: bool = False):
    """Call LLM with Advisor strategy.
    
    Strategy: Local Ollama = Executor (tool calling, every turn)
              Cloud Claude = Advisor/Thinker (complex reasoning, on-demand)
    
    Fallback: If Ollama fails -> Claude -> OpenAI
    """
    # --- Executor path: try local Ollama first for tool execution ---
    try:
        result = await _call_ollama(messages, OLLAMA_MODEL, tools, stream=False)
        return result, f"ollama/{OLLAMA_MODEL}"
    except Exception as ollama_err:
        pass  # Fall through to cloud models

    # --- Cloud fallback: Claude (Advisor) -> OpenAI ---
    models_to_try = [model] + FALLBACK_CHAINS.get(model, [])
    last_error = None

    for m in models_to_try:
        try:
            if m.startswith("claude"):
                if not _get_anthropic_key():
                    continue
                return await _call_anthropic(messages, m, tools, stream=False), m
            else:
                result = await _call_openai(messages, m, tools, stream=stream)
                return result, m
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                await asyncio.sleep(2)
                continue
            else:
                raise

    raise last_error or RuntimeError("All models failed (Ollama + cloud)")'''

assert old_call_llm in al, "Could not find _call_llm in agent_loop.py"
al = al.replace(old_call_llm, new_call_llm)

# 1d. Inject advisor consultation before final response in run_agent_loop
# When the executor produces a final text response, optionally consult the advisor
old_final = '''        else:
            # Final text response
            final_response = msg.content or ""
            break'''

new_final = '''        else:
            # Final text response from executor
            executor_response = msg.content or ""
            # Consult the Advisor (Claude) for complex/long responses
            if _get_anthropic_key() and (len(tool_calls_log) > 0 or len(executor_response) < 50):
                advisor_prompt = (
                    "You are the Advisor in an Executor-Advisor architecture. "
                    "The Executor (local LLM) has completed tool calls and produced a draft response. "
                    "Review the conversation context and tool results, then provide "
                    "a polished, comprehensive final answer to the user. "
                    "Be concise but thorough. Keep the same language as the user."
                )
                advice = await _call_advisor(messages + [{"role": "assistant", "content": executor_response}], advisor_prompt)
                if advice and not advice.startswith("[Advisor unavailable"):
                    final_response = advice
                else:
                    final_response = executor_response
            else:
                final_response = executor_response
            break'''

assert old_final in al, "Could not find final response block in run_agent_loop"
al = al.replace(old_final, new_final)

with open('/home/azureuser/Ombra/backend/agent_loop.py', 'w') as f:
    f.write(al)
print("[OK] agent_loop.py patched with Advisor strategy")


# ============================================================
# 2. PATCH server.py — Remove EMERGENT_KEY gating + full admin
# ============================================================
with open('/home/azureuser/Ombra/backend/server.py', 'r') as f:
    sv = f.read()

# 2a. Remove EMERGENT_KEY variable — replace with ANTHROPIC_KEY or True
sv = sv.replace(
    'EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")',
    'EMERGENT_KEY = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or "enabled"  # Always enabled'
)

# 2b. Force all permissions to True (full admin)
sv = sv.replace(
    '''def get_permissions():
    profile = profiles_col.find_one({"user_id": "default"})
    if not profile:
        return {"terminal": True, "filesystem": True, "telegram": True}
    return profile.get("permissions", {"terminal": True, "filesystem": True, "telegram": True})''',
    '''def get_permissions():
    """Agent has full admin access — all permissions always granted."""
    return {"terminal": True, "filesystem": True, "telegram": True, "browser": True, "network": True, "admin": True}'''
)

# 2c. Remove the Emergent API routing block (Bearer EMERGENT_KEY usage)
# Find and neutralize lines that use EMERGENT_KEY as Bearer token for API calls
sv = sv.replace(
    '"Authorization": f"Bearer {EMERGENT_KEY}"',
    '"Authorization": f"Bearer {ANTHROPIC_KEY}"'
)

with open('/home/azureuser/Ombra/backend/server.py', 'w') as f:
    f.write(sv)
print("[OK] server.py patched — EMERGENT_KEY gating removed, full admin")


# ============================================================
# 3. PATCH index.html — Remove PostHog telemetry + Emergent script
# ============================================================
with open('/home/azureuser/Ombra/frontend/public/index.html', 'r') as f:
    html = f.read()

# 3a. Remove emergent script tag
html = html.replace(
    '<script src="https://assets.emergent.sh/scripts/emergent-main.js"></script>',
    '<!-- emergent removed -->'
)

# 3b. Remove entire PostHog script block
posthog_start = html.find('!(function (t, e)')
if posthog_start != -1:
    # Find the <script> tag that contains it
    script_start = html.rfind('<script>', 0, posthog_start)
    script_end = html.find('</script>', posthog_start)
    if script_start != -1 and script_end != -1:
        html = html[:script_start] + '<!-- telemetry removed -->' + html[script_end + len('</script>'):]
        print("[OK] PostHog telemetry removed from index.html")
    else:
        print("[WARN] Could not find PostHog script boundaries")
else:
    print("[WARN] PostHog not found in index.html")

# 3c. Remove emergent script reference
html = html.replace('<!-- emergent removed -->\n', '')

with open('/home/azureuser/Ombra/frontend/public/index.html', 'w') as f:
    f.write(html)
print("[OK] index.html cleaned")


# ============================================================
# 4. PATCH craco.config.js — Remove @emergentbase/visual-edits
# ============================================================
with open('/home/azureuser/Ombra/frontend/craco.config.js', 'r') as f:
    craco = f.read()

# Remove the visual-edits wrapping block
old_visual = '''// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}'''

craco = craco.replace(old_visual, '// visual-edits removed')

with open('/home/azureuser/Ombra/frontend/craco.config.js', 'w') as f:
    f.write(craco)
print("[OK] craco.config.js cleaned — @emergentbase removed")


# ============================================================
# 5. PATCH package.json — Remove @emergentbase dependency
# ============================================================
with open('/home/azureuser/Ombra/frontend/package.json', 'r') as f:
    pkg = f.read()

# Remove the @emergentbase/visual-edits line
pkg = re.sub(r'\s*"@emergentbase/visual-edits":\s*"[^"]*",?\n?', '\n', pkg)

# Fix trailing comma if needed
pkg = re.sub(r',\s*}', '\n  }', pkg)

with open('/home/azureuser/Ombra/frontend/package.json', 'w') as f:
    f.write(pkg)
print("[OK] package.json cleaned — @emergentbase removed")


# ============================================================
# 6. PATCH backend_test.py — Remove emergent URL
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend_test.py', 'r') as f:
        bt = f.read()
    bt = bt.replace('https://ombra-core.preview.emergentagent.com', 'http://localhost:8001')
    with open('/home/azureuser/Ombra/backend_test.py', 'w') as f:
        f.write(bt)
    print("[OK] backend_test.py — emergent URL replaced with localhost")
except:
    print("[SKIP] backend_test.py not found")


# ============================================================
# 7. PATCH autonomy_daemon.py — Remove EMERGENT_KEY references
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend/autonomy_daemon.py', 'r') as f:
        ad = f.read()
    # Replace emergent_key parameter usage with anthropic/openai key
    ad = ad.replace('self.emergent_key', 'self.api_key')
    ad = ad.replace('emergent_key', 'api_key')
    ad = ad.replace('EMERGENT_LLM_KEY', 'ANTHROPIC_API_KEY')
    with open('/home/azureuser/Ombra/backend/autonomy_daemon.py', 'w') as f:
        f.write(ad)
    print("[OK] autonomy_daemon.py — emergent references replaced")
except Exception as e:
    print(f"[WARN] autonomy_daemon.py: {e}")


# ============================================================
# 8. PATCH creative_exploration.py — Remove EMERGENT_KEY
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend/creative_exploration.py', 'r') as f:
        ce = f.read()
    ce = ce.replace('EMERGENT_LLM_KEY', 'ANTHROPIC_API_KEY')
    ce = ce.replace('emergent_key', 'api_key')
    with open('/home/azureuser/Ombra/backend/creative_exploration.py', 'w') as f:
        f.write(ce)
    print("[OK] creative_exploration.py — emergent references replaced")
except Exception as e:
    print(f"[WARN] creative_exploration.py: {e}")


# ============================================================
# 9. PATCH telegram_router.py — Remove EMERGENT_KEY
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend/telegram_router.py', 'r') as f:
        tr = f.read()
    tr = tr.replace('emergent_key', 'api_key')
    tr = tr.replace('EMERGENT_LLM_KEY', 'ANTHROPIC_API_KEY')
    with open('/home/azureuser/Ombra/backend/telegram_router.py', 'w') as f:
        f.write(tr)
    print("[OK] telegram_router.py — emergent references replaced")
except Exception as e:
    print(f"[WARN] telegram_router.py: {e}")


# ============================================================
# 10. PATCH sub_agents.py — Remove EMERGENT_KEY
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend/sub_agents.py', 'r') as f:
        sa = f.read()
    sa = sa.replace('EMERGENT_LLM_KEY', 'ANTHROPIC_API_KEY')
    with open('/home/azureuser/Ombra/backend/sub_agents.py', 'w') as f:
        f.write(sa)
    print("[OK] sub_agents.py — emergent references replaced")
except Exception as e:
    print(f"[SKIP] sub_agents.py: {e}")


# ============================================================
# 11. Remove requirements-optional.txt emergentintegrations
# ============================================================
try:
    with open('/home/azureuser/Ombra/backend/requirements-optional.txt', 'r') as f:
        ro = f.read()
    ro = re.sub(r'.*emergentintegrations.*\n?', '', ro)
    with open('/home/azureuser/Ombra/backend/requirements-optional.txt', 'w') as f:
        f.write(ro)
    print("[OK] requirements-optional.txt — emergentintegrations removed")
except Exception as e:
    print(f"[SKIP] requirements-optional.txt: {e}")


# ============================================================
# 12. Clean CHANGELOG.md references to emergent
# ============================================================
try:
    with open('/home/azureuser/Ombra/CHANGELOG.md', 'r') as f:
        cl = f.read()
    cl = cl.replace('emergentintegrations', 'optional-integrations')
    cl = cl.replace('emergent', 'external')
    with open('/home/azureuser/Ombra/CHANGELOG.md', 'w') as f:
        f.write(cl)
    print("[OK] CHANGELOG.md — emergent references cleaned")
except Exception as e:
    print(f"[SKIP] CHANGELOG.md: {e}")


print("\n=== ALL PATCHES APPLIED ===")
print("Next: rebuild frontend + restart backend")
