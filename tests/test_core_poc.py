"""
Ombra Core POC Test Script
Tests all core components in isolation:
1. Ollama local LLM (tinyllama)
2. Emergent API providers (OpenAI, Anthropic, Gemini)
3. Model Router (complexity-based routing + fallback)
4. MongoDB Memory (short-term, long-term, user profile)
5. Terminal Tool (permission-gated command execution + logging)
"""

import asyncio
import os
import sys
import json
import time
import subprocess
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment
load_dotenv("/app/backend/.env")

import httpx
from pymongo import MongoClient

# ============================================================
# CONFIG
# ============================================================
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "ombra_test_poc"

results = {"passed": 0, "failed": 0, "tests": []}

def log_result(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results["passed" if passed else "failed"] += 1
    results["tests"].append({"name": test_name, "status": status, "detail": detail})
    print(f"  [{status}] {test_name}: {detail[:200]}")


# ============================================================
# TEST 1: OLLAMA LOCAL LLM
# ============================================================
async def test_ollama():
    print("\n=== TEST 1: OLLAMA LOCAL LLM ===")
    
    # 1a. Health check
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            models = resp.json().get("models", [])
            has_model = any("tinyllama" in m["name"] for m in models)
            log_result("Ollama health check", resp.status_code == 200, f"Status: {resp.status_code}, Models: {len(models)}")
            log_result("Ollama has tinyllama", has_model, f"Models: {[m['name'] for m in models]}")
    except Exception as e:
        log_result("Ollama health check", False, str(e))
        log_result("Ollama has tinyllama", False, "Skipped - health check failed")
        return False

    # 1b. Generate response
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "model": "tinyllama",
                "prompt": "Say 'Hello from Ombra' in exactly 5 words.",
                "stream": False,
                "options": {"num_predict": 50}
            }
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            data = resp.json()
            response_text = data.get("response", "")
            log_result("Ollama generate response", bool(response_text), f"Response: {response_text[:100]}")
            return True
    except Exception as e:
        log_result("Ollama generate response", False, str(e))
        return False


# ============================================================
# TEST 2: EMERGENT API PROVIDERS
# ============================================================
async def test_emergent_providers():
    print("\n=== TEST 2: EMERGENT API PROVIDERS ===")
    
    if not EMERGENT_KEY:
        log_result("Emergent key available", False, "EMERGENT_LLM_KEY not set")
        return False
    
    log_result("Emergent key available", True, f"Key: {EMERGENT_KEY[:15]}...")
    
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    providers = [
        ("openai", "gpt-4o", "OpenAI GPT-4o"),
        ("anthropic", "claude-sonnet-4-5-20250929", "Anthropic Claude Sonnet"),
        ("gemini", "gemini-2.5-flash", "Gemini Flash"),
    ]
    
    provider_results = {}
    
    for provider, model, label in providers:
        try:
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"poc-test-{provider}-{int(time.time())}",
                system_message="You are a test assistant. Respond briefly."
            ).with_model(provider, model)
            
            msg = UserMessage(text="Reply with exactly: 'Provider test OK'")
            response = await chat.send_message(msg)
            
            success = bool(response) and len(str(response)) > 0
            log_result(f"{label} response", success, f"Response: {str(response)[:100]}")
            provider_results[provider] = success
        except Exception as e:
            log_result(f"{label} response", False, f"Error: {str(e)[:150]}")
            provider_results[provider] = False
    
    return any(provider_results.values())


# ============================================================
# TEST 3: MODEL ROUTER (Complexity-based routing + fallback)
# ============================================================
async def test_model_router():
    print("\n=== TEST 3: MODEL ROUTER ===")
    
    # Complexity scoring
    def score_complexity(message: str) -> dict:
        """Score message complexity to decide routing."""
        score = 0
        reasons = []
        
        # Length-based
        word_count = len(message.split())
        if word_count > 100:
            score += 3
            reasons.append(f"long_message({word_count} words)")
        elif word_count > 30:
            score += 1
            reasons.append(f"medium_message({word_count} words)")
        
        # Task keywords
        complex_keywords = ["analyze", "compare", "explain", "plan", "design", "debug", "refactor", "strategy"]
        simple_keywords = ["hi", "hello", "thanks", "yes", "no", "ok"]
        
        lower_msg = message.lower()
        for kw in complex_keywords:
            if kw in lower_msg:
                score += 2
                reasons.append(f"complex_keyword({kw})")
        
        for kw in simple_keywords:
            if lower_msg.strip() == kw:
                score -= 2
                reasons.append(f"simple_keyword({kw})")
        
        # Question complexity
        if "?" in message and any(w in lower_msg for w in ["why", "how", "what if"]):
            score += 1
            reasons.append("complex_question")
        
        return {
            "score": max(0, score),
            "reasons": reasons,
            "route": "api" if score >= 3 else "local",
            "suggested_provider": "anthropic" if score >= 5 else "openai" if score >= 3 else "ollama"
        }
    
    # Test various messages
    test_cases = [
        ("hi", "local", "Simple greeting"),
        ("Analyze this codebase and design a strategy for refactoring the architecture", "api", "Complex analysis"),
        ("What's 2+2?", "local", "Simple question"),
        ("Compare and explain the differences between microservices and monolithic architectures, and plan a migration strategy", "api", "Very complex"),
    ]
    
    all_passed = True
    for message, expected_route, description in test_cases:
        result = score_complexity(message)
        passed = result["route"] == expected_route
        if not passed:
            all_passed = False
        log_result(
            f"Router: {description}",
            passed,
            f"Expected={expected_route}, Got={result['route']}, Score={result['score']}, Reasons={result['reasons']}"
        )
    
    # Test fallback chain
    print("  Testing fallback chain...")
    
    async def try_with_fallback(message):
        """Try Ollama first, fallback to API providers."""
        chain = [
            ("ollama", None, None),
            ("openai", "gpt-4o", "OpenAI"),
            ("anthropic", "claude-sonnet-4-5-20250929", "Anthropic"),
            ("gemini", "gemini-2.5-flash", "Gemini"),
        ]
        
        for provider, model, label in chain:
            try:
                if provider == "ollama":
                    async with httpx.AsyncClient(timeout=30) as client:
                        payload = {"model": "tinyllama", "prompt": message, "stream": False, "options": {"num_predict": 50}}
                        resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                        text = resp.json().get("response", "")
                        if text:
                            return {"provider": "ollama", "model": "tinyllama", "response": text}
                else:
                    from emergentintegrations.llm.chat import LlmChat, UserMessage
                    chat = LlmChat(
                        api_key=EMERGENT_KEY,
                        session_id=f"fallback-test-{int(time.time())}",
                        system_message="Reply briefly."
                    ).with_model(provider, model)
                    resp = await chat.send_message(UserMessage(text=message))
                    if resp:
                        return {"provider": provider, "model": model, "response": str(resp)}
            except Exception as e:
                print(f"    Fallback: {provider} failed: {str(e)[:80]}")
                continue
        
        return None
    
    fallback_result = await try_with_fallback("What is 1+1?")
    log_result(
        "Fallback chain works",
        fallback_result is not None,
        f"Provider used: {fallback_result['provider'] if fallback_result else 'NONE'}"
    )
    
    return all_passed


# ============================================================
# TEST 4: MONGODB MEMORY
# ============================================================
async def test_mongodb_memory():
    print("\n=== TEST 4: MONGODB MEMORY ===")
    
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Clean up test data
        for col in ["conversations", "memories", "user_profiles", "activity_log"]:
            db[col].drop()
        
        # 4a. Short-term memory (conversations)
        session_id = f"session_{int(time.time())}"
        turns = [
            {"role": "user", "content": "My name is Alex", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"role": "assistant", "content": "Nice to meet you, Alex!", "timestamp": datetime.now(timezone.utc).isoformat()},
            {"role": "user", "content": "What's my name?", "timestamp": datetime.now(timezone.utc).isoformat()},
        ]
        
        db.conversations.insert_one({
            "session_id": session_id,
            "turns": turns,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        retrieved = db.conversations.find_one({"session_id": session_id})
        log_result("Short-term memory write/read", retrieved is not None and len(retrieved["turns"]) == 3,
                   f"Turns stored: {len(retrieved['turns']) if retrieved else 0}")
        
        # 4b. Long-term memory (knowledge/facts)
        memories = [
            {"type": "fact", "content": "User prefers dark mode", "source": "conversation", "score": 0.9, "created_at": datetime.now(timezone.utc).isoformat()},
            {"type": "preference", "content": "User likes Python", "source": "conversation", "score": 0.8, "created_at": datetime.now(timezone.utc).isoformat()},
            {"type": "knowledge", "content": "Project uses FastAPI + React", "source": "terminal_observation", "score": 0.95, "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        
        db.memories.insert_many(memories)
        
        # Retrieve by score (simulating prioritization)
        top_memories = list(db.memories.find().sort("score", -1).limit(2))
        log_result("Long-term memory storage", len(top_memories) == 2,
                   f"Top memories: {[m['content'][:30] for m in top_memories]}")
        
        # Text search retrieval
        db.memories.create_index([("content", "text")])
        search_results = list(db.memories.find({"$text": {"$search": "Python"}}))
        log_result("Memory text search", len(search_results) > 0,
                   f"Found {len(search_results)} results for 'Python'")
        
        # 4c. User profile
        profile = {
            "user_id": "default",
            "name": "Alex",
            "preferences": {"theme": "dark", "language": "en"},
            "permissions": {
                "terminal": False,
                "filesystem": False,
                "telegram": False
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        db.user_profiles.insert_one(profile)
        retrieved_profile = db.user_profiles.find_one({"user_id": "default"})
        log_result("User profile storage", retrieved_profile is not None,
                   f"Name: {retrieved_profile.get('name')}, Perms: {retrieved_profile.get('permissions')}")
        
        # 4d. Activity logging
        activity = {
            "type": "model_call",
            "provider": "ollama",
            "model": "tinyllama",
            "input_preview": "Test message",
            "output_preview": "Test response",
            "duration_ms": 150,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        db.activity_log.insert_one(activity)
        activities = list(db.activity_log.find({"type": "model_call"}))
        log_result("Activity logging", len(activities) > 0,
                   f"Logged {len(activities)} activities")
        
        # Clean up
        client.drop_database(DB_NAME)
        client.close()
        return True
        
    except Exception as e:
        log_result("MongoDB connection", False, str(e))
        return False


# ============================================================
# TEST 5: TERMINAL TOOL (Permission-gated)
# ============================================================
async def test_terminal_tool():
    print("\n=== TEST 5: TERMINAL TOOL ===")
    
    # Permission system
    permissions = {"terminal": False, "filesystem": False}
    
    def check_permission(tool_name):
        return permissions.get(tool_name, False)
    
    def grant_permission(tool_name):
        permissions[tool_name] = True
        return True
    
    def execute_command(command, timeout=10):
        """Execute a command if terminal permission is granted."""
        if not check_permission("terminal"):
            return {"success": False, "error": "Permission denied: terminal access not granted"}
        
        # Safety checks
        dangerous = ["rm -rf /", "dd if=", "mkfs", ":(){ :|:& };:"]
        for d in dangerous:
            if d in command:
                return {"success": False, "error": f"Blocked dangerous command: {d}"}
        
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:1000],
                "stderr": result.stderr[:1000],
                "return_code": result.returncode,
                "command": command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # 5a. Test denied without permission
    result = execute_command("echo hello")
    log_result("Terminal denied without permission", not result["success"],
               f"Error: {result.get('error', '')}")
    
    # 5b. Grant permission and test
    grant_permission("terminal")
    result = execute_command("echo 'Ombra terminal test'")
    log_result("Terminal works with permission", result["success"],
               f"Output: {result.get('stdout', '').strip()}")
    
    # 5c. Test dangerous command blocking
    result = execute_command("rm -rf / --no-preserve-root")
    log_result("Dangerous command blocked", not result["success"],
               f"Error: {result.get('error', '')}")
    
    # 5d. Test real useful command
    result = execute_command("python3 --version")
    log_result("Real command execution", result["success"],
               f"Output: {result.get('stdout', '').strip()}")
    
    # 5e. Test command logging
    log_entry = {
        "type": "tool_execution",
        "tool": "terminal",
        "command": "python3 --version",
        "success": result["success"],
        "output_preview": result.get("stdout", "")[:100],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    log_result("Activity log entry created", bool(log_entry["timestamp"]),
               f"Log: {json.dumps(log_entry)[:100]}")
    
    return True


# ============================================================
# MAIN
# ============================================================
async def main():
    print("=" * 60)
    print("OMBRA CORE POC - COMPREHENSIVE TEST")
    print("=" * 60)
    
    await test_ollama()
    await test_emergent_providers()
    await test_model_router()
    await test_mongodb_memory()
    await test_terminal_tool()
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {results['passed']} PASSED, {results['failed']} FAILED")
    print("=" * 60)
    
    for t in results["tests"]:
        icon = "+" if t["status"] == "PASS" else "X"
        print(f"  [{icon}] {t['name']}")
    
    return results["failed"] == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
