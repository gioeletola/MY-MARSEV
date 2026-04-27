# SOVEREIGN AI OS

> 280+ specialized agents · 41 connectors · 23 labs · 16 operating modes · FastAPI web UI

A self-directed, multi-agent AI operating system built on the Anthropic Claude API. Orchestrates a stratified hierarchy of agents across business, personal, finance, security, research, and strategy domains — with full memory persistence, semantic search, a7-layer security stack, and a real-time WebSocket dashboard.

---

## Quick Start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Set ANTHROPIC_API_KEY (required), SOVEREIGN_PASSWORD, AUTH_SECRET_KEY

# 3. Start web UI
python main.py serve --port 8080
# Open http://localhost:8080

# 4. Or use the CLI
python main.py run "Analyse my cashflow and suggest 3 savings actions"
python main.py run --interactive     # REPL mode
python main.py demo                  # full pipeline test
python main.py brief                 # morning briefing
```

---

## Architecture

```
User Input
  │
  ▼
InputPipeline (input_fabric/)
  │  Normalise · classify · extract intent · security scan
  ▼
CEOAgent  [LEVEL 5]                        claude-opus-4-6
  │  Strategic intent analysis + mode selection
  ▼
ChiefOfStaff → Coordinator  [LEVEL 5]      claude-sonnet-4-6
  │  Task decomposition (1–5 parallel tasks) + agent routing
  ▼
AgentSwarm  [LEVEL 2–4]    ←── Semaphore(5) concurrency gate
  │  280+ specialized agents dispatched in parallel
  │  7-step workflow: OBSERVE→ANALYZE→PLAN→EXECUTE→VERIFY→REPORT→SAVE_MEMORY
  ▼
GuardianAgent + ApprovalGate
  │  7-layer security · risk scoring · human-in-the-loop escalation
  ▼
StructuredOutput
  │
  ├── DecisionLedger    append-only JSONL audit log
  ├── MemoryManager     14-domain persistent memory + semantic search
  └── MetricsCollector  latency · tokens · cost tracking
```

---

## Features

| Category | Details |
|---|---|
| **Agents** | 280+ agents in 5 tiers (L2–L5) across Finance, Business, Personal, Imperial, Security, Offline, Black-Tier |
| **Memory** | 14 domains (identity, financial, project, decision, diary, health, learning, relationship, …) with lazy-cached TF-IDF semantic search; upgrades to dense embeddings with `pip install -e ".[embeddings]"` |
| **Connectors** | 41 integrations: 21 connected, 17 beta, 3 stub — Binance, Stripe, Telegram, Slack, Spotify, Strava, Shopify, Discord, Linear, CoinGecko, and more |
| **Labs** | 23 experimental labs (Finance, Simulation, Cyber, Red Team, Strategy, Bio, Behavioral, …) with DRAFT→RUNNING→COMPLETED→GRADUATED lifecycle |
| **Operating Modes** | 16 modes: command, business, personal, finance, study, travel, research, builder, local_offline, survival, founder, war, prestige, silent, recovery, emergency |
| **Security** | 7-layer SecurityStack: prompt injection detection, PII masking, dangerous command blocking, RBAC, secret obfuscation, audit log, incident escalation |
| **Governance** | RBAC, EscalationChain, SpendingLimits, RiskScoringEngine, ChangeManagement |
| **Web UI** | FastAPI + WebSocket + JWT auth + 9 HTML templates (dashboard, finance cockpit, business wall, HUD, approvals, expansion, entities, settings, admin) |
| **Prompt caching** | `cache_control: ephemeral` on static system prompt → ~70% token cost reduction |
| **Proactive** | GoalMonitor, SuggestionEngine, SilentOps, DailyDigest, EventEngine |

---

## CLI Reference

```bash
# Core
python main.py run "prompt"          # one-shot
python main.py run --interactive     # REPL
python main.py demo                  # full pipeline test
python main.py status                # system health
python main.py serve --port 8080     # web UI
python main.py telegram              # Telegram bot
python main.py brief                 # morning briefing
python main.py report --print        # weekly report

# Agents
python main.py agent list
python main.py agent info <agent_id>

# Connectors (41 total)
python main.py connector list
python main.py connector sync <connector_id>
python main.py connector health

# Labs (23 experimental labs)
python main.py lab list
python main.py lab status <lab_id>
python main.py lab experiments <lab_id>
python main.py lab run <lab_id> --template 0

# Skills
python main.py skill list
python main.py skill run <skill_id> --input '{"key": "value"}'
python main.py skill enable <skill_id>

# Vault (encrypted secrets)
python main.py vault set <key> <value>
python main.py vault get <key>
python main.py vault list
python main.py vault delete <key>

# Model catalog
python main.py model list
python main.py model list --tier frontier
python main.py model list --local
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | — | Obtain JWT token |
| GET | `/health` | — | System health JSON |
| WS | `/ws?token=<jwt>` | JWT | Real-time agent streaming |
| GET | `/api/usage` | JWT | Token usage stats |
| GET | `/api/agents` | — | All registered agents |
| GET | `/api/mode` | — | Current operating mode |
| POST | `/api/mode` | JWT | Switch mode |
| GET | `/api/memory/{domain}` | JWT | Read memory domain |
| GET | `/api/finance/summary` | — | Finance dashboard |
| GET | `/api/finance/transactions` | — | Transaction list |
| GET | `/api/goals` | — | Active goals |
| POST | `/api/goals` | JWT | Create goal |
| GET | `/api/projects` | — | Projects list |
| GET | `/api/connectors` | — | All connector statuses |
| GET | `/api/integrations` | — | Integration manager state |
| GET | `/api/next-actions` | — | Next action list |
| GET | `/api/morning-brief` | — | Morning briefing JSON |
| GET | `/expansion` | — | Expansion dashboard UI |
| GET | `/entities` | — | Entity management UI |
| GET | `/admin` | — | Admin panel |

---

## Operating Modes (16)

| Mode | Use case |
|---|---|
| `command` | Direct execution — maximum capability |
| `business` | CRM, finance, HR, legal, strategy |
| `personal` | Calendar, diary, health, goals |
| `finance` | Cashflow, budgeting, investment |
| `study` | Notes, summarisation, quizzing |
| `travel` | Itinerary, bookings, logistics |
| `research` | Multi-source synthesis, reports |
| `builder` | Code, architecture, deployment |
| `local_offline` | No external API calls |
| `survival` | Crisis mode — minimal footprint |
| `founder` | Startup ops — fundraising, team, GTM |
| `war` | High-stakes decision-making |
| `prestige` | Brand, luxury, high-touch service |
| `silent` | Background processing, no interruptions |
| `recovery` | Post-crisis stabilisation |
| `emergency` | Critical incident response |

---

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | Claude API access |
| `SOVEREIGN_PASSWORD` | Recommended | Web UI login password |
| `AUTH_SECRET_KEY` | Recommended | JWT signing key (64-char random) |
| `SECRET_MANAGER_KEY` | Optional | Vault encryption key |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot |
| `SLACK_BOT_TOKEN` | Optional | Slack integration |
| `BINANCE_API_KEY` | Optional | Binance trading |
| `STRIPE_SECRET_KEY` | Optional | Stripe payments |

See `.env.example` for the full list of 50+ connector variables.

---

## Extending SOVEREIGN

### New Agent
```python
# sovereign/swarm/your_domain_agents.py
NewAgent = _make_worker(
    "unique_agent_id",
    "Human Readable Specialty",
    "Detailed instructions for the agent...",
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    requires_review=False,
    confidence=0.82,
)
# Register in orchestrator.py _init_swarm()
```

### New Connector
```python
# sovereign/integrations/connectors/my_connector.py
class MyConnector(ConnectorBase):
    connector_id = "my_service"
    connector_name = "My Service"
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    async def connect(self) -> bool: ...
    async def sync(self) -> SyncResult: ...
    async def health(self) -> ConnectorHealth: ...
# Add to sovereign/integrations/connectors/__init__.py
```

### New Lab Experiment
```python
from sovereign.labs import FinanceLab
lab = FinanceLab()
exp = lab.quick_experiment(template_index=0)  # starts from template
lab.record_observation(exp.experiment_id, "Treatment shows 22% improvement")
lab.record_result(exp.experiment_id, "sharpe_ratio_improvement", 0.23)
result = lab.complete(exp.experiment_id)  # evaluates hypothesis
lab.graduate(exp.experiment_id)           # promotes to production
```

---

## Development

```bash
# Tests
python -m pytest tests/ -q --tb=short

# Lint
python -m ruff check .

# Type check
python -m mypy sovereign/

# With dense embeddings (better memory search)
pip install -e ".[embeddings]"

# With PDF support
pip install -e ".[pdf]"

# All extras
pip install -e ".[full,dev]"
```

---

## Docker

```bash
docker-compose up --build    # build and start
docker-compose up -d         # detached
docker-compose logs -f       # follow logs
```

---

## License

Proprietary — all rights reserved.
