# SOVEREIGN AI OS

A multi-agent AI operating system built on the Anthropic Claude API. Orchestrates 280+ specialized agents across business, personal, finance, security, and strategy domains.

## Architecture

```
User Input
  → InputPipeline (input_fabric/)
  → CEOAgent (executive/) — intent + mode selection
  → ChiefOfStaff → Coordinator — task decomposition + routing
  → AgentSwarm (swarm/) — parallel task dispatch [Semaphore(5)]
  → GuardianAgent + ApprovalGate — safety + human-in-the-loop
  → StructuredOutput → DecisionLedger + MemoryManager
```

## Running

```bash
# Install
pip install -e ".[dev]"

# CLI demo (requires ANTHROPIC_API_KEY)
python main.py demo

# Interactive REPL
python main.py run --interactive

# System status
python main.py status

# Web UI
python main.py serve --port 8080
# Open http://localhost:8080

# Telegram bot
python main.py telegram

# Morning briefing
python main.py brief

# Weekly report
python main.py report --print

# Tests
pytest tests/ -v
```

## CLI Sub-commands

```bash
# Agents
python main.py agent list
python main.py agent info <agent_id>

# Connectors (41 total: 21 connected, 17 beta, 3 stub)
python main.py connector list
python main.py connector sync <connector_id>
python main.py connector health

# Skills
python main.py skill list
python main.py skill run <skill_id> --input '{"key": "value"}'

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

## Key Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required — Claude API access |
| `SOVEREIGN_PASSWORD` | Web UI login password |
| `AUTH_SECRET_KEY` | JWT signing key (64-char random string) |
| `SECRET_MANAGER_KEY` | Vault encryption key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot integration |
| `SLACK_BOT_TOKEN` | Slack integration |

Copy `.env.example` to `.env` and fill in all relevant keys.

## Directory Structure

| Path | Purpose |
|---|---|
| `sovereign/orchestrator.py` | Master wiring — 10-step session flow |
| `sovereign/executive/` | CEO, ChiefOfStaff, Coordinator, Guardian, ApprovalGate, TaskSetter |
| `sovereign/swarm/` | All 280+ agent classes (factory pattern) |
| `sovereign/memory/` | 14-domain memory system with semantic search (TF-IDF + sentence-transformers) |
| `sovereign/tools/builtin/` | web_search, code_exec, file_ops, memory_tool, notes, calendar, bookmarks, etc. |
| `sovereign/claude/client.py` | Claude API client with prompt caching |
| `sovereign/kernel/` | Constitution, ActionClasses, StopConditions |
| `sovereign/authority/` | ApprovalGate, EscalationThresholds, Policy |
| `sovereign/governance/` | RBAC, EscalationChain, SpendingLimits, RiskScoring, ChangeManagement |
| `sovereign/security/` | SecretManager, SecurityStack (7-layer), AccessControl, SessionMonitor |
| `sovereign/integrations/` | 41 connectors (Finance, Social, Productivity, E-Commerce, Health, Travel) |
| `sovereign/integrations/connectors/` | BinanceConnector, StripeConnector, TelegramConnector, SlackConnector, … |
| `sovereign/infra/` | TaskQueue, Scheduler, WebhookRouter, AuthManager, Watchdog |
| `sovereign/labs/` | 23 experimental labs (framework + individual) |
| `sovereign/centers/` | 27 operational centers |
| `sovereign/observability/` | Metrics, EvalAgent, HealthMonitor, StructuredLogger, ModelPerformanceTracker |
| `sovereign/registries/` | Agent, Tool, Prompt, Workflow, Policy, Decision, Experiment registries |
| `sovereign/layers/` | RealityTwin, TimeMachine, TrustEngine, AttentionEngine, HumanLayer, SovereignExit, LegacyLayer |
| `sovereign/modes/` | 16 operating modes |
| `sovereign/proactive/` | GoalMonitor, SuggestionEngine, SilentOps, EventEngine, DailyDigest |
| `sovereign/reporting/` | WeeklyReport builder + Telegram sender |
| `sovereign/api/` | FastAPI server + WebSocket handler + 9 HTML templates |
| `sovereign/expansion/` | CapabilityGapDetector, ExpansionManager |
| `config/` | sovereign.yaml, models.yaml, operating_modes.yaml |
| `prompts/` | System and task prompt templates |
| `docs/` | API spec, agent map, permission matrix |

## Operating Modes (16)

`command` · `business` · `personal` · `finance` · `study` · `travel` · `research` · `builder` · `local_offline` · `survival` · `founder` · `war` · `prestige` · `silent` · `recovery` · `emergency`

## Agent Count (~280)

| File | Count |
|---|---|
| `finance_agents.py` | 26 |
| `business_agents.py` | 72 |
| `personal_agents.py` + `personal_workers.py` | ~80 |
| `imperial_agents.py` | ~57 |
| `decision_networking_agents.py` | 15 |
| `security_agents.py` | 5 |
| `offline_agents.py` | 4 |
| `black_tier_agents.py` | ~10 |
| Executive core | 8 |

## Connector Registry (41)

| Status | Connectors |
|---|---|
| **connected** (21) | Binance, CoinGecko, Discord, EdX, GitHub, HackerNews, Linear, Mailchimp, Notion (partial), RSS, Revolut, Skyscanner, Slack, Spotify, Strava, Stripe, Telegram, Typeform, Weather, WhatsApp (partial), X |
| **beta** (17) | Airbnb, Amazon, Bambu Lab, Calendar, Contacts, Deliveroo, eToro, Facebook, Gmail, Instagram, LinkedIn, MetaTrader, NotebookLM, Shopify, Uber, WhatsApp, Calendly |
| **stub** (3) | Farfetch, Oopbuy, Sisal |

## Adding a New Agent

```python
# In sovereign/swarm/your_domain_agents.py
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

## Adding a New Connector

```python
# In sovereign/integrations/connectors/my_connector.py
class MyConnector(ConnectorBase):
    connector_id = "my_service"
    connector_name = "My Service"
    connector_description = "What it does."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False

    async def connect(self) -> bool: ...
    async def sync(self) -> SyncResult: ...
    async def health(self) -> ConnectorHealth: ...

# Add to sovereign/integrations/connectors/__init__.py
```

## Adding a New Tool

```python
# In sovereign/tools/builtin/my_tool.py
class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "What it does."
    parameters_schema = {...}

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            return {"result": result, "error": None}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
```

## Security

- **Web UI**: login with `SOVEREIGN_PASSWORD`, JWT stored in localStorage, passed as `?token=` on WebSocket
- **Vault**: secrets encrypted at rest via `SecretManager` — use `python main.py vault set KEY VALUE`
- **SecurityStack**: 7-layer defense — prompt injection, PII, dangerous commands, RBAC, secret masking, audit, incident escalation
- **WebSocket**: unauthenticated connections are rejected with code 4401

## Prompt Caching

All Claude calls use `cache_control: ephemeral` on the static system prompt section (~1500 tokens). After the first call, cache reads replace ~70% of input token cost. See `sovereign/claude/client.py` and `prompt_builder.py`.
