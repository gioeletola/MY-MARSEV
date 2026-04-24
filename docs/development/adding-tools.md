# Adding Tools

Tools are callable capabilities exposed to agents via the tool registry.
Each tool implements the `BaseTool` interface.

## Minimal Example

```python
# sovereign/tools/builtin/my_tool.py
from sovereign.tools.base_tool import BaseTool

class MyTool(BaseTool):
    tool_id = "my_tool"
    name = "My Tool"
    description = "Fetches data from an external source."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The query to process",
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
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.example.com", params={"q": query})
            return resp.text
```

## Registration

Register in `sovereign/tools/tool_registry.py` inside `_register_builtins()`:

```python
from sovereign.tools.builtin.my_tool import MyTool

self.register(MyTool())
```

## Tool Schema Requirements

The `parameters_schema` must be a valid JSON Schema object. Agents receive this
schema when selecting tools. Make the `description` field precise — it directly
affects whether the model chooses your tool.

## Safety Guidelines

- Never execute shell commands without the `code_exec` tool's sandbox
- Validate all external inputs at the tool boundary
- Return `{"result": None, "error": "message"}` on failure — never raise
- Respect the `requires_approval` flag for destructive operations

## Testing Tools

```python
@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    result = await tool.execute({"query": "test"}, {})
    assert result["error"] is None
    assert result["result"] is not None
```
