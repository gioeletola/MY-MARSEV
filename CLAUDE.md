# SOVEREIGN AI OS

A multi-agent AI operating system. Orchestrates 334 specialized agents across business, personal, finance, security, and strategy domains.

> **Status:** Alpha/Advanced Prototype — architecture is solid, hardening in progress. Not recommended for autonomous execution on critical systems without human supervision.
>
> **Primary provider:** Anthropic Claude (required — set `ANTHROPIC_API_KEY`)
> | Tier | Model ID |
> |---|---|
> | Frontier | `claude-opus-4-7` |
> | Balanced (default) | `claude-sonnet-4-6` |
> | Fast / cheap | `claude-haiku-4-5-20251001` |
>
> **Optional providers** (activate by setting their key):
> | Key | Provider | Models |
> |---|---|---|
> | `OPENAI_API_KEY` | OpenAI | GPT-4o, GPT-4o-mini |
> | `GEMINI_API_KEY` | Google Gemini | 1.5 Pro, 1.5 Flash |
> | `PERPLEXITY_API_KEY` | Perplexity | Sonar, Sonar Pro (web-augmented) |
> | `MOONSHOT_API_KEY` | Kimi (Moonshot AI) | kimi-latest, moonshot-v1-32k, moonshot-v1-8k |
> | Ollama running locally | Qwen / local | qwen2.5:7b–qwen3:32b, Mistral 7B |
>
> All optional providers degrade gracefully: if the key/endpoint is absent they return a stub and the router falls back to Claude.

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

# Copy and fill env (ANTHROPIC_API_KEY is required; all others are optional)
cp .env.example .env && $EDITOR .env

# Pre-flight check (validates env, configs, dirs, packages)
python main.py check

# Pre-flight check WITH live Claude API call (costs ~1 token)
python main.py check --live

# CLI demo (requires ANTHROPIC_API_KEY)
python main.py demo

# Build local standalone app (no Python required on target machine)
./scripts/build_local.sh
./dist/sovereign/sovereign serve --port 8080

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

# Connectors (44 total: 21 connected, 20 beta, 3 stub→beta upgraded)
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
| `sovereign/swarm/` | All 326 agent classes (factory pattern) |
| `sovereign/memory/` | 18-domain memory system with semantic search: ChromaDB + sentence-transformers (all-MiniLM-L6-v2) with TF-IDF fallback. Install: `pip install chromadb sentence-transformers` |
| `sovereign/tools/builtin/` | web_search, code_exec, file_ops, memory_tool, notes, calendar, hash, url, date, text_analysis, base64, uuid, number, color, template_render, markdown, diff, translation, etc. |
| `sovereign/claude/client.py` | Claude API client with prompt caching (primary execution path) |
| `sovereign/models/` | Multi-provider layer: AnthropicProvider, OpenAIProvider, GeminiProvider, PerplexityProvider, QwenProvider, LocalProvider, ProviderDispatcher |
| `sovereign/kernel/` | Constitution, ActionClasses, StopConditions |
| `sovereign/authority/` | ApprovalGate, EscalationThresholds, Policy |
| `sovereign/governance/` | RBAC, EscalationChain, SpendingLimits, RiskScoring, ChangeManagement |
| `sovereign/security/` | SecretManager, SecurityStack (7-layer), AccessControl, SessionMonitor |
| `sovereign/integrations/` | 44 connectors (Finance, Social, Productivity, E-Commerce, Health, Travel) |
| `sovereign/integrations/connectors/` | BinanceConnector, StripeConnector, TelegramConnector, SlackConnector, YouTubeConnector, RedditConnector, ProductHuntConnector, … |
| `scripts/` | `build_local.sh` — PyInstaller local app packaging |
| `sovereign.spec` | PyInstaller spec for standalone desktop/server binary |
| `sovereign/infra/` | TaskQueue, Scheduler, WebhookRouter, AuthManager, Watchdog |
| `sovereign/labs/` | 23 experimental labs (framework + individual) |
| `sovereign/centers/` | 27 operational centers |
| `sovereign/observability/` | Metrics, EvalAgent, HealthMonitor, StructuredLogger, ModelPerformanceTracker |
| `sovereign/registries/` | Agent, Tool, Prompt, Workflow, Policy, Decision, Experiment registries |
| `sovereign/layers/` | RealityTwin, TimeMachine, TrustEngine, AttentionEngine, HumanLayer, SovereignExit, LegacyLayer |
| `sovereign/modes/` | 17 operating modes |
| `sovereign/proactive/` | GoalMonitor, SuggestionEngine, SilentOps, EventEngine, DailyDigest |
| `sovereign/reporting/` | WeeklyReport builder + Telegram sender |
| `sovereign/api/` | FastAPI server + WebSocket handler + 9 HTML templates |
| `sovereign/expansion/` | CapabilityGapDetector, ExpansionManager |
| `config/` | sovereign.yaml, models.yaml, operating_modes.yaml |
| `prompts/` | System and task prompt templates |
| `docs/` | API spec, agent map, permission matrix |

## Operating Modes (17)

`command` · `business` · `personal` · `finance` · `study` · `travel` · `research` · `builder` · `local_offline` · `survival` · `founder` · `war` · `prestige` · `silent` · `recovery` · `emergency` · `caveman`

> **caveman** — budget-constrained mode: forces cheapest models (Haiku → Qwen → local), terse synthetic responses, 512-token output cap, offline-capable. NOT a model — it's a mode that overrides routing. See `sovereign/modes/caveman_mode.py`.

## Agent Count (326)

| File | Count |
|---|---|
| `finance_agents.py` | 25 |
| `business_agents.py` | 72 |
| `personal_agents.py` | 45 |
| `personal_workers.py` | 63 |
| `imperial_agents.py` | 58 |
| `decision_networking_agents.py` | 15 |
| `security_agents.py` | 5 |
| `offline_agents.py` | 4 |
| `black_tier_agents.py` | 39 |
| Executive core | 8 |
| **Total** | **334** |

## Connector Registry (44)

| Status | Connectors |
|---|---|
| **connected** (21) | Binance, CoinGecko, Discord, EdX, GitHub, HackerNews, Linear, Mailchimp, Notion (partial), RSS, Revolut, Skyscanner, Slack, Spotify, Strava, Stripe, Telegram, Typeform, Weather, WhatsApp (partial), X |
| **beta** (20) | Airbnb, Amazon, Bambu Lab, Calendar, Contacts, Deliveroo, eToro, Facebook, Gmail, Instagram, LinkedIn, MetaTrader, NotebookLM, Shopify, Uber, WhatsApp, Calendly, Farfetch, Oopbuy, Sisal |
| **new** (3) | YouTube (Data API v3), Reddit (public JSON + search), ProductHunt (GraphQL) |

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
from sovereign.tools.base_tool import BaseTool, ToolSchema

class MyTool(BaseTool):
    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="my_tool",
            description="What it does.",
            input_schema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"],
            },
        )

    async def execute(self, param: str, **_) -> dict:
        return {"result": f"processed: {param}"}
```

## Security

- **Web UI**: login with `SOVEREIGN_PASSWORD`, JWT (HMAC-SHA256) stored in localStorage
- **WebSocket auth**: use `GET /api/ws-ticket` to obtain a 30-second single-use ticket, then connect with `?ticket=<ticket>`. The legacy `?token=` URL param is deprecated (logs may capture it).
- **Vault**: secrets encrypted at rest via `SecretManager` (PBKDF2-SHA256) — use `python main.py vault set KEY VALUE`
- **SecurityStack**: 7-layer defense — prompt injection, PII, dangerous commands, RBAC, secret masking, audit, incident escalation
- **WebSocket**: unauthenticated connections rejected with code 4401
- **Security headers**: HSTS, CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Permissions-Policy on every response
- **Production mode**: set `SOVEREIGN_ENV=production` to enforce all secrets are present at startup (`AUTH_SECRET_KEY`, `SOVEREIGN_PASSWORD`, `SECRET_MANAGER_KEY`)

## Prompt Caching

All Claude calls use `cache_control: ephemeral` on the static system prompt section (~1500 tokens). After the first call, cache reads replace ~70% of input token cost. See `sovereign/claude/client.py` and `prompt_builder.py`.
