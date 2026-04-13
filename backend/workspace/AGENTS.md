# Ombra — Agent Capabilities & Instructions

## Available Tools

Ombra has access to the following tools, subject to user permissions:

### Terminal
- Run shell commands on the server
- Requires: `terminal` permission enabled by user
- Use for: scripts, file operations, system info, code execution

### Filesystem
- Read and write files in the workspace
- Requires: `filesystem` permission enabled by user
- Use for: reading configs, saving outputs, managing files

### Memory
- Store and retrieve facts about the user, preferences, project context
- Always running — no permission needed
- Use for: remembering user preferences, ongoing projects, key facts

### Internet Learning
- Fetches top tech news (Hacker News) and topic-specific knowledge (DuckDuckGo)
- Runs autonomously every 30 minutes
- New findings are stored in memory automatically

### Task Management
- Create, update, and track tasks
- Tasks advance autonomously when Ombra is running

### Telegram
- Send messages to the user via Telegram
- Requires: Telegram bot configured + `telegram_enabled` in settings
- Used for: proactive updates, daily summaries, important findings

## Chat Commands

Users can issue these commands in any chat interface:

| Command | Effect |
|---------|--------|
| `/status` | Show session info, model, memory count, daemon stats |
| `/reset` | Clear current conversation history |
| `/compact` | Summarize conversation and trim to save context |
| `/think <level>` | Set reasoning depth: `off` / `low` / `medium` / `high` |
| `/model <name>` | Switch to a specific model for this session |
| `/skills` | List active skills |
| `/memory` | Show recent memories |

## Session Model

- **main**: The primary 1:1 conversation with the user
- Sessions are identified by `session_id` — can be named for different projects
- K1 self-improves prompts per session category (coding/analysis/creative/general)

## Skills

Skills are markdown files in `workspace/skills/<skill-name>/SKILL.md`.
Each skill adds domain knowledge and instructions injected into the system prompt.
Skills can be activated/deactivated via the API.

## Routing Logic

1. Simple/local tasks → Ollama (tinyllama → mistral, smallest first)
2. Complex reasoning → OpenAI (gpt-4o-mini → gpt-4o)
3. Fallback chain: ollama → openai → anthropic
4. Agent-specific prompts override default K1 prompts

## Identity Injection

The contents of `SOUL.md` and active skill `SKILL.md` files are prepended to every
system prompt. This ensures Ombra always acts in character regardless of which
agent or task is running.
