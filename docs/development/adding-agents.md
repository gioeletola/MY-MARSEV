# Adding Agents

## Using the Factory Pattern

The fastest way to add a new worker agent is with `_make_worker`:

```python
# sovereign/swarm/my_domain_agents.py
from sovereign.swarm.base_agent import _make_worker

MyAgent = _make_worker(
    agent_id="my_agent",
    specialty="My Domain Specialist",
    instructions=(
        "You are a specialist in [domain]. "
        "Your job is to [specific responsibility]. "
        "Always [key behavior]."
    ),
    tools=["memory_tool", "web_search"],
    model="claude-sonnet-4-6",
    requires_review=False,
    confidence=0.82,
)

MY_AGENTS = [MyAgent]
```

Then register in `sovereign/orchestrator.py` inside `_init_swarm()`:

```python
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

## Custom Agent (Full Implementation)

For agents that need custom behavior beyond the factory pattern:

```python
from sovereign.swarm.base_agent import BaseAgent, AgentTask
from sovereign.output.output_contract import OutputStatus, StructuredOutput

class MyCustomAgent(BaseAgent):
    agent_id = "my_custom_agent"
    agent_name = "My Custom Agent"
    model = "claude-sonnet-4-6"
    requires_review = False

    async def run(self, task: AgentTask, ctx: dict) -> StructuredOutput:
        # Build system prompt
        system = (
            "You are a specialist in [domain].\n"
            f"{self._constitution.render_for_prompt()}"
        )

        # Call Claude
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

## Agent Naming Conventions

| Suffix | Meaning |
|---|---|
| `_agent` | Generic agent |
| `_chief` | Domain coordinator (manages workers) |
| `_analyst` | Data/research analysis |
| `_specialist` | Deep domain expert |
| `_manager` | Process/workflow management |

## Tool Access

Specify allowed tools in `_make_worker(tools=[...])`.
Available builtin tools:

| Tool ID | Description |
|---|---|
| `memory_tool` | Read/write agent memory |
| `web_search` | DuckDuckGo search |
| `code_exec` | Execute Python in sandbox |
| `file_ops` | Read/write files |
| `notes` | Personal notes |
| `calendar` | Calendar access |
| `bookmarks` | Bookmark manager |

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
```
