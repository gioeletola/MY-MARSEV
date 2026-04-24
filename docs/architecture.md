# SOVEREIGN AI OS — Architecture

## Overview

SOVEREIGN is a multi-agent AI operating system built on Anthropic Claude API. It orchestrates 200+ specialized agents, persists context across 14 memory domains, and exposes a real-time web UI + REST API.

```
User Input (text / web / Telegram)
  ↓
InputPipeline  ── validates, normalizes, classifies
  ↓
CEOAgent  ────── intent parsing, mode selection, strategic brief
  ↓
ChiefOfStaff ── task decomposition, priority ordering
  ↓
TaskSetter ───── agent hint selection, tool assignment
  ↓
AgentSwarm ───── asyncio.gather + Semaphore(5) parallel dispatch
  │
  ├── Executive agents: CEO, ChiefOfStaff, Guardian, TaskSetter, DecisionBrief
  ├── Finance agents (26): portfolio, tax, cashflow, budget…
  ├── Business agents (72): strategy, marketing, operations, HR…
  ├── Personal agents (80): health, relationships, travel, notes…
  ├── Imperial agents (57): geopolitical, historical, prestige…
  └── Security/Offline/Domain agents
  ↓
GuardianAgent ── safety review on all EXECUTE-class actions
  ↓
ApprovalGate ─── human-in-the-loop for high-risk actions
  ↓
StructuredOutput ─ 14-field result contract
  ↓
DecisionLedger ── append-only JSONL audit log
  ↓
MemoryManager ─── semantic + graph + temporal write-back
```

## Layer Stack

| Layer | Path | Purpose |
|---|---|---|
| **Kernel** | `sovereign/kernel/` | Constitution, ActionClass enum, StopConditions |
| **Authority** | `sovereign/authority/` | ApprovalGate, EscalationThresholds, Policy |
| **Executive Core** | `sovereign/executive/` | CEO, ChiefOfStaff, Guardian, TaskSetter, Coordinator |
| **Agent Swarm** | `sovereign/swarm/` | 200+ agents via `_make_worker()` factory |
| **Memory** | `sovereign/memory/` | 14 domains, semantic search, graph traversal |
| **Claude Client** | `sovereign/claude/` | Prompt caching, tool loop, streaming, retry |
| **Model Router** | `sovereign/router/` | Multi-provider routing, circuit-breaker fallback |
| **Tools** | `sovereign/tools/` | 15+ built-in tools + registry |
| **Input Fabric** | `sovereign/input_fabric/` | 13-step input normalization pipeline |
| **Output Contract** | `sovereign/output/` | StructuredOutput dataclass |
| **Registries** | `sovereign/registries/` | Agent, tool, prompt, workflow, decision ledger |
| **Governance** | `sovereign/governance/` | RBAC, spending limits, risk scoring, escalation |
| **Security** | `sovereign/security/` | Lockdown, quarantine, access control, session monitor |
| **Observability** | `sovereign/observability/` | Health monitor, eval agent, model tracker |
| **Modes** | `sovereign/modes/` | 16 operating modes with different constraints |
| **Integrations** | `sovereign/integrations/` | Telegram, Email, Calendar, Slack, Notion, CRM |
| **Infra** | `sovereign/infra/` | TaskQueue, Scheduler, WebhookRouter, AuthManager |
| **Models** | `sovereign/models/` | Anthropic, OpenAI, Gemini, Qwen, Local providers |
| **Layers** | `sovereign/layers/` | RealityTwin, TimeMachine, TrustEngine, HumanLayer, Legacy |
| **Expansion** | `sovereign/expansion/` | CapabilityGapDetector, AgentPromoter, BuilderStudio |
| **Devices** | `sovereign/devices/` | DeviceGateway, SensorManager, ActionLoop |
| **HUD** | `sovereign/hud/` | Jarvis overlay, camera feed, voice commands |
| **API** | `sovereign/api/` | FastAPI server, WebSocket handler, 10 dashboard templates |

## Data Flow — Single Request

```
1. POST /ws  {"type":"chat","message":"Analyze my portfolio"}
2. WebSocketSessionManager.handle_chat()
3. orchestrator.handle_request(user_input, mode="finance")
4. InputPipeline.process() → normalized, classified input
5. MemoryManager.get_snapshot() → 14-domain memory context
6. CEOAgent → strategic intent: "financial_analysis"
7. ChiefOfStaff → tasks: [portfolio_review, risk_assessment, recommendations]
8. asyncio.gather(*[dispatch(t) for t in tasks], semaphore=5)
9. GuardianAgent.review_action() on EXECUTE-class tasks
10. ApprovalGate.request_approval() if risk > threshold
11. StructuredOutput aggregation
12. DecisionLedger.record()
13. MemoryManager.write() → update financial domain
14. WS push: stream_delta + stream_done + health
```

## Prompt Caching Strategy

```
System Message Structure:
  [BLOCK 1 — static, cache_control:ephemeral]
    - Constitutional kernel (~800 tokens)
    - Agent persona + capabilities (~400 tokens)
    - Tool schemas (~300 tokens)
  [BLOCK 2 — dynamic, no cache]
    - Session memory snapshot (~500 tokens)
    - Recent conversation context (~300 tokens)

Cache hit saves ~70% of input token cost.
```

## Security Model

```
All requests → InputPipeline (injection scan, PII detection)
               ↓
             ActionClass ceiling enforcement
               ↓ (EXECUTE class)
             GuardianAgent review
               ↓ (risk > threshold)
             ApprovalGate (human confirmation or policy auto-approve)
               ↓
             SecurityStack (output scan for PII leakage)
               ↓
             DecisionLedger (immutable audit trail)
```
