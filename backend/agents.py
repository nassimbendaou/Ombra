"""
Ombra Multi-Agent System
- Built-in agents: Coder, Researcher, Planner, Executor
- User-creatable custom agents
- Agent delegation + handoff tracking
"""
import uuid
from datetime import datetime, timezone

# Built-in agent templates
BUILTIN_AGENTS = [
    {
        "agent_id": "coder",
        "name": "Coder",
        "role": "specialist",
        "description": "Expert software engineer. Writes, reviews, and debugs code across multiple languages.",
        "system_prompt": "You are an expert software engineer named Ombra-Coder. You write clean, efficient, well-documented code. You debug issues methodically. When given a coding task, produce complete working code with clear explanations. Use best practices and modern patterns.",
        "tools_allowed": ["terminal", "filesystem"],
        "provider_preference": "anthropic",
        "temperature": 0.3,
        "builtin": True,
        "icon": "code",
        "color": "#38bdf8"
    },
    {
        "agent_id": "researcher",
        "name": "Researcher",
        "role": "specialist",
        "description": "Deep research analyst. Synthesizes information, compares options, and provides thorough analysis.",
        "system_prompt": "You are an expert research analyst named Ombra-Researcher. You conduct thorough analysis, compare alternatives, cite sources, and present findings clearly. Break complex topics into digestible insights. Always provide balanced perspectives.",
        "tools_allowed": ["filesystem"],
        "provider_preference": "anthropic",
        "temperature": 0.5,
        "builtin": True,
        "icon": "search",
        "color": "#a78bfa"
    },
    {
        "agent_id": "planner",
        "name": "Planner",
        "role": "specialist",
        "description": "Strategic planner. Decomposes goals into actionable steps with priorities and dependencies.",
        "system_prompt": "You are Ombra-Planner, a strategic planning expert. When given a goal, decompose it into clear, actionable steps. Identify dependencies, priorities, estimated effort, and potential risks. Output structured plans in a numbered format with clear checkpoints.",
        "tools_allowed": [],
        "provider_preference": "anthropic",
        "temperature": 0.4,
        "builtin": True,
        "icon": "map",
        "color": "#f59e0b"
    },
    {
        "agent_id": "executor",
        "name": "Executor",
        "role": "specialist",
        "description": "Task executor. Carries out planned steps using available tools, handles errors and retries.",
        "system_prompt": "You are Ombra-Executor, a reliable task executor. Given a specific step or command, carry it out precisely. Report results clearly. If an error occurs, analyze it and suggest a fix or retry strategy. Always report what you did and the outcome.",
        "tools_allowed": ["terminal", "filesystem"],
        "provider_preference": "openai",
        "temperature": 0.2,
        "builtin": True,
        "icon": "play",
        "color": "#22c55e"
    },
]

def classify_task_for_agent(message: str) -> str:
    """Classify which agent is best for a task."""
    lower = message.lower()
    
    code_keywords = ["code", "function", "class", "bug", "debug", "implement", "refactor", "api", "script", "program", "algorithm", "syntax"]
    research_keywords = ["research", "compare", "analyze", "study", "review", "evaluate", "investigate", "differences", "pros and cons"]
    plan_keywords = ["plan", "strategy", "roadmap", "steps", "goal", "project", "timeline", "milestone", "decompose", "break down"]
    exec_keywords = ["run", "execute", "install", "deploy", "build", "test", "command", "terminal"]
    
    scores = {
        "coder": sum(1 for k in code_keywords if k in lower),
        "researcher": sum(1 for k in research_keywords if k in lower),
        "planner": sum(1 for k in plan_keywords if k in lower),
        "executor": sum(1 for k in exec_keywords if k in lower),
    }
    
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "auto"  # No clear match, use general agent
    return best
