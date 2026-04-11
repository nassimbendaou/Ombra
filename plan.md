# plan.md

## 1. Objectives
- ✅ **Core agent loop proven end-to-end**: request → memory retrieval → model routing (Ollama vs API) → optional tool execution (terminal) → learning writebacks → activity logging → response.
- ✅ **Multi-provider model routing + fallback implemented** across:
  - **Ollama (local)** with `tinyllama`
  - **Cloud APIs (Anthropic, OpenAI, Gemini)** via **Emergent Universal Key**
- ✅ **MongoDB memory system implemented** for:
  - short-term conversation history
  - long-term memories (text-index retrieval + scoring)
  - user profile + permission state
- ✅ **V1 web app delivered** (dashboard + chat + permissions + activity timeline + settings + onboarding)
  - transparent, proactive (“white card mode”), safe-by-default permissions
- ➜ **Next objective (Phase 3)**: expand autonomy/intuition, richer memory retrieval, and plugin readiness (Telegram activation, more tools), plus hardening.

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
- Implemented a unified service in `/app/backend/server.py` with:
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

### Phase 3 — Add More Features (expand autonomy + intuition + plugins)
**Goal:** move from “capable assistant” to “autonomous agent” with deeper planning/execution, better memory retrieval, and plugin/tool expansion.

**Planned user stories (Phase 3)**
1. As a user, I can create **multi-step goals** and Ombra decomposes them into tasks with retries.
2. As a user, I can see **why Ombra suggested** something (memory links + pattern references).
3. As a user, I can control **quiet hours** and proactive behavior cadence.
4. As a user, I can **activate Telegram** by adding a token and receive daily summaries.
5. As a user, I can view/edit/reset learned profile and manage memories (pin/forget/export subset).

**Work (recommended next increments)**
- Autonomy engine (upgrade from CRUD → execution):
  - planner: generate step list + tool needs + stop conditions
  - executor loop: run steps, retry/backoff, mark done/failed
  - background runner (interval) + UI controls (start/stop)
- “Intuition” MVP:
  - intent prediction using: last N turns + profile + top memories
  - proactive suggestion generation grounded in activity + memories
  - prefetch relevant memories when opening a chat session
- Memory upgrades:
  - utility scoring (recency + reinforcement + user feedback)
  - decay/forgetting + pin/lock
  - hybrid retrieval (text + metadata); optional embeddings if enabled later
- Tool & plugin framework:
  - formal tool registry with scopes
  - Telegram plugin wiring (still disabled until token provided)
  - file system tool (behind permissions) for read/write operations

**End-of-phase testing (Phase 3)**
- E2E: create goal → tasks generated → execute at least one tool step → full audit trail + daily summary shown.

---

### Phase 4 — Hardening, Security, and Optional Auth
**Goal:** make terminal/tool usage safer, improve reliability and observability, and add optional auth/data controls.

**Planned user stories (Phase 4)**
1. As a user, I can run terminal commands with stronger guardrails and see redaction of secrets.
2. As a user, I can export/delete my data (memories/logs/conversations).
3. As a user, I can enable authentication once stable.
4. As a user, I can configure allowed command patterns and working directory.
5. As a user, I can run Ombra reliably across restarts (state recovery).

**Work**
- Terminal hardening:
  - allowlist/denylist rules per user
  - sandbox directories + resource/time limits
  - secret redaction (env vars, tokens)
- Observability:
  - structured logs with trace IDs for chat/tool calls
  - error dashboards + retry telemetry
- Data governance:
  - export/delete endpoints
  - memory compaction + retention policies
- Optional auth:
  - JWT-based auth and role-based permissions (only after user approval)
- Regression + performance testing

## 3. Next Actions (immediate)
1. ✅ Completed: POC + full V1 delivery.
2. Decide Phase 3 scope:
   - Autonomy execution loop first, or memory improvements first, or Telegram activation first.
3. If proceeding with Phase 3:
   - Implement task planner + executor loop + UI controls
   - Add file system tool behind permissions
   - Add memory scoring/decay + pinning
4. Add a small regression suite that runs on each change:
   - key API endpoints + basic UI navigation checks.

## 4. Success Criteria
- ✅ Core loop reliability: model routing works with metadata + fallback.
- ✅ Permissions enforced: no tool runs without explicit grant; all actions logged.
- ✅ Memory works: recall improves responses; stored info visible via logs/timeline.
- ✅ UI transparency: dashboard + timeline reflect model/tool/memory events.
- ✅ White-card mode: proactive suggestions available.
- ➜ Phase 3 success: multi-step goal execution with retries, grounded suggestions with memory links, and plugin/tool expansion without compromising safety.
