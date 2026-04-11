"""
Ombra Self-Improving System
- Tracks metrics per provider/model/agent
- Adjusts routing thresholds automatically
- Manages prompt variants with bandit-style selection
- Records and applies learning changes
"""
from datetime import datetime, timezone


def calculate_provider_performance(metrics: list) -> dict:
    """Calculate performance scores per provider."""
    provider_stats = {}
    for m in metrics:
        provider = m.get("provider", "unknown")
        if provider not in provider_stats:
            provider_stats[provider] = {"total": 0, "success": 0, "total_ms": 0, "positive_feedback": 0, "negative_feedback": 0}
        
        stats = provider_stats[provider]
        stats["total"] += 1
        if m.get("success", True):
            stats["success"] += 1
        stats["total_ms"] += m.get("duration_ms", 0)
        if m.get("feedback") == "positive":
            stats["positive_feedback"] += 1
        elif m.get("feedback") == "negative":
            stats["negative_feedback"] += 1
    
    results = {}
    for provider, stats in provider_stats.items():
        total = stats["total"]
        results[provider] = {
            "total_calls": total,
            "success_rate": stats["success"] / max(total, 1),
            "avg_response_ms": stats["total_ms"] / max(total, 1),
            "positive_rate": stats["positive_feedback"] / max(total, 1),
            "negative_rate": stats["negative_feedback"] / max(total, 1),
            "overall_score": (
                (stats["success"] / max(total, 1)) * 0.4 +
                (stats["positive_feedback"] / max(total, 1)) * 0.4 +
                (1 - min(stats["total_ms"] / max(total, 1) / 10000, 1)) * 0.2
            )
        }
    
    return results


def suggest_routing_adjustments(performance: dict, current_thresholds: dict) -> list:
    """Suggest routing threshold adjustments based on performance."""
    changes = []
    
    for provider, stats in performance.items():
        if stats["total_calls"] < 5:
            continue  # Not enough data
        
        # If a provider has high success + positive feedback, increase its usage
        if stats["overall_score"] > 0.8 and provider != "ollama":
            changes.append({
                "type": "increase_usage",
                "provider": provider,
                "reason": f"High performance score ({stats['overall_score']:.2f})",
                "suggested_action": f"Route more complex tasks to {provider}"
            })
        
        # If a provider has high failure or negative feedback, reduce usage
        if stats["success_rate"] < 0.7 or stats["negative_rate"] > 0.3:
            changes.append({
                "type": "decrease_usage",
                "provider": provider,
                "reason": f"Low success ({stats['success_rate']:.2f}) or high negative feedback ({stats['negative_rate']:.2f})",
                "suggested_action": f"Reduce routing to {provider}, prefer alternatives"
            })
    
    return changes


def update_prompt_performance(prompt_id: str, feedback: str, prompts_col) -> dict:
    """Update a prompt's performance based on feedback."""
    prompt = prompts_col.find_one({"prompt_id": prompt_id})
    if not prompt:
        return None
    
    update = {"usage_count": prompt.get("usage_count", 0) + 1}
    if feedback == "positive":
        update["success_count"] = prompt.get("success_count", 0) + 1
    
    total = update["usage_count"]
    success = update.get("success_count", prompt.get("success_count", 0))
    update["performance_score"] = success / max(total, 1)
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    prompts_col.update_one({"prompt_id": prompt_id}, {"$set": update})
    return update
