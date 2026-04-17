"""
Calculator tool — safe mathematical expression evaluator.

Uses an AST node-visitor whitelist. Never calls eval() directly.
Permitted: numeric literals, +, -, *, /, **, //, %, unary -, unary +,
and the safe built-in functions: round, abs, min, max, int, float.
"""
from __future__ import annotations

import ast
import logging
import math
import operator
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe AST evaluator
# ---------------------------------------------------------------------------

_SAFE_BUILTINS: dict[str, Any] = {
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
}

_BINARY_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_UNARY_OPS: dict[type, Any] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class _SafeEvalVisitor(ast.NodeVisitor):
    """
    Recursively evaluate a parsed AST, allowing only safe numeric operations.

    Raises ValueError for any unsupported node type.
    """

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    # Python < 3.8 compatibility for Num nodes (already covers 3.8+ via Constant)
    def visit_Num(self, node: Any) -> Any:  # type: ignore[override]
        return node.n

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _BINARY_OPS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = self.visit(node.operand)
        return _UNARY_OPS[op_type](operand)

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed (e.g. round(x, 2))")
        func_name = node.func.id
        if func_name not in _SAFE_BUILTINS:
            raise ValueError(
                f"Function '{func_name}' is not allowed. "
                f"Permitted: {sorted(_SAFE_BUILTINS)}"
            )
        args = [self.visit(a) for a in node.args]
        if node.keywords:
            raise ValueError("Keyword arguments in function calls are not supported")
        return _SAFE_BUILTINS[func_name](*args)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def _safe_eval(expression: str) -> int | float:
    """
    Parse and evaluate a numeric expression safely.

    Raises ValueError if the expression is malformed or uses disallowed constructs.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in expression: {exc}") from exc

    result = _SafeEvalVisitor().visit(tree)

    if isinstance(result, complex):
        raise ValueError("Complex number results are not supported")
    if not isinstance(result, (int, float)):
        raise ValueError(f"Expression did not evaluate to a number: {type(result).__name__}")
    if math.isnan(result) or math.isinf(result):
        raise ValueError(f"Result is not finite: {result}")
    return result


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------


class CalculatorTool(BaseTool):
    """Safe mathematical expression evaluator using AST node visitor."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="calculator_tool",
            description="Safe mathematical calculations",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["calculate"],
                        "description": "Operation to perform. Currently only 'calculate' is supported.",
                    },
                    "expression": {
                        "type": "string",
                        "description": (
                            "Mathematical expression to evaluate, e.g. '2 ** 10', "
                            "'round(3.14159, 2)', 'abs(-42)', 'min(3, 7, 1)'. "
                            "Allowed operators: +, -, *, /, **, //, %. "
                            "Allowed functions: round, abs, min, max, int, float."
                        ),
                    },
                },
                "required": ["action", "expression"],
            },
        )

    async def execute(
        self,
        action: str,
        expression: str = "",
        **_: Any,
    ) -> Any:
        """Evaluate a mathematical expression and return the numeric result."""
        try:
            if action != "calculate":
                return {"error": f"Unknown action: {action}"}
            if not expression:
                return {"error": "expression is required for calculate"}
            numeric_result = _safe_eval(expression)
            logger.debug("CalculatorTool: %s = %s", expression, numeric_result)
            return {"result": numeric_result, "expression": expression}
        except ValueError as exc:
            return {"result": None, "error": str(exc)}
        except ZeroDivisionError:
            return {"result": None, "error": "Division by zero"}
        except OverflowError:
            return {"result": None, "error": "Arithmetic overflow — result too large"}
        except Exception as exc:
            logger.error("CalculatorTool unexpected error expression=%r: %s", expression, exc)
            return {"result": None, "error": str(exc)}
