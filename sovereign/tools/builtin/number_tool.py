"""Number Tool — math, formatting, unit conversion, statistics."""
from __future__ import annotations

import math
import statistics
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

_UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    "length": {
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "ft": 0.3048, "in": 0.0254, "yd": 0.9144, "mi": 1609.344,
    },
    "weight": {
        "kg": 1.0, "g": 0.001, "mg": 0.000001, "lb": 0.453592, "oz": 0.0283495, "t": 1000.0,
    },
    "temperature": {},  # handled specially
    "area": {
        "m2": 1.0, "km2": 1_000_000.0, "cm2": 0.0001, "ft2": 0.092903,
        "acre": 4046.86, "ha": 10000.0,
    },
    "speed": {
        "ms": 1.0, "kph": 0.277778, "mph": 0.44704, "knot": 0.514444,
    },
    "data": {
        "b": 1.0, "kb": 1024.0, "mb": 1_048_576.0, "gb": 1_073_741_824.0,
        "tb": 1_099_511_627_776.0,
    },
}


class NumberTool(BaseTool):
    """Math operations, number formatting, unit conversion, and statistics."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="number_tool",
            description="Math operations (floor/ceil/round/sqrt/log/pow), format numbers, convert units, compute statistics on lists.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["math", "format", "convert_unit", "stats", "percentage", "clamp"],
                        "description": "math|format|convert_unit|stats|percentage|clamp",
                    },
                    "value": {"type": "number", "description": "Primary numeric value"},
                    "values": {"type": "array", "description": "List of numbers for stats"},
                    "operation": {"type": "string", "description": "Math: floor|ceil|round|sqrt|log|log10|pow|abs|sign|factorial"},
                    "operand": {"type": "number", "description": "Second operand for pow/log"},
                    "decimals": {"type": "integer", "description": "Decimal places for round/format"},
                    "from_unit": {"type": "string", "description": "Source unit for convert_unit"},
                    "to_unit": {"type": "string", "description": "Target unit for convert_unit"},
                    "unit_type": {"type": "string", "description": "length|weight|area|speed|data"},
                    "part": {"type": "number", "description": "Part value for percentage"},
                    "total": {"type": "number", "description": "Total value for percentage"},
                    "min_val": {"type": "number", "description": "Min for clamp"},
                    "max_val": {"type": "number", "description": "Max for clamp"},
                    "locale_format": {"type": "string", "description": "Format style: decimal|currency|percent|scientific"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, value: float = 0.0, values: list | None = None,
        operation: str = "round", operand: float = 2.0, decimals: int = 2,
        from_unit: str = "", to_unit: str = "", unit_type: str = "length",
        part: float = 0.0, total: float = 100.0,
        min_val: float = 0.0, max_val: float = 100.0,
        locale_format: str = "decimal", **_: Any,
    ) -> Any:
        try:
            if action == "math":
                return self._math(value, operation, operand, decimals)
            if action == "format":
                return self._format(value, decimals, locale_format)
            if action == "convert_unit":
                return self._convert(value, from_unit, to_unit, unit_type)
            if action == "stats":
                return self._stats(values if values is not None else [value])
            if action == "percentage":
                return self._percentage(part, total, decimals)
            if action == "clamp":
                clamped = max(min_val, min(max_val, value))
                return {"result": clamped, "clamped": clamped != value, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _math(self, v: float, op: str, operand: float, decimals: int) -> dict:
        ops = {
            "floor": lambda x, _: math.floor(x),
            "ceil": lambda x, _: math.ceil(x),
            "round": lambda x, d: round(x, int(d)),
            "sqrt": lambda x, _: math.sqrt(x),
            "log": lambda x, b: math.log(x, b) if b != 0 else math.log(x),
            "log10": lambda x, _: math.log10(x),
            "pow": lambda x, b: math.pow(x, b),
            "abs": lambda x, _: abs(x),
            "sign": lambda x, _: (1 if x > 0 else (-1 if x < 0 else 0)),
            "factorial": lambda x, _: math.factorial(int(x)),
        }
        if op not in ops:
            return {"result": None, "error": f"Unknown operation: {op}"}
        result = ops[op](v, operand if op in ("log", "pow", "round") else decimals)
        return {"result": result, "operation": op, "error": None}

    def _format(self, v: float, decimals: int, style: str) -> dict:
        if style == "scientific":
            fmt = f"{v:.{decimals}e}"
        elif style == "percent":
            fmt = f"{v * 100:.{decimals}f}%"
        elif style == "currency":
            fmt = f"${v:,.{decimals}f}"
        else:
            fmt = f"{v:,.{decimals}f}"
        return {"result": fmt, "raw": v, "error": None}

    def _convert(self, v: float, from_u: str, to_u: str, utype: str) -> dict:
        if utype == "temperature":
            return self._convert_temp(v, from_u, to_u)
        table = _UNIT_CONVERSIONS.get(utype, {})
        if from_u not in table or to_u not in table:
            return {"result": None, "error": f"Unknown unit '{from_u}' or '{to_u}' in {utype}"}
        base = v * table[from_u]
        result = base / table[to_u]
        return {"result": round(result, 6), "from": f"{v} {from_u}", "to": f"{result:.6g} {to_u}", "error": None}

    def _convert_temp(self, v: float, from_u: str, to_u: str) -> dict:
        in_celsius = {"c": v, "f": (v - 32) * 5 / 9, "k": v - 273.15}.get(from_u.lower())
        if in_celsius is None:
            return {"result": None, "error": f"Unknown temperature unit: {from_u}"}
        out = {"c": in_celsius, "f": in_celsius * 9 / 5 + 32, "k": in_celsius + 273.15}.get(to_u.lower())
        if out is None:
            return {"result": None, "error": f"Unknown temperature unit: {to_u}"}
        return {"result": round(out, 4), "error": None}

    def _stats(self, vals: list) -> dict:
        nums = [float(x) for x in vals if isinstance(x, (int, float))]
        if not nums:
            return {"result": None, "error": "No numeric values provided"}
        return {
            "result": {
                "count": len(nums),
                "sum": round(sum(nums), 6),
                "mean": round(statistics.mean(nums), 6),
                "median": round(statistics.median(nums), 6),
                "mode": statistics.mode(nums) if len(set(nums)) < len(nums) else None,
                "stdev": round(statistics.stdev(nums), 6) if len(nums) > 1 else 0.0,
                "variance": round(statistics.variance(nums), 6) if len(nums) > 1 else 0.0,
                "min": min(nums),
                "max": max(nums),
                "range": max(nums) - min(nums),
            },
            "error": None,
        }

    def _percentage(self, part: float, total: float, decimals: int) -> dict:
        if total == 0:
            return {"result": None, "error": "Total cannot be zero"}
        pct = (part / total) * 100
        return {
            "result": round(pct, decimals),
            "formatted": f"{pct:.{decimals}f}%",
            "ratio": round(part / total, decimals + 2),
            "error": None,
        }
