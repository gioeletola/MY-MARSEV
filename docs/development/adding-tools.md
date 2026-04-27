# Adding Tools — SOVEREIGN AI OS v0.3.0

Tools are callable capabilities exposed to agents via the tool registry. Each tool implements the `BaseTool` interface. Agents select tools dynamically based on the `description` field, so precision there is important.

---

## Minimal Example

```python
# sovereign/tools/builtin/my_tool.py
from sovereign.tools.base_tool import BaseTool

class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "Fetches data from an external source given a search query."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The query to look up",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            query = params["query"]
            result = await self._fetch(query)
            return {"result": result, "error": None}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    async def _fetch(self, query: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.example.com", params={"q": query})
            resp.raise_for_status()
            return resp.text
```

---

## Registration

Register the tool in `sovereign/tools/tool_registry.py` inside `_register_builtins()`:

```python
from sovereign.tools.builtin.my_tool import MyTool

def _register_builtins(self) -> None:
    ...
    self.register(MyTool())
```

After restarting SOVEREIGN the tool is available to any agent that lists its `tool_id` in the `tools=` parameter of `_make_worker()`.

---

## `BaseTool` Interface

| Attribute / method | Type | Required | Description |
|---|---|---|---|
| `tool_id` | `str` | Yes | Unique identifier used in `tools=[...]` |
| `name` | `str` | Yes | Human-readable name |
| `description` | `str` | Yes | What the tool does — shown to the model for selection |
| `parameters_schema` | `dict` | Yes | JSON Schema for the input `params` dict |
| `requires_approval` | `bool` | No | If `True`, execution is gated by the ApprovalGate |
| `execute(params, context)` | `async` method | Yes | Main execution logic; must return `{"result": ..., "error": ...}` |

---

## Tool Schema Requirements

`parameters_schema` must be a valid JSON Schema `object`. Guidelines:

- Make each property `description` precise — the model uses it to decide whether to call your tool.
- List all required keys in the `required` array.
- Use `enum` for constrained string values (e.g., `"enum": ["asc", "desc"]`).

**Multi-parameter example:**

```python
parameters_schema = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query string",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results to return (1–20)",
            "default": 5,
        },
        "sort": {
            "type": "string",
            "enum": ["relevance", "date"],
            "description": "Result ordering",
            "default": "relevance",
        },
    },
    "required": ["query"],
}
```

---

## Safety Guidelines

- Never execute shell commands outside the `code_exec` tool's sandbox.
- Validate all external inputs at the tool boundary before using them.
- Always return `{"result": None, "error": "message"}` on failure — never raise from `execute()`.
- Set `requires_approval = True` for any tool that modifies data, sends messages, or makes purchases.
- Respect the `SOVEREIGN_DATA_DIR` environment variable when accessing files — do not hard-code paths.

---

## Builtin Tools Reference

| Tool ID | File | Description |
|---|---|---|
| `memory_tool` | `memory_tool.py` | Read/write/search across all 14 memory domains |
| `web_search` | `web_search.py` | DuckDuckGo search (no API key required) |
| `code_exec` | `code_exec.py` | Execute Python in a sandboxed subprocess |
| `file_ops` | `file_ops.py` | Read/write files in the data directory |
| `notes` | `notes.py` | Append/read personal notes |
| `calendar` | `calendar.py` | Read calendar events; create reminders |
| `bookmarks` | `bookmarks.py` | Add/search bookmarks |

---

## Testing Your Tool

```python
# tests/test_my_tool.py
import pytest
from sovereign.tools.builtin.my_tool import MyTool

@pytest.mark.asyncio
async def test_my_tool_success():
    tool = MyTool()
    result = await tool.execute({"query": "test"}, {})
    assert result["error"] is None
    assert result["result"] is not None

@pytest.mark.asyncio
async def test_my_tool_missing_required_param():
    tool = MyTool()
    result = await tool.execute({}, {})
    assert result["error"] is not None
```

Run with:

```bash
pytest tests/test_my_tool.py -v
```
