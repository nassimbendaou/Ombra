# plan.md

## 1. Objectives
- ✅ **Core agent loop proven end-to-end**: request → memory retrieval → model routing (Ollama vs API) → optional tool execution → learning writebacks → activity logging → response.
- ✅ **Multi-provider model routing + fallback implemented** across:
  - **Ollama (local)** with `tinyllama` (and hardware-aware recommendations for more models)
  - **Cloud APIs (Anthropic, OpenAI, Gemini)** via **Emergent Universal Key**
- ✅ **MongoDB memory system implemented** for:
  - short-term conversation history
  - long-term memories (text-index retrieval + utility scoring)
  - user profile + permission state
- ✅ **V1 web app delivered** (dashboard + chat + permissions + activity timeline + settings + onboarding)
  - transparent, proactive (“white card mode”), safe-by-default permissions
- ✅ **Phase 3 completed**: Ombra evolved into a **true autonomous, multi-agent system** with:
  - **Ombra-K1** local learning meta-layer on top of Ollama
  - **task planner + executor** (multi-step goals with execution logging)
  - **multi-agent delegation** (built-in + user-created agents)
  - **self-improving loops** (feedback-driven prompt/provider optimization)
  - **filesystem tool + Telegram integration**
  - **memory scoring/decay + deeper intuition**

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
  - Memory (MongoDB):
    - conversations (`/api/chat/history`)
    - long-term memories with text index (`/api/memories`)
    - user profile + permissions (`/api/permissions`, `/api/onboarding`)
    - settings (`/api/settings`)
  - Learning: heuristic extraction to long-term memories
  - Activity tracker: append-only activity log (`/api/activity`, `/api/activity/summary`)
  - Autonomy MVP:
    - task CRUD (`/api/tasks`)
    - white-card suggestions endpoint (`/api/white-card/suggestions`)
  - Tool system:
    - terminal execution endpoint (`/api/tools/terminal`) behind permissions + safety checks

**Frontend (React + Tailwind + shadcn/ui)**
- Dark-first premium dashboard UI per `/app/design_guidelines.md`:
  - ✅ Onboarding (permissions setup)
  - ✅ Dashboard: daily summary, system status, tasks, suggestions, recent activity
  - ✅ Chat: status indicator, provider/model badge, routing transparency toggle, provider override dropdown, white-card toggle, session inspector
  - ✅ Permissions: toggles + rationale + confirmation dialog for elevated permissions
  - ✅ Activity Timeline: filterable events with expandable JSON details
  - ✅ Settings: runtime (Ollama), models (preference), learning controls
- Installed UX support libs:
  - `framer-motion` for micro-animations
  - `react-router-dom` for routing
  - `recharts` ready for sparklines (optional usage)

**End-of-phase testing**
- ✅ E2E validation completed:
  - onboarding → dashboard → chat → activity logs visible
  - model routing verified with real Ollama responses and API availability
  - permissions enforcement validated

---

### Phase 3 — Autonomous Multi-Agent + Ombra-K1 (expanded autonomy, learning, tools, plugins)
**Goal:** transform Ombra into a **multi-agent, self-improving autonomous system** with a strong local-first workflow (Ombra-K1) and cloud escalation.

**Status:** ✅ COMPLETED
- Backend: ✅ **16/16 Phase 3 APIs tested successfully (100%)**
- Frontend: ✅ **95%** (all pages functional; one minor timeout in a single settings element during automated UI testing)

#### Phase 3 User Stories (delivered)
1. ✅ **Multi-step goals**: create a goal, Ombra decomposes it into steps and executes/assists with execution.
2. ✅ **Explainability**: see routing rationale, agent used, model/provider used, and activity logs.
3. ✅ **Multi-agent delegation**: tasks auto-route to specialist agents (Coder/Researcher/Planner/Executor).
4. ✅ **Custom agents**: create custom agents with persona/system prompt, tools, provider preference, and UI management.
5. ✅ **Self-improving loops**: feedback-driven improvement of prompts and provider usage; metrics exposed.
6. ✅ **Ombra-K1 local learning system**:
   - local-first via Ollama
   - adaptive prompt library per task category
   - teacher-student distillation when cloud models are used
   - hardware-aware model recommendations and management
7. ✅ **Telegram integration**: bot connected, test endpoint working, send message + send daily summary supported.
8. ✅ **Filesystem tool**: permission-gated read/write/list with path sanitization and logging.
9. ✅ **Memory scoring/decay**: utility scoring, pin/unpin, decay + forgetting for low-score memories.
10. ✅ **Deeper intuition**: intent prediction + proactive suggestions endpoints.

#### Phase 3 Work Breakdown (implemented)

##### 3.1 Agent Framework + Multi-Agent Orchestrator
- **Backend**
  - Agent schema + registry (Mongo-backed): built-in + user-defined.
  - Auto-classifier routes tasks to agents.
  - Agent execution trace stored in activity timeline.
  - APIs:
    - `GET/POST/PUT/DELETE /api/agents`
    - `POST /api/agents/{agent_id}/run`
    - `/api/chat` supports `agent_id` and auto-agent selection.
- **Frontend**
  - ✅ **Agents page**:
    - list built-in + custom agents
    - create agent modal
    - run agent dialog
    - delete custom agents (built-ins protected)
  - ✅ **Chat enhancements**:
    - agent selector dropdown (Auto or specific agent)

##### 3.2 Task Planner + Executor Loop
- **Backend**
  - ✅ Goal planning endpoint:
    - `POST /api/goals/plan` (planner agent uses cloud model for decomposition)
  - ✅ Task execution endpoint:
    - `POST /api/tasks/{id}/execute` (executor agent suggests/advances next action and logs execution)
- **Frontend**
  - ✅ Integrated via dashboard/tasks visibility (execution logs visible via activity timeline).

##### 3.3 Ombra-K1 Local Model System (local-first, learns from cloud)
- **Backend**
  - ✅ Prompt library seeded with multiple categories and performance tracking (`k1_prompts`).
  - ✅ Teacher-student distillation: cloud calls create reusable “rules” (`k1_distillations`).
  - ✅ Hardware-aware model recommendations based on `hardware_ram` setting.
  - ✅ Ollama model management APIs:
    - `GET /api/ollama/models`
    - `GET /api/ollama/recommendations`
    - `POST /api/ollama/pull`
    - `DELETE /api/ollama/models/{model_name}`
  - ✅ K1 APIs:
    - `GET /api/k1/prompts`
    - `GET /api/k1/distillations`
- **Frontend**
  - ✅ **Model Manager** page:
    - installed models
    - recommendations (4GB/8GB/16GB/32GB+)
    - pull model actions
    - K1 prompt library stats and distillation insights

##### 3.4 Self-Improving Loops (automatic + transparent for major changes)
- **Backend**
  - ✅ Feedback capture:
    - `POST /api/feedback`
  - ✅ Learning metrics and suggested adjustments:
    - `GET /api/learning/metrics`
    - `GET /api/learning/changes` (ready for change-history persistence)
  - ✅ Prompt performance updates from user feedback.
- **Frontend**
  - ✅ Chat: thumbs up/down per assistant response.

##### 3.5 Memory Scoring / Decay + Pinning
- **Backend**
  - ✅ Memory schema includes: `utility_score`, `access_count`, `last_accessed_at`, `pinned`, `decay_rate`.
  - ✅ Pin/unpin:
    - `PUT /api/memories/{id}/pin`
  - ✅ Decay job:
    - `POST /api/memories/decay`
- **Frontend**
  - Currently exposed via APIs + activity timeline; dedicated memory management UI remains a Phase 4 candidate.

##### 3.6 Filesystem Tool (permission-gated)
- **Backend**
  - ✅ Safe read/write/list tools:
    - `POST /api/tools/fs/read`
    - `POST /api/tools/fs/write`
    - `POST /api/tools/fs/list`
  - ✅ Path sanitization + safe base directories (`/tmp`, `/app`) and blocked patterns.
- **Frontend**
  - Permission toggle exists; tool actions appear in activity logs.

##### 3.7 Telegram Integration (token provided)
- **Backend**
  - ✅ Token configured via `TELEGRAM_BOT_TOKEN`.
  - ✅ Bot connectivity:
    - `POST /api/telegram/test`
  - ✅ Send message:
    - `POST /api/telegram/send`
  - ✅ Send daily summary:
    - `POST /api/telegram/send-summary`
- **Frontend**
  - ✅ Settings: Telegram tab with enable + chat id input and bot connection status.

##### 3.8 Deeper Intuition System
- **Backend**
  - ✅ Intent prediction:
    - `GET /api/intuition/prediction`
  - ✅ Proactive suggestions:
    - `GET /api/intuition/suggestions`
- **Frontend**
  - Suggestions are visible on dashboard via white-card; further “Next best actions” UX can be expanded in Phase 4.

#### Phase 3 End-of-phase testing (executed)
- ✅ E2E scenario validated:
  - Agents: list/create/run/delete custom agent
  - Goal planning + task execution loop
  - Ollama models listed + recommendations displayed
  - K1 prompts + distillations present
  - Feedback captured and learning metrics updated
  - Memory decay + pinning endpoints functional
  - Filesystem tool gating works
  - Telegram bot connected and send endpoints functional
  - Intuition endpoints return predictions and suggestions

---

### Phase 4 — Hardening, Security, Observability, and “True Autonomy” Upgrades
**Goal:** strengthen safety/reliability, expand autonomous execution, and improve governance.

**Status:** 🔜 Planned (next)

**Planned user stories (Phase 4)**
1. Stronger terminal hardening:
   - allowlist/denylist rules per user
   - sandbox directories + resource/time limits
   - secret redaction (env vars, tokens)
2. Filesystem governance:
   - configurable safe roots per user
   - diff preview + confirmation for writes
3. Telegram worker:
   - optional polling worker mode for inbound messages
   - command router (`/summary`, `/tasks`, `/status`, `/run <task_id>`)
4. True multi-step autonomous execution:
   - task planner produces structured JSON steps
   - executor runs tools automatically when permissions exist
   - pause/resume/cancel states + retries/backoff
5. Memory UX:
   - dedicated “Memory” page: search, pinning, score visualization, delete/export
6. Observability:
   - structured logs + trace IDs
   - performance dashboards (provider/agent latency and success)
7. Data governance:
   - export/delete endpoints
   - retention policies
8. Optional authentication:
   - JWT + RBAC (after explicit user approval)

**Work**
- Terminal hardening:
  - allowlist/denylist rules
  - safe working directory config
  - redaction middleware
- Reliability:
  - background job scheduler for memory decay + daily summaries
  - retries with circuit-breakers for provider calls
- Security:
  - permission scope improvements (per tool, per directory)
  - audit log integrity

## 3. Next Actions (immediate)
1. ✅ Completed: Phase 1, Phase 2, Phase 3.
2. Begin Phase 4 hardening in the following order:
   1) Tool safety + governance (terminal + filesystem)
   2) Autonomous execution engine improvements (pause/resume/cancel + structured plans)
   3) Telegram inbound worker + command router
   4) Memory management UX
   5) Observability + data governance
3. Add/expand regression suite:
   - agents CRUD + run
   - goal planning + task step execution
   - K1 prompts/distillations retrieval
   - model manager endpoints
   - Telegram test + send summary
   - filesystem gated read/write/list

## 4. Success Criteria
- ✅ Core loop reliability: routing works with metadata + fallback.
- ✅ Permissions enforced: no tool runs without explicit grant; all actions logged.
- ✅ Memory works: recall improves responses; stored info visible via logs/timeline.
- ✅ UI transparency: dashboard + timeline reflect model/tool/memory/agent events.
- ✅ White-card mode: proactive suggestions available.
- ✅ Phase 3 success:
  - Multi-agent delegation works (built-in + custom agents)
  - Multi-step goals can be planned and execution-assisted with logging
  - Ombra-K1 prompt library adapts and tracks performance
  - Teacher-student distillation persists reusable “rules” from cloud calls
  - Hardware-aware local model recommendations + pulling works
  - Telegram connectivity and send/daily summary endpoints operational
  - Memory scoring/decay and intuition improve relevance and proactivity
- Phase 4 success (target):
  - safer tool execution + governance
  - true autonomous multi-step execution with pause/resume/cancel
  - inbound Telegram command router
  - memory management UI + export/delete
  - improved observability and reliability
