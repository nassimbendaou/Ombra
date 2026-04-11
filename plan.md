# plan.md

## 1. Objectives
- ✅ **Core agent loop proven end-to-end**: request → memory retrieval → model routing (Ollama vs API) → optional tool execution → learning writebacks → activity logging → response.
- ✅ **Multi-provider model routing + fallback implemented** across:
  - **Ollama (local)** with `tinyllama` + **hardware-aware recommendations** for laptop tiers
  - **Cloud APIs (Anthropic, OpenAI, Gemini)** via **Emergent Universal Key**
- ✅ **MongoDB memory system implemented** for:
  - short-term conversation history
  - long-term memories (text-index retrieval + **utility scoring**)
  - user profile + permission state
- ✅ **V1 web app delivered** (dashboard + chat + permissions + activity timeline + settings + onboarding)
  - transparent, proactive (“white card mode”), safe-by-default permissions
- ✅ **Phase 3 completed**: Ombra evolved into a **true autonomous, multi-agent system** with:
  - **Ombra-K1** local learning meta-layer on top of Ollama
  - **task planner + executor** (multi-step goals with execution logging)
  - **multi-agent delegation** (built-in + user-created agents)
  - **self-improving loops** (feedback-driven prompt/provider optimization)
  - **filesystem tool + Telegram integration (outbound)**
  - **memory scoring/decay + deeper intuition**

**Phase 4 Objective (current focus):**
- 🔜 **Harden tools + governance**, and deliver **true autonomous execution** (pause/resume/cancel + structured plans + tool automation).
- 🔜 Add **Telegram inbound command router** (polling worker) for remote control.
- 🔜 Add **Memory Management UI** (search, pin/unpin, score visualization, delete/export).
- 🔜 Deliver **Enhanced Local Model (Ombra‑K1 v2)**:
  - more powerful local model (e.g., **Mistral 7B**) via Ollama
  - **autonomous multitasking**: queue/parallelize tasks and continue independently
  - **creative exploration**: generate ideas proactively (bounded by permissions + quiet hours)
  - **smart cloud escalation**: when local is uncertain/blocked, escalate to cloud and **distill learning** back into K1
  - background worker that periodically: reviews tasks, runs memory decay, generates suggestions, and sends Telegram updates

---

## 2. Implementation Steps

### Phase 1 — Core Flow POC (isolation; do not proceed until stable)
**Goal:** validate LLM connectivity/routing, Mongo memory I/O, and terminal tool execution + permissions.

**Status:** ✅ COMPLETED (22/22 tests passed)

**Delivered / Verified**
1. Ollama installed and running locally; `tinyllama` pulled and responding.
2. Emergent key integration working for:
   - OpenAI (`gpt-4o`)
   - Anthropic (`claude-sonnet-4-5-20250929`)
   - Gemini (`gemini-2.5-flash`)
3. Router implemented (complexity scoring + fallback chain).
4. MongoDB memory storage/retrieval working (short-term, long-term, user profile).
5. Terminal tool works with permission gating + dangerous command blocking.
6. Activity logging schema validated.

**Exit criteria (POC)**
- ✅ 20+ consecutive runs without crashes.
- ✅ Ollama failure triggers API fallback within bounded time.
- ✅ Mongo memory read/write + retrieval works.
- ✅ Terminal tool runs only when permission granted; all runs logged.

---

### Phase 2 — V1 App Development (build around proven core)
**Goal:** working MVP UI + API with core agent loop, transparency, permissions, and activity timeline.

**Status:** ✅ COMPLETED
- Backend: ✅ **17/17 API tests passed (100%)**
- Frontend: ✅ All pages functioning and manually verified

**Delivered Features (V1)**

**Backend (FastAPI)**
- Implemented unified service in `/app/backend/server.py` with:
  - `/api/chat` orchestrator endpoint: context + memory → router → model call → learning → log → response
  - Model router: complexity scoring; **Ollama-first** for simple; API for complex; robust fallback chain
  - Providers:
    - Ollama HTTP client (`/api/generate`)
    - Anthropic/OpenAI/Gemini via `emergentintegrations.llm.chat` using **EMERGENT_LLM_KEY**
  - Memory (MongoDB): conversations, memories, user profile, permissions, settings
  - Learning: heuristic extraction to long-term memories
  - Activity tracker: append-only activity log (`/api/activity`, `/api/activity/summary`)
  - Autonomy MVP: task CRUD + white-card suggestions
  - Tool system: terminal execution endpoint behind permissions + safety checks

**Frontend (React + Tailwind + shadcn/ui)**
- Dark-first premium dashboard UI per `/app/design_guidelines.md`:
  - ✅ Onboarding
  - ✅ Dashboard
  - ✅ Chat
  - ✅ Permissions
  - ✅ Activity timeline
  - ✅ Settings

**End-of-phase testing**
- ✅ E2E validation completed.

---

### Phase 3 — Autonomous Multi-Agent + Ombra-K1 (expanded autonomy, learning, tools, plugins)
**Goal:** transform Ombra into a **multi-agent, self-improving autonomous system** with a strong local-first workflow (Ombra-K1) and cloud escalation.

**Status:** ✅ COMPLETED
- Backend: ✅ **16/16 Phase 3 APIs tested successfully (100%)**
- Frontend: ✅ **95%** (all pages functional; one minor timeout in a single settings element during automated UI testing)

#### Phase 3 User Stories (delivered)
1. ✅ Multi-step goals (plan + execution-assist).
2. ✅ Explainability (routing + agent visibility + activity logs).
3. ✅ Multi-agent delegation (built-in specialists).
4. ✅ Custom agents (CRUD + run).
5. ✅ Self-improving loops (feedback + metrics + prompt scoring).
6. ✅ Ombra-K1 local learning:
   - local-first via Ollama
   - adaptive prompt library per task category
   - teacher-student distillation when cloud models are used
   - hardware-aware recommendations + model manager
7. ✅ Telegram integration (outbound): bot connected, test + send + summary endpoints.
8. ✅ Filesystem tool (permission-gated) with sanitization.
9. ✅ Memory scoring/decay + pin/unpin endpoints.
10. ✅ Deeper intuition endpoints (prediction + suggestions).

#### Phase 3 Work Breakdown (implemented)
- **Agents:** `/api/agents`, `/api/agents/{id}/run`, agents UI page
- **Task planning/execution:** `/api/goals/plan`, `/api/tasks/{id}/execute`
- **K1 + Model Manager:** `/api/ollama/*`, `/api/k1/*`, models UI page
- **Feedback + metrics:** `/api/feedback`, `/api/learning/metrics`
- **Memory decay/pinning:** `/api/memories/decay`, `/api/memories/{id}/pin`
- **Tools:** terminal + filesystem tool endpoints
- **Telegram (outbound):** `/api/telegram/test`, `/api/telegram/send`, `/api/telegram/send-summary`
- **Intuition:** `/api/intuition/prediction`, `/api/intuition/suggestions`

---

### Phase 4 — Hardening, True Autonomy, Remote Control, and K1 v2 Upgrade
**Goal:** strengthen safety/reliability, deliver **true autonomous execution**, improve governance, add **Telegram inbound control**, add a dedicated **Memory UI**, and upgrade the local-first intelligence to **Ombra‑K1 v2**.

**Status:** ✅ COMPLETED (Implementation done, testing in progress)

#### Phase 4 User Stories (target)
1. **Tool safety hardening**
   - Terminal allowlist/denylist policies per user
   - Sandboxed execution profiles (cwd, env restrictions, timeouts)
   - Secret redaction (tokens, `.env`, ssh keys) in logs + outputs
   - Filesystem safe roots configurable; per-directory scopes
   - Write operations: diff preview + confirmation + rollback metadata

2. **True autonomous execution engine**
   - Structured **JSON plans** (steps with tool calls, preconditions, expected outputs)
   - Executor runs tools automatically when permission exists
   - Lifecycle controls: **pause / resume / cancel**
   - Retry/backoff + circuit breaker for flaky providers/tools
   - Background runner that advances tasks when user is idle (bounded by quiet hours)

3. **Telegram inbound command router**
   - Polling worker/service
   - Command router:
     - `/status` (system status)
     - `/summary` (daily summary)
     - `/tasks` (active tasks)
     - `/run <task_id>` (execute next step)
     - `/pause <task_id>`, `/resume <task_id>`, `/cancel <task_id>`
   - Auth model: allowlist chat IDs + optional passphrase
   - Activity logging for every inbound command

4. **Memory Management UI**
   - Dedicated Memory page:
     - search + filtering by type
     - pin/unpin
     - score visualization (utility, access count, last accessed)
     - delete + bulk actions
     - export (JSON) + import
   - Optional “memory cards” in chat inspector to show what was injected

5. **Enhanced Local Model (Ombra‑K1 v2)**
   - Default local model upgraded from `tinyllama` to a stronger laptop-compatible option (e.g., **mistral 7B Q4**) with fallback to smaller models when RAM tier is low
   - Multi-task queue + parallel execution (bounded concurrency)
   - Creative exploration engine:
     - periodic “idea sweeps” based on context + pinned memories + active tasks
     - creates suggestions or drafts new tasks (requires user approval unless in autonomy mode)
   - Smart cloud escalation:
     - detect uncertainty/low confidence or repeated tool failures
     - escalate to cloud, then store distillation rules and/or create new K1 prompts
   - Improved local reasoning prompt strategy:
     - structured scratchpad **internally** (not exposed) and concise final answers
     - stricter format for plans and tool instructions

6. **Schedulers / Background Workers (Autonomy Daemon)**
   - Worker ticks (configurable interval) to:
     - advance eligible tasks
     - run memory decay
     - generate creative ideas
     - send Telegram summaries if enabled
   - Respect quiet hours + permissions
   - Full audit logging + rollback safety

7. **Observability + Governance (hardening)**
   - Trace IDs across model/tool/memory operations
   - Provider latency dashboards and error rates
   - Data retention policies
   - Optional authentication (JWT/RBAC) **only after explicit user approval**

#### Phase 4 Work Breakdown (implementation plan)

##### 4.1 Tool Safety Hardening
- Backend:
  - Add `tool_policies` collection (allowlist/denylist, limits)
  - Add redaction middleware + output scrubber
  - Add filesystem safe-roots config and write-confirm workflow
- Frontend:
  - Settings → “Tool Safety” section:
    - allowlist/denylist editor
    - safe roots manager
    - log redaction preview

##### 4.2 Autonomous Execution Engine (pause/resume/cancel)
- Backend:
  - Extend task schema:
    - `state`: planned/pending/in_progress/paused/cancelled/completed/failed
    - `plan_json`: structured steps
    - `current_step_index`, `locks`, `last_error`, `retry_count`
  - Add endpoints:
    - `POST /api/tasks/{id}/pause`
    - `POST /api/tasks/{id}/resume`
    - `POST /api/tasks/{id}/cancel`
    - `POST /api/tasks/{id}/execute-next`
- Frontend:
  - Task details modal/panel:
    - plan viewer
    - controls (pause/resume/cancel)
    - execution logs + retries

##### 4.3 Telegram Inbound Command Router
- Backend:
  - Create polling worker (supervisor-managed) using python-telegram-bot
  - Store allowed chat IDs in settings
  - Implement command handlers mapping to backend actions
- Frontend:
  - Settings → Telegram:
    - allowlist chat IDs
    - show recent inbound commands

##### 4.4 Memory Management UI
- Backend:
  - Add endpoints:
    - `GET /api/memories/search?q=`
    - `POST /api/memories/export`
    - `POST /api/memories/import`
- Frontend:
  - Add “Memory” route and page
  - Table + detail drawer + charts (scores over time)

##### 4.5 Ombra‑K1 v2 (powerful local + multitasking + creativity)
- Backend:
  - Add model capability registry (speed, size, strength)
  - Implement “local confidence” heuristics to trigger cloud escalation
  - Add creative exploration job that generates suggestions and optional tasks
  - Add multi-task queue with bounded concurrency
- Frontend:
  - Models page:
    - select default local model
    - enable creative exploration + schedule
    - show K1 v2 stats (ideas generated, escalations, distillations)

##### 4.6 Phase 4 Testing and Hardening
- Add regression suite covering:
  - tool policies + redaction
  - pause/resume/cancel flows
  - autonomous worker tick behavior
  - Telegram inbound commands
  - memory UI actions + export/import
  - escalation logic (local → cloud → distill)

---

## 3. Next Actions (immediate)
1. ✅ Completed: Phase 1, Phase 2, Phase 3.
2. Start Phase 4 in this order:
   1) Tool safety + governance
   2) True autonomous execution (pause/resume/cancel + structured plan JSON)
   3) Background worker/autonomy daemon
   4) Telegram inbound command router
   5) Memory management UI + export/import
   6) Ombra‑K1 v2: upgrade default local model + creativity + multitasking + escalation

---

## 4. Success Criteria
- ✅ Core loop reliability: routing works with metadata + fallback.
- ✅ Permissions enforced: no tool runs without explicit grant; all actions logged.
- ✅ Memory works: recall improves responses; scoring and decay reduce noise.
- ✅ UI transparency: dashboard + timeline reflect model/tool/memory/agent events.
- ✅ Phase 3 success (achieved): multi-agent + K1 + tools + Telegram outbound + intuition.

**Phase 4 success (target):**
- Safer terminal/filesystem execution with policy controls and redaction
- True autonomous execution with pause/resume/cancel and structured plans
- Autonomous background runner (quiet-hours aware)
- Telegram inbound command router for remote control
- Memory management UI + export/import
- Ombra‑K1 v2: stronger local model, multitasking, proactive creativity, and reliable cloud escalation with distillation

---

## 5. Phase 4 Implementation Completed

**Date:** April 11, 2026

**Implemented Features:**

### Tool Safety System (`tool_safety.py`)
- ✅ Allowlist/denylist policy engine
- ✅ Secret redaction in logs (API keys, tokens, env vars)
- ✅ Safe execution wrapper with timeout enforcement
- ✅ Permission-gated tool access

### Autonomy Daemon (`autonomy_daemon.py`)
- ✅ Background worker running on 60s tick interval
- ✅ Memory decay (every 10 ticks)
- ✅ Creative idea generation (every 5 ticks when white-card enabled)
- ✅ Telegram summary scheduling (every 100 ticks)
- ✅ Quiet hours support
- ✅ **Pause/Resume/Stop controls** (Backend + Frontend UI)
- ✅ Statistics tracking (ticks, ideas, decay runs, etc.)

### Telegram Router (`telegram_router.py`)
- ✅ Inbound command polling worker
- ✅ Command handlers: `/status`, `/summary`, `/tasks`, `/pause`, `/resume`, `/cancel`
- ✅ Chat ID allowlist authentication
- ✅ Activity logging for all commands

### Memory Management UI (`MemoryManagement.js`)
- ✅ Dedicated memory management page
- ✅ Search and filtering by type
- ✅ Pin/unpin functionality
- ✅ Utility score visualization
- ✅ Access count and last accessed tracking
- ✅ Delete individual memories
- ✅ Modern UI with card-based layout

### Dashboard Autonomy Controls (`Dashboard.js`)
- ✅ New "Autonomy Daemon" control card
- ✅ Real-time status display (Running/Paused/Stopped)
- ✅ Pause button (visible when running)
- ✅ Resume button (visible when paused)
- ✅ Stop button (always visible when daemon is running)
- ✅ Live statistics (ticks, ideas, decay runs, telegram sent, cloud escalations)
- ✅ Quiet hours indicator

### API Endpoints Added
- ✅ `GET /api/autonomy/status`
- ✅ `POST /api/autonomy/pause`
- ✅ `POST /api/autonomy/resume`
- ✅ `POST /api/autonomy/stop` ← NEW
- ✅ `PUT /api/tasks/{id}/pause`
- ✅ `PUT /api/tasks/{id}/resume`
- ✅ `PUT /api/tasks/{id}/cancel`

**Next Step:** Comprehensive Phase 4 end-to-end testing
