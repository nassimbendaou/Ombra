import os
import json
import asyncio
import subprocess
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pymongo import MongoClient, DESCENDING, TEXT
from bson import ObjectId
import httpx

load_dotenv()

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
from tool_safety import redact_secrets, check_command_policy, create_safe_env, DEFAULT_DENYLIST, DEFAULT_ALLOWLIST
from autonomy_daemon import AutonomyDaemon
from telegram_router import TelegramRouter
from scheduler import TaskScheduler
from task_queue import TaskQueue
from creative_exploration import CreativeExplorer

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ombra_db")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

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

# Daemons (initialized in lifespan)
autonomy_daemon = None
telegram_router = None
task_scheduler = None
task_queue = None
creative_explorer = None

# Create indexes
try:
    memories_col.create_index([("content", TEXT)])
    activity_col.create_index([("timestamp", DESCENDING)])
    activity_col.create_index([("type", 1)])
    conversations_col.create_index([("session_id", 1)])
    agents_col.create_index([("agent_id", 1)], unique=True)
    feedback_col.create_index([("timestamp", DESCENDING)])
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
                return {"available": True, "models": [m["name"] for m in models]}
    except Exception:
        pass
    return {"available": False, "models": []}


async def call_ollama(prompt: str, system_message: str = "", model: str = "tinyllama"):
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
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    provider_models = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-5-20250929",
        "gemini": "gemini-2.5-flash"
    }

    actual_model = model or provider_models.get(provider, "gpt-4o")
    actual_provider = provider or "openai"

    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"ombra-{uuid.uuid4().hex[:8]}",
        system_message=system_message or "You are Ombra, an intelligent autonomous AI assistant."
    ).with_model(actual_provider, actual_model)

    msg = UserMessage(text=prompt)
    response = await chat.send_message(msg)
    return str(response)


async def route_and_respond(message: str, system_message: str = "", conversation_context: str = "",
                            force_provider: str = None, agent_id: str = None):
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

    if conversation_context:
        sys_msg += f"\n\nRecent conversation context:\n{conversation_context}"

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
        "agent_id": agent_id
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


# ============================================================
# LEARNING SYSTEM (Enhanced)
# ============================================================
async def extract_and_learn(user_message: str, assistant_response: str, session_id: str):
    try:
        lower = user_message.lower()
        pref_patterns = [
            ("i prefer", "preference"), ("i like", "preference"),
            ("i don't like", "preference"), ("i always", "habit"),
            ("i usually", "habit"), ("my name is", "identity"),
            ("i work", "context"), ("i'm working on", "context"),
        ]

        for pattern, mem_type in pref_patterns:
            if pattern in lower:
                memories_col.insert_one({
                    "type": mem_type,
                    "content": user_message,
                    "source": "conversation",
                    "session_id": session_id,
                    "utility_score": 0.8,
                    "access_count": 0,
                    "pinned": False,
                    "decay_rate": 0.01,
                    "last_accessed_at": now_iso(),
                    "created_at": now_iso()
                })
                log_activity("memory_write", {
                    "memory_type": mem_type,
                    "content_preview": user_message[:80],
                    "source": "learning_extraction"
                })
                break

        conversation = conversations_col.find_one({"session_id": session_id})
        if conversation and len(conversation.get("turns", [])) % 10 == 0:
            summary = f"Conversation topic: {user_message[:100]}"
            memories_col.insert_one({
                "type": "conversation_summary",
                "content": summary,
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
        return {"terminal": False, "filesystem": False, "telegram": False}
    return profile.get("permissions", {"terminal": False, "filesystem": False, "telegram": False})


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

    # Start Telegram router if token configured
    if TELEGRAM_TOKEN:
        telegram_router = TelegramRouter(db, route_and_respond, dashboard_summary)
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
# CHAT (Enhanced with Agent + K1)
# ============================================================
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:12]}"

    conversation = conversations_col.find_one({"session_id": session_id})
    context = ""
    if conversation:
        recent_turns = conversation.get("turns", [])[-6:]
        context = "\n".join([f"{t['role']}: {t['content'][:200]}" for t in recent_turns])

    system_addition = ""
    if req.white_card_mode:
        system_addition = "\n\nYou are in 'White Card' mode. Be proactive: suggest ideas, improvements, next steps. Explore creative solutions. Think ahead for the user."

    # Auto-classify agent if not specified
    agent_id = req.agent_id
    if not agent_id or agent_id == "auto":
        agent_id = classify_task_for_agent(req.message)

    result = await route_and_respond(
        message=req.message,
        system_message=system_addition,
        conversation_context=context,
        force_provider=req.force_provider,
        agent_id=agent_id if agent_id != "auto" else None
    )

    user_turn = {"role": "user", "content": req.message, "timestamp": now_iso()}
    assistant_turn = {
        "role": "assistant",
        "content": result["response"],
        "timestamp": now_iso(),
        "provider": result["provider_used"],
        "model": result["model_used"],
        "routing": result["routing"],
        "agent_id": agent_id,
        "k1_prompt": result.get("k1_prompt_used")
    }

    if conversation:
        conversations_col.update_one(
            {"session_id": session_id},
            {"$push": {"turns": {"$each": [user_turn, assistant_turn]}},
             "$set": {"updated_at": now_iso()}}
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
        "category": result.get("category")
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
                "telegram_enabled": False, "hardware_ram": "16gb"}
    return serialize_doc(settings)


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    update = {"updated_at": now_iso()}
    for field in ["ollama_url", "ollama_model", "preferred_provider", "preferred_model",
                  "learning_enabled", "white_card_enabled", "quiet_hours_start", "quiet_hours_end",
                  "telegram_chat_id", "telegram_enabled", "hardware_ram"]:
        val = getattr(req, field, None)
        if val is not None:
            update[field] = val
    settings_col.update_one({"user_id": "default"}, {"$set": update})
    log_activity("system", {"event": "settings_updated", "changes": update})
    return await get_settings()


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
