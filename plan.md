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
- ➜ **Updated Phase 3 objective**: evolve Ombra from an assistant into a **true autonomous, multi-agent system** with:
  - **Ombra-K1** (local “learning” meta-model layer on top of Ollama)
  - **task planner + executor** (multi-step goals with retries)
  - **multi-agent delegation** (built-in + user-created agents)
  - **self-improving loops** (auto prompt/routing/strategy optimization)
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

**Status:** 🔜 READY TO START (scope confirmed)

#### Phase 3 User Stories (updated)
1. **Multi-step goals**: As a user, I can create a goal, and Ombra decomposes it into steps and executes them with retries.
2. **Explainability**: As a user, I can see why a suggestion/decision happened (linked memories, patterns, and routing rationale).
3. **Multi-agent delegation**: As a user, I can run tasks that automatically route to specialist agents (Coder/Researcher/Planner/Executor) and observe handoffs.
4. **Custom agents**: As a user, I can create custom agents with persona/system prompt, tools, and guardrails.
5. **Self-improving loops**: As a user, Ombra automatically improves prompts/routing/strategies based on success metrics and feedback; major changes are surfaced for review.
6. **Ombra-K1 local learning system**: As a user, Ombra runs local-first via Ollama, adapts prompts, manages local models based on laptop specs, and learns from cloud model “teacher” responses.
7. **Telegram integration**: As a user, I can message Ombra via Telegram and receive daily summaries and notifications.
8. **Filesystem tool**: As a user, I can allow Ombra to read/write files (permission-gated) for real workflows.
9. **Memory scoring/decay**: As a user, Ombra’s memory automatically prioritizes useful knowledge, decays stale memories, and lets me pin critical ones.
10. **Deeper intuition**: As a user, Ombra predicts intent, preloads relevant memories, and proposes proactive next steps.

#### Phase 3 Work Breakdown (recommended order)

##### 3.1 Agent Framework + Multi-Agent Orchestrator
- **Backend**
  - Define `Agent` schema (built-in + user-defined):
    - `agent_id`, `name`, `role`, `system_prompt`, `tools_allowed`, `provider_preferences`, `temperature`, `guardrails`
  - Implement `AgentRegistry` (Mongo-backed): create/update/list/delete agents.
  - Implement `MultiAgentOrchestrator`:
    - classifies task type → selects agent(s)
    - supports delegation + handoff logs (agent-to-agent events)
    - agent execution trace stored in activity timeline
  - APIs:
    - `GET/POST/PUT/DELETE /api/agents`
    - `POST /api/agents/run` (run agent on an input)
    - extend `/api/chat` to support `agent_id` optional

- **Frontend**
  - New **Agents** page:
    - list agents + status + tools + provider preference
    - create/edit agent modal (system prompt, tools)
  - Chat enhancements:
    - optional agent selector (default = Auto)

##### 3.2 Task Planner + Executor Loop (true autonomy)
- **Backend**
  - Upgrade tasks from CRUD → **execution engine**:
    - planner: goal → step list (tool needs, agent assignment, stop conditions)
    - executor: runs steps, retries with backoff, marks progress
    - supports human-in-the-loop checkpoints when required permissions missing
  - APIs:
    - `POST /api/goals/plan`
    - `POST /api/tasks/{id}/run`
    - `POST /api/tasks/{id}/pause` / `resume` / `cancel`

- **Frontend**
  - Dashboard: show “active executions” with progress
  - Tasks panel: step breakdown + run/pause/resume

##### 3.3 Ombra-K1 Local Model System (local-first, learns from cloud)
- **Concept**: Ombra-K1 is not a fine-tuned model; it is a **meta-layer** that:
  - maintains adaptive system prompts and routing heuristics
  - chooses the best local Ollama model for the job
  - escalates to cloud models when needed
  - distills “teacher” (cloud) outputs into reusable local prompt patterns and memories

- **Backend**
  - `OmbraK1Manager`:
    - maintains prompt variants (“prompt library”) with performance stats
    - generates “optimized system prompts” per agent and task category
    - teacher-student loop: when cloud used, store:
      - task signature → cloud response summary → extracted reusable rules
  - **Hardware-aware model manager**:
    - user provides/edits config (RAM tier + optional CPU/GPU)
    - recommended model list per tier:
      - 8GB: 3B–7B quantized
      - 16GB: 7B–13B quantized
      - 32GB+: 13B–34B+ quantized
    - auto pull models with Ollama (`ollama pull ...`) and track installed
  - APIs:
    - `GET /api/ollama/models` (installed)
    - `GET /api/ollama/recommendations` (based on user config)
    - `POST /api/ollama/pull`
    - `GET /api/k1/prompts` + `POST /api/k1/prompts/activate`

- **Frontend**
  - New **Model Manager** page:
    - installed models + sizes
    - recommendations based on user config
    - pull model button + progress
  - New **K1 Insights** panel:
    - “what improved recently” (prompt/routing changes)

##### 3.4 Self-Improving Loops (automatic + transparent for major changes)
- **Backend**
  - Collect metrics per:
    - provider/model
    - agent
    - tool execution success
    - task completion success
  - Add **user feedback** in chat (thumbs up/down) stored in Mongo
  - Auto adjustments:
    - routing thresholds
    - prompt selection (bandit-style choice among prompt variants)
    - agent selection weights
  - “Major change” policy:
    - new agent prompt baseline OR routing policy shifts require user-visible event
  - APIs:
    - `POST /api/feedback`
    - `GET /api/learning/metrics`
    - `GET /api/learning/changes` (history)

- **Frontend**
  - Chat: thumbs up/down per assistant response
  - New dashboard widget: “Learning Improvements” + metrics

##### 3.5 Memory Scoring / Decay + Pinning
- **Backend**
  - Extend memory schema:
    - `utility_score`, `last_accessed_at`, `access_count`, `pinned`, `decay_rate`
  - Retrieval:
    - hybrid: text relevance + utility + recency
  - Decay job:
    - periodically reduce utility for stale, unpinned memories
  - APIs:
    - `PUT /api/memories/{id}/pin`
    - `GET /api/memories/search`

- **Frontend**
  - Memory management page/section:
    - filter by type, pinned, score
    - pin/unpin

##### 3.6 Filesystem Tool (permission-gated)
- **Backend**
  - Implement safe read/write tools with:
    - allowed base directories
    - path sanitization
    - activity logging
  - APIs:
    - `POST /api/tools/fs/read`
    - `POST /api/tools/fs/write`

- **Frontend**
  - Add tool cards in chat when file actions happen
  - Permissions page already supports filesystem toggle

##### 3.7 Telegram Integration (token provided)
- **Backend**
  - Store Telegram config in settings
  - Start Telegram bot worker:
    - incoming messages → `/api/chat` (session per chat id)
    - outgoing: daily summary + notifications + task updates
    - quick commands (e.g., `/summary`, `/tasks`, `/run <task_id>`)
  - Token provided:
    - `8626997824:AAFYfotH7ZcOYbQHAFNT0cJSZ0QqtbYuib8`
  - APIs:
    - `POST /api/telegram/test`
    - `POST /api/telegram/send`

- **Frontend**
  - Settings: Telegram enable + chat id instructions + test button

##### 3.8 Deeper Intuition System
- **Backend**
  - Intent prediction:
    - infer probable user goal using recent turns + pinned memories + profile
  - Proactive context loading:
    - prefetch memories and attach to agent context
  - Suggestion generator:
    - grounded suggestions with memory/task references
  - APIs:
    - `GET /api/intuition/prediction`
    - `GET /api/intuition/suggestions`

- **Frontend**
  - Dashboard: “Next best actions” panel
  - Chat: contextual suggestion chips

#### Phase 3 End-of-phase testing (updated)
- E2E: create goal → planner generates steps → multi-agent execution runs → tool step reads/writes file → at least one cloud escalation → distilled learning saved → activity timeline shows:
  - agent delegation events
  - model calls with providers
  - memory writebacks with scores
  - Telegram summary delivered

---

### Phase 4 — Hardening, Security, and Optional Auth
**Goal:** make tools safer, improve reliability/observability, add governance + optional auth.

**Status:** 🔜 Planned

**Planned user stories (Phase 4)**
1. Run terminal commands with stronger guardrails and secret redaction.
2. Export/delete data (memories/logs/conversations).
3. Optional authentication.
4. Configure allowed command patterns + working directory.
5. Reliable restarts with state recovery.

**Work**
- Terminal hardening:
  - allowlist/denylist rules per user
  - sandbox directories + resource/time limits
  - secret redaction (env vars, tokens)
- Observability:
  - structured logs, trace IDs
  - failure dashboards + retry telemetry
- Data governance:
  - export/delete endpoints
  - retention policies
- Optional auth:
  - JWT + RBAC (after user approval)
- Regression + performance testing

## 3. Next Actions (immediate)
1. ✅ Completed: POC + full V1 delivery.
2. Start Phase 3 in the recommended order:
   1) Agent framework + orchestrator
   2) Task planner + executor
   3) Ombra-K1 prompt library + Ollama model manager
   4) Self-improving loops + feedback
   5) Memory scoring/decay + pinning
   6) Filesystem tool
   7) Telegram integration activation
   8) Intuition system upgrades
3. Add a regression suite for Phase 3:
   - agent CRUD + goal planning + task execution
   - model manager endpoints
   - Telegram test send

## 4. Success Criteria
- ✅ Core loop reliability: routing works with metadata + fallback.
- ✅ Permissions enforced: no tool runs without explicit grant; all actions logged.
- ✅ Memory works: recall improves responses; stored info visible via logs/timeline.
- ✅ UI transparency: dashboard + timeline reflect model/tool/memory events.
- ✅ White-card mode: proactive suggestions available.
- **Phase 3 success (updated):**
  - Multi-agent delegation works (built-in + custom agents)
  - Multi-step goals execute with retries and tool usage
  - Ombra-K1 improves prompts/routing automatically and distills cloud “teacher” responses
  - Hardware-aware local model selection/pulling works
  - Telegram messaging + daily summaries operational
  - Memory scoring/decay and intuition improve relevance and proactivity
