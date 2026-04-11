"""
Ombra-K1: Local Learning Meta-Model Layer
- Adaptive system prompts that improve over time
- Hardware-aware model recommendations
- Teacher-student loop (learns from cloud model responses)
- Prompt library with performance tracking
"""
import os
from datetime import datetime, timezone

# Model recommendations by RAM tier
MODEL_RECOMMENDATIONS = {
    "4gb": [
        {"name": "tinyllama", "size": "637MB", "params": "1.1B", "description": "Ultra-light, good for simple tasks", "quantization": "Q4_0"},
        {"name": "phi", "size": "1.6GB", "params": "2.7B", "description": "Microsoft's small but capable model", "quantization": "Q4_0"},
    ],
    "8gb": [
        {"name": "tinyllama", "size": "637MB", "params": "1.1B", "description": "Ultra-light, good for simple tasks", "quantization": "Q4_0"},
        {"name": "phi3:mini", "size": "2.2GB", "params": "3.8B", "description": "Microsoft Phi-3 Mini - great balance", "quantization": "Q4_K_M"},
        {"name": "llama3.2:3b", "size": "2.0GB", "params": "3B", "description": "Meta's Llama 3.2 3B - fast and capable", "quantization": "Q4_K_M"},
        {"name": "gemma2:2b", "size": "1.6GB", "params": "2B", "description": "Google's compact model", "quantization": "Q4_K_M"},
    ],
    "16gb": [
        {"name": "llama3.2:3b", "size": "2.0GB", "params": "3B", "description": "Fast and efficient", "quantization": "Q4_K_M"},
        {"name": "mistral", "size": "4.1GB", "params": "7B", "description": "Excellent general-purpose model", "quantization": "Q4_K_M"},
        {"name": "llama3.1:8b", "size": "4.7GB", "params": "8B", "description": "Meta's latest 8B - strong reasoning", "quantization": "Q4_K_M"},
        {"name": "codellama:7b", "size": "3.8GB", "params": "7B", "description": "Specialized for code tasks", "quantization": "Q4_K_M"},
        {"name": "deepseek-coder-v2:lite", "size": "8.9GB", "params": "16B", "description": "DeepSeek's coding specialist", "quantization": "Q4_K_M"},
    ],
    "32gb": [
        {"name": "mistral", "size": "4.1GB", "params": "7B", "description": "Fast general-purpose", "quantization": "Q4_K_M"},
        {"name": "llama3.1:8b", "size": "4.7GB", "params": "8B", "description": "Strong 8B model", "quantization": "Q4_K_M"},
        {"name": "mixtral:8x7b", "size": "26GB", "params": "46.7B MoE", "description": "Powerful mixture-of-experts model", "quantization": "Q4_K_M"},
        {"name": "llama3.1:70b", "size": "40GB", "params": "70B", "description": "Meta's powerful 70B (requires swap)", "quantization": "Q4_K_M"},
        {"name": "qwen2.5:14b", "size": "8.9GB", "params": "14B", "description": "Alibaba's 14B - strong multilingual", "quantization": "Q4_K_M"},
    ],
}

# Default prompt library entries
DEFAULT_PROMPTS = [
    {
        "prompt_id": "general_v1",
        "name": "General Assistant",
        "category": "general",
        "system_prompt": "You are Ombra, an intelligent autonomous AI assistant. Be helpful, concise, and proactive. Suggest improvements and next steps when relevant.",
        "performance_score": 0.7,
        "usage_count": 0,
        "success_count": 0,
        "active": True
    },
    {
        "prompt_id": "coding_v1",
        "name": "Code Expert",
        "category": "coding",
        "system_prompt": "You are Ombra, an expert programmer. Write clean, efficient code with clear explanations. Use modern best practices. Always include error handling.",
        "performance_score": 0.7,
        "usage_count": 0,
        "success_count": 0,
        "active": True
    },
    {
        "prompt_id": "analysis_v1",
        "name": "Deep Analyst",
        "category": "analysis",
        "system_prompt": "You are Ombra, an analytical thinker. Break down complex problems systematically. Consider multiple angles. Provide data-driven conclusions when possible.",
        "performance_score": 0.7,
        "usage_count": 0,
        "success_count": 0,
        "active": True
    },
    {
        "prompt_id": "creative_v1",
        "name": "Creative Thinker",
        "category": "creative",
        "system_prompt": "You are Ombra in creative mode. Think outside the box. Propose novel solutions. Connect ideas across domains. Be bold in your suggestions.",
        "performance_score": 0.7,
        "usage_count": 0,
        "success_count": 0,
        "active": True
    }
]

def select_best_prompt(category: str, prompts: list) -> dict:
    """Select the best prompt for a category based on performance."""
    matching = [p for p in prompts if p.get("category") == category and p.get("active", True)]
    if not matching:
        matching = [p for p in prompts if p.get("category") == "general" and p.get("active", True)]
    if not matching:
        return DEFAULT_PROMPTS[0]
    
    # Weighted selection: 70% performance score, 30% exploration
    import random
    if random.random() < 0.3 and len(matching) > 1:
        return random.choice(matching)
    
    return max(matching, key=lambda p: p.get("performance_score", 0.5))


def categorize_message(message: str) -> str:
    """Categorize a message for prompt selection."""
    lower = message.lower()
    if any(k in lower for k in ["code", "function", "class", "bug", "debug", "implement", "script", "program"]):
        return "coding"
    if any(k in lower for k in ["analyze", "compare", "explain", "study", "research", "evaluate"]):
        return "analysis"
    if any(k in lower for k in ["create", "design", "imagine", "idea", "brainstorm", "innovate"]):
        return "creative"
    return "general"


def generate_teacher_distillation(cloud_response: str, task_signature: str) -> dict:
    """Extract reusable patterns from a cloud model response for local learning."""
    # Extract key patterns from the cloud response
    patterns = {
        "task_signature": task_signature,
        "response_length": len(cloud_response),
        "has_code": "```" in cloud_response,
        "has_list": any(cloud_response.count(f"{i}.") > 0 for i in range(1, 10)),
        "has_explanation": len(cloud_response) > 200,
        "response_summary": cloud_response[:300] + "..." if len(cloud_response) > 300 else cloud_response,
        "extracted_rules": [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Extract structural rules
    if patterns["has_code"]:
        patterns["extracted_rules"].append("Include code blocks when coding tasks are present")
    if patterns["has_list"]:
        patterns["extracted_rules"].append("Use numbered lists for structured content")
    if patterns["has_explanation"]:
        patterns["extracted_rules"].append("Provide detailed explanations for complex topics")
    
    return patterns
