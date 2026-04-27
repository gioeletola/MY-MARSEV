# Adding Agents — SOVEREIGN AI OS v0.3.0

SOVEREIGN uses a factory pattern to create worker agents. Most agents can be created with a single `_make_worker()` call. Custom behavior requires subclassing `BaseAgent`.

---

## Agent Tiers

| Tier | Role | Typical model | Location |
|---|---|---|---|
| **L5** | Executive (CEO, CoS, Coordinator) | `claude-opus-4-6` | `sovereign/executive/` |
| **L4** | Domain chiefs | `claude-sonnet-4-6` | `sovereign/swarm/<domain>_agents.py` |
| **L3** | Senior specialists | `claude-sonnet-4-6` | `sovereign/swarm/<domain>_agents.py` |
| **L2** | Worker agents (default) | `claude-sonnet-4-6` | `sovereign/swarm/<domain>_agents.py` |
| **L2f** | Fast/cheap workers | `claude-haiku-4-5-20251001` | `sovereign/swarm/<domain>_agents.py` |

---

## The `_make_worker()` Factory

The fastest way to add a new worker agent:

```python
# sovereign/swarm/my_domain_agents.py
from sovereign.swarm.base_agent import _make_worker

MyAgent = _make_worker(
    agent_id="my_agent",                     # unique string ID
    specialty="My Domain Specialist",        # human-readable name
    instructions=(
        "You are a specialist in [domain]. "
        "Your job is to [specific responsibility]. "
        "Always [key behavior]. "
        "Deliver structured, actionable output."
    ),
    tools=["memory_tool", "web_search"],     # see available tools below
    model="claude-sonnet-4-6",              # model to use
    requires_review=False,                   # set True for high-risk agents
    confidence=0.82,                         # default confidence score (0–1)
)

MY_AGENTS = [MyAgent]
```

### `_make_worker()` parameters

| Parameter | Type | Description |
|---|---|---|
| `agent_id` | `str` | Unique identifier; used for routing and registry lookup |
| `specialty` | `str` | Human-readable name shown in logs and the web UI |
| `instructions` | `str` | The agent's system prompt — what it does and how |
| `tools` | `list[str]` | Tool IDs available to this agent |
| `model` | `str` | Model ID from the catalog (default: `claude-sonnet-4-6`) |
| `requires_review` | `bool` | If `True`, output goes through ApprovalGate before delivery |
| `confidence` | `float` | Default confidence score attached to outputs (0.0–1.0) |

---

## Registering in the Orchestrator

After defining the agent, register it in `sovereign/orchestrator.py` inside `_init_swarm()`:

```python
# sovereign/orchestrator.py  —  inside _init_swarm()
from sovereign.swarm.my_domain_agents import MY_AGENTS

for agent_cls in MY_AGENTS:
    agent = agent_cls(
        claude_client=self._claude,
        tool_registry=self._tool_registry,
        memory_manager=self._memory,
        constitution=self._constitution,
    )
    self._agent_registry.register(agent)
```

After restarting SOVEREIGN the new agent appears in `python main.py agent list`.

---

## Custom Agent (Full Subclass)

For agents that need non-standard behavior (multi-step logic, custom tool handling, etc.):

```python
from sovereign.swarm.base_agent import BaseAgent, AgentTask
from sovereign.output.output_contract import OutputStatus, StructuredOutput

class MyCustomAgent(BaseAgent):
    agent_id = "my_custom_agent"
    agent_name = "My Custom Agent"
    model = "claude-sonnet-4-6"
    requires_review = False

    async def run(self, task: AgentTask, ctx: dict) -> StructuredOutput:
        system = (
            "You are a specialist in [domain].\n"
            f"{self._constitution.render_for_prompt()}"
        )

        response = await self._call_claude(
            messages=[{"role": "user", "content": task.objective}],
            system=system,
        )

        return StructuredOutput(
            session_id=task.task_id,
            agent_id=self.agent_id,
            task_id=task.task_id,
            status=OutputStatus.SUCCESS,
            result=response,
            confidence=0.85,
        )
```

---

## Available Builtin Tools

Specify allowed tools in `_make_worker(tools=[...])`:

| Tool ID | Description |
|---|---|
| `memory_tool` | Read/write/search agent memory across all 14 domains |
| `web_search` | DuckDuckGo search (no API key required) |
| `code_exec` | Execute Python in a sandboxed subprocess |
| `file_ops` | Read/write files within the data directory |
| `notes` | Personal notes (append/read) |
| `calendar` | Calendar access (read events, create reminders) |
| `bookmarks` | Bookmark manager (add/search bookmarks) |

---

## Agent Naming Conventions

| Suffix | Meaning |
|---|---|
| `_agent` | Generic agent |
| `_chief` | Domain coordinator (manages sub-workers) |
| `_analyst` | Data or research analysis |
| `_specialist` | Deep domain expert |
| `_manager` | Process or workflow management |

---

## Testing Your Agent

```python
# tests/test_my_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sovereign.swarm.my_domain_agents import MyAgent
from sovereign.swarm.base_agent import AgentTask

@pytest.mark.asyncio
async def test_my_agent_runs():
    agent = MyAgent(
        claude_client=AsyncMock(),
        tool_registry=MagicMock(),
        memory_manager=MagicMock(),
        constitution=MagicMock(),
    )
    task = AgentTask(task_id="t1", objective="Test task", action_class=2)
    result = await agent.run(task, {})
    assert result.agent_id == "my_agent"
    assert result.status.value == "success"
```

Run with:

```bash
pytest tests/test_my_agent.py -v
```

---

## Existing Agent Files

| File | Domain | Approx. count |
|---|---|---|
| `sovereign/swarm/finance_agents.py` | Finance | 26 |
| `sovereign/swarm/business_agents.py` | Business | 72 |
| `sovereign/swarm/personal_agents.py` + `personal_workers.py` | Personal | ~80 |
| `sovereign/swarm/imperial_agents.py` | Imperial / advanced | ~57 |
| `sovereign/swarm/decision_networking_agents.py` | Decision & Networking | 15 |
| `sovereign/swarm/security_agents.py` | Security | 5 |
| `sovereign/swarm/offline_agents.py` | Offline | 4 |
| `sovereign/swarm/black_tier_agents.py` | Black-tier | ~10 |
| `sovereign/executive/` | Executive core | 8 |
