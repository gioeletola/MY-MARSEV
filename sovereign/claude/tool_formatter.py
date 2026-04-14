"""
Tool formatter — converts internal tool definitions to the Anthropic API format.
"""
from __future__ import annotations

from typing import Any


def tools_to_api(tool_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Validate and normalise a list of tool definitions for the Anthropic API.

    Each tool dict must have: name, description, input_schema.
    Returns a list ready to pass as the ``tools`` parameter to the API.
    """
    result: list[dict[str, Any]] = []
    for tool in tool_dicts:
        if not all(k in tool for k in ("name", "description", "input_schema")):
            raise ValueError(
                f"Tool dict missing required keys (name, description, input_schema): {tool}"
            )
        result.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
        )
    return result


def parse_tool_use_block(block: Any) -> tuple[str, str, dict[str, Any]]:
    """
    Parse a tool_use content block from a Claude API response.

    Returns:
        (tool_use_id, tool_name, tool_input)
    """
    return block.id, block.name, dict(block.input)


def make_tool_result_block(
    tool_use_id: str,
    content: Any,
    is_error: bool = False,
) -> dict[str, Any]:
    """
    Build a tool_result content block for the next user turn.

    Args:
        tool_use_id: The ``id`` from the tool_use block.
        content:     The result to return to Claude. Will be str-coerced.
        is_error:    If True, sets is_error=True so Claude knows the call failed.
    """
    block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": str(content),
    }
    if is_error:
        block["is_error"] = True
    return block
