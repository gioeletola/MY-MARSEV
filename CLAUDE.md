# SOVEREIGN AI OS

A multi-agent AI operating system built on the Anthropic Claude API. Orchestrates 200+ specialized agents across business, personal, finance, security, and strategy domains.

## Architecture

```
User Input
  → InputPipeline (input_fabric/)
  → CEOAgent (executive/) — intent + mode selection
  → ChiefOfStaff → TaskSetter — task decomposition
  → AgentSwarm (swarm/) — parallel task dispatch [Semaphore(5)]
  → GuardianAgent + ApprovalGate — safety + human-in-the-loop
  → StructuredOutput → DecisionLedger + MemoryManager
```

## Running

```bash
# Install
pip install -e ".[dev]"

# CLI demo (no server needed)
python main.py demo

# System status
python main.py status

# Web UI (requires ANTHROPIC_API_KEY)
python main.py serve --port 8080
# Open http://localhost:8080

# Tests
pytest tests/ -v
```

## Key Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required — Claude API access |
| `SECRET_MANAGER_KEY` | Optional — secret obfuscation key |
| `AUTH_SECRET_KEY` | Optional — JWT signing key |

Copy `.env.example` to `.env` and fill in.

## Directory Structure

| Path | Purpose |
|---|---|
| `sovereign/orchestrator.py` | Master wiring — 10-step session flow |
| `sovereign/executive/` | CEO, ChiefOfStaff, Guardian, ApprovalGate, TaskSetter |
| `sovereign/swarm/` | All 200+ agent classes (factory pattern) |
| `sovereign/memory/` | 14-domain memory system with semantic search |
| `sovereign/tools/builtin/` | web_search, code_exec, file_ops, memory_tool, notes, calendar, bookmarks, etc. |
| `sovereign/claude/client.py` | Claude API client with prompt caching |
| `sovereign/kernel/` | Constitution, ActionClasses, StopConditions |
| `sovereign/authority/` | ApprovalGate, EscalationThresholds, Policy |
| `sovereign/governance/` | RBAC, EscalationChain, SpendingLimits, RiskScoring, ChangeManagement |
| `sovereign/security/` | SecretManager, AccessControl, SessionMonitor, Quarantine, Lockdown |
| `sovereign/integrations/` | Email, Calendar, Telegram, CRM, Analytics stubs |
| `sovereign/infra/` | TaskQueue, Scheduler, WebhookRouter, AuthManager |
| `sovereign/labs/` | 21 experimental labs (framework + individual) |
| `sovereign/centers/` | 27 operational centers |
| `sovereign/observability/` | Metrics, EvalAgent, HealthMonitor, StructuredLogger |
| `sovereign/registries/` | Agent, Tool, Prompt, Workflow, Policy, Decision registries |
| `sovereign/layers/` | RealityTwin, TimeMachine, TrustEngine, AttentionEngine, HumanLayer, SovereignExit, LegacyLayer |
| `sovereign/modes/` | 10 operating modes (command, business, personal, finance, ...) |
| `sovereign/api/` | FastAPI server + WebSocket handler + index.html |
| `config/` | sovereign.yaml, models.yaml, operating_modes.yaml |
| `prompts/` | System and task prompt templates |
| `docs/` | API spec, agent map, permission matrix |

## Operating Modes

`command` · `business` · `personal` · `finance` · `study` · `travel` · `research` · `builder` · `local_offline` · `survival`

## Agent Count (~200+)

| File | Count |
|---|---|
| `finance_agents.py` | 26 |
| `business_agents.py` | 72 |
| `personal_agents.py` + `personal_workers.py` | ~80 |
| `imperial_agents.py` | ~57 |
| `decision_networking_agents.py` | 15 |
| `security_agents.py` | 5 |
| `offline_agents.py` | 4 |
| Executive core | 8 |

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
            ...
            return {"result": result, "error": None}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
```

## Adding a New Integration

Inherit `BaseIntegration` in `sovereign/integrations/`, implement `connect`, `fetch`, `push`, register in `IntegrationManager`.

## Prompt Caching

All Claude calls use `cache_control: ephemeral` on the static system prompt section (~1500 tokens). After the first call, cache reads replace ~70% of input token cost. See `sovereign/claude/client.py` and `prompt_builder.py`.
