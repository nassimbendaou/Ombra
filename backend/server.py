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

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ombra_db")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

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

# Create indexes
try:
    memories_col.create_index([("content", TEXT)])
    activity_col.create_index([("timestamp", DESCENDING)])
    activity_col.create_index([("type", 1)])
    conversations_col.create_index([("session_id", 1)])
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
# MODEL ROUTER
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
    
    complex_keywords = ["analyze", "compare", "explain", "plan", "design", "debug", "refactor", "strategy", "architecture", "optimize", "implement", "evaluate", "research"]
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
        system_message=system_message or "You are Ombra, an intelligent autonomous AI assistant. Be helpful, concise, and proactive."
    ).with_model(actual_provider, actual_model)
    
    msg = UserMessage(text=prompt)
    response = await chat.send_message(msg)
    return str(response)


async def route_and_respond(message: str, system_message: str = "", conversation_context: str = "", force_provider: str = None):
    start_time = time.time()
    routing = score_complexity(message)
    
    sys_msg = system_message or "You are Ombra, an intelligent autonomous AI assistant. You help users with tasks, answer questions, and proactively suggest improvements. Be concise, helpful, and transparent about your reasoning."
    
    if conversation_context:
        sys_msg += f"\n\nRecent conversation context:\n{conversation_context}"
    
    # Retrieve relevant memories
    try:
        relevant_memories = list(memories_col.find({"$text": {"$search": message[:100]}}).limit(3))
        if relevant_memories:
            memory_context = "\n".join([m.get("content", "") for m in relevant_memories])
            sys_msg += f"\n\nRelevant memories:\n{memory_context}"
    except Exception:
        pass
    
    provider_used = force_provider or routing["suggested_provider"]
    model_used = ""
    response_text = ""
    fallback_chain = []
    
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
            # Fallback to API
            for fp in ["anthropic", "openai", "gemini"]:
                try:
                    response_text = await call_api_provider(message, sys_msg, fp, None)
                    provider_used = fp
                    model_used = {"anthropic": "claude-sonnet-4-5-20250929", "openai": "gpt-4o", "gemini": "gemini-2.5-flash"}.get(fp)
                    fallback_chain.append({"provider": fp, "success": True})
                    break
                except Exception as e2:
                    fallback_chain.append({"provider": fp, "success": False, "reason": str(e2)})
    else:
        # API route
        api_chain = [provider_used] + [p for p in ["anthropic", "openai", "gemini"] if p != provider_used]
        for fp in api_chain:
            try:
                response_text = await call_api_provider(message, sys_msg, fp, None)
                provider_used = fp
                model_used = {"anthropic": "claude-sonnet-4-5-20250929", "openai": "gpt-4o", "gemini": "gemini-2.5-flash"}.get(fp)
                fallback_chain.append({"provider": fp, "success": True})
                break
            except Exception as e:
                fallback_chain.append({"provider": fp, "success": False, "reason": str(e)})
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    result = {
        "response": response_text or "I apologize, but I couldn't generate a response. All providers failed.",
        "routing": routing,
        "provider_used": provider_used,
        "model_used": model_used,
        "fallback_chain": fallback_chain,
        "duration_ms": duration_ms
    }
    
    # Log activity
    log_activity("model_call", {
        "provider": provider_used,
        "model": model_used,
        "routing_score": routing["score"],
        "routing_reasons": routing["reasons"],
        "input_preview": message[:100],
        "output_preview": response_text[:200] if response_text else "",
        "fallback_chain": fallback_chain
    }, duration_ms)
    
    return result


# ============================================================
# LEARNING SYSTEM
# ============================================================
async def extract_and_learn(user_message: str, assistant_response: str, session_id: str):
    """Extract patterns and store as memories."""
    try:
        # Simple heuristic learning
        lower = user_message.lower()
        
        # Preference detection
        pref_patterns = [
            ("i prefer", "preference"),
            ("i like", "preference"),
            ("i don't like", "preference"),
            ("i always", "habit"),
            ("i usually", "habit"),
            ("my name is", "identity"),
            ("i work", "context"),
            ("i'm working on", "context"),
        ]
        
        for pattern, mem_type in pref_patterns:
            if pattern in lower:
                memories_col.insert_one({
                    "type": mem_type,
                    "content": user_message,
                    "source": "conversation",
                    "session_id": session_id,
                    "score": 0.8,
                    "access_count": 0,
                    "created_at": now_iso()
                })
                log_activity("memory_write", {
                    "memory_type": mem_type,
                    "content_preview": user_message[:80],
                    "source": "learning_extraction"
                })
                break
        
        # Store interaction summary periodically
        conversation = conversations_col.find_one({"session_id": session_id})
        if conversation and len(conversation.get("turns", [])) % 10 == 0:
            # Every 10 turns, create a summary memory
            summary = f"Conversation topic: {user_message[:100]}"
            memories_col.insert_one({
                "type": "conversation_summary",
                "content": summary,
                "source": "auto_summary",
                "session_id": session_id,
                "score": 0.6,
                "access_count": 0,
                "created_at": now_iso()
            })
    except Exception:
        pass


# ============================================================
# TOOL SYSTEM
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
    
    dangerous = ["rm -rf /", "dd if=", "mkfs", ":(){ :|:& };:", "chmod -R 777 /", "shutdown", "reboot", "format"]
    for d in dangerous:
        if d in command:
            return {"success": False, "error": f"Blocked dangerous command pattern: {d}"}
    
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            cwd="/tmp"
        )
        output = {
            "success": result.returncode == 0,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
            "return_code": result.returncode,
            "command": command
        }
        
        log_activity("tool_execution", {
            "tool": "terminal",
            "command": command,
            "success": output["success"],
            "output_preview": (result.stdout[:200] or result.stderr[:200])
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

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "medium"

class TerminalRequest(BaseModel):
    command: str
    timeout: Optional[int] = 30


# ============================================================
# LIFESPAN
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize default profile if not exists
    if not profiles_col.find_one({"user_id": "default"}):
        profiles_col.insert_one({
            "user_id": "default",
            "name": "User",
            "preferences": {"theme": "dark", "language": "en"},
            "permissions": {"terminal": False, "filesystem": False, "telegram": False},
            "onboarded": False,
            "created_at": now_iso(),
            "updated_at": now_iso()
        })
    
    if not settings_col.find_one({"user_id": "default"}):
        settings_col.insert_one({
            "user_id": "default",
            "ollama_url": OLLAMA_URL,
            "ollama_model": "tinyllama",
            "preferred_provider": "auto",
            "preferred_model": "",
            "learning_enabled": True,
            "white_card_enabled": False,
            "quiet_hours_start": "",
            "quiet_hours_end": "",
            "created_at": now_iso(),
            "updated_at": now_iso()
        })
    
    log_activity("system", {"event": "startup", "message": "Ombra system started"})
    yield
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
    return {
        "status": "healthy",
        "timestamp": now_iso(),
        "ollama": ollama,
        "mongodb": {"connected": True},
        "api_key_configured": bool(EMERGENT_KEY)
    }


# ============================================================
# CHAT
# ============================================================
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or f"session_{uuid.uuid4().hex[:12]}"
    
    # Get conversation context
    conversation = conversations_col.find_one({"session_id": session_id})
    context = ""
    if conversation:
        recent_turns = conversation.get("turns", [])[-6:]
        context = "\n".join([f"{t['role']}: {t['content'][:200]}" for t in recent_turns])
    
    # White card mode: add proactive suggestions
    system_addition = ""
    if req.white_card_mode:
        system_addition = "\n\nYou are in 'White Card' mode. Be proactive: suggest ideas, improvements, and next steps. Explore creative solutions. Think ahead for the user."
    
    # Route and respond
    result = await route_and_respond(
        message=req.message,
        system_message=system_addition,
        conversation_context=context,
        force_provider=req.force_provider
    )
    
    # Save to conversation
    user_turn = {"role": "user", "content": req.message, "timestamp": now_iso()}
    assistant_turn = {
        "role": "assistant",
        "content": result["response"],
        "timestamp": now_iso(),
        "provider": result["provider_used"],
        "model": result["model_used"],
        "routing": result["routing"]
    }
    
    if conversation:
        conversations_col.update_one(
            {"session_id": session_id},
            {
                "$push": {"turns": {"$each": [user_turn, assistant_turn]}},
                "$set": {"updated_at": now_iso()}
            }
        )
    else:
        conversations_col.insert_one({
            "session_id": session_id,
            "turns": [user_turn, assistant_turn],
            "created_at": now_iso(),
            "updated_at": now_iso()
        })
    
    # Learning
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
        "duration_ms": result["duration_ms"]
    }


@app.get("/api/chat/history")
async def get_chat_history(session_id: str = None):
    if session_id:
        conv = conversations_col.find_one({"session_id": session_id})
        if conv:
            return serialize_doc(conv)
        return {"session_id": session_id, "turns": []}
    
    # Return list of sessions
    sessions = list(conversations_col.find({}, {"session_id": 1, "created_at": 1, "updated_at": 1, "turns": {"$slice": 1}}).sort("updated_at", DESCENDING).limit(20))
    return [{"session_id": s["session_id"], "created_at": s.get("created_at", ""), "updated_at": s.get("updated_at", ""), "preview": s.get("turns", [{}])[0].get("content", "")[:80] if s.get("turns") else ""} for s in sessions]


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
    
    # Count today's activities
    today_activities = list(activity_col.find({"timestamp": {"$gte": today_start}}))
    
    model_calls = [a for a in today_activities if a.get("type") == "model_call"]
    tool_executions = [a for a in today_activities if a.get("type") == "tool_execution"]
    memory_ops = [a for a in today_activities if a.get("type") in ["memory_write", "memory_read"]]
    
    # Provider breakdown
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
        "total_activities": len(today_activities),
        "providers_used": providers_used,
        "total_duration_ms": total_duration,
        "avg_response_ms": int(total_duration / max(len(model_calls), 1)),
        "summary": f"Today: {len(model_calls)} chats, {len(tool_executions)} tool runs, {len(memory_ops)} memory ops."
    }


@app.get("/api/dashboard/status")
async def system_status():
    ollama = await check_ollama_health()
    
    # Check MongoDB
    try:
        client.admin.command('ping')
        mongo_ok = True
    except Exception:
        mongo_ok = False
    
    # Memory stats
    memory_count = memories_col.count_documents({})
    conversation_count = conversations_col.count_documents({})
    
    # Autonomy status
    active_tasks = tasks_col.count_documents({"status": {"$in": ["pending", "in_progress"]}})
    
    return {
        "ollama": {"status": "online" if ollama["available"] else "offline", "models": ollama["models"]},
        "cloud_api": {"status": "configured" if EMERGENT_KEY else "not_configured"},
        "memory": {"status": "online" if mongo_ok else "offline", "memories": memory_count, "conversations": conversation_count},
        "autonomy": {"status": "active" if active_tasks > 0 else "idle", "active_tasks": active_tasks},
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
    log_activity("system", {"event": "onboarding_complete", "permissions": {
        "terminal": req.terminal, "filesystem": req.filesystem, "telegram": req.telegram
    }})
    
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
    activities = list(
        activity_col.find(query)
        .sort("timestamp", DESCENDING)
        .skip(offset)
        .limit(limit)
    )
    
    return {
        "activities": [serialize_doc(a) for a in activities],
        "total": total,
        "offset": offset,
        "limit": limit
    }


@app.get("/api/activity/summary")
async def activity_daily_summary():
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    activities = list(activity_col.find({"timestamp": {"$gte": today_start}}))
    
    type_counts = {}
    for a in activities:
        t = a.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total": len(activities),
        "by_type": type_counts,
        "timeline_preview": [serialize_doc(a) for a in activities[:10]]
    }


# ============================================================
# TASKS
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
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "steps": [],
        "result": None
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


# ============================================================
# SETTINGS
# ============================================================
@app.get("/api/settings")
async def get_settings():
    settings = settings_col.find_one({"user_id": "default"})
    if not settings:
        return {
            "ollama_url": OLLAMA_URL,
            "ollama_model": "tinyllama",
            "preferred_provider": "auto",
            "preferred_model": "",
            "learning_enabled": True,
            "white_card_enabled": False,
            "quiet_hours_start": "",
            "quiet_hours_end": ""
        }
    return serialize_doc(settings)


@app.put("/api/settings")
async def update_settings(req: SettingsUpdate):
    update = {"updated_at": now_iso()}
    for field in ["ollama_url", "ollama_model", "preferred_provider", "preferred_model", "learning_enabled", "white_card_enabled", "quiet_hours_start", "quiet_hours_end"]:
        val = getattr(req, field, None)
        if val is not None:
            update[field] = val
    
    settings_col.update_one({"user_id": "default"}, {"$set": update})
    
    log_activity("system", {"event": "settings_updated", "changes": update})
    return await get_settings()


# ============================================================
# TERMINAL TOOL API
# ============================================================
@app.post("/api/tools/terminal")
async def terminal_endpoint(req: TerminalRequest):
    result = execute_terminal_command(req.command, req.timeout)
    return result


# ============================================================
# MEMORIES
# ============================================================
@app.get("/api/memories")
async def get_memories(mem_type: Optional[str] = None, limit: int = 50):
    query = {}
    if mem_type:
        query["type"] = mem_type
    
    mems = list(memories_col.find(query).sort("created_at", DESCENDING).limit(limit))
    return [serialize_doc(m) for m in mems]


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    memories_col.delete_one({"_id": ObjectId(memory_id)})
    return {"status": "deleted"}


@app.delete("/api/memories")
async def clear_memories():
    memories_col.delete_many({})
    return {"status": "cleared"}


# ============================================================
# WHITE CARD (PROACTIVE SUGGESTIONS)
# ============================================================
@app.get("/api/white-card/suggestions")
async def get_white_card_suggestions():
    """Generate proactive suggestions based on recent activity and memories."""
    # Get recent activities
    recent = list(activity_col.find().sort("timestamp", DESCENDING).limit(10))
    
    # Get memories
    top_memories = list(memories_col.find().sort("score", DESCENDING).limit(5))
    
    # Get active tasks
    active_tasks = list(tasks_col.find({"status": {"$in": ["pending", "in_progress"]}}))
    
    suggestions = []
    
    if not recent:
        suggestions.append({
            "type": "getting_started",
            "title": "Start a conversation",
            "description": "Chat with me to get started. I can help with coding, analysis, planning, and more.",
            "action": "chat"
        })
    
    if active_tasks:
        for task in active_tasks[:3]:
            suggestions.append({
                "type": "task_followup",
                "title": f"Continue: {task.get('title', 'Untitled')}",
                "description": f"You have a {task.get('priority', 'medium')} priority task that needs attention.",
                "action": "task",
                "task_id": str(task.get("_id", ""))
            })
    
    if top_memories:
        suggestions.append({
            "type": "memory_insight",
            "title": "Based on what I know about you",
            "description": f"I've learned {len(top_memories)} things about your preferences. Want to review them?",
            "action": "memories"
        })
    
    model_calls = [a for a in recent if a.get("type") == "model_call"]
    if model_calls:
        last_topic = model_calls[0].get("details", {}).get("input_preview", "")
        if last_topic:
            suggestions.append({
                "type": "continue_conversation",
                "title": "Continue where we left off",
                "description": f"We were discussing: {last_topic[:60]}...",
                "action": "chat"
            })
    
    return {"suggestions": suggestions}
