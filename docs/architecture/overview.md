# Architecture Overview — SOVEREIGN AI OS v0.3.0

SOVEREIGN is a multi-agent AI operating system. Every user request flows through a fixed 10-step pipeline before reaching the agent swarm; responses travel back through the same layers for safety review, approval, and persistence.

---

## 10-Step Session Flow

```
Step 1  User Input
          ↓
Step 2  InputPipeline          sovereign/input_fabric/pipeline.py
          │  Normalise · classify · extract intent · security scan
          ↓
Step 3  CEOAgent               sovereign/executive/ceo_agent.py
          │  Strategic intent analysis + mode selection
          │  Model: claude-opus-4-6
          ↓
Step 4  ChiefOfStaff           sovereign/executive/chief_of_staff.py
       + Coordinator           sovereign/executive/coordinator.py
          │  Task decomposition (1–5 parallel tasks) + agent routing
          │  Model: claude-sonnet-4-6
          ↓
Step 5  AgentSwarm             sovereign/swarm/   ←── Semaphore(5)
          │  280+ specialized agents dispatched in parallel
          │  7-step workflow per agent:
          │  OBSERVE → ANALYZE → PLAN → EXECUTE → VERIFY → REPORT → SAVE_MEMORY
          ↓
Step 6  GuardianAgent          sovereign/executive/guardian.py
          │  7-layer security · risk scoring · PII masking
          ↓
Step 7  ApprovalGate           sovereign/authority/approval_gate.py
          │  Human-in-the-loop escalation for high-risk actions
          ↓
Step 8  Aggregate Results
          │  Merge swarm outputs into StructuredOutput
          ↓
Step 9  DecisionLedger         sovereign/registries/decision_ledger.py
          │  Append-only JSONL audit log
          ↓
Step 10 MemoryManager          sovereign/memory/memory_manager.py
          │  Persist session context to 14-domain memory store
```

---

## Agent Tiers

| Tier | Role | Model | Examples |
|---|---|---|---|
| **L5** | Executive strategy | `claude-opus-4-6` | CEOAgent, ChiefOfStaff, Coordinator |
| **L4** | Domain chiefs | `claude-sonnet-4-6` | FinanceChief, SecurityChief, BusinessChief |
| **L3** | Senior specialists | `claude-sonnet-4-6` | RiskAnalyst, StrategySpecialist, LegalAdvisor |
| **L2** | Worker agents | `claude-sonnet-4-6` | InvoiceAgent, HealthAgent, CalendarAgent |
| **L2f** | Fast/cheap workers | `claude-haiku-4-5` | ClassificationAgent, RoutingAgent |

Total: **280+ agents** across Finance (26), Business (72), Personal (~80), Imperial (~57), Decision/Networking (15), Security (5), Offline (4), Black-Tier (~10), and Executive core (8).

---

## Major Components

| Path | Purpose |
|---|---|
| `sovereign/orchestrator.py` | Master wiring — 10-step session flow |
| `sovereign/executive/` | CEO, ChiefOfStaff, Coordinator, Guardian, ApprovalGate, TaskSetter |
| `sovereign/swarm/` | All 280+ agent classes (factory pattern via `_make_worker`) |
| `sovereign/input_fabric/` | InputPipeline: normalise, classify, intent extraction, security scan |
| `sovereign/memory/` | 14-domain memory system with semantic search (TF-IDF + sentence-transformers) |
| `sovereign/tools/builtin/` | web_search, code_exec, file_ops, memory_tool, notes, calendar, bookmarks |
| `sovereign/claude/client.py` | Claude API client with prompt caching (`cache_control: ephemeral`) |
| `sovereign/kernel/` | Constitution, ActionClasses, StopConditions |
| `sovereign/authority/` | ApprovalGate, EscalationThresholds, Policy |
| `sovereign/governance/` | RBAC, EscalationChain, SpendingLimits, RiskScoring, ChangeManagement |
| `sovereign/security/` | SecretManager, SecurityStack (7-layer), AccessControl, SessionMonitor |
| `sovereign/integrations/` | 41 connectors (Finance, Social, Productivity, E-Commerce, Health, Travel) |
| `sovereign/infra/` | TaskQueue, Scheduler, WebhookRouter, AuthManager, Watchdog |
| `sovereign/labs/` | 21 experimental labs (LabsFramework + individual lab classes) |
| `sovereign/centers/` | 27 operational centers |
| `sovereign/observability/` | Metrics, EvalAgent, HealthMonitor, StructuredLogger, ModelPerformanceTracker |
| `sovereign/registries/` | Agent, Tool, Prompt, Workflow, Policy, Decision, Experiment registries |
| `sovereign/layers/` | RealityTwin, TimeMachine, TrustEngine, AttentionEngine, HumanLayer, SovereignExit, LegacyLayer |
| `sovereign/modes/` | 16 operating modes |
| `sovereign/proactive/` | GoalMonitor, SuggestionEngine, SilentOps, EventEngine, DailyDigest |
| `sovereign/reporting/` | WeeklyReport builder + Telegram sender |
| `sovereign/api/` | FastAPI server + WebSocket handler + 9 HTML templates |
| `sovereign/expansion/` | CapabilityGapDetector, ExpansionManager |
| `sovereign/router/` | ModelRouter — multi-factor model selection |
| `sovereign/engine/` | AnthropicEngine, OllamaEngine, OpenAICompatEngine, MultiEngine |
| `config/` | sovereign.yaml, models.yaml, operating_modes.yaml |
| `prompts/` | System and task prompt templates |

---

## Security Stack (7 layers)

The `GuardianAgent` applies all 7 layers in order before any output leaves the system:

1. **Prompt injection detection** — blocks jailbreak and override attempts
2. **PII masking** — redacts personally identifiable information when in safe mode
3. **Dangerous command blocking** — halts shell/code execution above risk threshold
4. **RBAC enforcement** — validates agent permissions against policy
5. **Secret obfuscation** — masks API keys and credentials in output
6. **Audit logging** — writes every decision to the append-only ledger
7. **Incident escalation** — triggers alert chain for high-severity events

---

## Concurrency Model

The AgentSwarm uses `asyncio.Semaphore(5)` to cap parallel Claude API calls at 5 simultaneous requests. The ChiefOfStaff decomposes tasks into 1–5 parallel sub-tasks; each is dispatched to the most appropriate worker agent in the swarm.

---

## Prompt Caching

All Claude calls use `cache_control: ephemeral` on the static system prompt section (Constitution ~1,500 tokens + agent persona). After the first call per session, cache reads replace ~70% of input token cost. See `sovereign/claude/client.py` and `sovereign/claude/prompt_builder.py`.

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
| `local_offline` | No external API calls — Ollama only |
| `survival` | Crisis mode — minimal footprint |
| `founder` | Startup ops — fundraising, team, GTM |
| `war` | High-stakes decision-making |
| `prestige` | Brand, luxury, high-touch service |
| `silent` | Background processing, no interruptions |
| `recovery` | Post-crisis stabilisation |
| `emergency` | Critical incident response |

See [model-routing.md](model-routing.md) for how the model selection changes per mode.
