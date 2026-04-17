import os
import json
import asyncio
import subprocess
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING, TEXT
from bson import ObjectId
import httpx
try:
    from sse_starlette.sse import EventSourceResponse
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False

load_dotenv()

# Token cost table (per 1M tokens)
MODEL_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "tinyllama": {"input": 0, "output": 0},
    "mistral": {"input": 0, "output": 0},
}

# Module imports
from agents import BUILTIN_AGENTS, classify_task_for_agent
from ombra_k1 import (
    MODEL_RECOMMENDATIONS, DEFAULT_PROMPTS, select_best_prompt,
    categorize_message, generate_teacher_distillation
)
from self_improve import (
    calculate_provider_performance, suggest_routing_adjustments,
    update_prompt_performance
)
from telegram_bot import (
    send_telegram_message, get_bot_info,
    format_daily_summary, format_task_list
)
from filesystem_tool import read_file, write_file, list_directory
try:
    from agent_loop import run_agent_loop, stream_agent_loop
    AGENT_LOOP_AVAILABLE = True
except ImportError:
    AGENT_LOOP_AVAILABLE = False
from tool_safety import redact_secrets, check_command_policy, create_safe_env, DEFAULT_DENYLIST, DEFAULT_ALLOWLIST
from autonomy_daemon import AutonomyDaemon
from telegram_router import TelegramRouter
from scheduler import TaskScheduler
from task_queue import TaskQueue
from creative_exploration import CreativeExplorer
from workspace_loader import (
    build_system_prompt, get_active_skill_ids,
    detect_skills_for_message, list_skills, load_skill,
    install_skill, delete_skill, load_soul
)

# New module imports
from plugin_hooks import hook_manager, register_default_hooks
from streaming import stream_manager, StreamEventType, sse_generator
from security_tools import (
    scan_ports, check_ssl, audit_system, analyze_logs,
    check_dns, check_http_headers, compute_file_hashes,
    check_file_integrity, scan_dependencies, lookup_ip_reputation,
    full_security_scan, whois_lookup, enumerate_subdomains,
    fingerprint_technology, run_traceroute, grab_banners, wayback_lookup
)

# Load persistent .env file (survives restarts, written by set_claude_key etc.)
_ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ombra_db")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# OAuth email configuration (no longer needed — using app passwords)
# GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
# GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
# MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
# OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "")

# MongoDB
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
conversations_col = db["conversations"]
memories_col = db["memories"]
profiles_col = db["user_profiles"]
activity_col = db["activity_log"]
tasks_col = db["tasks"]
settings_col = db["settings"]
agents_col = db["agents"]
prompts_col = db["k1_prompts"]
feedback_col = db["feedback"]
learning_col = db["learning_changes"]
distillation_col = db["k1_distillations"]
tool_policies_col = db["tool_policies"]
webhooks_col = db["webhooks"]
email_drafts_col = db["email_drafts"]

# Daemons (initialized in lifespan)
autonomy_daemon = None
telegram_router = None
task_scheduler = None
task_queue = None
creative_explorer = None


# ============================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws) if hasattr(self.active, 'discard') else None
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_typing(self, session_id: str, is_typing: bool):
        await self.broadcast({"type": "typing", "session_id": session_id, "typing": is_typing})

    async def send_event(self, event_type: str, data: dict):
        await self.broadcast({"type": event_type, **data})


ws_manager = ConnectionManager()


# ============================================================
# TOKEN + USAGE UTILITIES
# ============================================================
def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken if available, else rough estimate."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost in USD for a given model and token counts."""
    model_key = next((k for k in MODEL_COSTS if k in (model or "").lower()), None)
    if not model_key:
        return 0.0
    rates = MODEL_COSTS[model_key]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def prune_conversation(turns: list, max_tokens: int = 12000) -> list:
    """
    Trim oldest turns until total estimated tokens is under max_tokens.
    Always keeps the first turn (context) and last 2 turns.
    """
    if not turns:
        return turns
    total = sum(estimate_tokens(t.get("content", "")) for t in turns)
    if total <= max_tokens:
        return turns
    # Keep compacted system turns, trim from index 1
    result = [t for t in turns if t.get("compacted")]
    normal = [t for t in turns if not t.get("compacted")]
    while normal and sum(estimate_tokens(t.get("content", "")) for t in result + normal) > max_tokens:
        if len(normal) > 4:
            normal.pop(0)  # drop oldest normal turn
        else:
            break
    pruned = result + normal
    if len(pruned) < len(turns):
        db["activity_log"].insert_one({
            "type": "session_pruned",
            "details": {"turns_removed": len(turns) - len(pruned), "original": len(turns)},
            "duration_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return pruned

# Create indexes
try:
    memories_col.create_index([("content", TEXT)])
    memories_col.create_index([("type", 1), ("created_at", DESCENDING)])
    activity_col.create_index([("timestamp", DESCENDING)])
    activity_col.create_index([("type", 1), ("timestamp", DESCENDING)])
    conversations_col.create_index([("session_id", 1)])
    agents_col.create_index([("agent_id", 1)], unique=True)
    feedback_col.create_index([("timestamp", DESCENDING)])
    tasks_col.create_index([("status", 1), ("created_at", DESCENDING)])
except Exception:
    pass


def serialize_doc(doc):
    if doc is None:
        return None
    doc = dict(doc)
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, list):
            doc[key] = [serialize_doc(v) if isinstance(v, dict) else (str(v) if isinstance(v, ObjectId) else v) for v in value]
        elif isinstance(value, dict):
            doc[key] = serialize_doc(value)
    return doc


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log_activity(activity_type, details, duration_ms=0):
    entry = {
        "type": activity_type,
        "details": details,
        "duration_ms": duration_ms,
        "timestamp": now_iso()
    }
    activity_col.insert_one(entry)
    return entry


# ============================================================
# MODEL ROUTER (Enhanced with K1 + Self-Improving)
# ============================================================
def score_complexity(message: str) -> dict:
    score = 0
    reasons = []
    word_count = len(message.split())

    if word_count > 100:
        score += 3
        reasons.append(f"long_message({word_count} words)")
    elif word_count > 30:
        score += 1
        reasons.append(f"medium_message({word_count} words)")

    complex_keywords = ["analyze", "compare", "explain", "plan", "design", "debug", "refactor",
                        "strategy", "architecture", "optimize", "implement", "evaluate", "research"]
    simple_keywords = ["hi", "hello", "thanks", "yes", "no", "ok", "hey", "bye"]

    lower_msg = message.lower()
    for kw in complex_keywords:
        if kw in lower_msg:
            score += 2
            reasons.append(f"complex_keyword({kw})")

    for kw in simple_keywords:
        if lower_msg.strip() == kw:
            score -= 2
            reasons.append(f"simple_keyword({kw})")

    if "?" in message and any(w in lower_msg for w in ["why", "how", "what if", "could you"]):
        score += 1
        reasons.append("complex_question")

    if len(message) > 500:
        score += 2
        reasons.append("very_long_input")

    score = max(0, score)

    if score >= 5:
        route = "api"
        provider = "anthropic"
    elif score >= 3:
        route = "api"
        provider = "openai"
    else:
        route = "local"
        provider = "ollama"

    return {
        "score": score,
        "reasons": reasons,
        "route": route,
        "suggested_provider": provider
    }


async def check_ollama_health():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                # Sort by size ascending so smallest/fastest model is used first
                models_sorted = sorted(models, key=lambda m: m.get("size", 0))
                return {"available": True, "models": [m["name"] for m in models_sorted]}
    except Exception:
        pass
    return {"available": False, "models": []}


async def call_ollama(prompt: str, system_message: str = "", model: str = "tinyllama"):
    # Resolve best available model if not specified
    if not model:
        status = await check_ollama_health()
        model = status["models"][0] if status.get("models") else "tinyllama"
    full_prompt = f"{system_message}\n\nUser: {prompt}\nAssistant:" if system_message else prompt
    async with httpx.AsyncClient(timeout=120) as c:
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"num_predict": 500, "temperature": 0.7}
        }
        resp = await c.post(f"{OLLAMA_URL}/api/generate", json=payload)
        data = resp.json()
        return data.get("response", "")


async def call_api_provider(prompt: str, system_message: str, provider: str, model: str):
    """Call external API provider with exponential backoff retry (max 3 attempts)."""
    provider_models = {
        "openai": "gpt-4o",
        "anthropic": "claude-3-5-sonnet-20241022",
        "gemini": "gemini-2.0-flash"
    }
    actual_model = model or provider_models.get(provider, "gpt-4o")

    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            if provider == "openai" or not provider:
                async with httpx.AsyncClient(timeout=60) as c:
                    resp = await c.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {EMERGENT_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": actual_model,
                            "messages": [
                                {"role": "system", "content": system_message or "You are Ombra, an intelligent autonomous AI assistant."},
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": 1000,
                            "temperature": 0.7
                        }
                    )
                    data = resp.json()
                    if "error" in data:
                        err_msg = data['error'].get('message', str(data['error']))
                        # Don't retry auth errors
                        if "invalid_api_key" in err_msg.lower() or "unauthorized" in err_msg.lower():
                            raise Exception(f"OpenAI error: {err_msg}")
                        raise Exception(f"OpenAI error: {err_msg}")
                    return data["choices"][0]["message"]["content"]

            elif provider == "anthropic":
                anthropic_key = ANTHROPIC_KEY or EMERGENT_KEY
                if not anthropic_key:
                    raise Exception("No Anthropic API key configured (ANTHROPIC_API_KEY or EMERGENT_LLM_KEY)")
                async with httpx.AsyncClient(timeout=60) as c:
                    resp = await c.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": anthropic_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": actual_model,
                            "max_tokens": 1000,
                            "system": system_message or "You are Ombra, an intelligent autonomous AI assistant.",
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    data = resp.json()
                    if "error" in data:
                        raise Exception(f"Anthropic error: {data['error'].get('message', str(data['error']))}")
                    return data["content"][0]["text"]

            else:
                raise Exception(f"Unsupported provider: {provider}")

        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                await asyncio.sleep(delay)
                continue
            raise


async def route_and_respond(message: str, system_message: str = "", conversation_context: str = "",
                            force_provider: str = None, agent_id: str = None,
                            active_skills: list = None, thinking_level: str = "low"):
    start_time = time.time()
    routing = score_complexity(message)

    # K1: Select best prompt based on message category
    category = categorize_message(message)
    k1_prompts = list(prompts_col.find({"active": True}))
    if not k1_prompts:
        k1_prompts = DEFAULT_PROMPTS
    best_prompt = select_best_prompt(category, k1_prompts)

    sys_msg = system_message or best_prompt.get("system_prompt",
        "You are Ombra, an intelligent autonomous AI assistant.")

    # Agent-specific system prompt
    if agent_id and agent_id != "auto":
        agent = agents_col.find_one({"agent_id": agent_id})
        if agent:
            sys_msg = agent.get("system_prompt", sys_msg)
            if agent.get("provider_preference"):
                force_provider = agent["provider_preference"]

    # Auto-detect relevant skills from the message
    skill_ids = active_skills or detect_skills_for_message(message)
    # Also include any globally-activated skills
    global_skills = get_active_skill_ids(db)
    all_skills = list(dict.fromkeys(global_skills + skill_ids))  # deduplicate, preserve order

    # Inject SOUL.md + active skills into system prompt (OpenClaw-style workspace injection)
    sys_msg = build_system_prompt(sys_msg, active_skill_ids=all_skills)

    if conversation_context:
        sys_msg += f"\n\nRecent conversation context:\n{conversation_context}"

    # Apply thinking level (affects temperature + instruction style)
    if thinking_level == "high":
        sys_msg += "\n\nThink carefully and thoroughly before responding. Show your reasoning step by step."
    elif thinking_level == "medium":
        sys_msg += "\n\nThink through this before responding."
    # "low" and "off" use default behavior

    # Retrieve relevant memories with scoring
    try:
        relevant_memories = list(memories_col.find(
            {"$text": {"$search": message[:100]}}
        ).sort("utility_score", DESCENDING).limit(5))
        if relevant_memories:
            memory_context = "\n".join([m.get("content", "") for m in relevant_memories])
            sys_msg += f"\n\nRelevant memories:\n{memory_context}"
            # Update access counts
            for m in relevant_memories:
                memories_col.update_one(
                    {"_id": m["_id"]},
                    {"$inc": {"access_count": 1}, "$set": {"last_accessed_at": now_iso()}}
                )
    except Exception:
        pass

    provider_used = force_provider or routing["suggested_provider"]
    model_used = ""
    response_text = ""
    fallback_chain = []
    used_cloud = False

    if force_provider:
        routing["route"] = "api" if force_provider != "ollama" else "local"
        routing["suggested_provider"] = force_provider

    # Try routing
    if routing["route"] == "local" or provider_used == "ollama":
        try:
            ollama_status = await check_ollama_health()
            if ollama_status["available"] and ollama_status["models"]:
                model_used = ollama_status["models"][0]
                response_text = await call_ollama(message, sys_msg, model_used)
                provider_used = "ollama"
                fallback_chain.append({"provider": "ollama", "success": True})
            else:
                fallback_chain.append({"provider": "ollama", "success": False, "reason": "not available"})
                raise Exception("Ollama not available")
        except Exception as e:
            if not fallback_chain:
                fallback_chain.append({"provider": "ollama", "success": False, "reason": str(e)})
            for fp in ["anthropic", "openai", "gemini"]:
                try:
                    response_text = await call_api_provider(message, sys_msg, fp, None)
                    provider_used = fp
                    model_used = {"anthropic": "claude-sonnet-4-5-20250929", "openai": "gpt-4o", "gemini": "gemini-2.5-flash"}.get(fp)
                    fallback_chain.append({"provider": fp, "success": True})
                    used_cloud = True
                    break
                except Exception as e2:
                    fallback_chain.append({"provider": fp, "success": False, "reason": str(e2)})
    else:
        api_chain = [provider_used] + [p for p in ["anthropic", "openai", "gemini"] if p != provider_used]
        for fp in api_chain:
            try:
                response_text = await call_api_provider(message, sys_msg, fp, None)
                provider_used = fp
                model_used = {"anthropic": "claude-sonnet-4-5-20250929", "openai": "gpt-4o", "gemini": "gemini-2.5-flash"}.get(fp)
                fallback_chain.append({"provider": fp, "success": True})
                used_cloud = True
                break
            except Exception as e:
                fallback_chain.append({"provider": fp, "success": False, "reason": str(e)})

    duration_ms = int((time.time() - start_time) * 1000)

    # Usage tracking
    input_tokens = estimate_tokens(sys_msg + message)
    output_tokens = estimate_tokens(response_text) if response_text else 0
    cost_usd = calculate_cost(input_tokens, output_tokens, model_used or "")

    # K1 Teacher-Student: If cloud was used, distill the response
    if used_cloud and response_text:
        task_sig = categorize_message(message) + ":" + message[:50]
        distillation = generate_teacher_distillation(response_text, task_sig)
        distillation["provider"] = provider_used
        distillation["model"] = model_used
        distillation_col.insert_one(distillation)
        log_activity("k1_learning", {
            "event": "teacher_distillation",
            "provider": provider_used,
            "task_category": category,
            "rules_extracted": len(distillation.get("extracted_rules", []))
        })

    # Update K1 prompt usage
    if best_prompt.get("prompt_id"):
        prompts_col.update_one(
            {"prompt_id": best_prompt["prompt_id"]},
            {"$inc": {"usage_count": 1}, "$set": {"updated_at": now_iso()}}
        )

    result = {
        "response": response_text or "I apologize, but I couldn't generate a response. All providers failed.",
        "routing": routing,
        "provider_used": provider_used,
        "model_used": model_used,
        "fallback_chain": fallback_chain,
        "duration_ms": duration_ms,
        "k1_prompt_used": best_prompt.get("prompt_id", "default"),
        "category": category,
        "agent_id": agent_id,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost_usd, 6),
        }
    }

    log_activity("model_call", {
        "provider": provider_used,
        "model": model_used,
        "routing_score": routing["score"],
        "routing_reasons": routing["reasons"],
        "input_preview": message[:100],
        "output_preview": response_text[:200] if response_text else "",
        "fallback_chain": fallback_chain,
        "k1_prompt": best_prompt.get("prompt_id"),
        "agent_id": agent_id
    }, duration_ms)

    return result


async def stream_route_and_respond(message: str, sys_msg: str, model_used: str,
                                    provider_used: str, ollama_available: bool):
    """
    Generator that streams tokens. Tries Ollama stream first, then OpenAI stream.
    Yields JSON-lines: {"token": "..."} or {"done": true, "usage": {...}}
    """
    import json as _json
    start = time.time()
    full_response = ""

    if ollama_available and (not provider_used or provider_used == "ollama"):
        try:
            full_prompt = f"{sys_msg}\n\nUser: {message}\nAssistant:" if sys_msg else message
            async with httpx.AsyncClient(timeout=120) as c:
                async with c.stream("POST", f"{OLLAMA_URL}/api/generate", json={
                    "model": model_used or "tinyllama",
                    "prompt": full_prompt,
                    "stream": True,
                    "options": {"num_predict": 500, "temperature": 0.7}
                }) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = _json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                full_response += token
                                yield f"data: {_json.dumps({'token': token})}\n\n"
                            if chunk.get("done"):
                                break
                        except Exception:
                            pass
        except Exception:
            pass

    elif EMERGENT_KEY and provider_used in (None, "openai", "api"):
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                async with c.stream("POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {EMERGENT_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": sys_msg or "You are Ombra."},
                            {"role": "user", "content": message}
                        ],
                        "max_tokens": 800,
                        "temperature": 0.7,
                        "stream": True
                    }
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = _json.loads(raw)
                            token = chunk["choices"][0]["delta"].get("content", "")
                            if token:
                                full_response += token
                                yield f"data: {_json.dumps({'token': token})}\n\n"
                        except Exception:
                            pass
        except Exception:
            pass

    if not full_response:
        full_response = "I couldn't generate a response."
        yield f"data: {_json.dumps({'token': full_response})}\n\n"

    input_tokens = estimate_tokens(sys_msg + message)
    output_tokens = estimate_tokens(full_response)
    cost = calculate_cost(input_tokens, output_tokens, model_used or "")
    duration_ms = int((time.time() - start) * 1000)

    yield f"data: {_json.dumps({'done': True, 'full_response': full_response, 'duration_ms': duration_ms, 'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'total_tokens': input_tokens + output_tokens, 'cost_usd': round(cost, 6)}})}\n\n"


# ============================================================
# LEARNING SYSTEM (Enhanced)
# ============================================================
async def extract_and_learn(user_message: str, assistant_response: str, session_id: str):
    try:
        lower = user_message.lower()

        # Pattern-based fast extraction for key personal facts
        pref_patterns = [
            ("i prefer", "preference"), ("i like", "preference"),
            ("i don't like", "preference"), ("i always", "habit"),
            ("i usually", "habit"), ("my name is", "identity"),
            ("i work", "context"), ("i'm working on", "context"),
            ("i am ", "identity"), ("my project", "context"),
            ("remember that", "explicit"), ("don't forget", "explicit"),
        ]

        stored = False
        for pattern, mem_type in pref_patterns:
            if pattern in lower:
                # Use Ollama to extract the actual fact, not raw message
                try:
                    fact = await call_ollama(
                        f"Extract the key fact or preference from this message in one short sentence: \"{user_message[:200]}\"",
                        system="Extract only the factual information. Be concise. No explanation.",
                        model=None  # uses first available
                    )
                    content = fact.strip() if fact.strip() else user_message[:200]
                except Exception:
                    content = user_message[:200]

                memories_col.insert_one({
                    "type": mem_type,
                    "content": content,
                    "source": "conversation",
                    "session_id": session_id,
                    "utility_score": 0.85,
                    "access_count": 0,
                    "pinned": False,
                    "decay_rate": 0.005,
                    "last_accessed_at": now_iso(),
                    "created_at": now_iso()
                })
                log_activity("memory_write", {
                    "memory_type": mem_type,
                    "content_preview": content[:80],
                    "source": "learning_extraction"
                })
                stored = True
                break

        # Every 5 turns, ask Ollama to extract any learnable facts from the exchange
        conversation = conversations_col.find_one({"session_id": session_id})
        turn_count = len(conversation.get("turns", [])) if conversation else 0
        if turn_count > 0 and turn_count % 5 == 0:
            try:
                facts = await call_ollama(
                    f"User said: \"{user_message[:300]}\"\nAssistant replied: \"{assistant_response[:300]}\"\n\nList any facts about the user worth remembering (max 2 bullet points, or say NONE):",
                    system="You extract useful personal facts, preferences, or context about the user from conversations. Be concise.",
                    model=None
                )
                if facts and "NONE" not in facts.upper() and len(facts.strip()) > 10:
                    memories_col.insert_one({
                        "type": "conversation_fact",
                        "content": facts.strip()[:400],
                        "source": "ai_extraction",
                        "session_id": session_id,
                        "utility_score": 0.7,
                        "access_count": 0,
                        "pinned": False,
                        "decay_rate": 0.01,
                        "last_accessed_at": now_iso(),
                        "created_at": now_iso()
                    })
                    log_activity("memory_write", {
                        "memory_type": "conversation_fact",
                        "content_preview": facts[:80],
                        "source": "ai_extraction"
                    })
            except Exception:
                pass

        # Summary every 10 turns
        if turn_count > 0 and turn_count % 10 == 0:
            try:
                summary = await call_ollama(
                    f"Summarize the main topic and outcome of this conversation turn in one sentence. User: \"{user_message[:200]}\"",
                    system="Write a factual one-sentence summary.",
                    model=None
                )
                content = summary.strip() if summary.strip() else f"Conversation about: {user_message[:100]}"
            except Exception:
                content = f"Conversation about: {user_message[:100]}"
            memories_col.insert_one({
                "type": "conversation_summary",
                "content": content,
                "source": "auto_summary",
                "session_id": session_id,
                "utility_score": 0.6,
                "access_count": 0,
                "pinned": False,
                "decay_rate": 0.02,
                "last_accessed_at": now_iso(),
                "created_at": now_iso()
            })
    except Exception:
        pass


# ============================================================
# TOOL SYSTEM (Enhanced with Filesystem)
# ============================================================
def get_permissions():
    profile = profiles_col.find_one({"user_id": "default"})
    if not profile:
        return {"terminal": True, "filesystem": True, "telegram": True}
    return profile.get("permissions", {"terminal": True, "filesystem": True, "telegram": True})


def execute_terminal_command(command: str, timeout: int = 30):
    perms = get_permissions()
    if not perms.get("terminal", False):
        return {"success": False, "error": "Permission denied: terminal access not granted", "requires_permission": "terminal"}

    # Load policies
    policies = tool_policies_col.find_one({"user_id": "default"}) or {}
    policy_check = check_command_policy(command, policies)
    if not policy_check["allowed"]:
        log_activity("tool_blocked", {
            "tool": "terminal", "command": command,
            "reason": policy_check["reason"], "severity": policy_check["severity"]
        })
        return {"success": False, "error": f"Blocked: {policy_check['reason']}", "severity": policy_check["severity"]}

    try:
        safe_env = create_safe_env()
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            cwd="/tmp", env=safe_env
        )
        # Redact secrets from output
        stdout = redact_secrets(result.stdout[:2000])
        stderr = redact_secrets(result.stderr[:1000])

        output = {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "command": command
        }

        log_activity("tool_execution", {
            "tool": "terminal",
            "command": command,
            "success": output["success"],
            "output_preview": redact_secrets((result.stdout[:200] or result.stderr[:200]))
        })

        return output
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# PYDANTIC MODELS
# ============================================================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    force_provider: Optional[str] = None
    white_card_mode: bool = False
    agent_id: Optional[str] = None
    enable_tools: Optional[bool] = None  # None = auto-detect from permissions

class PermissionUpdate(BaseModel):
    terminal: Optional[bool] = None
    filesystem: Optional[bool] = None
    telegram: Optional[bool] = None

class SettingsUpdate(BaseModel):
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    learning_enabled: Optional[bool] = None
    white_card_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    hardware_ram: Optional[str] = None
    morning_summary_hour_utc: Optional[int] = None
    email_host: Optional[str] = None
    email_port: Optional[int] = None
    email_user: Optional[str] = None
    email_pass: Optional[str] = None
    email_from: Optional[str] = None
    email_enabled: Optional[bool] = None

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"

class TerminalRequest(BaseModel):
    command: str
    timeout: Optional[int] = 30

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    system_prompt: str
    tools_allowed: Optional[List[str]] = []
    provider_preference: Optional[str] = "auto"
    temperature: Optional[float] = 0.5
    icon: Optional[str] = "bot"
    color: Optional[str] = "#888888"

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools_allowed: Optional[List[str]] = None
    provider_preference: Optional[str] = None
    temperature: Optional[float] = None
    icon: Optional[str] = None
    color: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    message_index: int
    feedback: str  # "positive" or "negative"
    comment: Optional[str] = ""

class GoalPlanRequest(BaseModel):
    goal: str
    context: Optional[str] = ""

class FileReadRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    path: str
    content: str

class TelegramSendRequest(BaseModel):
    chat_id: str
    message: str

class OllamaPullRequest(BaseModel):
    model_name: str


# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global autonomy_daemon, telegram_router, task_scheduler, task_queue, creative_explorer

    # Initialize default profile
    if not profiles_col.find_one({"user_id": "default"}):
        profiles_col.insert_one({
            "user_id": "default", "name": "User",
            "preferences": {"theme": "dark", "language": "en"},
            "permissions": {"terminal": False, "filesystem": False, "telegram": False},
            "onboarded": False,
            "created_at": now_iso(), "updated_at": now_iso()
        })

    if not settings_col.find_one({"user_id": "default"}):
        settings_col.insert_one({
            "user_id": "default",
            "ollama_url": OLLAMA_URL, "ollama_model": "mistral",
            "preferred_provider": "auto", "preferred_model": "",
            "learning_enabled": True, "white_card_enabled": False,
            "quiet_hours_start": "", "quiet_hours_end": "",
            "telegram_chat_id": "", "telegram_enabled": False,
            "hardware_ram": "16gb",
            "creativity_enabled": False, "creativity_cadence_ticks": 5,
            "created_at": now_iso(), "updated_at": now_iso()
        })
    else:
        # Upgrade default model to mistral if still tinyllama
        settings_col.update_one(
            {"user_id": "default", "ollama_model": "tinyllama"},
            {"$set": {"ollama_model": "mistral"}}
        )

    # Seed default tool policies
    if not tool_policies_col.find_one({"user_id": "default"}):
        tool_policies_col.insert_one({
            "user_id": "default",
            "mode": "denylist",
            "denylist": DEFAULT_DENYLIST,
            "allowlist": DEFAULT_ALLOWLIST,
            "created_at": now_iso()
        })

    # Seed builtin agents
    for agent in BUILTIN_AGENTS:
        if not agents_col.find_one({"agent_id": agent["agent_id"]}):
            agent["created_at"] = now_iso()
            agent["updated_at"] = now_iso()
            agents_col.insert_one(agent)

    # Seed K1 prompts
    for prompt in DEFAULT_PROMPTS:
        if not prompts_col.find_one({"prompt_id": prompt["prompt_id"]}):
            prompt["created_at"] = now_iso()
            prompt["updated_at"] = now_iso()
            prompts_col.insert_one(prompt)

    # Start autonomy daemon
    autonomy_daemon = AutonomyDaemon(db, OLLAMA_URL, EMERGENT_KEY)
    daemon_task = asyncio.create_task(autonomy_daemon.start())

    # Start Telegram router if token configured (full chat parity)
    if TELEGRAM_TOKEN:
        telegram_router = TelegramRouter(
            db,
            route_and_respond_fn=route_and_respond,
            get_summary_fn=dashboard_summary,
            run_agent_loop_fn=run_agent_loop if AGENT_LOOP_AVAILABLE else None,
            load_soul_fn=load_soul,
            extract_and_learn_fn=extract_and_learn,
            prune_conversation_fn=prune_conversation,
            get_permissions_fn=get_permissions,
            classify_agent_fn=classify_task_for_agent,
            emergent_key=EMERGENT_KEY,
        )
        tg_task = asyncio.create_task(telegram_router.poll_loop())

    # Start Task Queue with worker pool
    task_queue = TaskQueue(db, execute_task_step)
    await task_queue.start()

    # Start Task Scheduler
    async def enqueue_task(task_id):
        """Callback for scheduler to enqueue tasks."""
        await task_queue.enqueue(task_id)
    
    task_scheduler = TaskScheduler(db, enqueue_task)
    scheduler_task = asyncio.create_task(task_scheduler.start())

    # Start Creative Explorer
    settings = settings_col.find_one({"user_id": "default"}) or {}
    creative_explorer = CreativeExplorer(db, OLLAMA_URL, EMERGENT_KEY)
    creative_explorer.update_settings(
        enabled=settings.get("creativity_enabled", False),
        cadence_ticks=settings.get("creativity_cadence_ticks", 5)
    )

    log_activity("system", {"event": "startup", "message": "Ombra system started (Phase 5: Scheduling + Queue + Creativity)"})

    # Initialize new subsystems
    register_default_hooks()
    log_activity("system", {"event": "hooks_loaded", "message": "Plugin hooks initialized"})

    # Restore persisted MCP servers
    try:
        from mcp_client import mcp_manager as _mcp_restore
        await _mcp_restore.restore_servers()
        mcp_st = _mcp_restore.get_status()
        if mcp_st["total_servers"] > 0:
            log_activity("system", {"event": "mcp_restored", "message": f"Restored {mcp_st['connected']}/{mcp_st['total_servers']} MCP servers ({mcp_st['total_tools']} tools)"})
    except Exception as e:
        log_activity("system", {"event": "mcp_restore_error", "message": str(e)})

    yield

    # Cleanup
    if autonomy_daemon:
        autonomy_daemon.stop()
    if telegram_router:
        telegram_router.stop()
    if task_scheduler:
        task_scheduler.stop()
    if task_queue:
        task_queue.stop()
    log_activity("system", {"event": "shutdown", "message": "Ombra system stopped"})


app = FastAPI(title="Ombra AI Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HEALTH
# ============================================================
@app.get("/api/health")
async def health():
    ollama = await check_ollama_health()
    tg_info = await get_bot_info() if TELEGRAM_TOKEN else {"success": False}
    return {
        "status": "healthy",
        "timestamp": now_iso(),
        "ollama": ollama,
        "mongodb": {"connected": True},
        "api_key_configured": bool(EMERGENT_KEY),
        "telegram": {"configured": bool(TELEGRAM_TOKEN), "bot_info": tg_info.get("bot", {}) if tg_info.get("success") else None}
    }


# ============================================================
# CHAT (Enhanced with Agent + K1 + Chat Commands)
# ============================================================

# Per-session state (thinking level, model override)
_session_state: dict = {}


async def handle_chat_command(cmd: str, session_id: str) -> dict | None:
    """
    Handle /slash commands like OpenClaw. Returns a command response dict or None if not a command.
    """
    cmd = cmd.strip()
    if not cmd.startswith("/"):
        return None

    parts = cmd.split(None, 1)
    command = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    state = _session_state.get(session_id, {})

    if command == "/status":
        ollama = await check_ollama_health()
        mem_count = memories_col.count_documents({})
        task_count = tasks_col.count_documents({"status": "pending"})
        daemon_stats = autonomy_daemon.stats if autonomy_daemon else {}
        thinking = state.get("thinking_level", "low")
        model = state.get("model_override") or (ollama["models"][0] if ollama.get("models") else "none")
        txt = (
            f"**Ombra Status** — session `{session_id}`\n"
            f"Model: {model} | Thinking: {thinking}\n"
            f"Memories: {mem_count} | Pending tasks: {task_count}\n"
            f"Daemon ticks: {daemon_stats.get('ticks', 0)} | "
            f"Autonomous actions: {daemon_stats.get('autonomous_actions', 0)} | "
            f"Internet learns: {daemon_stats.get('internet_learns', 0)}"
        )
        return {"response": txt, "command": "status", "session_id": session_id}

    elif command == "/reset":
        conversations_col.delete_one({"session_id": session_id})
        _session_state.pop(session_id, None)
        return {"response": "Session reset. Starting fresh.", "command": "reset", "session_id": session_id}

    elif command == "/compact":
        conversation = conversations_col.find_one({"session_id": session_id})
        if not conversation or not conversation.get("turns"):
            return {"response": "Nothing to compact.", "command": "compact", "session_id": session_id}
        turns = conversation["turns"]
        full_text = "\n".join(f"{t['role']}: {t['content'][:300]}" for t in turns[-20:])
        try:
            summary = await call_ollama(
                f"Summarize this conversation in 3-5 sentences:\n\n{full_text}",
                system="Write a factual summary of the conversation. Include key decisions, topics, and outcomes.",
                model=None
            )
        except Exception:
            summary = f"Conversation about: {turns[0].get('content', '')[:100]}"
        # Replace turns with a single summary turn
        summary_turn = {
            "role": "system",
            "content": f"[Compacted] {summary}",
            "timestamp": now_iso(),
            "compacted": True
        }
        conversations_col.update_one(
            {"session_id": session_id},
            {"$set": {"turns": [summary_turn], "updated_at": now_iso()}}
        )
        return {"response": f"Conversation compacted.\n\nSummary: {summary}", "command": "compact", "session_id": session_id}

    elif command == "/think":
        level = arg.lower() if arg else "medium"
        if level not in ("off", "low", "medium", "high"):
            return {"response": "Usage: /think <off|low|medium|high>", "command": "think", "session_id": session_id}
        _session_state.setdefault(session_id, {})["thinking_level"] = level
        return {"response": f"Thinking level set to **{level}**.", "command": "think", "session_id": session_id}

    elif command == "/model":
        if not arg:
            return {"response": "Usage: /model <model-name>  e.g. /model mistral", "command": "model", "session_id": session_id}
        _session_state.setdefault(session_id, {})["model_override"] = arg
        return {"response": f"Model override set to **{arg}** for this session.", "command": "model", "session_id": session_id}

    elif command == "/skills":
        skills = list_skills()
        if not skills:
            return {"response": "No skills installed.", "command": "skills", "session_id": session_id}
        active = get_active_skill_ids(db)
        lines = [f"{'✓' if s['id'] in active else '○'} **{s['name']}** (`{s['id']}`): {s['purpose']}" for s in skills]
        return {"response": "**Available Skills:**\n\n" + "\n".join(lines), "command": "skills", "session_id": session_id}

    elif command == "/memory":
        mems = list(memories_col.find().sort("utility_score", -1).limit(10))
        if not mems:
            return {"response": "No memories stored yet.", "command": "memory", "session_id": session_id}
        lines = [f"• [{m.get('type', '?')}] {m.get('content', '')[:120]}" for m in mems]
        return {"response": "**Recent Memories:**\n\n" + "\n".join(lines), "command": "memory", "session_id": session_id}

    elif command == "/verbose":
        flag = arg.lower() if arg else "on"
        _session_state.setdefault(session_id, {})["verbose"] = (flag == "on")
        return {"response": f"Verbose routing info **{'on' if flag == 'on' else 'off'}**.", "command": "verbose", "session_id": session_id}

    elif command == "/trace":
        flag = arg.lower() if arg else "on"
        _session_state.setdefault(session_id, {})["trace"] = (flag == "on")
        return {"response": f"Fallback trace **{'on' if flag == 'on' else 'off'}**.", "command": "trace", "session_id": session_id}

    elif command == "/usage":
        mode = arg.lower() if arg else "tokens"
        if mode not in ("off", "tokens", "full"):
            return {"response": "Usage: /usage <off|tokens|full>", "command": "usage", "session_id": session_id}
        _session_state.setdefault(session_id, {})["usage_display"] = mode
        labels = {"off": "hidden", "tokens": "token count", "full": "tokens + cost"}
        return {"response": f"Usage footer set to **{labels[mode]}**.", "command": "usage", "session_id": session_id}

    elif command == "/cron":
        sub = arg.split(None, 1)
        sub_cmd = sub[0].lower() if sub else "list"
        if sub_cmd == "list":
            crons = list(tasks_col.find({"cron": True}).sort("created_at", -1).limit(10))
            if not crons:
                return {"response": "No cron jobs defined.", "command": "cron", "session_id": session_id}
            lines = [f"• `{c.get('cron_schedule', '?')}` — {c.get('task', '')[:80]}" for c in crons]
            return {"response": "**Cron Jobs:**\n\n" + "\n".join(lines), "command": "cron", "session_id": session_id}
        elif sub_cmd == "add" and len(sub) > 1:
            rest = sub[1].strip()
            # Expect: "schedule" "task description"
            import re as _re
            m = _re.match(r'"([^"]+)"\s+"([^"]+)"', rest)
            if not m:
                return {"response": 'Usage: /cron add "schedule" "task description"\nExample: /cron add "every day at 9am" "summarize recent activity"', "command": "cron", "session_id": session_id}
            sched, task_desc = m.group(1), m.group(2)
            tasks_col.insert_one({
                "task": task_desc,
                "cron": True,
                "cron_schedule": sched,
                "status": "active",
                "created_at": now_iso(),
                "session_id": session_id
            })
            return {"response": f"Cron job added: `{sched}` → {task_desc}", "command": "cron", "session_id": session_id}
        else:
            return {"response": "Usage: /cron list | /cron add \"schedule\" \"task\"", "command": "cron", "session_id": session_id}

    elif command == "/sessions":
        sub = arg.split(None, 1)
        sub_cmd = sub[0].lower() if sub else "list"
        if sub_cmd == "list":
            sessions = list(conversations_col.find({}, {"session_id": 1, "updated_at": 1}).sort("updated_at", -1).limit(10))
            if not sessions:
                return {"response": "No active sessions.", "command": "sessions", "session_id": session_id}
            lines = [f"• `{s['session_id']}` — last active {s.get('updated_at', '?')[:19]}" for s in sessions]
            return {"response": "**Active Sessions:**\n\n" + "\n".join(lines), "command": "sessions", "session_id": session_id}
        elif sub_cmd == "send" and len(sub) > 1:
            rest = sub[1].strip()
            parts2 = rest.split(None, 1)
            if len(parts2) < 2:
                return {"response": "Usage: /sessions send <session_id> <message>", "command": "sessions", "session_id": session_id}
            target_session, fwd_msg = parts2[0], parts2[1]
            # Store outgoing messages for that session to pick up
            conversations_col.update_one(
                {"session_id": target_session},
                {"$push": {"turns": {"role": "agent", "content": f"[From {session_id}]: {fwd_msg}", "timestamp": now_iso()}}},
                upsert=True
            )
            return {"response": f"Message sent to session `{target_session}`.", "command": "sessions", "session_id": session_id}
        else:
            return {"response": "Usage: /sessions list | /sessions send <session_id> <message>", "command": "sessions", "session_id": session_id}

    return None  # Not a recognized command


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket control plane — real-time typing indicators and daemon events."""
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """SSE streaming endpoint — tokens arrive in real-time."""
    import json as _json
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:12]}"

    cmd_result = await handle_chat_command(req.message, session_id)
    if cmd_result:
        async def cmd_gen():
            yield f"data: {_json.dumps({'type': 'start', 'session_id': session_id})}\n\n"
            yield f"data: {_json.dumps({'type': 'token', 'text': cmd_result['response']})}\n\n"
            yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'provider': 'system', 'model': 'command'})}\n\n"
        return StreamingResponse(cmd_gen(), media_type="text/event-stream")

    conversation = conversations_col.find_one({"session_id": session_id})
    context = ""
    if conversation:
        recent_turns = [t for t in conversation.get("turns", [])[-12:] if not t.get("compacted")]
        context = "\n".join([f"{t['role']}: {t['content'][:500]}" for t in recent_turns])

    state = _session_state.get(session_id, {})
    thinking_level = state.get("thinking_level", "low")

    agent_id = req.agent_id
    if not agent_id or agent_id == "auto":
        agent_id = classify_task_for_agent(req.message)

    category = categorize_message(req.message)
    k1_prompts = list(prompts_col.find({"active": True})) or DEFAULT_PROMPTS
    best_prompt = select_best_prompt(category, k1_prompts)
    sys_msg = best_prompt.get("system_prompt", "You are Ombra.")
    if agent_id:
        agent = agents_col.find_one({"agent_id": agent_id})
        if agent:
            sys_msg = agent.get("system_prompt", sys_msg)
    if req.white_card_mode:
        sys_msg += "\n\nYou are in 'White Card' mode. Be proactive: suggest ideas, improvements, next steps."
    skill_ids = detect_skills_for_message(req.message)
    sys_msg = build_system_prompt(sys_msg, active_skill_ids=skill_ids)
    if context:
        sys_msg += f"\n\nRecent context:\n{context}"
    if thinking_level == "high":
        sys_msg += "\n\nThink carefully step by step."

    ollama_health = await check_ollama_health()
    ollama_ok = ollama_health.get("available", False)
    models = ollama_health.get("models", ["tinyllama"])

    if req.force_provider:
        provider = req.force_provider
    elif ollama_ok:
        provider = "ollama"
    else:
        provider = "openai"

    model = state.get("model_override") or (models[0] if provider == "ollama" else "gpt-4o-mini")

    # Decide whether to use agentic loop for streaming
    perms = get_permissions()
    use_tools_stream = req.enable_tools
    if use_tools_stream is None:
        # Enable tools by default when agent loop is available
        use_tools_stream = bool(AGENT_LOOP_AVAILABLE and EMERGENT_KEY)

    async def event_generator():
        await ws_manager.send_typing(session_id, True)
        yield f"data: {_json.dumps({'type': 'start', 'session_id': session_id, 'provider': provider, 'model': model})}\n\n"

        full_response = ""
        tool_calls_made = []

        if AGENT_LOOP_AVAILABLE and use_tools_stream and EMERGENT_KEY:
            soul = load_soul() or ""
            # Build dynamic MCP tools list
            mcp_tools_hint = ""
            try:
                from mcp_client import mcp_manager as _mcp_mgr
                status = _mcp_mgr.get_status()
                if status["total_tools"] > 0:
                    mcp_names = []
                    for srv in status["servers"]:
                        if srv["connected"]:
                            for tn in srv["tool_names"]:
                                mcp_names.append(f"mcp_{srv['server_id']}_{tn}")
                    if mcp_names:
                        mcp_tools_hint = (
                            "\n\n## Connected MCP Tools\n"
                            "These tools are from connected MCP servers and are available for you to call directly:\n"
                            + ", ".join(mcp_names) + "\n"
                            "Use them when they can help accomplish the user's task."
                        )
            except Exception:
                pass
            tools_hint = (
                "\n\nYou have tools available and should USE them when the user asks you to do something. "
                "NEVER tell the user to 'do it manually' or 'visit the link yourself'. YOU are the autonomous agent — YOU do the work. "
                "If one approach fails, try another. If a website blocks you, try a different website. NEVER give up after one failure. "
                "Available: read_emails, draft_email, web_search, fetch_url, browser_research, terminal, read_file, "
                "write_file, list_dir, python_exec, memory_store, create_task, http_request, git_run, install_packages, "
                "generate_video, screenshot, codebase_search, rag_search, multi_file_edit, github_action, "
                "spawn_subagents, analyze_image, computer_use, mcp_connect. "
                "Execute tasks — don't just describe what you would do. "
                "Use install_packages to install dependencies (pip, npm, or apt) whenever a project needs them. "
                "For notifications from generated scripts, use TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."
                "\n\n## Environment Awareness (CRITICAL)\n"
                "You are running on a HEADLESS Linux server. There is NO desktop, NO GUI, NO display.\n"
                "- You CANNOT open VS Code, browsers, file managers, or any GUI app.\n"
                "- You CANNOT use xdg-open, xdotool, import (ImageMagick), or display commands.\n"
                "- To show something visual: use the `screenshot` tool to capture a URL as an image.\n"
                "- To let the user see a web page: start an HTTP server and give a proxy preview link.\n"
                "- Your workspace is /tmp/ombra_workspace. All files you create go there. You CAN read/write files there freely.\n"
                "- NEVER say 'I cannot access files' or 'restrictions prevent me' if the file is in your workspace. Just read it.\n"
                "\n\n## Preview / Serving Rules (MANDATORY)\n"
                "When you create HTML/CSS/JS files that the user wants to preview:\n"
                "1. ALWAYS start a local HTTP server: `python3 -m http.server <PORT> --bind 127.0.0.1` (pick a port like 8080, 8090, etc.)\n"
                "2. The preview URL is ALWAYS: http://20.67.232.113/api/preview/proxy/<PORT>/<relative-path-from-workspace>\n"
                "3. NEVER give raw file paths or /api/preview?path= links — they break relative imports.\n"
                "4. NEVER give http://20.67.232.113:<PORT> links — the user can't reach internal ports directly.\n"
                "5. If the server command times out, that's NORMAL (it becomes a background process). The preview URL still works.\n"
                "6. ALWAYS test the preview URL yourself with fetch_url before sharing it.\n"
                "\n\n## Code-Quality Rules (MANDATORY)\n"
                "1. After writing or editing ANY file, always read it back to verify syntax.\n"
                "2. After writing a Python script, run `python -c \"import py_compile; py_compile.compile('<file>', doraise=True)\"` to catch syntax errors.\n"
                "3. If you create a script meant to run continuously, test it with a short dry-run (e.g., run for 5 seconds then exit) before telling the user it is done.\n"
                "4. Never leave placeholder values like `YOUR_API_KEY` — pull real values from env vars.\n"
                "5. When a tool call fails, read the error, fix the root cause, and retry — do NOT repeat the same call blindly.\n"
                "6. Limit yourself to 3 retry attempts per tool call; after that, report the failure to the user.\n"
                "7. For any non-trivial code, write at least one quick validation test before considering the task complete.\n"
                "8. When a tool returns a preview_url or any URL, ALWAYS use that EXACT URL. NEVER fabricate, shorten, or invent URLs. Copy the URL verbatim from the tool result.\n"
                "9. NEVER wrap URLs in markdown bold (**), italics (*), or backticks (`). URLs must be plain text or in a markdown link like [text](url). Formatting characters break the link."
                "\n\n## Browser Autonomy (computer_use tool)\n"
                "When you need to interact with a website:\n"
                "1. FIRST: navigate to the URL — this auto-returns all interactive elements (buttons, links, inputs).\n"
                "2. If a cookie/consent banner appears, use action=handle_consent to auto-dismiss it.\n"
                "3. Use action=find_and_click with text= to click buttons/links by their visible text (e.g., text='Accept all').\n"
                "4. Use action=find_and_type with label= and value= to fill in form fields by their label.\n"
                "5. NEVER guess CSS selectors. Navigate first, read the interactive_elements list, then use find_and_click/find_and_type.\n"
                "6. After each action, check the result to verify it worked before proceeding.\n"
            ) + mcp_tools_hint
            extra_ctx = []
            if context:
                extra_ctx = [{"role": "system", "content": f"Conversation context:\n{context}"}]
            async for event in stream_agent_loop(
                message=req.message,
                system_prompt=soul + tools_hint + (req.white_card_mode and "\n\nYou are in 'White Card' mode." or ""),
                model="claude-sonnet-4-5-20250929",
                session_id=session_id,
                db=db,
                tools_enabled=True,
                extra_context=extra_ctx
            ):
                if event["type"] == "text_chunk":
                    full_response += event["content"]
                    yield f"data: {_json.dumps({'type': 'token', 'token': event['content']})}\n\n"
                elif event["type"] in ("tool_start", "tool_result"):
                    yield f"data: {_json.dumps(event)}\n\n"
                elif event["type"] == "done":
                    tool_calls_made = event.get("tool_calls", [])
                    yield f"data: {_json.dumps({'type': 'done', 'session_id': session_id, 'provider': 'openai', 'model': 'gpt-4o', 'tool_calls': tool_calls_made, 'iterations': event.get('iterations', 1), 'duration_ms': event.get('duration_ms', 0)})}\n\n"
                elif event["type"] == "error":
                    yield f"data: {_json.dumps({'type': 'error', 'message': event.get('message', 'Agent error')})}\n\n"

            # Store conversation
            usr_turn = {"role": "user", "content": req.message, "timestamp": now_iso()}
            asst_turn = {"role": "assistant", "content": full_response, "timestamp": now_iso(),
                         "provider": "openai", "model": "gpt-4o", "tool_calls": tool_calls_made or None}
            existing_turns = conversation.get("turns", []) if conversation else []
            new_turns = prune_conversation(existing_turns + [usr_turn, asst_turn])
            if conversation:
                conversations_col.update_one({"session_id": session_id},
                    {"$set": {"turns": new_turns, "updated_at": now_iso()}})
            else:
                conversations_col.insert_one({"session_id": session_id, "turns": new_turns,
                    "created_at": now_iso(), "updated_at": now_iso()})
            await ws_manager.send_typing(session_id, False)
            return

        async for chunk in stream_route_and_respond(req.message, sys_msg, model, provider, ollama_ok):
            # The chunks already include "data: ...\n\n" format
            if '"done":' in chunk:
                # Final done chunk — parse it and re-emit with type field
                try:
                    raw = chunk.replace("data: ", "", 1).strip()
                    done_data = _json.loads(raw)
                    done_data["type"] = "done"
                    done_data["session_id"] = session_id
                    full_response = done_data.get("full_response", full_response)
                    yield f"data: {_json.dumps(done_data)}\n\n"
                except Exception:
                    yield chunk
            else:
                # Token chunk — add type field
                try:
                    raw = chunk.replace("data: ", "", 1).strip()
                    tok_data = _json.loads(raw)
                    tok_data["type"] = "token"
                    token = tok_data.get("token", "")
                    full_response += token
                    yield f"data: {_json.dumps(tok_data)}\n\n"
                except Exception:
                    yield chunk

        # Store conversation with pruning
        usr_turn = {"role": "user", "content": req.message, "timestamp": now_iso()}
        asst_turn = {"role": "assistant", "content": full_response, "timestamp": now_iso(),
                     "provider": provider, "model": model}
        existing_turns = conversation.get("turns", []) if conversation else []
        new_turns = prune_conversation(existing_turns + [usr_turn, asst_turn])

        if conversation:
            conversations_col.update_one({"session_id": session_id},
                {"$set": {"turns": new_turns, "updated_at": now_iso()}})
        else:
            conversations_col.insert_one({"session_id": session_id, "turns": new_turns,
                "created_at": now_iso(), "updated_at": now_iso()})

        settings = settings_col.find_one({"user_id": "default"}) or {}
        if settings.get("learning_enabled", True):
            asyncio.create_task(extract_and_learn(req.message, full_response, session_id))

        await ws_manager.send_typing(session_id, False)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:12]}"

    # Handle chat commands first
    cmd_result = await handle_chat_command(req.message, session_id)
    if cmd_result:
        return {
            "session_id": session_id,
            "response": cmd_result["response"],
            "provider": "system",
            "model": "command",
            "routing": {"route": "command"},
            "fallback_chain": [],
            "duration_ms": 0,
            "command": cmd_result.get("command"),
        }

    conversation = conversations_col.find_one({"session_id": session_id})
    context = ""
    if conversation:
        recent_turns = [t for t in conversation.get("turns", [])[-12:] if not t.get("compacted")]
        context = "\n".join([f"{t['role']}: {t['content'][:500]}" for t in recent_turns])

    system_addition = ""
    if req.white_card_mode:
        system_addition = "\n\nYou are in 'White Card' mode. Be proactive: suggest ideas, improvements, next steps. Explore creative solutions. Think ahead for the user."

    # Get session state (thinking level, model override)
    state = _session_state.get(session_id, {})
    thinking_level = state.get("thinking_level", "low")
    model_override = state.get("model_override")

    # Auto-classify agent if not specified
    agent_id = req.agent_id
    if not agent_id or agent_id == "auto":
        agent_id = classify_task_for_agent(req.message)

    # Decide whether to use the agentic tool loop
    perms = get_permissions()
    use_tools = req.enable_tools
    if use_tools is None:
        # Enable tools by default when agent loop is available
        use_tools = bool(AGENT_LOOP_AVAILABLE and EMERGENT_KEY)

    tool_calls_made = []
    await ws_manager.send_typing(session_id, True)

    if AGENT_LOOP_AVAILABLE and use_tools and EMERGENT_KEY:
        # Build system prompt for agent loop
        soul = load_soul() or ""
        # Build dynamic MCP tools list
        mcp_tools_hint = ""
        try:
            from mcp_client import mcp_manager as _mcp_mgr2
            status = _mcp_mgr2.get_status()
            if status["total_tools"] > 0:
                mcp_names = []
                for srv in status["servers"]:
                    if srv["connected"]:
                        for tn in srv["tool_names"]:
                            mcp_names.append(f"mcp_{srv['server_id']}_{tn}")
                if mcp_names:
                    mcp_tools_hint = (
                        "\n\n## Connected MCP Tools\n"
                        "These tools are from connected MCP servers and are available for you to call directly:\n"
                        + ", ".join(mcp_names) + "\n"
                        "Use them when they can help accomplish the user's task."
                    )
        except Exception:
            pass
        tools_hint = (
            "\n\nYou have tools available and should USE them when the user asks you to do something. "
            "NEVER tell the user to 'do it manually' or 'visit the link yourself'. YOU are the autonomous agent — YOU do the work. "
            "If one approach fails, try another. If a website blocks you, try a different website. NEVER give up after one failure. "
            "Available: read_emails, draft_email, web_search, fetch_url, browser_research, terminal, read_file, "
            "write_file, list_dir, python_exec, memory_store, create_task, http_request, git_run, install_packages, "
            "generate_video, screenshot, codebase_search, rag_search, multi_file_edit, github_action, "
            "spawn_subagents, analyze_image, computer_use, mcp_connect. "
            "Execute tasks — don't just describe what you would do. "
            "Use install_packages to install dependencies (pip, npm, or apt) whenever a project needs them. "
            "For notifications from generated scripts, use TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."
            "\n\n## Environment Awareness (CRITICAL)\n"
            "You are running on a HEADLESS Linux server. There is NO desktop, NO GUI, NO display.\n"
            "- You CANNOT open VS Code, browsers, file managers, or any GUI app.\n"
            "- You CANNOT use xdg-open, xdotool, import (ImageMagick), or display commands.\n"
            "- To show something visual: use the `screenshot` tool to capture a URL as an image.\n"
            "- To let the user see a web page: start an HTTP server and give a proxy preview link.\n"
            "- Your workspace is /tmp/ombra_workspace. All files you create go there. You CAN read/write files there freely.\n"
            "- NEVER say 'I cannot access files' or 'restrictions prevent me' if the file is in your workspace. Just read it.\n"
            "\n\n## Preview / Serving Rules (MANDATORY)\n"
            "When you create HTML/CSS/JS files that the user wants to preview:\n"
            "1. ALWAYS start a local HTTP server: `python3 -m http.server <PORT> --bind 127.0.0.1` (pick a port like 8080, 8090, etc.)\n"
            "2. The preview URL is ALWAYS: http://20.67.232.113/api/preview/proxy/<PORT>/<relative-path-from-workspace>\n"
            "3. NEVER give raw file paths or /api/preview?path= links — they break relative imports.\n"
            "4. NEVER give http://20.67.232.113:<PORT> links — the user can't reach internal ports directly.\n"
            "5. If the server command times out, that's NORMAL (it becomes a background process). The preview URL still works.\n"
            "6. ALWAYS test the preview URL yourself with fetch_url before sharing it.\n"
            "\n\n## Code-Quality Rules (MANDATORY)\n"
            "1. After writing or editing ANY file, always read it back to verify syntax.\n"
            "2. After writing a Python script, run `python -c \"import py_compile; py_compile.compile('<file>', doraise=True)\"` to catch syntax errors.\n"
            "3. If you create a script meant to run continuously, test it with a short dry-run (e.g., run for 5 seconds then exit) before telling the user it is done.\n"
            "4. Never leave placeholder values like `YOUR_API_KEY` — pull real values from env vars.\n"
            "5. When a tool call fails, read the error, fix the root cause, and retry — do NOT repeat the same call blindly.\n"
            "6. Limit yourself to 3 retry attempts per tool call; after that, report the failure to the user.\n"
            "7. For any non-trivial code, write at least one quick validation test before considering the task complete.\n"
            "8. When a tool returns a preview_url or any URL, ALWAYS use that EXACT URL. NEVER fabricate, shorten, or invent URLs. Copy the URL verbatim from the tool result.\n"
            "9. NEVER wrap URLs in markdown bold (**), italics (*), or backticks (`). URLs must be plain text or in a markdown link like [text](url). Formatting characters break the link."
            "\n\n## Browser Autonomy (computer_use tool)\n"
            "When you need to interact with a website:\n"
            "1. FIRST: navigate to the URL — this auto-returns all interactive elements (buttons, links, inputs).\n"
            "2. If a cookie/consent banner appears, use action=handle_consent to auto-dismiss it.\n"
            "3. Use action=find_and_click with text= to click buttons/links by their visible text (e.g., text='Accept all').\n"
            "4. Use action=find_and_type with label= and value= to fill in form fields by their label.\n"
            "5. NEVER guess CSS selectors. Navigate first, read the interactive_elements list, then use find_and_click/find_and_type.\n"
            "6. After each action, check the result to verify it worked before proceeding.\n"
        ) + mcp_tools_hint
        extra_ctx = []
        if context:
            extra_ctx = [{"role": "system", "content": f"Conversation context:\n{context}"}]
        model = "claude-sonnet-4-5-20250929"
        agent_result = await run_agent_loop(
            message=req.message,
            system_prompt=soul + tools_hint + system_addition,
            model=model,
            session_id=session_id,
            db=db,
            tools_enabled=True,
            extra_context=extra_ctx
        )
        result = {
            "response": agent_result["response"],
            "provider_used": "anthropic" if agent_result["model"].startswith("claude") else "openai",
            "model_used": agent_result["model"],
            "routing": {"route": "agent_loop", "iterations": agent_result["iterations"]},
            "fallback_chain": [],
            "duration_ms": agent_result["duration_ms"],
            "usage": {},
            "k1_prompt_used": None,
            "category": "agent"
        }
        tool_calls_made = agent_result["tool_calls"]
    else:
        result = await route_and_respond(
            message=req.message,
            system_message=system_addition,
            conversation_context=context,
            force_provider=req.force_provider or (model_override if model_override else None),
            agent_id=agent_id if agent_id != "auto" else None,
            thinking_level=thinking_level,
        )

    await ws_manager.send_typing(session_id, False)

    user_turn = {"role": "user", "content": req.message, "timestamp": now_iso()}
    assistant_turn = {
        "role": "assistant",
        "content": result["response"],
        "timestamp": now_iso(),
        "provider": result["provider_used"],
        "model": result["model_used"],
        "routing": result["routing"],
        "agent_id": agent_id,
        "k1_prompt": result.get("k1_prompt_used"),
        "tool_calls": tool_calls_made if tool_calls_made else None
    }

    if conversation:
        existing_turns = conversation.get("turns", [])
        new_turns = prune_conversation(existing_turns + [user_turn, assistant_turn])
        conversations_col.update_one(
            {"session_id": session_id},
            {"$set": {"turns": new_turns, "updated_at": now_iso()}}
        )
    else:
        conversations_col.insert_one({
            "session_id": session_id,
            "turns": [user_turn, assistant_turn],
            "created_at": now_iso(), "updated_at": now_iso()
        })

    settings = settings_col.find_one({"user_id": "default"}) or {}
    if settings.get("learning_enabled", True):
        await extract_and_learn(req.message, result["response"], session_id)

    # Build usage footer based on session preference
    usage = result.get("usage", {})
    usage_mode = _session_state.get(session_id, {}).get("usage_display", "tokens")
    usage_footer = None
    if usage_mode == "tokens" and usage:
        usage_footer = f"{usage.get('total_tokens', 0)} tokens"
    elif usage_mode == "full" and usage:
        usage_footer = f"{usage.get('total_tokens', 0)} tokens · ${usage.get('cost_usd', 0):.4f}"

    # Show verbose routing if flag set
    verbose = _session_state.get(session_id, {}).get("verbose", False)
    trace = _session_state.get(session_id, {}).get("trace", False)
    routing_info = None
    if verbose:
        routing_info = result.get("routing")
    trace_info = None
    if trace:
        trace_info = result.get("fallback_chain")

    await ws_manager.send_event("response", {"session_id": session_id})

    return {
        "session_id": session_id,
        "response": result["response"],
        "provider": result["provider_used"],
        "model": result["model_used"],
        "routing": result["routing"],
        "fallback_chain": result["fallback_chain"],
        "duration_ms": result["duration_ms"],
        "agent_id": agent_id,
        "k1_prompt": result.get("k1_prompt_used"),
        "category": result.get("category"),
        "usage": usage,
        "usage_footer": usage_footer,
        "routing_info": routing_info,
        "trace_info": trace_info,
        "tool_calls": tool_calls_made if tool_calls_made else None,
    }


@app.get("/api/chat/history")
async def get_chat_history(session_id: str = None):
    if session_id:
        conv = conversations_col.find_one({"session_id": session_id})
        if conv:
            return serialize_doc(conv)
        return {"session_id": session_id, "turns": []}

    sessions = list(conversations_col.find(
        {}, {"session_id": 1, "created_at": 1, "updated_at": 1, "turns": {"$slice": 1}}
    ).sort("updated_at", DESCENDING).limit(20))
    return [{"session_id": s["session_id"], "created_at": s.get("created_at", ""),
             "updated_at": s.get("updated_at", ""),
             "preview": s.get("turns", [{}])[0].get("content", "")[:80] if s.get("turns") else ""} for s in sessions]


@app.delete("/api/chat/history")
async def clear_chat_history(session_id: str = None):
    if session_id:
        conversations_col.delete_one({"session_id": session_id})
    else:
        conversations_col.delete_many({})
    return {"status": "cleared"}


# ============================================================
# DASHBOARD
# ============================================================
@app.get("/api/dashboard/summary")
async def dashboard_summary():
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_activities = list(activity_col.find({"timestamp": {"$gte": today_start}}))

    model_calls = [a for a in today_activities if a.get("type") == "model_call"]
    tool_executions = [a for a in today_activities if a.get("type") == "tool_execution"]
    memory_ops = [a for a in today_activities if a.get("type") in ["memory_write", "memory_read"]]
    k1_events = [a for a in today_activities if a.get("type") == "k1_learning"]

    providers_used = {}
    for mc in model_calls:
        p = mc.get("details", {}).get("provider", "unknown")
        providers_used[p] = providers_used.get(p, 0) + 1

    total_duration = sum(a.get("duration_ms", 0) for a in today_activities)

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_interactions": len(model_calls),
        "tool_executions": len(tool_executions),
        "memory_operations": len(memory_ops),
        "k1_learning_events": len(k1_events),
        "total_activities": len(today_activities),
        "providers_used": providers_used,
        "total_duration_ms": total_duration,
        "avg_response_ms": int(total_duration / max(len(model_calls), 1)),
        "summary": f"Today: {len(model_calls)} chats, {len(tool_executions)} tool runs, {len(memory_ops)} memory ops, {len(k1_events)} K1 learning events."
    }


@app.get("/api/dashboard/status")
async def system_status():
    ollama = await check_ollama_health()
    try:
        client.admin.command('ping')
        mongo_ok = True
    except Exception:
        mongo_ok = False

    memory_count = memories_col.count_documents({})
    conversation_count = conversations_col.count_documents({})
    active_tasks = tasks_col.count_documents({"status": {"$in": ["pending", "in_progress"]}})
    agent_count = agents_col.count_documents({})
    distillation_count = distillation_col.count_documents({})

    return {
        "ollama": {"status": "online" if ollama["available"] else "offline", "models": ollama["models"]},
        "cloud_api": {"status": "configured" if EMERGENT_KEY else "not_configured"},
        "memory": {"status": "online" if mongo_ok else "offline", "memories": memory_count, "conversations": conversation_count},
        "autonomy": {"status": "active" if active_tasks > 0 else "idle", "active_tasks": active_tasks},
        "agents": {"count": agent_count},
        "k1": {"distillations": distillation_count},
        "telegram": {"configured": bool(TELEGRAM_TOKEN)},
        "timestamp": now_iso()
    }


# ============================================================
# PERMISSIONS
# ============================================================
@app.get("/api/permissions")
async def get_permissions_endpoint():
    profile = profiles_col.find_one({"user_id": "default"})
    if not profile:
        return {"terminal": False, "filesystem": False, "telegram": False, "onboarded": False}
    return {
        "terminal": profile.get("permissions", {}).get("terminal", False),
        "filesystem": profile.get("permissions", {}).get("filesystem", False),
        "telegram": profile.get("permissions", {}).get("telegram", False),
        "onboarded": profile.get("onboarded", False)
    }


@app.put("/api/permissions")
async def update_permissions(req: PermissionUpdate):
    update_data = {}
    if req.terminal is not None:
        update_data["permissions.terminal"] = req.terminal
    if req.filesystem is not None:
        update_data["permissions.filesystem"] = req.filesystem
    if req.telegram is not None:
        update_data["permissions.telegram"] = req.telegram
    if update_data:
        update_data["updated_at"] = now_iso()
        profiles_col.update_one({"user_id": "default"}, {"$set": update_data})
        log_activity("permission_change", {
            "changes": {k.split('.')[-1]: v for k, v in update_data.items() if k.startswith('permissions')}
        })
    return await get_permissions_endpoint()


@app.post("/api/onboarding")
async def complete_onboarding(req: PermissionUpdate):
    update_data = {"onboarded": True, "updated_at": now_iso()}
    if req.terminal is not None:
        update_data["permissions.terminal"] = req.terminal
    if req.filesystem is not None:
        update_data["permissions.filesystem"] = req.filesystem
    if req.telegram is not None:
        update_data["permissions.telegram"] = req.telegram
    profiles_col.update_one({"user_id": "default"}, {"$set": update_data})
    log_activity("system", {"event": "onboarding_complete"})
    return {"status": "onboarded", "permissions": await get_permissions_endpoint()}


# ============================================================
# ACTIVITY TIMELINE
# ============================================================
@app.get("/api/activity")
async def get_activity(
    activity_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0
):
    query = {}
    if activity_type and activity_type != "all":
        query["type"] = activity_type
    total = activity_col.count_documents(query)
    activities = list(activity_col.find(query).sort("timestamp", DESCENDING).skip(offset).limit(limit))
    return {"activities": [serialize_doc(a) for a in activities], "total": total, "offset": offset, "limit": limit}


@app.get("/api/activity/summary")
async def activity_daily_summary():
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    activities = list(activity_col.find({"timestamp": {"$gte": today_start}}))
    type_counts = {}
    for a in activities:
        t = a.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    return {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "total": len(activities),
            "by_type": type_counts, "timeline_preview": [serialize_doc(a) for a in activities[:10]]}


# ============================================================
# TASKS (Enhanced with goal planning)
# ============================================================
@app.get("/api/tasks")
async def get_tasks(status: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    tasks = list(tasks_col.find(query).sort("created_at", DESCENDING).limit(50))
    return [serialize_doc(t) for t in tasks]


@app.post("/api/tasks")
async def create_task(req: TaskCreate):
    task = {
        "title": req.title, "description": req.description,
        "priority": req.priority, "status": "pending",
        "created_at": now_iso(), "updated_at": now_iso(),
        "steps": [], "result": None, "agent_id": None,
        "execution_log": [], "retries": 0
    }
    result = tasks_col.insert_one(task)
    task["_id"] = str(result.inserted_id)
    log_activity("autonomy", {"event": "task_created", "title": req.title, "priority": req.priority})
    return serialize_doc(task)


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, status: str = None, result: str = None):
    update = {"updated_at": now_iso()}
    if status:
        update["status"] = status
    if result:
        update["result"] = result
    tasks_col.update_one({"_id": ObjectId(task_id)}, {"$set": update})
    task = tasks_col.find_one({"_id": ObjectId(task_id)})
    log_activity("autonomy", {"event": "task_updated", "task_id": task_id, "status": status})
    return serialize_doc(task)


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    tasks_col.delete_one({"_id": ObjectId(task_id)})
    return {"status": "deleted"}


# Goal Planning
@app.post("/api/goals/plan")
async def plan_goal(req: GoalPlanRequest):
    """Use AI to decompose a goal into actionable steps."""
    prompt = f"""Decompose this goal into clear, actionable steps. For each step:
- Give a short title
- Specify which tool/agent might be needed (coder, researcher, planner, executor, terminal, filesystem)
- Estimate difficulty (easy/medium/hard)
- Note any dependencies on other steps

Goal: {req.goal}
{f'Context: {req.context}' if req.context else ''}

Return as a structured numbered list."""

    result = await route_and_respond(
        message=prompt,
        system_message="You are Ombra-Planner. Decompose goals into actionable step lists.",
        force_provider="anthropic",
        agent_id="planner"
    )

    # Create the goal as a parent task
    goal_task = {
        "title": req.goal[:200],
        "description": req.context or "",
        "priority": "high",
        "status": "planned",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "steps": [],
        "plan": result["response"],
        "result": None,
        "agent_id": "planner",
        "execution_log": [],
        "retries": 0
    }
    task_result = tasks_col.insert_one(goal_task)
    goal_task["_id"] = str(task_result.inserted_id)

    log_activity("autonomy", {
        "event": "goal_planned",
        "goal": req.goal[:100],
        "plan_preview": result["response"][:200]
    })

    return {
        "task": serialize_doc(goal_task),
        "plan": result["response"],
        "provider": result["provider_used"],
        "duration_ms": result["duration_ms"]
    }


@app.post("/api/tasks/{task_id}/execute")
async def execute_task_step(task_id: str):
    """Execute the next step of a task."""
    task = tasks_col.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.get("status") in ["completed", "cancelled"]:
        return {"status": "already_finished", "task": serialize_doc(task)}

    # Ask the executor agent to work on this task
    prompt = f"""Execute or advise on this task:
Title: {task.get('title', '')}
Description: {task.get('description', '')}
Plan: {task.get('plan', 'No plan yet')}
Previous execution log: {json.dumps(task.get('execution_log', [])[-3:])}

Provide the next concrete action to take and expected outcome."""

    result = await route_and_respond(
        message=prompt,
        force_provider="anthropic",
        agent_id="executor"
    )

    # Update task
    exec_entry = {
        "step": len(task.get("execution_log", [])) + 1,
        "action": result["response"][:500],
        "provider": result["provider_used"],
        "timestamp": now_iso()
    }

    tasks_col.update_one(
        {"_id": ObjectId(task_id)},
        {
            "$push": {"execution_log": exec_entry},
            "$set": {"status": "in_progress", "updated_at": now_iso()},
            "$inc": {"retries": 0}
        }
    )

    log_activity("autonomy", {
        "event": "task_step_executed",
        "task_id": task_id,
        "step": exec_entry["step"]
    })

    updated = tasks_col.find_one({"_id": ObjectId(task_id)})
    return {"step": exec_entry, "task": serialize_doc(updated)}


# ============================================================
# AGENTS (CRUD + Run)
# ============================================================
@app.get("/api/agents")
async def list_agents():
    agents = list(agents_col.find().sort("builtin", DESCENDING))
    return [serialize_doc(a) for a in agents]


@app.post("/api/agents")
async def create_agent(req: AgentCreate):
    agent_id = f"custom_{uuid.uuid4().hex[:8]}"
    agent = {
        "agent_id": agent_id,
        "name": req.name,
        "role": "custom",
        "description": req.description,
        "system_prompt": req.system_prompt,
        "tools_allowed": req.tools_allowed,
        "provider_preference": req.provider_preference,
        "temperature": req.temperature,
        "builtin": False,
        "icon": req.icon,
        "color": req.color,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    agents_col.insert_one(agent)
    log_activity("autonomy", {"event": "agent_created", "agent_id": agent_id, "name": req.name})
    return serialize_doc(agent)


@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdate):
    update = {"updated_at": now_iso()}
    for field in ["name", "description", "system_prompt", "tools_allowed", "provider_preference", "temperature", "icon", "color"]:
        val = getattr(req, field, None)
        if val is not None:
            update[field] = val
    agents_col.update_one({"agent_id": agent_id}, {"$set": update})
    agent = agents_col.find_one({"agent_id": agent_id})
    return serialize_doc(agent)


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    agent = agents_col.find_one({"agent_id": agent_id})
    if agent and agent.get("builtin"):
        raise HTTPException(status_code=400, detail="Cannot delete built-in agents")
    agents_col.delete_one({"agent_id": agent_id})
    return {"status": "deleted"}


@app.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, req: ChatRequest):
    """Run a specific agent on an input."""
    agent = agents_col.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await route_and_respond(
        message=req.message,
        system_message=agent.get("system_prompt", ""),
        force_provider=agent.get("provider_preference") if agent.get("provider_preference") != "auto" else None,
        agent_id=agent_id
    )

    log_activity("agent_execution", {
        "agent_id": agent_id,
        "agent_name": agent.get("name"),
        "input_preview": req.message[:100],
        "output_preview": result["response"][:200],
        "provider": result["provider_used"]
    })

    return {
        "agent_id": agent_id,
        "agent_name": agent.get("name"),
        "response": result["response"],
        "provider": result["provider_used"],
        "model": result["model_used"],
        "duration_ms": result["duration_ms"]
    }


# ============================================================
# SETTINGS
# ============================================================
@app.get("/api/settings")
async def get_settings():
    settings = settings_col.find_one({"user_id": "default"})
    if not settings:
        return {"ollama_url": OLLAMA_URL, "ollama_model": "tinyllama", "preferred_provider": "auto",
                "preferred_model": "", "learning_enabled": True, "white_card_enabled": False,
                "quiet_hours_start": "", "quiet_hours_end": "", "telegram_chat_id": "",
                "telegram_enabled": False, "hardware_ram": "16gb", "morning_summary_hour_utc": 8,
                "email_host": "smtp.gmail.com", "email_port": 587, "email_user": "",
                "email_pass": "", "email_from": "", "email_enabled": False}
    if "morning_summary_hour_utc" not in settings:
        settings["morning_summary_hour_utc"] = 8
    # Never expose email password to frontend
    doc = serialize_doc(settings)
    if doc.get("email_pass"):
        doc["email_pass"] = "••••••••"
    return doc


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    update = {"updated_at": now_iso()}
    for field in ["ollama_url", "ollama_model", "preferred_provider", "preferred_model",
                  "learning_enabled", "white_card_enabled", "quiet_hours_start", "quiet_hours_end",
                  "telegram_chat_id", "telegram_enabled", "hardware_ram", "morning_summary_hour_utc",
                  "email_host", "email_port", "email_user", "email_pass", "email_from", "email_enabled"]:
        val = getattr(req, field, None)
        if val is not None:
            # Don't overwrite email_pass with the masked placeholder
            if field == "email_pass" and val == "••••••••":
                continue
            update[field] = val
    settings_col.update_one({"user_id": "default"}, {"$set": update})
    log_activity("system", {"event": "settings_updated", "changes": update})
    return await get_settings()


# ── Anthropic / Claude API Key Management ────────────────────────────────────

@app.get("/api/settings/claude")
async def get_claude_status():
    """Check if Anthropic API key is configured."""
    key = ANTHROPIC_KEY or EMERGENT_KEY
    has_key = bool(key)
    return {
        "configured": has_key,
        "source": "ANTHROPIC_API_KEY" if ANTHROPIC_KEY else ("EMERGENT_LLM_KEY" if EMERGENT_KEY else "none"),
        "model": "claude-sonnet-4-5-20250929",
    }


@app.post("/api/settings/claude")
async def set_claude_key(request: Request):
    """Set or update the Anthropic API key at runtime."""
    global ANTHROPIC_KEY
    payload = await request.json()
    key = payload.get("api_key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="api_key is required")
    # Validate the key by making a simple API call
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}]
                }
            )
            data = resp.json()
            if "error" in data:
                raise HTTPException(status_code=400, detail=f"Invalid key: {data['error'].get('message', '')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Key validation failed: {str(e)}")
    # Store in env and memory
    ANTHROPIC_KEY = key
    os.environ["ANTHROPIC_API_KEY"] = key
    # Persist to .env file so it survives restarts
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path) as _ef:
            env_lines = [l for l in _ef.readlines() if not l.startswith("ANTHROPIC_API_KEY=")]
    env_lines.append(f"ANTHROPIC_API_KEY={key}\n")
    with open(env_path, "w") as _ef:
        _ef.writelines(env_lines)
    # Persist to settings collection
    settings_col.update_one(
        {"user_id": "default"},
        {"$set": {"anthropic_api_key_set": True, "updated_at": now_iso()}},
        upsert=True
    )
    log_activity("system", {"event": "claude_key_configured"})
    return {"status": "configured", "model": "claude-sonnet-4-5-20250929"}


# ── Bastion / RDP Management ────────────────────────────────────────────────

@app.get("/api/bastion/status")
async def bastion_status():
    """Get current xRDP status and connection info."""
    import subprocess
    try:
        result = subprocess.run(["systemctl", "is-active", "xrdp"], capture_output=True, text=True, timeout=5)
        xrdp_running = result.stdout.strip() == "active"
    except Exception:
        xrdp_running = False

    # Get the server's public IP
    server_ip = os.environ.get("SERVER_PUBLIC_IP", "20.67.232.113")
    rdp_port = int(os.environ.get("RDP_PORT", "3389"))

    # Check for bastion user
    bastion_user = os.environ.get("BASTION_USER", "ombra-rdp")
    try:
        result = subprocess.run(["id", bastion_user], capture_output=True, text=True, timeout=5)
        user_exists = result.returncode == 0
    except Exception:
        user_exists = False

    return {
        "xrdp_running": xrdp_running,
        "server_ip": server_ip,
        "rdp_port": rdp_port,
        "bastion_user": bastion_user if user_exists else None,
        "user_exists": user_exists,
        "connection_string": f"{server_ip}:{rdp_port}" if xrdp_running else None,
    }


@app.post("/api/bastion/setup")
async def bastion_setup(request: Request):
    """Create bastion user and start xRDP. Requires sudo."""
    import subprocess
    payload = await request.json()
    username = payload.get("username", "ombra-rdp")
    password = payload.get("password", "")
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Sanitize username
    import re as _re
    if not _re.match(r'^[a-z_][a-z0-9_-]*$', username):
        raise HTTPException(status_code=400, detail="Invalid username format")

    results = []
    try:
        # Create user if not exists
        check = subprocess.run(["id", username], capture_output=True, text=True, timeout=5)
        if check.returncode != 0:
            subprocess.run(
                ["sudo", "useradd", "-m", "-s", "/bin/bash", username],
                capture_output=True, text=True, timeout=10, check=True
            )
            results.append(f"User '{username}' created")
        else:
            results.append(f"User '{username}' already exists")

        # Set password
        proc = subprocess.run(
            ["sudo", "chpasswd"],
            input=f"{username}:{password}",
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            results.append("Password set")
        else:
            results.append(f"Password set failed: {proc.stderr}")

        # Install xrdp if not present
        check_xrdp = subprocess.run(["which", "xrdp"], capture_output=True, text=True, timeout=5)
        if check_xrdp.returncode != 0:
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "xrdp", "xfce4", "xfce4-goodies"],
                capture_output=True, text=True, timeout=300
            )
            results.append("xRDP + XFCE installed")
            # Configure xsession for the user
            subprocess.run(
                ["sudo", "bash", "-c", f"echo 'xfce4-session' > /home/{username}/.xsession"],
                capture_output=True, text=True, timeout=5
            )
            subprocess.run(
                ["sudo", "chown", f"{username}:{username}", f"/home/{username}/.xsession"],
                capture_output=True, text=True, timeout=5
            )
        else:
            results.append("xRDP already installed")

        # Enable and start xrdp
        subprocess.run(["sudo", "systemctl", "enable", "xrdp"], capture_output=True, text=True, timeout=10)
        subprocess.run(["sudo", "systemctl", "start", "xrdp"], capture_output=True, text=True, timeout=10)
        results.append("xRDP started")

        # Save bastion user info
        os.environ["BASTION_USER"] = username
        settings_col.update_one(
            {"user_id": "default"},
            {"$set": {"bastion_user": username, "bastion_configured": True, "updated_at": now_iso()}},
            upsert=True
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Setup failed: {e.stderr or str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "results": results, "username": username}


@app.post("/api/bastion/restart")
async def bastion_restart():
    """Restart xRDP service."""
    import subprocess
    try:
        subprocess.run(["sudo", "systemctl", "restart", "xrdp"], capture_output=True, text=True, timeout=15, check=True)
        return {"status": "restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# TERMINAL + FILESYSTEM TOOLS
# ============================================================
@app.post("/api/tools/terminal")
async def terminal_endpoint(req: TerminalRequest):
    return execute_terminal_command(req.command, req.timeout)


@app.post("/api/tools/fs/read")
async def fs_read_endpoint(req: FileReadRequest):
    perms = get_permissions()
    if not perms.get("filesystem", False):
        return {"success": False, "error": "Permission denied: filesystem access not granted"}
    result = read_file(req.path)
    if result["success"]:
        log_activity("tool_execution", {"tool": "filesystem", "action": "read", "path": req.path})
    return result


@app.post("/api/tools/fs/write")
async def fs_write_endpoint(req: FileWriteRequest):
    perms = get_permissions()
    if not perms.get("filesystem", False):
        return {"success": False, "error": "Permission denied: filesystem access not granted"}
    result = write_file(req.path, req.content)
    if result["success"]:
        log_activity("tool_execution", {"tool": "filesystem", "action": "write", "path": req.path})
    return result


@app.post("/api/tools/fs/list")
async def fs_list_endpoint(req: FileReadRequest):
    perms = get_permissions()
    if not perms.get("filesystem", False):
        return {"success": False, "error": "Permission denied: filesystem access not granted"}
    result = list_directory(req.path)
    if result["success"]:
        log_activity("tool_execution", {"tool": "filesystem", "action": "list", "path": req.path})
    return result


# ── Preview endpoint: serve files Ombra created ─────────────
PREVIEW_ALLOWED_DIRS = ["/tmp", "/home/azureuser"]
PREVIEW_ALLOWED_EXT = {
    ".html", ".htm", ".css", ".js", ".json", ".txt", ".md",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
}
PREVIEW_MIME = {
    ".html": "text/html", ".htm": "text/html", ".css": "text/css",
    ".js": "application/javascript", ".json": "application/json",
    ".txt": "text/plain", ".md": "text/plain", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon",
}

@app.get("/api/preview")
async def preview_file(path: str = Query(...)):
    """Serve a file for in-app preview (HTML, images, etc.)."""
    import pathlib
    real = str(pathlib.Path(path).resolve())
    # Security: must be under an allowed directory
    if not any(real.startswith(d) for d in PREVIEW_ALLOWED_DIRS):
        raise HTTPException(403, "Path not in allowed preview directories")
    ext = pathlib.Path(real).suffix.lower()
    if ext not in PREVIEW_ALLOWED_EXT:
        raise HTTPException(400, f"File type {ext} not allowed for preview")
    if not os.path.isfile(real):
        raise HTTPException(404, "File not found")
    media = PREVIEW_MIME.get(ext, "application/octet-stream")
    return FileResponse(real, media_type=media)

@app.get("/api/preview/dir")
async def preview_list_dir(path: str = Query("/tmp")):
    """List files in a directory for preview browsing."""
    import pathlib
    real = str(pathlib.Path(path).resolve())
    if not any(real.startswith(d) for d in PREVIEW_ALLOWED_DIRS):
        raise HTTPException(403, "Path not in allowed preview directories")
    if not os.path.isdir(real):
        raise HTTPException(404, "Directory not found")
    entries = []
    try:
        for item in sorted(os.listdir(real)):
            full = os.path.join(real, item)
            entries.append({
                "name": item,
                "is_dir": os.path.isdir(full),
                "size": os.path.getsize(full) if os.path.isfile(full) else None,
                "ext": pathlib.Path(item).suffix.lower(),
            })
    except PermissionError:
        raise HTTPException(403, "Permission denied")
    return {"path": real, "entries": entries}


PROXY_ALLOWED_PORTS = set(range(3000, 9999))  # only proxy local dev server ports

def _rewrite_html_for_proxy(html: str, port: int) -> str:
    """Rewrite root-absolute HTML asset links so React/Vite/Flask pages load via proxy."""
    base = f"/api/preview/proxy/{port}/"
    # Insert base href if missing to make relative links resolve through proxy path route.
    if "<head" in html and "<base " not in html:
        html = html.replace("<head>", f'<head><base href="{base}">', 1)
    # Rewrite root-absolute attributes that would otherwise hit nginx root.
    for attr in ("src", "href", "action"):
        html = html.replace(f'{attr}="/', f'{attr}="{base}')
        html = html.replace(f"{attr}='/", f"{attr}='{base}")
    return html


async def _preview_proxy_impl(port: int, path: str = "/"):
    if port not in PROXY_ALLOWED_PORTS:
        raise HTTPException(400, f"Port {port} not in allowed range (3000-9998)")
    clean_path = "/" + (path or "").lstrip("/")
    target = f"http://127.0.0.1:{port}{clean_path}"
    from starlette.responses import Response, HTMLResponse

    # Retry up to 3 times with short delays — server may still be starting
    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(target, follow_redirects=True)
            content_type = resp.headers.get("content-type", "text/html")

            # For HTML documents, rewrite root-absolute links to remain inside proxy.
            if "text/html" in content_type.lower():
                text = resp.text
                text = _rewrite_html_for_proxy(text, port)
                return Response(content=text, status_code=resp.status_code, media_type="text/html")

            return Response(content=resp.content, status_code=resp.status_code, media_type=content_type)
        except httpx.ConnectError as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(2)  # wait for server to start
                continue
        except Exception as e:
            last_error = e
            break

    # Friendly HTML error page instead of raw JSON
    proxy_base = f"/api/preview/proxy/{port}"
    error_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>Preview Unavailable</title>
<meta http-equiv="refresh" content="5;url={proxy_base}{clean_path}">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Space Grotesk',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;
display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:48px;
max-width:480px;text-align:center}}
h1{{font-size:20px;margin-bottom:12px;color:#f0f6fc}}
p{{font-size:14px;line-height:1.6;color:#8b949e;margin-bottom:8px}}
.port{{color:#58a6ff;font-family:'IBM Plex Mono',monospace}}
.hint{{font-size:12px;color:#484f58;margin-top:16px}}
.retry{{display:inline-block;margin-top:16px;padding:8px 20px;background:#21262d;
border:1px solid #30363d;border-radius:8px;color:#58a6ff;text-decoration:none;font-size:13px}}
.retry:hover{{background:#30363d}}
.spinner{{display:inline-block;width:20px;height:20px;border:2px solid #30363d;
border-top-color:#58a6ff;border-radius:50%;animation:spin 1s linear infinite;margin-bottom:16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body><div class="card">
<div class="spinner"></div>
<h1>Waiting for server on port <span class="port">{port}</span></h1>
<p>The preview server isn't responding yet. This usually means it's still starting up.</p>
<p class="hint">This page will auto-retry in 5 seconds.</p>
<a class="retry" href="{proxy_base}{clean_path}">Retry Now</a>
</div></body></html>"""
    return HTMLResponse(content=error_html, status_code=503)


@app.api_route("/api/preview/proxy/{port}/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def preview_proxy_path(port: int, full_path: str, request: Request):
    """Preferred route: /api/preview/proxy/8000/index.html — supports all HTTP methods."""
    if request.method == "GET":
        return await _preview_proxy_impl(port, f"/{full_path}")
    # Forward non-GET requests to local server
    if port not in PROXY_ALLOWED_PORTS:
        raise HTTPException(400, f"Port {port} not in allowed range (3000-9998)")
    clean_path = "/" + full_path.lstrip("/")
    target = f"http://127.0.0.1:{port}{clean_path}"
    from starlette.responses import Response
    try:
        body = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.request(request.method, target, content=body, headers=headers, follow_redirects=True)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/octet-stream"))
    except httpx.ConnectError:
        raise HTTPException(502, f"Cannot connect to local server on port {port}")
    except Exception as e:
        raise HTTPException(502, f"Proxy error: {str(e)[:200]}")


@app.get("/api/preview/proxy")
async def preview_proxy_query(port: int = Query(...), path: str = Query("/")):
    """Back-compat query route: /api/preview/proxy?port=8000&path=/index.html"""
    return await _preview_proxy_impl(port, path)


# ============================================================
# MEMORIES (Enhanced with scoring/decay/pin)
# ============================================================
@app.get("/api/memories")
async def get_memories(mem_type: Optional[str] = None, limit: int = 50):
    query = {}
    if mem_type:
        query["type"] = mem_type
    mems = list(memories_col.find(query).sort("utility_score", DESCENDING).limit(limit))
    return [serialize_doc(m) for m in mems]


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    memories_col.delete_one({"_id": ObjectId(memory_id)})
    return {"status": "deleted"}


@app.delete("/api/memories")
async def clear_memories():
    memories_col.delete_many({})
    return {"status": "cleared"}


@app.put("/api/memories/{memory_id}/pin")
async def pin_memory(memory_id: str, pinned: bool = True):
    memories_col.update_one(
        {"_id": ObjectId(memory_id)},
        {"$set": {"pinned": pinned, "updated_at": now_iso()}}
    )
    mem = memories_col.find_one({"_id": ObjectId(memory_id)})
    return serialize_doc(mem)


@app.post("/api/memories/decay")
async def run_memory_decay():
    """Run decay on unpinned memories."""
    unpinned = list(memories_col.find({"pinned": {"$ne": True}}))
    decayed = 0
    removed = 0
    for mem in unpinned:
        score = mem.get("utility_score", 0.5)
        decay = mem.get("decay_rate", 0.01)
        new_score = max(0, score - decay)

        if new_score < 0.1:
            memories_col.delete_one({"_id": mem["_id"]})
            removed += 1
        else:
            memories_col.update_one(
                {"_id": mem["_id"]},
                {"$set": {"utility_score": round(new_score, 3), "updated_at": now_iso()}}
            )
            decayed += 1

    log_activity("memory_decay", {"decayed": decayed, "removed": removed})
    return {"decayed": decayed, "removed": removed}


# ============================================================
# FEEDBACK + SELF-IMPROVING
# ============================================================
@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    feedback_entry = {
        "session_id": req.session_id,
        "message_index": req.message_index,
        "feedback": req.feedback,
        "comment": req.comment,
        "timestamp": now_iso()
    }
    feedback_col.insert_one(feedback_entry)

    # Update K1 prompt performance
    conv = conversations_col.find_one({"session_id": req.session_id})
    if conv and req.message_index < len(conv.get("turns", [])):
        turn = conv["turns"][req.message_index]
        k1_prompt = turn.get("k1_prompt")
        if k1_prompt:
            update_prompt_performance(k1_prompt, req.feedback, prompts_col)

    log_activity("feedback", {
        "session_id": req.session_id,
        "feedback": req.feedback,
        "message_index": req.message_index
    })

    return {"status": "recorded"}


@app.get("/api/learning/metrics")
async def get_learning_metrics():
    """Get performance metrics for self-improvement."""
    # Collect recent activity for performance analysis
    recent_calls = list(activity_col.find({"type": "model_call"}).sort("timestamp", DESCENDING).limit(100))

    metrics = []
    for call in recent_calls:
        details = call.get("details", {})
        metrics.append({
            "provider": details.get("provider"),
            "model": details.get("model"),
            "duration_ms": call.get("duration_ms", 0),
            "success": True,
            "feedback": None
        })

    # Get feedback
    recent_feedback = list(feedback_col.find().sort("timestamp", DESCENDING).limit(100))
    feedback_summary = {"positive": 0, "negative": 0}
    for fb in recent_feedback:
        feedback_summary[fb.get("feedback", "positive")] = feedback_summary.get(fb.get("feedback", "positive"), 0) + 1

    performance = calculate_provider_performance(metrics)
    adjustments = suggest_routing_adjustments(performance, {})

    # K1 prompt performance
    prompts = list(prompts_col.find({"active": True}))
    prompt_stats = [
        {
            "prompt_id": p["prompt_id"],
            "name": p.get("name"),
            "category": p.get("category"),
            "performance_score": p.get("performance_score", 0),
            "usage_count": p.get("usage_count", 0),
            "success_count": p.get("success_count", 0)
        }
        for p in prompts
    ]

    return {
        "provider_performance": performance,
        "suggested_adjustments": adjustments,
        "feedback_summary": feedback_summary,
        "total_feedback": len(recent_feedback),
        "k1_prompts": prompt_stats,
        "distillations": distillation_col.count_documents({})
    }


@app.get("/api/learning/changes")
async def get_learning_changes():
    """Get history of learning/improvement changes."""
    changes = list(learning_col.find().sort("timestamp", DESCENDING).limit(50))
    return [serialize_doc(c) for c in changes]


# ============================================================
# OLLAMA MODEL MANAGER
# ============================================================
@app.get("/api/ollama/models")
async def get_ollama_models():
    """Get installed Ollama models."""
    ollama = await check_ollama_health()
    if not ollama["available"]:
        return {"available": False, "models": [], "error": "Ollama not running"}

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(f"{OLLAMA_URL}/api/tags")
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m.get("name"),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                    "details": m.get("details", {})
                })
            return {"available": True, "models": models}
    except Exception as e:
        return {"available": False, "models": [], "error": str(e)}


@app.get("/api/ollama/recommendations")
async def get_model_recommendations():
    """Get model recommendations based on user hardware config."""
    settings = settings_col.find_one({"user_id": "default"}) or {}
    ram_tier = settings.get("hardware_ram", "16gb")
    recs = MODEL_RECOMMENDATIONS.get(ram_tier, MODEL_RECOMMENDATIONS["16gb"])

    # Check which are already installed
    ollama = await check_ollama_health()
    installed = [m.split(":")[0] for m in ollama.get("models", [])]

    for rec in recs:
        rec["installed"] = rec["name"].split(":")[0] in installed

    return {
        "ram_tier": ram_tier,
        "recommendations": recs,
        "installed_models": ollama.get("models", [])
    }


@app.post("/api/ollama/pull")
async def pull_ollama_model(req: OllamaPullRequest):
    """Pull/download an Ollama model."""
    try:
        async with httpx.AsyncClient(timeout=600) as c:
            resp = await c.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": req.model_name, "stream": False},
                timeout=600
            )
            data = resp.json()
            log_activity("system", {"event": "ollama_model_pulled", "model": req.model_name, "status": data.get("status")})
            return {"success": True, "model": req.model_name, "status": data.get("status", "success")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/ollama/models/{model_name}")
async def delete_ollama_model(model_name: str):
    """Delete an Ollama model."""
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.delete(f"{OLLAMA_URL}/api/delete", json={"name": model_name})
            return {"success": resp.status_code == 200, "model": model_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# K1 PROMPTS
# ============================================================
@app.get("/api/k1/prompts")
async def get_k1_prompts():
    prompts = list(prompts_col.find().sort("performance_score", DESCENDING))
    return [serialize_doc(p) for p in prompts]


@app.post("/api/k1/prompts")
async def create_k1_prompt(name: str, category: str, system_prompt: str):
    prompt = {
        "prompt_id": f"custom_{uuid.uuid4().hex[:8]}",
        "name": name,
        "category": category,
        "system_prompt": system_prompt,
        "performance_score": 0.5,
        "usage_count": 0,
        "success_count": 0,
        "active": True,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    prompts_col.insert_one(prompt)
    return serialize_doc(prompt)


@app.get("/api/k1/distillations")
async def get_distillations(limit: int = 20):
    dists = list(distillation_col.find().sort("timestamp", DESCENDING).limit(limit))
    return [serialize_doc(d) for d in dists]


# ============================================================
# TELEGRAM
# ============================================================
@app.post("/api/telegram/test")
async def test_telegram():
    """Test Telegram bot connection."""
    info = await get_bot_info()
    return info


@app.post("/api/telegram/send")
async def send_telegram(req: TelegramSendRequest):
    """Send a message via Telegram."""
    result = await send_telegram_message(req.chat_id, req.message)
    if result["success"]:
        log_activity("tool_execution", {"tool": "telegram", "action": "send", "chat_id": req.chat_id})
    return result


@app.post("/api/telegram/send-summary")
async def send_telegram_summary():
    """Send daily summary via Telegram."""
    settings = settings_col.find_one({"user_id": "default"}) or {}
    chat_id = settings.get("telegram_chat_id")
    if not chat_id:
        return {"success": False, "error": "No Telegram chat ID configured"}

    summary = await dashboard_summary()
    text = format_daily_summary(summary)
    result = await send_telegram_message(chat_id, text)
    return result


# ============================================================
# EMAIL
# ============================================================
@app.post("/api/email/test")
async def test_email():
    """Send a test email using the configured SMTP settings."""
    import smtplib, ssl
    from email.mime.text import MIMEText

    settings = settings_col.find_one({"user_id": "default"}) or {}
    host = settings.get("email_host") or os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    port = int(settings.get("email_port") or os.environ.get("EMAIL_PORT", "587"))
    user = settings.get("email_user") or os.environ.get("EMAIL_USER", "")
    passwd = settings.get("email_pass") or os.environ.get("EMAIL_PASS", "")
    from_addr = settings.get("email_from") or user

    if not user or not passwd:
        return {"success": False, "error": "Email user/password not configured"}

    try:
        msg = MIMEText("This is a test email from Ombra. Your email configuration is working correctly.")
        msg["Subject"] = "Ombra – Email Test"
        msg["From"] = from_addr
        msg["To"] = user  # send test to self
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(user, passwd)
            server.sendmail(from_addr, user, msg.as_string())
        log_activity("system", {"event": "email_test", "status": "success", "host": host})
        return {"success": True, "message": f"Test email sent to {user}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ── Email Provider Connect (App Passwords) ────────────────────────────────────
PROVIDER_SMTP = {
    "google": {"host": "smtp.gmail.com", "port": 587},
    "microsoft": {"host": "smtp.office365.com", "port": 587},
    "icloud": {"host": "smtp.mail.me.com", "port": 587},
}


class EmailProviderConnect(BaseModel):
    provider: str  # google | microsoft | icloud
    email: str
    app_password: str


@app.get("/api/email/provider/status")
async def email_provider_status():
    """Return which email provider is connected."""
    s = settings_col.find_one({"user_id": "default"}) or {}
    provider = s.get("email_provider", "none")
    return {
        "provider": provider,
        "email": s.get("email_provider_email", ""),
        "connected": provider != "none" and bool(s.get("email_provider_email")),
    }


@app.post("/api/email/provider/connect")
async def email_provider_connect(req: EmailProviderConnect):
    """Verify SMTP credentials and save provider connection."""
    import smtplib, ssl
    if req.provider not in PROVIDER_SMTP:
        return {"success": False, "error": f"Unknown provider: {req.provider}"}
    if not req.email or not req.app_password:
        return {"success": False, "error": "Email and app password are required"}
    smtp = PROVIDER_SMTP[req.provider]
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp["host"], smtp["port"], timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(req.email, req.app_password)
    except Exception as e:
        return {"success": False, "error": f"SMTP login failed: {str(e)[:150]}"}
    settings_col.update_one({"user_id": "default"}, {"$set": {
        "email_provider": req.provider,
        "email_provider_email": req.email,
        "email_provider_pass": req.app_password,
        "email_host": smtp["host"],
        "email_port": smtp["port"],
        "email_user": req.email,
        "email_pass": req.app_password,
        "email_from": req.email,
        "email_enabled": True,
        "updated_at": now_iso(),
    }}, upsert=True)
    log_activity("system", {"event": "email_provider_connected", "provider": req.provider, "email": req.email})
    return {"success": True, "email": req.email}


@app.post("/api/email/provider/disconnect")
async def email_provider_disconnect():
    """Disconnect email provider."""
    s = settings_col.find_one({"user_id": "default"}) or {}
    provider = s.get("email_provider", "none")
    settings_col.update_one({"user_id": "default"}, {
        "$set": {
            "email_provider": "none",
            "email_provider_email": "",
            "email_provider_pass": "",
            "email_enabled": False,
            "updated_at": now_iso(),
        }
    })
    log_activity("system", {"event": "email_provider_disconnected", "provider": provider})
    return {"success": True, "disconnected": provider}


# ── Email Drafts ──────────────────────────────────────────────────────────────
@app.get("/api/email/drafts")
async def list_email_drafts():
    """Return all pending email drafts."""
    drafts = list(email_drafts_col.find({"status": "pending"}).sort("created_at", DESCENDING))
    for d in drafts:
        d["_id"] = str(d["_id"])
    return {"drafts": drafts}


@app.get("/api/email/drafts/count")
async def count_email_drafts():
    """Return count of pending drafts (for badge)."""
    count = email_drafts_col.count_documents({"status": "pending"})
    return {"count": count}


@app.post("/api/email/drafts/{draft_id}/send")
async def send_email_draft(draft_id: str):
    """Approve and send an email draft via SMTP."""
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from bson import ObjectId

    try:
        draft = email_drafts_col.find_one({"_id": ObjectId(draft_id), "status": "pending"})
    except Exception:
        raise HTTPException(404, "Invalid draft ID")
    if not draft:
        raise HTTPException(404, "Draft not found or already processed")

    # Get email config
    s = settings_col.find_one({"user_id": "default"}) or {}
    host = s.get("email_host") or os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    port = int(s.get("email_port") or os.environ.get("EMAIL_PORT", "587"))
    user = s.get("email_user") or os.environ.get("EMAIL_USER", "")
    passwd = s.get("email_pass") or os.environ.get("EMAIL_PASS", "")
    from_addr = s.get("email_from") or user

    if not user or not passwd:
        return {"success": False, "error": "Email not configured. Connect a provider in Settings first."}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = draft["subject"]
        msg["From"] = from_addr
        msg["To"] = draft["to"]
        mime_type = "html" if draft.get("html") else "plain"
        msg.attach(MIMEText(draft["body"], mime_type))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(user, passwd)
            server.sendmail(from_addr, draft["to"], msg.as_string())

        email_drafts_col.update_one({"_id": ObjectId(draft_id)}, {"$set": {
            "status": "sent",
            "sent_at": now_iso(),
        }})
        log_activity("system", {"event": "email_draft_sent", "to": draft["to"], "subject": draft["subject"]})
        return {"success": True, "message": f"Email sent to {draft['to']}"}
    except Exception as e:
        return {"success": False, "error": f"Send failed: {str(e)[:200]}"}


@app.delete("/api/email/drafts/{draft_id}")
async def delete_email_draft(draft_id: str):
    """Discard an email draft."""
    from bson import ObjectId
    try:
        result = email_drafts_col.update_one(
            {"_id": ObjectId(draft_id), "status": "pending"},
            {"$set": {"status": "discarded", "discarded_at": now_iso()}}
        )
    except Exception:
        raise HTTPException(404, "Invalid draft ID")
    if result.modified_count == 0:
        raise HTTPException(404, "Draft not found or already processed")
    return {"success": True}


# ============================================================
# WHITE CARD (Enhanced with intuition)
# ============================================================
@app.get("/api/white-card/suggestions")
async def get_white_card_suggestions():
    recent = list(activity_col.find().sort("timestamp", DESCENDING).limit(10))
    top_memories = list(memories_col.find().sort("utility_score", DESCENDING).limit(5))
    active_tasks = list(tasks_col.find({"status": {"$in": ["pending", "in_progress", "planned"]}}))

    suggestions = []

    if not recent:
        suggestions.append({
            "type": "getting_started", "title": "Start a conversation",
            "description": "Chat with me to get started. I can help with coding, analysis, planning, and more.",
            "action": "chat"
        })

    if active_tasks:
        for task in active_tasks[:3]:
            suggestions.append({
                "type": "task_followup", "title": f"Continue: {task.get('title', 'Untitled')}",
                "description": f"You have a {task.get('priority', 'medium')} priority task that needs attention.",
                "action": "task", "task_id": str(task.get("_id", ""))
            })

    if top_memories:
        suggestions.append({
            "type": "memory_insight", "title": "Based on what I know about you",
            "description": f"I've learned {len(top_memories)} things about your preferences. Want to review them?",
            "action": "memories"
        })

    model_calls = [a for a in recent if a.get("type") == "model_call"]
    if model_calls:
        last_topic = model_calls[0].get("details", {}).get("input_preview", "")
        if last_topic:
            suggestions.append({
                "type": "continue_conversation", "title": "Continue where we left off",
                "description": f"We were discussing: {last_topic[:60]}...",
                "action": "chat"
            })

    # K1 insight suggestion
    distillation_count = distillation_col.count_documents({})
    if distillation_count > 0:
        suggestions.append({
            "type": "k1_learning", "title": "Ombra-K1 is learning",
            "description": f"I've distilled {distillation_count} cloud model responses into local learning patterns.",
            "action": "k1"
        })

    return {"suggestions": suggestions}


# ============================================================
# INTUITION SYSTEM
# ============================================================
@app.get("/api/intuition/prediction")
async def get_intent_prediction():
    """Predict user's likely next intent."""
    recent_convos = list(conversations_col.find().sort("updated_at", DESCENDING).limit(3))
    recent_tasks = list(tasks_col.find().sort("updated_at", DESCENDING).limit(3))
    top_memories = list(memories_col.find({"pinned": True}).limit(5))

    predictions = []

    # Analyze recent conversation topics
    for conv in recent_convos:
        turns = conv.get("turns", [])
        if turns:
            last_user = [t for t in turns if t["role"] == "user"]
            if last_user:
                topic = last_user[-1]["content"][:100]
                category = categorize_message(topic)
                predictions.append({
                    "type": "conversation_continuation",
                    "confidence": 0.7,
                    "prediction": f"Likely to continue {category} discussion: {topic[:60]}",
                    "suggested_agent": classify_task_for_agent(topic)
                })

    # Task-based predictions
    for task in recent_tasks:
        if task.get("status") in ["pending", "in_progress", "planned"]:
            predictions.append({
                "type": "task_continuation",
                "confidence": 0.8,
                "prediction": f"May want to work on: {task.get('title', 'Untitled')}",
                "task_id": str(task.get("_id", ""))
            })

    return {"predictions": predictions[:5], "timestamp": now_iso()}


@app.get("/api/intuition/suggestions")
async def get_intuition_suggestions():
    """Get proactive suggestions grounded in memory and activity."""
    suggestions = []

    # Memory-grounded suggestions
    top_memories = list(memories_col.find({"type": {"$in": ["preference", "habit", "context"]}}).sort("utility_score", DESCENDING).limit(3))
    for mem in top_memories:
        suggestions.append({
            "type": "memory_based",
            "content": mem.get("content", "")[:100],
            "memory_type": mem.get("type"),
            "score": mem.get("utility_score", 0)
        })

    # K1 distillation insights
    recent_dist = list(distillation_col.find().sort("timestamp", DESCENDING).limit(3))
    for dist in recent_dist:
        rules = dist.get("extracted_rules", [])
        if rules:
            suggestions.append({
                "type": "k1_insight",
                "content": f"Learned: {', '.join(rules[:2])}",
                "source": "teacher_distillation"
            })

    return {"suggestions": suggestions, "timestamp": now_iso()}


# ============================================================
# WORKSPACE — SOUL, SKILLS (OpenClaw-style)
# ============================================================

class SkillCreate(BaseModel):
    id: str
    content: str

@app.get("/api/workspace/soul")
async def get_soul():
    """Return the SOUL.md persona content."""
    return {"content": load_soul()}

@app.get("/api/skills")
async def get_skills():
    """List all installed skills and which are active."""
    skills = list_skills()
    active = get_active_skill_ids(db)
    for s in skills:
        s["active"] = s["id"] in active
    return skills

@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    content = load_skill(skill_id)
    if not content:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"id": skill_id, "content": content}

@app.post("/api/skills")
async def create_skill(req: SkillCreate):
    """Install or update a skill."""
    ok = install_skill(req.id, req.content)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to install skill")
    return {"status": "installed", "id": req.id}

@app.delete("/api/skills/{skill_id}")
async def remove_skill(skill_id: str):
    """Remove a skill."""
    # Also deactivate it
    settings_col.update_one({"user_id": "default"}, {"$pull": {"active_skills": skill_id}})
    ok = delete_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete skill")
    return {"status": "deleted", "id": skill_id}

@app.post("/api/skills/{skill_id}/activate")
async def activate_skill(skill_id: str):
    """Add a skill to the global active list."""
    skills = [s["id"] for s in list_skills()]
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    settings_col.update_one(
        {"user_id": "default"},
        {"$addToSet": {"active_skills": skill_id}}
    )
    return {"status": "activated", "id": skill_id}

@app.post("/api/skills/{skill_id}/deactivate")
async def deactivate_skill(skill_id: str):
    """Remove a skill from the global active list."""
    settings_col.update_one(
        {"user_id": "default"},
        {"$pull": {"active_skills": skill_id}}
    )
    return {"status": "deactivated", "id": skill_id}


# ============================================================
# WEBHOOKS — inbound triggers → agent
# ============================================================
class WebhookCreate(BaseModel):
    name: str
    description: str = ""
    agent_id: Optional[str] = None

@app.get("/api/webhooks")
async def list_webhooks():
    hooks = list(webhooks_col.find().sort("created_at", DESCENDING).limit(50))
    return [serialize_doc(h) for h in hooks]

@app.post("/api/webhooks")
async def create_webhook_endpoint(req: WebhookCreate):
    hook_id = f"hook_{uuid.uuid4().hex[:12]}"
    doc = {
        "hook_id": hook_id,
        "name": req.name,
        "description": req.description,
        "agent_id": req.agent_id,
        "created_at": now_iso(),
        "trigger_count": 0,
    }
    webhooks_col.insert_one(doc)
    return {"hook_id": hook_id, "name": req.name}

@app.delete("/api/webhooks/{hook_id}")
async def delete_webhook(hook_id: str):
    result = webhooks_col.delete_one({"hook_id": hook_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted"}

@app.post("/api/webhooks/{hook_id}/trigger")
async def trigger_webhook(hook_id: str, request: Request):
    hook = webhooks_col.find_one({"hook_id": hook_id})
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    payload_summary = str(payload)[:500]
    message = f"[Webhook trigger from '{hook.get('name', hook_id)}']: {payload_summary}"
    result = await route_and_respond(message=message, agent_id=hook.get("agent_id"))
    webhooks_col.update_one(
        {"hook_id": hook_id},
        {"$inc": {"trigger_count": 1}, "$set": {"last_triggered": now_iso()}}
    )
    activity_col.insert_one({
        "type": "webhook_trigger", "hook_id": hook_id, "hook_name": hook.get("name"),
        "response_preview": result["response"][:200], "timestamp": now_iso()
    })
    return {"hook_id": hook_id, "response": result["response"], "provider": result.get("provider_used")}


# ============================================================
# PHASE 4: AUTONOMY DAEMON STATUS + CONTROL
# ============================================================
@app.get("/api/autonomy/status")
async def get_autonomy_status():
    """Get autonomy daemon status."""
    if autonomy_daemon:
        return autonomy_daemon.get_status()
    return {"running": False, "paused": False, "stats": {}}


@app.post("/api/autonomy/pause")
async def pause_autonomy():
    """Pause the autonomy daemon."""
    if autonomy_daemon:
        autonomy_daemon.paused = True
        log_activity("autonomy", {"event": "daemon_paused"})
        return {"status": "paused"}
    return {"status": "not_running"}


@app.post("/api/autonomy/resume")
async def resume_autonomy():
    """Resume the autonomy daemon."""
    if autonomy_daemon:
        autonomy_daemon.paused = False
        log_activity("autonomy", {"event": "daemon_resumed"})
        return {"status": "resumed"}
    return {"status": "not_running"}


@app.post("/api/autonomy/stop")
async def stop_autonomy():
    """Stop the autonomy daemon completely."""
    if autonomy_daemon:
        autonomy_daemon.stop()
        log_activity("autonomy", {"event": "daemon_stopped"})
        return {"status": "stopped"}
    return {"status": "not_running"}


@app.post("/api/autonomy/tick")
async def force_tick():
    """Force a daemon tick."""
    if autonomy_daemon:
        result = await autonomy_daemon.tick()
        return {"status": "ticked", "result": result}
    return {"status": "not_running"}


# ============================================================
# BRAIN STATE (reasoning visualization)
# ============================================================
@app.get("/api/brain/state")
async def get_brain_state():
    """Aggregate reasoning data for the Brain View visualization."""
    now = datetime.now(timezone.utc)
    since_2h = (now - timedelta(hours=2)).isoformat()
    since_24h = (now - timedelta(hours=24)).isoformat()

    def _age(ts_str):
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return int((now - ts).total_seconds())
        except Exception:
            return 9999

    def _time_label(ts_str):
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            delta = now - ts
            if delta.total_seconds() < 60:
                return "just now"
            if delta.total_seconds() < 3600:
                return f"{int(delta.total_seconds() / 60)}m ago"
            return f"{int(delta.total_seconds() / 3600)}h ago"
        except Exception:
            return ""

    # ── Goals region ───────────────────────────────────────
    goal_mems = list(db["memories"].find(
        {"type": "k1_goals", "created_at": {"$gte": since_24h}}
    ).sort("created_at", -1).limit(5))
    goals_items = []
    current_goals = []
    for m in goal_mems:
        content = m.get("content", "")
        ts = m.get("created_at", "")
        goals_items.append({
            "type": "goal", "content": content.replace("K1 Goals: ", ""),
            "time": _time_label(ts), "age_seconds": _age(ts)
        })
        if not current_goals:
            current_goals = [g.strip() for g in content.replace("K1 Goals: ", "").split("|") if g.strip()]

    # ── Reasoning region ───────────────────────────────────
    reasoning_logs = list(db["activity_log"].find({
        "type": {"$in": ["k1_subagent_delegated", "k1_subagent_completed", "k1_tool_attempt"]},
        "timestamp": {"$gte": since_2h}
    }).sort("timestamp", -1).limit(15))
    reasoning_items = []
    for log in reasoning_logs:
        d = log.get("details", {})
        ts = log.get("timestamp", "")
        lt = log.get("type", "")
        if lt == "k1_subagent_delegated":
            reasoning_items.append({
                "type": "reasoning",
                "content": f"Delegated to {d.get('agent_name', '?')}: {d.get('subject', '')}",
                "details": d.get("reason", ""),
                "time": _time_label(ts), "age_seconds": _age(ts)
            })
        elif lt == "k1_subagent_completed":
            reasoning_items.append({
                "type": "reasoning",
                "content": f"Completed: {d.get('response_preview', '')[:120]}",
                "details": f"Verified: {d.get('verified', '?')} — {d.get('verify_note', '')}",
                "time": _time_label(ts), "age_seconds": _age(ts)
            })
        elif lt == "k1_tool_attempt":
            reasoning_items.append({
                "type": "tool",
                "content": f"{d.get('tool', '?')}({', '.join(f'{k}={v}' for k, v in list((d.get('args') or {}).items())[:2])})",
                "details": d.get("output_preview", "")[:100],
                "time": _time_label(ts), "age_seconds": _age(ts)
            })

    # ── Memory region ──────────────────────────────────────
    recent_mems = list(db["memories"].find({
        "type": {"$in": ["k1_research", "k1_insight", "k1_synthesis", "k1_tool_learn"]},
        "created_at": {"$gte": since_24h}
    }).sort("created_at", -1).limit(10))
    memory_items = [{
        "type": "insight" if "insight" in m.get("type", "") else "research" if "research" in m.get("type", "") else "synthesis",
        "content": m.get("content", "")[:200],
        "time": _time_label(m.get("created_at", "")),
        "age_seconds": _age(m.get("created_at", ""))
    } for m in recent_mems]

    # ── Actions region ─────────────────────────────────────
    action_logs = list(db["activity_log"].find({
        "type": {"$in": ["k1_autonomous_report", "k1_tool_action"]},
        "timestamp": {"$gte": since_2h}
    }).sort("timestamp", -1).limit(10))
    action_items = []
    for log in action_logs:
        d = log.get("details", {})
        ts = log.get("timestamp", "")
        if log.get("type") == "k1_autonomous_report":
            action_items.append({
                "type": "action", "content": d.get("summary", "")[:200],
                "time": _time_label(ts), "age_seconds": _age(ts)
            })
        else:
            action_items.append({
                "type": "tool",
                "content": f"Tool: {d.get('tool', '?')} — {'OK' if d.get('success') else 'FAIL'}",
                "details": d.get("preview", "")[:100],
                "time": _time_label(ts), "age_seconds": _age(ts)
            })

    # ── Learning region ────────────────────────────────────
    learn_mems = list(db["memories"].find({
        "type": {"$in": ["internet_knowledge", "creative_idea", "k1_daily_check"]},
        "created_at": {"$gte": since_24h}
    }).sort("created_at", -1).limit(10))
    learning_items = [{
        "type": "learning",
        "content": m.get("content", "")[:200],
        "time": _time_label(m.get("created_at", "")),
        "age_seconds": _age(m.get("created_at", ""))
    } for m in learn_mems]

    # ── Planning region ────────────────────────────────────
    planned_tasks = list(db["tasks"].find({
        "status": {"$in": ["pending", "planned", "in_progress"]}
    }).sort("created_at", -1).limit(8))
    planning_items = [{
        "type": "plan",
        "content": t.get("title", ""),
        "details": t.get("description", "")[:100],
        "time": _time_label(t.get("created_at", "")),
        "age_seconds": _age(t.get("created_at", ""))
    } for t in planned_tasks]

    # ── Thought stream (unified timeline) ──────────────────
    all_thoughts = sorted(
        goals_items + reasoning_items + memory_items + action_items + learning_items + planning_items,
        key=lambda x: x.get("age_seconds", 9999)
    )[:30]

    # ── Region summaries ───────────────────────────────────
    def _summary(items, fallback="Idle"):
        if items:
            return items[0]["content"][:120]
        return fallback

    # ── Stats from daemon ──────────────────────────────────
    daemon_stats = autonomy_daemon.stats if autonomy_daemon else {}

    return {
        "regions": {
            "goals":     {"items": goals_items,     "summary": _summary(goals_items, "No active goals")},
            "reasoning": {"items": reasoning_items, "summary": _summary(reasoning_items, "No active reasoning")},
            "memory":    {"items": memory_items,    "summary": _summary(memory_items, "No recent memories")},
            "actions":   {"items": action_items,    "summary": _summary(action_items, "No recent actions")},
            "learning":  {"items": learning_items,  "summary": _summary(learning_items, "No recent learning")},
            "planning":  {"items": planning_items,  "summary": _summary(planning_items, "No active plans")},
        },
        "thought_stream": all_thoughts,
        "current_goals": current_goals,
        "stats": daemon_stats,
        "timestamp": now.isoformat(),
    }


# ============================================================
# TASK LIFECYCLE (pause/resume/cancel)
# ============================================================
@app.put("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    tasks_col.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "paused", "updated_at": now_iso()}})
    log_activity("autonomy", {"event": "task_paused", "task_id": task_id})
    task = tasks_col.find_one({"_id": ObjectId(task_id)})
    return serialize_doc(task)


@app.put("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    tasks_col.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "in_progress", "updated_at": now_iso()}})
    log_activity("autonomy", {"event": "task_resumed", "task_id": task_id})
    task = tasks_col.find_one({"_id": ObjectId(task_id)})
    return serialize_doc(task)


@app.put("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    tasks_col.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
    log_activity("autonomy", {"event": "task_cancelled", "task_id": task_id})
    task = tasks_col.find_one({"_id": ObjectId(task_id)})
    return serialize_doc(task)


# ============================================================
# PHASE 5: TASK SCHEDULING
# ============================================================
class TaskScheduleRequest(BaseModel):
    mode: str  # "none", "interval", or "cron"
    interval_seconds: Optional[int] = None
    cron_expr: Optional[str] = None
    timezone: Optional[str] = "UTC"
    schedule_enabled: Optional[bool] = True
    respect_quiet_hours: Optional[bool] = True

@app.put("/api/tasks/{task_id}/schedule")
async def update_task_schedule(task_id: str, req: TaskScheduleRequest):
    """Update task scheduling configuration."""
    schedule = {
        "mode": req.mode,
        "interval_seconds": req.interval_seconds,
        "cron_expr": req.cron_expr,
        "timezone": req.timezone
    }
    
    # Compute next_run_at if schedule is enabled
    next_run_at = None
    if req.schedule_enabled and req.mode != "none" and task_scheduler:
        next_run_at = task_scheduler._compute_next_run(schedule)
    
    update_data = {
        "schedule": schedule,
        "schedule_enabled": req.schedule_enabled,
        "respect_quiet_hours": req.respect_quiet_hours,
        "updated_at": now_iso()
    }
    
    if next_run_at:
        update_data["next_run_at"] = next_run_at.isoformat()
    
    tasks_col.update_one({"_id": task_id}, {"$set": update_data})
    log_activity("scheduler", {"event": "schedule_updated", "task_id": task_id, "mode": req.mode})
    
    task = tasks_col.find_one({"_id": task_id})
    return serialize_doc(task)


@app.post("/api/tasks/{task_id}/run-now")
async def run_task_now(task_id: str):
    """Immediately enqueue a task for execution (bypass schedule)."""
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not available")
    
    try:
        task = tasks_col.find_one({"_id": ObjectId(task_id)})
    except:
        raise HTTPException(status_code=404, detail="Invalid task ID format")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    await task_queue.enqueue(task_id, priority=10)  # High priority for manual runs
    log_activity("scheduler", {"event": "task_run_now", "task_id": task_id})
    
    return {"status": "enqueued", "task_id": task_id}


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Get task scheduler status."""
    if task_scheduler:
        return task_scheduler.get_status()
    return {"running": False, "stats": {}}


@app.post("/api/scheduler/pause")
async def pause_scheduler():
    """Pause the task scheduler."""
    if task_scheduler:
        task_scheduler.paused = True
        log_activity("scheduler", {"event": "scheduler_paused"})
        return {"status": "paused"}
    return {"status": "not_running"}


@app.post("/api/scheduler/resume")
async def resume_scheduler():
    """Resume the task scheduler."""
    if task_scheduler:
        task_scheduler.paused = False
        log_activity("scheduler", {"event": "scheduler_resumed"})
        return {"status": "resumed"}
    return {"status": "not_running"}


# ============================================================
# PHASE 5: TASK QUEUE & WORKER POOL
# ============================================================
@app.get("/api/queue/status")
async def get_queue_status():
    """Get task queue and worker pool status."""
    if task_queue:
        return task_queue.get_status()
    return {"running": False, "queue_size": 0, "active_workers": 0, "stats": {}}


@app.post("/api/queue/rebalance")
async def rebalance_queue():
    """Trigger manual queue rebalancing (force auto-scale check)."""
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not available")
    
    # Force an immediate auto-scale check by adjusting thresholds temporarily
    log_activity("queue", {"event": "manual_rebalance_requested"})
    return {"status": "rebalancing", "message": "Auto-scale will adjust on next tick"}


# ============================================================
# PHASE 5: CREATIVE EXPLORATION
# ============================================================
class CreativitySettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    cadence_ticks: Optional[int] = None
    draft_tasks_auto: Optional[bool] = None

@app.get("/api/creativity/status")
async def get_creativity_status():
    """Get creative exploration engine status."""
    if creative_explorer:
        return creative_explorer.get_status()
    return {"enabled": False, "stats": {}}


@app.post("/api/creativity/run")
async def run_creativity_now():
    """Manually trigger creative idea generation."""
    if not creative_explorer:
        raise HTTPException(status_code=503, detail="Creative explorer not available")
    
    if not creative_explorer.enabled:
        raise HTTPException(status_code=400, detail="Creative exploration is disabled in settings")
    
    idea = await creative_explorer.generate_idea()
    log_activity("creativity", {"event": "manual_idea_generation"})
    
    if idea:
        return {"status": "generated", "idea": idea}
    return {"status": "no_idea", "reason": "insufficient_context"}


@app.put("/api/creativity/settings")
async def update_creativity_settings(req: CreativitySettingsRequest):
    """Update creative exploration settings."""
    if not creative_explorer:
        raise HTTPException(status_code=503, detail="Creative explorer not available")
    
    creative_explorer.update_settings(
        enabled=req.enabled,
        cadence_ticks=req.cadence_ticks,
        draft_tasks_auto=req.draft_tasks_auto
    )
    
    # Update in database
    update_data = {}
    if req.enabled is not None:
        update_data["creativity_enabled"] = req.enabled
    if req.cadence_ticks is not None:
        update_data["creativity_cadence_ticks"] = req.cadence_ticks
    if req.draft_tasks_auto is not None:
        update_data["creativity_draft_tasks_auto"] = req.draft_tasks_auto
    
    if update_data:
        settings_col.update_one({"user_id": "default"}, {"$set": update_data})
    
    log_activity("creativity", {"event": "settings_updated", "settings": req.dict(exclude_none=True)})
    return creative_explorer.get_status()


@app.post("/api/creativity/idea/{idea_id}/accept")
async def accept_creative_idea(idea_id: str):
    """Mark a creative idea as accepted."""
    if creative_explorer:
        creative_explorer.mark_idea_accepted(idea_id)
    return {"status": "accepted"}


@app.post("/api/creativity/idea/{idea_id}/ignore")
async def ignore_creative_idea(idea_id: str):
    """Mark a creative idea as ignored."""
    if creative_explorer:
        creative_explorer.mark_idea_ignored(idea_id)
    return {"status": "ignored"}


# ============================================================
# PHASE 5: ANALYTICS & MONITORING
# ============================================================
@app.get("/api/analytics/overview")
async def get_analytics_overview():
    """Get high-level analytics overview."""
    # Aggregate key metrics from the last 24 hours
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    # Total activity count
    total_activities = activity_col.count_documents({
        "timestamp": {"$gte": day_ago.isoformat()}
    })
    
    # Task stats
    total_tasks = tasks_col.count_documents({})
    completed_tasks_24h = tasks_col.count_documents({
        "status": "completed",
        "completed_at": {"$gte": day_ago.isoformat()}
    })
    failed_tasks_24h = tasks_col.count_documents({
        "status": "failed",
        "failed_at": {"$gte": day_ago.isoformat()}
    })
    
    # Memory stats
    total_memories = memories_col.count_documents({})
    pinned_memories = memories_col.count_documents({"pinned": True})
    
    # Provider usage (last 24h)
    provider_pipeline = [
        {"$match": {"type": "model", "timestamp": {"$gte": day_ago.isoformat()}}},
        {"$group": {"_id": "$details.provider", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    provider_usage = list(activity_col.aggregate(provider_pipeline))
    
    return {
        "period": "24h",
        "timestamp": now.isoformat(),
        "activities": {
            "total": total_activities
        },
        "tasks": {
            "total": total_tasks,
            "completed_24h": completed_tasks_24h,
            "failed_24h": failed_tasks_24h,
            "success_rate": round(completed_tasks_24h / max(1, completed_tasks_24h + failed_tasks_24h) * 100, 1)
        },
        "memory": {
            "total": total_memories,
            "pinned": pinned_memories
        },
        "providers": provider_usage
    }


@app.get("/api/analytics/autonomy")
async def get_analytics_autonomy():
    """Get autonomy daemon analytics."""
    if not autonomy_daemon:
        return {"enabled": False}
    
    status = autonomy_daemon.get_status()
    
    # Additional metrics from activity log
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    autonomy_activities = list(activity_col.find({
        "type": "autonomy_daemon",
        "timestamp": {"$gte": day_ago.isoformat()}
    }).sort("timestamp", -1).limit(100))
    
    return {
        **status,
        "recent_activities": len(autonomy_activities),
        "period": "24h"
    }


@app.get("/api/analytics/tasks")
async def get_analytics_tasks():
    """Get task execution analytics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    
    # Task status breakdown
    status_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_breakdown = {item["_id"]: item["count"] for item in tasks_col.aggregate(status_pipeline)}
    
    # Execution time stats (last 7 days with duration_ms)
    duration_pipeline = [
        {"$match": {"duration_ms": {"$exists": True, "$gt": 0}, "completed_at": {"$gte": week_ago.isoformat()}}},
        {"$group": {
            "_id": None,
            "avg_duration_ms": {"$avg": "$duration_ms"},
            "min_duration_ms": {"$min": "$duration_ms"},
            "max_duration_ms": {"$max": "$duration_ms"},
            "total_tasks": {"$sum": 1}
        }}
    ]
    duration_stats = list(tasks_col.aggregate(duration_pipeline))
    
    # Scheduled tasks count
    scheduled_count = tasks_col.count_documents({"schedule_enabled": True})
    
    return {
        "status_breakdown": status_breakdown,
        "duration_stats": duration_stats[0] if duration_stats else {},
        "scheduled_tasks": scheduled_count,
        "queue_status": task_queue.get_status() if task_queue else {}
    }


@app.get("/api/analytics/tools")
async def get_analytics_tools():
    """Get tool usage analytics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    # Tool execution counts (last 24h)
    tool_pipeline = [
        {"$match": {"type": "tool", "timestamp": {"$gte": day_ago.isoformat()}}},
        {"$group": {"_id": "$details.tool", "count": {"$sum": 1}, "avg_duration": {"$avg": "$duration_ms"}}},
        {"$sort": {"count": -1}}
    ]
    tool_usage = list(activity_col.aggregate(tool_pipeline))
    
    # Blocked commands
    blocked_pipeline = [
        {"$match": {"type": "tool", "details.blocked": True, "timestamp": {"$gte": day_ago.isoformat()}}},
        {"$count": "total"}
    ]
    blocked_result = list(activity_col.aggregate(blocked_pipeline))
    blocked_count = blocked_result[0]["total"] if blocked_result else 0
    
    return {
        "tool_usage": tool_usage,
        "blocked_commands_24h": blocked_count,
        "period": "24h"
    }


@app.get("/api/analytics/memory")
async def get_analytics_memory():
    """Get memory system analytics."""
    # Memory type breakdown
    type_pipeline = [
        {"$group": {"_id": "$type", "count": {"$sum": 1}, "avg_score": {"$avg": "$utility_score"}}}
    ]
    type_breakdown = list(memories_col.aggregate(type_pipeline))
    
    # Utility score distribution
    score_pipeline = [
        {"$bucket": {
            "groupBy": "$utility_score",
            "boundaries": [0, 0.25, 0.5, 0.75, 1.0],
            "default": "other",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    score_distribution = list(memories_col.aggregate(score_pipeline))
    
    # Recent decay operations (from activity log)
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    decay_activities = list(activity_col.find({
        "type": "autonomy_daemon",
        "details.actions": {"$regex": "memory_decay"},
        "timestamp": {"$gte": day_ago.isoformat()}
    }).limit(10))
    
    total_decayed = sum([
        int(a["details"]["actions"][0].split(": ")[1].split(" ")[0])
        for a in decay_activities
        if "memory_decay" in str(a.get("details", {}).get("actions", []))
    ]) if decay_activities else 0
    
    return {
        "type_breakdown": type_breakdown,
        "score_distribution": score_distribution,
        "total_memories": memories_col.count_documents({}),
        "pinned_memories": memories_col.count_documents({"pinned": True}),
        "decayed_24h": total_decayed
    }


@app.get("/api/analytics/providers")
async def get_analytics_providers():
    """Get LLM provider performance analytics."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    # Provider usage and latency (last 24h)
    provider_pipeline = [
        {"$match": {"type": "model", "timestamp": {"$gte": day_ago.isoformat()}}},
        {"$group": {
            "_id": "$details.provider",
            "count": {"$sum": 1},
            "avg_duration_ms": {"$avg": "$duration_ms"},
            "total_duration_ms": {"$sum": "$duration_ms"}
        }},
        {"$sort": {"count": -1}}
    ]
    provider_stats = list(activity_col.aggregate(provider_pipeline))
    
    # Error rates by provider
    error_pipeline = [
        {"$match": {"type": "model", "details.error": {"$exists": True}, "timestamp": {"$gte": day_ago.isoformat()}}},
        {"$group": {"_id": "$details.provider", "errors": {"$sum": 1}}}
    ]
    error_stats = {item["_id"]: item["errors"] for item in activity_col.aggregate(error_pipeline)}
    
    # Enrich with error rates
    for stat in provider_stats:
        provider = stat["_id"]
        stat["errors"] = error_stats.get(provider, 0)
        stat["error_rate"] = round(stat["errors"] / max(1, stat["count"]) * 100, 2)
    
    return {
        "providers": provider_stats,
        "period": "24h"
    }



# ============================================================
# TOOL SAFETY POLICIES
# ============================================================
class ToolPolicyUpdate(BaseModel):
    mode: Optional[str] = None
    denylist: Optional[List[str]] = None
    allowlist: Optional[List[str]] = None

@app.get("/api/tools/policies")
async def get_tool_policies():
    policies = tool_policies_col.find_one({"user_id": "default"})
    if not policies:
        return {"mode": "denylist", "denylist": DEFAULT_DENYLIST, "allowlist": DEFAULT_ALLOWLIST}
    return serialize_doc(policies)


@app.put("/api/tools/policies")
async def update_tool_policies(req: ToolPolicyUpdate):
    update = {"updated_at": now_iso()}
    if req.mode:
        update["mode"] = req.mode
    if req.denylist is not None:
        update["denylist"] = req.denylist
    if req.allowlist is not None:
        update["allowlist"] = req.allowlist
    tool_policies_col.update_one({"user_id": "default"}, {"$set": update}, upsert=True)
    log_activity("system", {"event": "tool_policies_updated"})
    return await get_tool_policies()


# ============================================================
# AUTONOMOUS MULTITASK EXECUTION (K1 v2)
# ============================================================
@app.post("/api/k1/autonomous-run")
async def k1_autonomous_run(req: ChatRequest):
    """Ombra-K1 v2: autonomous multitask execution.
    Uses local model first (Mistral), escalates to cloud if needed,
    and distills cloud responses for learning."""
    start_time = time.time()
    message = req.message

    # 1. Try local model (Mistral) first for creative/autonomous response
    local_success = False
    local_response = ""
    try:
        ollama_status = await check_ollama_health()
        if ollama_status["available"]:
            # Use Mistral for more capable local inference
            model = "mistral" if "mistral" in str(ollama_status["models"]) else (ollama_status["models"][0] if ollama_status["models"] else "tinyllama")

            # Enhanced K1 prompt with chain-of-thought
            k1_system = """You are Ombra-K1, an autonomous AI assistant running locally. You are creative, proactive, and capable.

When given a task:
1. THINK step by step about the best approach
2. Consider multiple strategies
3. Provide a comprehensive answer
4. If you're uncertain, say so clearly - a cloud model will be consulted

Be creative. Suggest novel approaches. Think outside the box."""

            local_response = await call_ollama(message, k1_system, model)
            # Check quality - if response is too short or uncertain, escalate
            if local_response and len(local_response.strip()) > 50:
                # Check for uncertainty markers
                uncertainty_markers = ["i'm not sure", "i don't know", "i cannot", "i can't", "uncertain", "beyond my"]
                is_uncertain = any(m in local_response.lower() for m in uncertainty_markers)
                if not is_uncertain:
                    local_success = True
    except Exception:
        pass

    # 2. If local failed or was uncertain, escalate to cloud
    cloud_response = ""
    cloud_provider = ""
    if not local_success:
        try:
            cloud_response = await call_api_provider(
                message,
                "You are Ombra, an autonomous AI. Be creative, thorough, and proactive. Provide comprehensive answers.",
                "anthropic", None
            )
            cloud_provider = "anthropic"

            # Distill cloud response for local learning
            task_sig = categorize_message(message) + ":" + message[:50]
            distillation = generate_teacher_distillation(cloud_response, task_sig)
            distillation["provider"] = "anthropic"
            distillation["model"] = "claude-sonnet-4-5-20250929"
            distillation_col.insert_one(distillation)

            log_activity("k1_learning", {
                "event": "cloud_escalation",
                "reason": "local_uncertain" if local_response else "local_failed",
                "provider": cloud_provider,
                "rules_extracted": len(distillation.get("extracted_rules", []))
            })
        except Exception:
            # Fallback to other providers
            for fp in ["openai", "gemini"]:
                try:
                    cloud_response = await call_api_provider(message, "Be creative and thorough.", fp, None)
                    cloud_provider = fp
                    break
                except Exception:
                    continue

    duration_ms = int((time.time() - start_time) * 1000)

    final_response = local_response if local_success else (cloud_response or local_response or "I couldn't process this request.")
    source = "local" if local_success else ("cloud" if cloud_response else "local_fallback")

    log_activity("k1_autonomous", {
        "source": source,
        "local_success": local_success,
        "cloud_escalated": bool(cloud_response),
        "cloud_provider": cloud_provider,
        "input_preview": message[:100],
        "output_preview": final_response[:200],
        "duration_ms": duration_ms
    })

    return {
        "response": final_response,
        "source": source,
        "local_attempted": True,
        "local_success": local_success,
        "cloud_escalated": bool(cloud_response and not local_success),
        "cloud_provider": cloud_provider or None,
        "duration_ms": duration_ms,
        "model_used": "mistral" if local_success else (cloud_provider or "unknown")
    }


# ============================================================
# NEW SUBSYSTEM ENDPOINTS
# ============================================================

# ── Plugin Hooks ──────────────────────────────────────────────────────────────

@app.get("/api/hooks")
async def list_hooks():
    return {"hooks": hook_manager.list_hooks(), "stats": hook_manager.get_stats()}

@app.get("/api/hooks/log")
async def hooks_log(limit: int = 50):
    return {"log": hook_manager.get_execution_log(limit)}

@app.post("/api/hooks/{hook_id}/enable")
async def enable_hook(hook_id: str):
    if hook_manager.enable(hook_id):
        return {"status": "enabled"}
    raise HTTPException(status_code=404, detail="Hook not found")

@app.post("/api/hooks/{hook_id}/disable")
async def disable_hook(hook_id: str):
    if hook_manager.disable(hook_id):
        return {"status": "disabled"}
    raise HTTPException(status_code=404, detail="Hook not found")

# ── Codebase Intelligence ─────────────────────────────────────────────────────

@app.get("/api/codebase/graph")
async def codebase_graph(directory: str = "/tmp/ombra_workspace"):
    try:
        from codebase_intelligence import file_graph
        file_graph.build(directory)
        return {
            "nodes": len(file_graph.nodes),
            "edges": len(file_graph.edges),
            "files": list(file_graph.nodes.keys())[:100],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/codebase/search")
async def codebase_search(q: str, search_type: str = "symbol"):
    try:
        from codebase_intelligence import file_graph
        if not file_graph.nodes:
            file_graph.build("/tmp/ombra_workspace")
        if search_type == "symbol":
            return {"results": file_graph.search_symbol(q)[:30]}
        else:
            return {"results": file_graph.search_code(q, "/tmp/ombra_workspace")[:30]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── RAG / Vector Embeddings ──────────────────────────────────────────────────

@app.post("/api/rag/index")
async def rag_index(directory: str = "/tmp/ombra_workspace"):
    try:
        from rag_engine import codebase_rag
        stats = codebase_rag.index_directory(directory)
        return {"status": "indexed", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rag/search")
async def rag_search(q: str, scope: str = "all", top_k: int = 5):
    try:
        from rag_engine import codebase_rag
        results = codebase_rag.search(q, top_k=top_k, scope=scope)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── MCP Servers ──────────────────────────────────────────────────────────────

@app.get("/api/mcp/status")
async def mcp_status():
    try:
        from mcp_client import mcp_manager
        return {"status": mcp_manager.get_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mcp/connect")
async def mcp_connect(request: Request):
    try:
        from mcp_client import mcp_manager, MCPServerConfig
        payload = await request.json()
        server_id = payload.get("server_id", "")
        command = payload.get("command", "")
        args = payload.get("args", [])
        url = payload.get("url", "")
        if not server_id:
            raise HTTPException(status_code=400, detail="server_id is required")
        cmd_args = args if isinstance(args, list) else (args.split() if args else [])
        transport = "sse" if url else "stdio"
        config = MCPServerConfig(
            server_id=server_id,
            name=server_id,
            transport=transport,
            command=command,
            args=cmd_args,
            url=url,
        )
        result = await mcp_manager.add_server(config)
        return {"status": "connected", "server_id": server_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/mcp/{server_id}")
async def mcp_disconnect(server_id: str):
    try:
        from mcp_client import mcp_manager
        await mcp_manager.remove_server(server_id)
        return {"status": "disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Sub-Agents ───────────────────────────────────────────────────────────────

@app.post("/api/subagents/run")
async def run_subagents(task: str, max_parallel: int = 3):
    try:
        from sub_agents import sub_agent_orchestrator
        result = await sub_agent_orchestrator.run(task, max_parallel=max_parallel)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Streaming ────────────────────────────────────────────────────────────────

@app.get("/api/stream/{channel_id}")
async def stream_channel(channel_id: str):
    channel = stream_manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return StreamingResponse(
        sse_generator(channel),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.get("/api/stream")
async def list_streams():
    return {"channels": stream_manager.list_channels()}

# ── GitHub Integration ───────────────────────────────────────────────────────

@app.get("/api/github/config")
async def get_github_config():
    """Return current GitHub owner/repo config (token masked)."""
    owner = os.environ.get("GITHUB_OWNER", "")
    repo = os.environ.get("GITHUB_REPO", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "owner": owner,
        "repo": repo,
        "token_set": bool(token),
        "token_preview": f"{token[:8]}..." if token else "",
    }

@app.post("/api/github/config")
async def set_github_config(request: Request):
    """Set GITHUB_OWNER, GITHUB_REPO and optionally GITHUB_TOKEN at runtime, persisted to .env."""
    payload = await request.json()
    owner = payload.get("owner", "").strip()
    repo = payload.get("repo", "").strip()
    token = payload.get("token", "").strip()
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="owner and repo are required")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path) as _ef:
            env_lines = [l for l in _ef.readlines()
                         if not l.startswith("GITHUB_OWNER=")
                         and not l.startswith("GITHUB_REPO=")
                         and (not token or not l.startswith("GITHUB_TOKEN="))]
    env_lines.append(f"GITHUB_OWNER={owner}\n")
    env_lines.append(f"GITHUB_REPO={repo}\n")
    if token:
        env_lines.append(f"GITHUB_TOKEN={token}\n")
    with open(env_path, "w") as _ef:
        _ef.writelines(env_lines)
    os.environ["GITHUB_OWNER"] = owner
    os.environ["GITHUB_REPO"] = repo
    if token:
        os.environ["GITHUB_TOKEN"] = token
    log_activity("system", {"event": "github_config_updated", "owner": owner, "repo": repo})
    return {"status": "saved", "owner": owner, "repo": repo}

@app.get("/api/github/status")
async def github_status():
    try:
        from github_integration import github_client
        repo = await github_client.get_repo()
        return {"connected": True, "repo": repo}
    except Exception as e:
        return {"connected": False, "error": str(e)}

# ── Vision ───────────────────────────────────────────────────────────────────

@app.post("/api/vision/analyze")
async def vision_analyze(image: str, prompt: str = "Describe this image.", mode: str = "describe"):
    try:
        from vision_engine import vision_engine
        if mode == "ocr":
            result = await vision_engine.extract_text(image)
        elif mode == "ui_analysis":
            result = await vision_engine.analyze_ui(image)
        else:
            result = await vision_engine.analyze(image, prompt=prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Context Engine ───────────────────────────────────────────────────────────

@app.post("/api/context/build")
async def build_context(message: str, max_tokens: int = 4000):
    try:
        from context_engine import context_engine
        context = context_engine.build_context(
            message=message,
            conversation_history=[],
            active_files=[],
            memories=[],
            max_tokens=max_tokens,
        )
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Security Center (Blue Team) ─────────────────────────────────────────────

@app.post("/api/security/port-scan")
async def api_port_scan(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    host = data.get("host", "localhost")
    ports = data.get("ports")
    timeout = data.get("timeout", 2.0)
    try:
        result = await scan_ports(host, ports, timeout)
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "port_scan"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/ssl-check")
async def api_ssl_check(request: Request):
    data = await request.json()
    try:
        result = await check_ssl(data["host"], data.get("port", 443))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "ssl_check"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/system-audit")
async def api_system_audit():
    try:
        result = await audit_system()
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "system_audit"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/log-analysis")
async def api_log_analysis(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await analyze_logs(data.get("log_paths"), data.get("lines", 2000))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "log_analysis"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/dns-check")
async def api_dns_check(request: Request):
    data = await request.json()
    try:
        return await check_dns(data["domain"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/http-headers")
async def api_http_headers(request: Request):
    data = await request.json()
    try:
        result = await check_http_headers(data["url"])
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "http_headers"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/file-hashes")
async def api_file_hashes(request: Request):
    data = await request.json()
    try:
        return await compute_file_hashes(data["paths"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/integrity-check")
async def api_integrity_check(request: Request):
    data = await request.json()
    try:
        return await check_file_integrity(data["baseline"], data["current"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/dep-scan")
async def api_dep_scan(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        return await scan_dependencies(data.get("project_path", "/home/azureuser/Ombra"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/ip-lookup")
async def api_ip_lookup(request: Request):
    data = await request.json()
    try:
        return await lookup_ip_reputation(data["ip"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/full-scan")
async def api_full_scan(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await full_security_scan(data.get("host", "localhost"))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "full_scan"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/security/history")
async def api_security_history(scan_type: str = None, limit: int = 20):
    try:
        scan_col = db["security_scans"]
        query = {}
        if scan_type:
            query["type"] = scan_type
        scans = list(scan_col.find(query, {"_id": 0}).sort("scan_time", DESCENDING).limit(limit))
        return {"scans": scans, "total": scan_col.count_documents(query)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/security/dashboard")
async def api_security_dashboard():
    """Aggregated security overview for the dashboard."""
    try:
        scan_col = db["security_scans"]
        latest = {}
        for stype in ["port_scan", "system_audit", "log_analysis", "ssl_check", "http_headers", "full_scan"]:
            doc = scan_col.find_one({"type": stype}, {"_id": 0}, sort=[("scan_time", DESCENDING)])
            if doc:
                latest[stype] = doc

        overall_score = None
        if "full_scan" in latest and "overall_score" in latest["full_scan"]:
            overall_score = latest["full_scan"]["overall_score"]
        elif "system_audit" in latest and "summary" in latest["system_audit"]:
            overall_score = latest["system_audit"]["summary"].get("score")

        alerts = []
        if "log_analysis" in latest:
            alerts.extend(latest["log_analysis"].get("alerts", []))
        if "system_audit" in latest:
            for f in latest["system_audit"].get("findings", [])[:5]:
                if f["severity"] in ("critical", "high"):
                    alerts.append({"type": f["category"], "severity": f["severity"], "message": f["finding"]})

        return {
            "overall_score": overall_score,
            "overall_grade": "A" if (overall_score or 0) >= 90 else "B" if (overall_score or 0) >= 75 else "C" if (overall_score or 0) >= 60 else "D" if (overall_score or 0) >= 40 else "F",
            "latest_scans": {k: v.get("scan_time") for k, v in latest.items()},
            "alerts": alerts[:10],
            "port_summary": latest.get("port_scan", {}).get("summary"),
            "system_summary": latest.get("system_audit", {}).get("summary"),
            "log_summary": latest.get("log_analysis", {}).get("summary"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── External Recon Endpoints ─────────────────────────────────────────────────

@app.post("/api/security/whois")
async def api_whois(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await whois_lookup(data["target"])
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "whois"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/subdomains")
async def api_subdomains(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await enumerate_subdomains(data["domain"])
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "subdomains"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/tech-fingerprint")
async def api_tech_fingerprint(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await fingerprint_technology(data["url"])
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "tech_fingerprint"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/traceroute")
async def api_traceroute(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await run_traceroute(data["host"], data.get("max_hops", 20))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "traceroute"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/banner-grab")
async def api_banner_grab(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await grab_banners(data["host"], data.get("ports"))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "banner_grab"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/security/wayback")
async def api_wayback(request: Request):
    body = await request.body()
    data = json.loads(body) if body else {}
    try:
        result = await wayback_lookup(data["url"], data.get("limit", 20))
        scan_col = db["security_scans"]
        scan_col.insert_one({**result, "type": "wayback"})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
