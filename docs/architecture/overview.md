# Architecture Overview

SOVEREIGN is a multi-agent AI operating system. A user request flows through
a series of fixed layers before reaching the agent swarm; responses travel
back through the same layers for safety review, approval, and persistence.

## Request Flow

```
User Input
  ↓ InputPipeline          sovereign/input_fabric/pipeline.py
  ↓ CEOAgent               sovereign/executive/ceo_agent.py
  ↓ ChiefOfStaff           sovereign/executive/chief_of_staff.py
  ↓ TaskSetter             sovereign/executive/task_setter.py
  ↓ AgentSwarm             sovereign/swarm/ (Semaphore(5) parallel)
  ↓ GuardianAgent          sovereign/executive/guardian.py
  ↓ ApprovalGate           sovereign/authority/approval_gate.py
  ↓ StructuredOutput       sovereign/output/output_contract.py
  ↓ DecisionLedger         sovereign/registries/decision_ledger.py
  ↓ MemoryManager          sovereign/memory/memory_manager.py
```

## Layers

| Layer | Path | Responsibility |
|---|---|---|
| Kernel | `sovereign/kernel/` | Constitution, action classes, stop conditions |
| Authority | `sovereign/authority/` | Approval gate, escalation thresholds |
| Executive | `sovereign/executive/` | CEO, CoS, Guardian, task decomposition |
| Swarm | `sovereign/swarm/` | 200+ specialized worker agents |
| Memory | `sovereign/memory/` | 14-domain semantic + graph memory |
| Tools | `sovereign/tools/` | Tool registry, builtin tools |
| Engine | `sovereign/engine/` | Model backend adapters (Anthropic, Ollama, OpenAI) |
| Intelligence | `sovereign/intelligence/` | Model catalog and routing metadata |
| Integrations | `sovereign/integrations/` | Connector fabric (Gmail, Notion, GitHub, Weather) |
| Governance | `sovereign/governance/` | RBAC, spending limits, risk scoring |
| Security | `sovereign/security/` | Secrets, access control, session monitor |
| Observability | `sovereign/observability/` | Metrics, health, structured logs |
| Telemetry | `sovereign/telemetry/` | Session instrumentation, aggregation |
| API | `sovereign/api/` | FastAPI server, WebSocket handler, UI |

## Agent Hierarchy

```
SystemAgent  (singleton, always active)
  └─ CEOAgent        — intent recognition, mode selection
       └─ ChiefOfStaff  — task decomposition
            └─ TaskSetter  — concrete task list
                 └─ WorkerAgents (200+)  — domain specialists
                      └─ EphemeralAgents  — single-objective, TTL-bound
```

## Model Routing

The `ModelRouter` in `sovereign/router/model_router.py` selects models based on:
- **Task complexity** → Opus (frontier) / Sonnet (balanced) / Haiku (fast)
- **Privacy mode** → local Qwen models only
- **Cost budget** → avoids expensive models for bulk ops
- **Offline mode** → Ollama-only

See [model-routing.md](model-routing.md) for the full decision matrix.

## Prompt Caching

All Claude calls use `cache_control: ephemeral` on the static system prompt section.
The constitutional kernel (~1,500 tokens) + agent persona are cached.
After the first call, cache reads replace ~70% of input token cost.

See `sovereign/claude/client.py` and `sovereign/claude/prompt_builder.py`.
