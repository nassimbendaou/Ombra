# Ombra - Autonomous AI Agent System

<div align="center">

<p align="center">
  <img src="./OMBRA_logo.png" alt="Ombra Banner" width="250"/>
</p>

**A complete, production-ready autonomous AI agent system with local-first intelligence, multi-agent orchestration, and advanced self-learning capabilities.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 20+](https://img.shields.io/badge/node.js-20+-green.svg)](https://nodejs.org/)
[![MongoDB](https://img.shields.io/badge/mongodb-7.0-green.svg)](https://www.mongodb.com/)

[Features](#features) • [Quick Start](#quick-start) • [Deployment](#deployment) • [User Guide](#user-guide) • [API Docs](#api-documentation) • [Changelog](./CHANGELOG.md)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [User Guide](#user-guide)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Changelog](./CHANGELOG.md)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

**Ombra** is a sophisticated autonomous AI agent system that combines local-first intelligence with cloud AI capabilities. It features multi-agent orchestration, advanced task scheduling, creative exploration, and comprehensive monitoring.

### Key Highlights

- 🧠 **Hybrid Intelligence**: Local LLMs (Ollama) + Cloud APIs (OpenAI/Anthropic/Google)
- 🤖 **Multi-Agent System**: Built-in specialists + custom agent creation
- 📅 **Advanced Scheduling**: Simple intervals + cron expressions
- 🔄 **Auto-Scaling Execution**: Intelligent worker pool (1-10 workers)
- 💡 **Creative Exploration**: Context-aware idea generation
- 📊 **Analytics Dashboard**: Real-time operational insights
- 🔒 **Security First**: Permission gating, tool safety, secret redaction
- 🌐 **Remote Control**: Telegram bot integration
- 🧩 **Self-Learning**: Ombra-K1 meta-layer for continuous improvement

---

## ✨ Features

### Phase 1-2: Core MVP
- ✅ **Hybrid Model Routing**: Automatic local/cloud selection based on task complexity
- ✅ **Memory System**: Short-term conversations + long-term semantic memory with decay
- ✅ **Dashboard**: Real-time system status and activity monitoring
- ✅ **Chat Interface**: Conversational AI with agent/model selection
- ✅ **Permission Manager**: Granular control over tool access
- ✅ **Activity Timeline**: Complete audit log of all operations

### Phase 3: Multi-Agent Framework
- ✅ **5 Built-in Agents**: Coder, Researcher, Planner, Executor, Custom
- ✅ **Ombra-K1 Learning**: Local meta-layer for distillation and self-improvement
- ✅ **Task Orchestration**: Multi-step goal execution with auto-retry
- ✅ **File System Tools**: Safe directory operations with sandboxing
- ✅ **Telegram Integration**: Outbound notifications and summaries
- ✅ **Model Manager**: Configure and test different LLM providers

### Phase 4: Hardening & Autonomy
- ✅ **Tool Safety**: Allowlist/denylist policies, secret redaction, timeout enforcement
- ✅ **Autonomy Daemon**: Background execution with pause/resume/stop controls
- ✅ **Telegram Router**: Inbound command processing (/status, /tasks, /run, etc.)
- ✅ **Memory Management UI**: Search, filter, pin, delete memories
- ✅ **Quiet Hours**: Respect user-defined low-activity periods

### Phase 5: Scheduling & Analytics
- ✅ **Task Scheduling**: Interval-based + cron expressions with timezone support
- ✅ **Intelligent Queue**: Auto-scaling worker pool (3-10 workers based on load)
- ✅ **Creative Exploration**: Internal context-based idea generation
- ✅ **Analytics Dashboard**: 
  - Task execution metrics and success rates
  - Provider performance and latency tracking
  - Tool usage analytics
  - Memory distribution and decay stats
  - Autonomy daemon insights

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  Dashboard | Chat | Agents | Models | Analytics | Settings │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
┌────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI)                          │
│  ┌──────────────┬──────────────┬──────────────────────┐    │
│  │ API Routes   │ Model Router │ Tool Safety Manager  │    │
│  ├──────────────┼──────────────┼──────────────────────┤    │
│  │ Scheduler    │ Task Queue   │ Creative Explorer    │    │
│  ├──────────────┼──────────────┼──────────────────────┤    │
│  │ Autonomy     │ Multi-Agent  │ Ombra-K1 Learning    │    │
│  │ Daemon       │ Framework    │ System               │    │
│  └──────────────┴──────────────┴──────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐  ┌──────▼──────┐  ┌─────▼─────┐
│   MongoDB    │  │   Ollama    │  │  Cloud    │
│  (Database)  │  │  (Local AI) │  │ APIs (AI) │
└──────────────┘  └─────────────┘  └───────────┘
```

### Tech Stack

**Backend:**
- **Framework**: FastAPI (Python 3.10+)
- **Database**: MongoDB 7.0
- **Local AI**: Ollama (Mistral 7B, TinyLlama 1B)
- **Cloud AI**: Emergent Universal Key (OpenAI, Anthropic, Google)
- **Task Queue**: Custom async queue with auto-scaling
- **Scheduler**: croniter + custom tick-based scheduler

**Frontend:**
- **Framework**: React 18
- **UI Components**: Shadcn/UI + Tailwind CSS
- **Charts**: Recharts
- **Routing**: React Router v6
- **HTTP Client**: Axios

**Infrastructure:**
- **Reverse Proxy**: Nginx
- **Process Manager**: Supervisor
- **SSL**: Let's Encrypt (Certbot)

---

## 📦 Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB | 50 GB |
| OS | Ubuntu 22.04 | Ubuntu 22.04 LTS |

### Required Software

- **Python**: 3.10 or higher
- **Node.js**: 20.x or higher
- **MongoDB**: 7.0 or higher
- **Ollama**: Latest version
- **Git**: Any recent version

### Required Credentials

1. **Emergent LLM Key** (Free tier available)
   - Sign up at: Emergent AI Platform
   - Provides unified access to OpenAI, Anthropic, Google models
   
2. **Telegram Bot Token** (Optional, for remote control)
   - Create bot via [@BotFather](https://t.me/botfather)
   - Save the bot token

---

## 🚀 Quick Start

### Local Development Setup

#### 1. Clone Repository
```bash
git clone <repository-url>
cd ombra
```

#### 2. Install MongoDB
```bash
# Ubuntu/Debian
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod
```

#### 3. Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral
ollama pull tinyllama
```

#### 4. Setup Backend
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional providers/features (safe to skip if unavailable)
pip install -r requirements-optional.txt

# Configure environment
cp .env.example .env
nano .env
```

**Edit `.env`:**
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=ombra_dev
EMERGENT_LLM_KEY=your_emergent_key_here
OLLAMA_URL=http://localhost:11434
TELEGRAM_BOT_TOKEN=your_telegram_token_here  # Optional
```

**Dependency policy note:**
- `requirements.txt` installs only the stable public dependency set.
- Optional/private integrations are isolated in `backend/requirements-optional.txt` so fresh environment rebuilds do not fail.

#### 5. Setup Frontend
```bash
cd ../frontend

# Install dependencies
npm install
# OR
yarn install

# Configure environment
cp .env.example .env
```

**Edit `frontend/.env`:**
```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

#### 6. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
# OR
yarn start
```

#### 7. Access Application
```
Frontend: http://localhost:3000
Backend API: http://localhost:8001
API Docs: http://localhost:8001/docs
```

---

## 🌐 Deployment

### Production Deployment to Azure VPS

We provide a comprehensive deployment guide for Azure Virtual Private Server.

**See:** [`DEPLOYMENT.md`](./DEPLOYMENT.md)

The deployment guide includes:
- ✅ Azure VM setup (Portal + CLI)
- ✅ Complete server configuration
- ✅ MongoDB, Ollama, Nginx installation
- ✅ SSL/HTTPS with Let's Encrypt
- ✅ Supervisor service management
- ✅ Security hardening (Firewall, Fail2Ban)
- ✅ Monitoring and backup procedures
- ✅ Troubleshooting guides

### Quick Deployment Summary

```bash
# 1. Create Azure VM (Ubuntu 22.04, 2 vCPU, 8GB RAM)
az vm create --resource-group ombra-rg --name ombra-vm --image Ubuntu2204 --size Standard_D2s_v3

# 2. SSH to VM
ssh azureuser@<VM_IP>

# 3. Install dependencies
sudo apt update && sudo apt upgrade -y
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs python3-pip mongodb-org nginx supervisor

# 4. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral tinyllama

# 5. Deploy application
sudo mkdir -p /opt/ombra
cd /opt/ombra
# Upload code, configure .env, build frontend

# 6. Configure services (see DEPLOYMENT.md)
# 7. Start and verify
sudo supervisorctl start all
```

---

## 📖 User Guide

### First Time Setup

#### 1. Onboarding
When you first access Ombra, you'll see the onboarding flow:

1. **Welcome Screen**: Introduction to Ombra
2. **Permission Setup**: Grant terminal/filesystem/telegram permissions
3. **Profile Creation**: Set your name and preferences
4. **Get Started**: Access the dashboard

#### 2. Configure Settings

Navigate to **Settings** page:

**Model Configuration:**
- **Ollama Model**: Select `mistral` (recommended) or `tinyllama`
- **Preferred Provider**: Choose `auto` (recommended), `ollama`, `openai`, `anthropic`, or `gemini`
- **White Card Mode**: Enable for proactive AI suggestions

**Autonomy Settings:**
- **Learning Enabled**: Enable K1 self-learning loops
- **Quiet Hours**: Set start/end times (e.g., 22:00 to 07:00)

**Telegram Integration:**
- **Chat ID**: Your Telegram chat ID
- **Enable Telegram**: Toggle on/off

**Creative Exploration:**
- **Enable Creativity**: Turn on context-based idea generation
- **Cadence**: How often to generate ideas (default: every 5 ticks)

### Using the Dashboard

The **Dashboard** provides a real-time overview:

**Metrics Cards:**
- Total conversations
- Total tasks
- Active agents
- Memory usage

**System Status:**
- CPU/Memory usage
- Ollama status
- Cloud API connectivity
- Database health

**Autonomy Daemon:**
- Running/Paused/Stopped status
- Ticks count
- Ideas generated
- Memory decay runs
- Telegram summaries sent
- **Controls**: Pause, Resume, Stop buttons

**Recent Activity:**
- Last 5 system activities
- Color-coded by type (model, tool, memory, etc.)

**Active Tasks:**
- Tasks in progress or pending
- Quick navigation to task details

**White Card Suggestions:**
- AI-generated proactive suggestions
- Accept or dismiss

### Chat Interface

Navigate to **Chat** page:

**Basic Usage:**
1. Type your message in the input box
2. Press Enter or click Send
3. AI responds with context-aware answers

**Agent Selection:**
- Click the agent dropdown (default: "General")
- Select specialist: Coder, Researcher, Planner, Executor
- Agent handles task with specialized prompts

**Model Selection:**
- Click the model dropdown
- Choose specific model (overrides auto-routing)
- Options: Mistral, TinyLlama, GPT-4o, Claude, Gemini

**White Card Mode:**
- Toggle white card icon in header
- AI becomes more proactive with suggestions
- Shows creative ideas and next steps

**Message Types:**
- User messages: Right-aligned, blue background
- AI responses: Left-aligned, dark background
- Tool executions: Yellow badge with tool name
- Errors: Red badge with error message

### Task Management

Navigate to **Dashboard** → **Active Tasks**:

**Create Task:**
1. Go to Chat
2. Ask AI to create a task (e.g., "Create a task to analyze server logs")
3. Task appears in Active Tasks section

**Task Lifecycle:**
- **Pending**: Created, waiting for execution
- **In Progress**: Currently being executed by worker
- **Completed**: Successfully finished
- **Failed**: Execution failed (see error details)
- **Cancelled**: Manually cancelled

**Task Scheduling:**
1. Create or select a task
2. Click "Schedule" button
3. Choose schedule type:
   - **Interval**: Run every X seconds/minutes/hours/days
   - **Cron**: Use cron expression (e.g., `0 9 * * 1-5` = weekdays at 9am)
4. Enable/disable schedule
5. Set "Respect Quiet Hours" preference

**Manual Execution:**
- Click "Run Now" to bypass schedule and execute immediately
- Task gets high priority in queue

### Memory Management

Navigate to **Memories** page:

**Search & Filter:**
- Use search box to find specific memories
- Filter by type: conversation, task, creative_idea, etc.

**Memory Actions:**
- **Pin**: Keep important memories (prevents decay)
- **Delete**: Remove memory permanently
- **View Details**: See full content, utility score, access count

**Memory Types:**
- **Conversation**: Chat history snippets
- **Task**: Task-related learnings
- **Creative Idea**: AI-generated suggestions
- **Tool**: Tool execution results
- **Agent**: Agent-specific knowledge

**Utility Scores:**
- Higher score = more important memory
- Scores decay over time based on access frequency
- Pinned memories maintain high scores

### Agent Management

Navigate to **Agents** page:

**Built-in Agents:**
- **Coder**: Code generation, debugging, refactoring
- **Researcher**: Information gathering, summarization
- **Planner**: Task breakdown, strategy formulation
- **Executor**: Multi-step task execution

**Create Custom Agent:**
1. Click "Create New Agent"
2. Enter name (e.g., "Legal Advisor")
3. Write system prompt (defines agent behavior)
4. Select available tools (terminal, filesystem, web, etc.)
5. Save agent

**Using Agents:**
1. In Chat, select agent from dropdown
2. Ask questions or give tasks
3. Agent responds with specialized expertise

**Manage Agents:**
- Edit system prompts
- Enable/disable specific tools
- Delete custom agents (built-in agents can't be deleted)

### Model Manager

Navigate to **Models** page:

**Test Models:**
1. Select provider (Ollama, OpenAI, Anthropic, Gemini)
2. Select model
3. Enter test prompt
4. Click "Test Model"
5. View response time and output

**Provider Status:**
- Green: Available and responding
- Yellow: Slow response (>2s)
- Red: Error or unavailable

**Model Information:**
- Capabilities (text, code, reasoning)
- Context window size
- Recommended use cases

### Analytics Dashboard

Navigate to **Analytics** page:

**Overview KPIs:**
- Activities (24h)
- Tasks Completed
- Success Rate
- Total Memories

**Tabs:**

**Tasks Tab:**
- Status distribution pie chart
- Execution performance metrics (avg/min/max duration)
- Queue status (queue size, active workers, concurrency)

**Providers Tab:**
- Request count by provider
- Average latency comparison
- Error rates
- Bar chart visualization

**Autonomy Tab:**
- Daemon running status
- Total ticks
- Ideas generated
- Memory decay runs
- Telegram summaries
- Cloud escalations

**Tools Tab:**
- Tool usage bar chart (24h)
- Execution counts per tool
- Blocked commands count

**Memory Tab:**
- Type distribution pie chart
- Total memories count
- Pinned memories
- Utility score distribution
- Decay operations (24h)

**Auto-Refresh:**
- Toggle auto-refresh on/off
- Updates every 10 seconds when enabled
- Manual refresh button available

### Telegram Remote Control

**Setup:**
1. Create bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID: Message [@userinfobot](https://t.me/userinfobot)
3. Add bot token and chat ID to Settings
4. Enable Telegram integration

**Available Commands:**
- `/status` - Get system status
- `/summary` - Get daily summary
- `/tasks` - List active tasks
- `/run <task_id>` - Execute task by ID
- `/pause <task_id>` - Pause task
- `/resume <task_id>` - Resume task
- `/cancel <task_id>` - Cancel task

**Automatic Summaries:**
- Ombra sends daily summaries automatically
- Frequency: Every 100 daemon ticks (~100 minutes)
- Includes: tasks completed, ideas generated, system health

### Permissions & Security

Navigate to **Permissions** page:

**Permission Types:**
- **Terminal**: Execute shell commands
- **Filesystem**: Read/write files
- **Telegram**: Send messages via bot

**Tool Safety Policies:**
1. Navigate to Settings → Tool Safety
2. Configure policies:
   - **Allowlist Mode**: Only listed commands allowed
   - **Denylist Mode**: All commands except listed are allowed
3. Add commands to allowlist/denylist
4. Set execution timeouts
5. Enable secret redaction

**Activity Audit:**
- All tool executions logged
- Navigate to Activity page
- Filter by type: tool, model, memory, etc.
- View execution details, duration, status

---

## ⚙️ Configuration

### Backend Environment Variables

**File:** `backend/.env`

```env
# Database
MONGO_URL=mongodb://localhost:27017
DB_NAME=ombra_production

# Local AI
OLLAMA_URL=http://localhost:11434

# Cloud AI (Emergent Universal Key)
EMERGENT_LLM_KEY=your_key_here

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Server
CORS_ORIGINS=*  # Restrict in production: https://yourdomain.com
HOST=0.0.0.0
PORT=8001
```

### Frontend Environment Variables

**File:** `frontend/.env` (development)

```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

**File:** `frontend/.env.production` (production)

```env
REACT_APP_BACKEND_URL=https://yourdomain.com
```

### MongoDB Configuration

**Default Collections:**
- `users` - User profiles and preferences
- `settings` - System configuration
- `conversations` - Chat history
- `messages` - Individual messages
- `memories` - Long-term semantic memory
- `tasks` - Task definitions and status
- `agents` - Custom agent configurations
- `activity_log` - Complete audit trail
- `k1_learning` - K1 distillation records
- `tool_policies` - Tool safety rules

**Indexes (Auto-created):**
```javascript
db.tasks.createIndex({ "status": 1, "created_at": -1 })
db.memories.createIndex({ "type": 1, "pinned": 1 })
db.activity_log.createIndex({ "timestamp": -1, "type": 1 })
db.messages.createIndex({ "conversation_id": 1, "timestamp": 1 })
```

### Ollama Models

**Recommended Models:**
- **mistral** (7B): Best balance of speed/quality for general tasks
- **tinyllama** (1B): Ultra-fast for simple queries

**Pull Models:**
```bash
ollama pull mistral
ollama pull tinyllama

# Optional: Larger models (requires more RAM)
ollama pull llama3
ollama pull codellama
```

**Model Configuration:**
Edit `backend/server.py` to adjust generation parameters:
```python
{
    "model": "mistral",
    "options": {
        "temperature": 0.7,      # Creativity (0.0-1.0)
        "top_p": 0.9,            # Diversity
        "num_predict": 1000,     # Max tokens
        "num_ctx": 8192          # Context window
    }
}
```

---

## 📡 API Documentation

Full API documentation with examples is available in the [API Reference](./API.md).

### Quick Examples

**Chat:**
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "agent_name": "general"}'
```

**Create Task:**
```bash
curl -X POST http://localhost:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Task", "goal": "Test execution"}'
```

**Schedule Task:**
```bash
curl -X PUT http://localhost:8001/api/tasks/{id}/schedule \
  -H "Content-Type: application/json" \
  -d '{"mode": "cron", "cron_expr": "0 9 * * *"}'
```

**Interactive Docs:** `http://localhost:8001/docs`

---

## 🛠️ Development

### Project Structure

```
ombra/
├── backend/           # FastAPI backend
├── frontend/          # React frontend
├── tests/             # Test files
├── DEPLOYMENT.md      # Deployment guide
├── README.md          # This file
└── plan.md            # Development roadmap
```

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

---

## 🐛 Troubleshooting

See [DEPLOYMENT.md](./DEPLOYMENT.md#troubleshooting) for comprehensive troubleshooting guide.

**Common Quick Fixes:**

```bash
# Restart all services
sudo supervisorctl restart all

# Check logs
tail -f /var/log/ombra/backend.err.log

# Verify MongoDB
sudo systemctl status mongod

# Check Ollama models
ollama list
```

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.
For compatibility with older references, see [contibution.md](./contibution.md).

---

## 📄 License

MIT License - see [LICENSE](./LICENSE) for details.

---

<div align="center">


⭐ Star us on GitHub if you find this helpful!

</div>
