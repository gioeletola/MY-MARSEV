# SOVEREIGN AI OS

> Multi-agent AI operating system — 200+ specialized agents across business, personal, finance, security, and strategy domains.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Start the web UI
python main.py serve --port 8080
# Open http://localhost:8080

# CLI demo (no API key needed)
python main.py demo

# System status
python main.py status
```

## Architecture

```
User Input
  │
  ▼
InputPipeline (input_fabric/)
  │  Normalise, classify, extract intent
  ▼
CEOAgent (executive/)
  │  Intent analysis + operating mode selection
  ▼
ChiefOfStaff → TaskSetter
  │  Task decomposition into parallel sub-tasks
  ▼
AgentSwarm (swarm/)          ← Semaphore(5) concurrency gate
  │  200+ specialised agents dispatched in parallel
  ▼
GuardianAgent + ApprovalGate (authority/)
  │  Safety checks + human-in-the-loop escalation
  ▼
StructuredOutput
  │
  ├── DecisionLedger  — append-only audit log
  └── MemoryManager   — 14-domain persistent memory
```

## Features

- **200+ specialised agents** spanning business, personal, finance, security, and strategy domains
- **10 operating modes** — command, business, personal, finance, study, travel, research, builder, local_offline, survival
- **14-domain memory system** with TF-IDF semantic search and optional ChromaDB vector store
- **Bayesian A/B experiment tracking** with auto-promotion of winning variants
- **Prompt caching** — ~70% reduction in input token cost via `cache_control: ephemeral`
- **Human-in-the-loop approval gate** — configurable risk thresholds, auto or CLI mode
- **RBAC + spending limits + risk scoring** — full governance layer
- **FastAPI + WebSocket** web UI with JWT authentication
- **Telegram bot integration** for mobile access
- **Proactive suggestions** and goal monitoring
- **Docker-ready** — single `docker-compose up` to start

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/status` | No | System health and version |
| POST | `/api/auth/login` | No | Obtain JWT token |
| GET | `/api/goals` | Yes | List active goals |
| POST | `/api/goals` | Yes | Create a new goal |
| GET | `/api/projects` | Yes | List projects |
| POST | `/api/projects` | Yes | Create a project |
| GET | `/api/finance/summary` | Yes | Finance dashboard summary |
| GET | `/api/finance/transactions` | Yes | Transaction list |
| POST | `/api/finance/transactions` | Yes | Record a transaction |
| GET | `/api/entities` | Yes | List connected entities |
| POST | `/api/entities` | Yes | Register a connected entity |
| GET | `/api/mode` | Yes | Current operating mode |
| POST | `/api/mode` | Yes | Switch operating mode |
| GET | `/api/memory/{domain}` | Yes | Read memory domain |
| POST | `/api/memory/{domain}` | Yes | Write to memory domain |
| GET | `/api/agents` | Yes | List all registered agents |
| GET | `/expansion` | Yes | Expansion center UI |
| GET | `/entities` | Yes | Entity management UI |

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API access |
| `AUTH_SECRET_KEY` | No | JWT signing key (default: insecure placeholder) |
| `SOVEREIGN_PASSWORD` | No | Web UI login password |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot integration |
| `OPENAI_API_KEY` | No | OpenAI fallback / Whisper transcription |
| `GEMINI_API_KEY` | No | Google Gemini integration |
| `SLACK_WEBHOOK_URL` | No | Slack notification webhook |
| `NOTION_API_KEY` | No | Notion workspace integration |

Copy `.env.example` to `.env` and fill in the values you need.

## Operating Modes

| Mode | Description |
|------|-------------|
| `command` | Direct command execution — maximum capability, minimal friction |
| `business` | Business operations — CRM, finance, HR, legal, strategy |
| `personal` | Personal productivity — calendar, diary, health, goals |
| `finance` | Financial analysis — cashflow, budgeting, investment tracking |
| `study` | Learning and research — note-taking, summarisation, quizzing |
| `travel` | Travel planning and logistics — itinerary, bookings, packing |
| `research` | Deep research — multi-source synthesis, citations, reports |
| `builder` | Engineering and building — code, architecture, deployment |
| `local_offline` | Offline-capable tasks — no external API calls required |
| `survival` | Minimal footprint — crisis mode with essential functions only |

## Adding Agents / Tools / Integrations

### New Agent

```python
# In sovereign/swarm/your_domain_agents.py
from sovereign.swarm.worker_agent import WorkerAgent

NewAgent = _make_worker(
    "unique_agent_id",
    "Human Readable Specialty",
    "Detailed instructions for the agent...",
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    requires_review=False,
    confidence=0.82,
)
# Add to YOUR_AGENTS list and register in orchestrator.py _init_swarm()
```

### New Tool

```python
# In sovereign/tools/builtin/my_tool.py
from sovereign.tools.base_tool import BaseTool, ToolSchema

class MyTool(BaseTool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="my_tool",
            description="What it does.",
            input_schema={"type": "object", "properties": {}, "required": []},
        )

    async def execute(self, **params) -> dict:
        try:
            result = ...
            return {"result": result, "error": None}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
```

### New Integration

```python
# In sovereign/integrations/my_integration.py
from sovereign.integrations.base_integration import BaseIntegration, IntegrationConfig

class MyIntegration(BaseIntegration):
    integration_id = "my_service"
    name = "My Service"

    def connect(self, config: IntegrationConfig) -> bool: ...
    def disconnect(self) -> bool: ...
    async def fetch(self, resource: str, params: dict) -> dict: ...
    async def push(self, resource: str, data: dict) -> dict: ...
```

Register in `IntegrationManager.__init__()`.

## Running Tests

```bash
# Run all tests with coverage
python -m pytest tests/ -q --tb=short --cov=sovereign --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_registries.py -v

# Lint check
python -m ruff check .
```

## Docker

```bash
# Build and start all services
docker-compose up --build

# Detached mode
docker-compose up -d

# View logs
docker-compose logs -f sovereign
```
