# plan.md

## 1. Objectives
- Prove the **core agent loop** works end-to-end: request → route model (Ollama vs API) → use memory → optionally run tool (terminal) → log actions → respond.
- Implement **model routing + fallback** across **Ollama + Anthropic/OpenAI/Gemini** (via Emergent Universal Key).
- Implement **MongoDB memory** (short-term, long-term, user profile/permissions) with retrieval + decay.
- Deliver a **V1 web app** (dashboard + chat + permissions + activity timeline) that is transparent, proactive (white-card mode), and safe-by-default.

## 2. Implementation Steps

### Phase 1 — Core Flow POC (isolation; do not proceed until stable)
**Goal:** validate LLM connectivity/routing, Mongo memory I/O, and terminal tool execution + permissions.

**User stories (POC)**
1. As a user, I can send a message and get a response even if Ollama is down (automatic API fallback).
2. As a user, I can see which model/provider was used and why (routing explanation).
3. As a user, I can grant terminal permission once and then let Ombra run a command safely.
4. As a user, I can ask something that requires recalling prior context and Ombra retrieves it from MongoDB.
5. As a user, I can view an audit log entry for every tool/model call.

**Steps**
1. Web search quick-playbook (best practices):
   - Ollama install/run + health check; OpenAI/Anthropic/Gemini request patterns; Mongo vector search options.
2. Create minimal Python scripts (no web app yet):
   - `poc_ollama.py`: start/check local Ollama, list models, run a short prompt.
   - `poc_llm_providers.py`: call Anthropic + OpenAI + Gemini via Emergent key (one prompt each), normalize outputs.
   - `poc_router.py`: implement complexity scoring (length/task keywords/required tools) + choose model; fallback chain (Ollama→Anthropic→OpenAI→Gemini).
   - `poc_memory.py`: Mongo collections + insert convo turns + retrieve top-k relevant memories (embedding-backed if available; else lexical baseline).
   - `poc_terminal_tool.py`: permission gate + run a safe command + capture stdout/stderr + log.
3. Define a **single normalized message schema** used across scripts:
   - request, route_decision, tool_calls, memory_reads/writes, final_answer.
4. Fix until stable:
   - Ensure timeouts/retries, provider error handling, deterministic logging, and fallback actually triggers.
5. Output: a short POC transcript + sample Mongo docs proving memory/logging.

**Exit criteria (POC)**
- 20 consecutive runs: router returns a valid answer with correct metadata and no crashes.
- Ollama failure triggers API fallback within a bounded timeout.
- Mongo memory read/write + retrieval works and is reflected in responses.
- Terminal tool runs only when permission granted and is fully logged.

---

### Phase 2 — V1 App Development (build around proven core)
**Goal:** working MVP UI + API with core agent loop, transparency, permissions, and activity timeline.

**User stories (V1)**
1. As a user, I can chat with Ombra and see status (thinking/executing/done) plus model used.
2. As a user, I can toggle “transparent reasoning” (show decision logs/tool traces without exposing secrets).
3. As a user, I can grant/revoke permissions (terminal/filesystem/telegram) and Ombra respects them.
4. As a user, I can open the dashboard to see today’s summary, active tasks, and recent actions.
5. As a user, I can enable “white card mode” where Ombra proposes proactive next steps and drafts plans.

**Backend (FastAPI)**
- Implement modules:
  - Orchestrator: single `/chat` endpoint driving: memory→route→tool(optional)→learn→log→respond.
  - Model Router: complexity score + task type classifier + fallback.
  - Providers:
    - Ollama client (local install/run helper + configurable endpoint).
    - Anthropic/OpenAI/Gemini clients via Emergent key.
  - Memory (Mongo):
    - short-term: conversation sessions
    - long-term: knowledge/memories (with embeddings when available)
    - profile: preferences + permissions
  - Learning: extract “facts/preferences/recurring intents” after each interaction; store as memories.
  - Autonomy (MVP): task queue + “propose task” + “run task” endpoints (no heavy scheduling yet).
  - Tools (MVP): terminal + file read/write (behind permissions); Telegram plugin stub interface.
  - Activity tracker: append-only action log; daily summarizer job invoked on demand.

**Frontend (React + Tailwind/shadcn)**
- Pages:
  - Chat: streaming-like UI (polling acceptable for MVP), status pills, model badge, tool call cards.
  - Dashboard: today summary, active tasks, recent decisions.
  - Permissions: toggles + rationale + last-used timestamp.
  - Activity timeline: filter by type (model/tool/memory/autonomy).
- UX requirements:
  - Always show: “what I’m doing now” and “what I did” (auditability).
  - Safe defaults: permissions off, confirm on first use.

**Integration**
- Shared types/schemas for: messages, tool calls, route decisions, activity events.
- Seed data: default user profile + no-permission state.

**End-of-phase testing**
- One full E2E run: chat → tool permission request → grant → command run → memory saved → dashboard shows logs.

---

### Phase 3 — Add More Features (expand autonomy + intuition + plugins)
**User stories (Phase 3)**
1. As a user, I can create multi-step goals and Ombra decomposes them into tasks with retries.
2. As a user, I can see why Ombra suggested something (memory links + pattern references).
3. As a user, I can set quiet hours and control when proactive actions occur.
4. As a user, I can enable Telegram later by adding a token and immediately receive summaries.
5. As a user, I can view and edit my learned profile (preferences, habits) and reset parts of memory.

**Work**
- Autonomy engine:
  - task planner (LLM-generated steps), execution loop, retry/backoff, stop conditions.
  - background runner (simple interval loop) + UI controls.
- “Intuition” MVP:
  - intent prediction using recent + profile + top memories.
  - prefetch relevant memories on chat open.
  - proactive suggestion generator (white-card).
- Memory improvements:
  - memory scoring (recency/utility), decay/forgetting, pin/lock important memories.
  - embeddings + vector search if available; otherwise hybrid lexical+metadata.
- Plugin framework:
  - tool registry + permission scopes; Telegram module fully wired but disabled until token.

**End-of-phase testing**
- E2E: create goal → tasks generated → one task runs terminal tool → logs + daily summary sent to UI.

---

### Phase 4 — Hardening, Security, and Optional Auth
**User stories (Phase 4)**
1. As a user, I can run terminal commands safely with guardrails and see redaction of secrets.
2. As a user, I can export my data (memories/logs) and delete it.
3. As a user, I can add login/auth once the app is stable.
4. As a user, I can configure allowed command patterns and working directory.
5. As a user, I can run Ombra reliably across restarts (state recovery).

**Work**
- Terminal hardening: allowlist/denylist, sandbox directory, resource limits, secrets redaction.
- Observability: structured logs, trace IDs per request, failure dashboards.
- Data tools: export/delete, memory compaction.
- Optional auth (only after user approval): simple JWT.
- Regression testing + performance checks.

## 3. Next Actions (immediate)
1. Run web search for: Ollama install in Linux containers + health checks; Emergent key usage per provider; Mongo vector search setup.
2. Implement Phase 1 POC scripts (router/providers/memory/terminal) and validate fallback.
3. Freeze normalized schemas and collection names in Mongo.
4. Start Phase 2 only after POC exit criteria passes.

## 4. Success Criteria
- Core loop reliability: chat works with correct routing metadata and fallback.
- Permissions enforced: no tool runs without explicit grant; all actions logged.
- Memory works: relevant recall improves responses; user can see what was stored.
- UI transparency: dashboard + timeline accurately reflect model/tool/memory events.
- Autonomy MVP: white-card suggestions + basic task execution without breaking safety rules.
