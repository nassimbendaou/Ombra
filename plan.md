# plan.md

## 1. Objectives
- ✅ **Core agent loop proven end-to-end**: request → memory retrieval → model routing (Ollama vs API) → optional tool execution → learning writebacks → activity logging → response.
- ✅ **Multi-provider model routing + fallback implemented** across:
  - **Ollama (local)** with `tinyllama` + `mistral` and **hardware-aware recommendations**
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
- ✅ **Phase 4 completed**: Tool safety hardening + autonomy daemon + Telegram inbound router + Memory Management UI + pause/resume/stop controls.

**Phase 5 Objective (current focus):**
- 🔜 **Advanced Task Scheduling**
  - support **simple schedules** (every X hours/days) and **cron schedules**
  - scheduling-aware execution respecting permissions + quiet hours
- 🔜 **Multi-task parallel execution**
  - bounded concurrency with **intelligent auto-scaling**
  - robust queueing, fairness, and safeguards
- 🔜 **Enhanced creative exploration** (internal learning only)
  - proactive idea generation and task drafting from internal context (memories/tasks/conversations)
  - safe-by-default and fully auditable
- 🔜 **Analytics / Monitoring Dashboard**
  - overview widgets on existing Dashboard + **dedicated Analytics page**
  - **auto-refresh polling** (5–10s) for real-time-ish operations visibility
  - provider/tool/task/memory/autonomy performance metrics

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

**Status:** ✅ COMPLETED

**Test Results:**
- Backend: ✅ **100%** - All Phase 4 endpoints working correctly
- Frontend: ✅ **100%** - All Phase 4 UI components and controls working, no regressions detected
- ✅ Added dashboard autonomy controls (pause/resume/stop) and `/api/autonomy/stop`

#### Phase 4 User Stories (delivered)
1. ✅ **Tool safety hardening**
2. ✅ **True autonomous execution engine** (pause/resume/cancel + daemon pause/resume/stop)
3. ✅ **Telegram inbound command router**
4. ✅ **Memory Management UI**
5. ✅ **Autonomy daemon** (tick loop: ideas/decay/telegram summary triggers)

---

### Phase 5 — Scheduling + Parallel Autonomy + Creative Exploration + Analytics
**Goal:** deliver advanced autonomy capabilities and production-grade operational visibility.

**Status:** 🔜 Planned (next)

#### Phase 5 Scope (approved decisions)
- Scheduling: ✅ **Both** simple schedules + cron schedules
- Parallelism: ✅ **Intelligent auto-scaling** bounded by safety limits
- Creative exploration: ✅ **Internal learning only** (no external browsing/search in Phase 5)
- Analytics UX: ✅ **Overview on Dashboard + dedicated Analytics page**
- Updates: ✅ **Auto-refresh polling** (5–10 seconds)

#### 5.1 Advanced Task Scheduling
**Backend**
- Add scheduling fields to `tasks`:
  - `schedule`: `{ mode: "none"|"interval"|"cron", interval_seconds?, cron_expr?, timezone? }`
  - `next_run_at`, `last_run_at`, `schedule_enabled`, `missed_runs_policy` (skip/catch-up)
  - `priority`, `queue_group` (optional)
- Add scheduler service (supervisor-managed worker or integrated asyncio background task):
  - computes `next_run_at` for eligible tasks
  - enqueues runnable tasks into execution queue
  - respects quiet hours + permissions + global rate limits
- Add endpoints:
  - `PUT /api/tasks/{id}/schedule`
  - `POST /api/tasks/{id}/run-now`
  - `GET /api/scheduler/status`
  - `POST /api/scheduler/pause` / `POST /api/scheduler/resume`

**Frontend**
- Task scheduling UI (likely in Tasks detail panel or Tasks page):
  - Schedule editor: Interval + Cron tabs
  - Next run time preview
  - Enable/disable schedule toggle
  - “Run now” CTA

**Testing**
- Unit: cron parsing and next_run computation
- Integration: task transitions + next_run updates

#### 5.2 Multi-task Parallel Execution (Queue + Workers)
**Backend**
- Introduce execution queue abstraction:
  - `task_queue` collection (or embed queue fields into `tasks`), with `status`, `locked_by`, `locked_at`, `attempts`, `last_error`
- Worker pool:
  - configurable hard limits: `max_concurrency_cap`
  - intelligent scaling: observe latency/errors and adjust active workers
  - fairness: avoid starving low-priority tasks; honor `priority`
- Add task lifecycle enhancements:
  - `in_progress` steps with `step_locks`, `retry/backoff`, circuit-breaker per tool/provider
- Add endpoints:
  - `GET /api/queue/status`
  - `POST /api/queue/rebalance`
  - `POST /api/tasks/{id}/retry`

**Frontend**
- Add queue status widget on Dashboard:
  - queued/running/failed/paused counts
  - active concurrency
- Add per-task execution telemetry:
  - last error, retry count, worker id

**Testing**
- Concurrency tests (locks, race prevention)
- Failure tests (provider/tool failures → backoff)

#### 5.3 Enhanced Creative Exploration (Internal)
**Backend**
- Add a “creative exploration engine” with:
  - configurable cadence (e.g., every N ticks)
  - input context sources: pinned memories, active tasks, recent conversation topics
  - outputs: suggestions (white cards) and optionally drafted tasks (requires approval)
- Add scoring and reinforcement:
  - track suggestion acceptance → boost patterns
  - track ignored suggestions → decay/avoid
- Add endpoints:
  - `GET /api/creativity/status`
  - `POST /api/creativity/run`
  - `PUT /api/creativity/settings`

**Frontend**
- Settings controls:
  - enable/disable
  - cadence slider
  - “draft tasks automatically” toggle (off by default)
- Dashboard: enhanced suggestions panel:
  - show why suggested (top 2 signals)

**Testing**
- Verify suggestions generated only when enabled
- Verify no tool execution without permission

#### 5.4 Analytics / Monitoring Dashboard
**Backend**
- Add analytics aggregation endpoints (Mongo aggregations) for:
  - autonomy daemon: ticks/min, pause duration, actions/tick, quiet hours blocks
  - task execution: success rate, avg duration, retries, failures by tool/provider
  - tool usage: command counts, blocked command counts, permission denials
  - memory: total, pinned, average utility, decay removals over time
  - provider performance: latency/error rate by provider/model
- Suggested endpoints:
  - `GET /api/analytics/overview`
  - `GET /api/analytics/autonomy`
  - `GET /api/analytics/tasks`
  - `GET /api/analytics/tools`
  - `GET /api/analytics/memory`
  - `GET /api/analytics/providers`

**Frontend**
- Add **Analytics page** (sidebar route):
  - Overview cards (KPIs)
  - Charts (Recharts) with subtle strokes (no heavy gradients)
  - Filters: time range (24h/7d/30d)
  - Auto-refresh polling every 5–10s (toggleable)
- Add Dashboard overview widgets:
  - small sparkline cards or KPI cards for autonomy/task/provider health

**Testing**
- Validate aggregations with seeded data
- Performance checks on large collections

#### 5.5 User Feedback 
**Status:** Deferred until Phase 5 + Analytics are delivered (per user request)
- Conduct structured walkthrough of:
  - autonomy controls
  - memory management flows
  - analytics usability
- Capture feedback and convert to Phase 5.1 patch sprint

---

## 3. Next Actions (immediate)
1. ✅ Completed: Phase 1, Phase 2, Phase 3, Phase 4.
2. Start Phase 5 in this order:
   1) Add scheduling schema + scheduler worker + endpoints
   2) Build execution queue + worker pool with intelligent scaling
   3) Enhance creative exploration (internal learning only)
   4) Implement Analytics backend aggregations + endpoints
   5) Build Analytics UI (overview on Dashboard + dedicated page) with auto-refresh
   6) Run regression suite + new Phase 5 tests
   7) Then perform user feedback/refinement cycle (Phase 5.1)

---

## 4. Success Criteria
- ✅ Core loop reliability: routing works with metadata + fallback.
- ✅ Permissions enforced: no tool runs without explicit grant; all actions logged.
- ✅ Memory works: recall improves responses; scoring and decay reduce noise.
- ✅ UI transparency: dashboard + timeline reflect model/tool/memory/agent events.
- ✅ Phase 3 success (achieved): multi-agent + K1 + tools + Telegram outbound + intuition.
- ✅ Phase 4 success (achieved): safety hardening + autonomy daemon + Telegram inbound + memory management + autonomy controls.

**Phase 5 success (target):**
- Scheduled tasks run reliably with clear next-run visibility and safe quiet-hours behavior
- Parallel task execution increases throughput without races, runaway loops, or unsafe tool calls
- Creative exploration produces useful suggestions with reinforcement learning from acceptance
- Analytics provides operational visibility (health, performance, errors) with minimal UI noise
- No regressions in Phase 1–4 features; all critical flows covered by automated tests
