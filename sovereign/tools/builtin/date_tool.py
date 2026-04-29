"""Date Tool — parse, format, diff, and manipulate dates without external deps."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class DateTool(BaseTool):
    """Parse, format, compare, and compute dates and durations."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="date_tool",
            description="Parse, format, and compute dates: current time, date arithmetic, diff between dates, business day checks.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["now", "parse", "format", "diff", "add", "weekday", "quarter", "iso_week"],
                        "description": "now|parse|format|diff|add|weekday|quarter|iso_week",
                    },
                    "date_str": {"type": "string", "description": "Date string (ISO 8601 preferred)"},
                    "date_str2": {"type": "string", "description": "Second date for diff"},
                    "fmt": {"type": "string", "description": "strftime format string"},
                    "days": {"type": "integer", "description": "Days to add (negative to subtract)"},
                    "weeks": {"type": "integer", "description": "Weeks to add"},
                    "months": {"type": "integer", "description": "Months to add (approximate)"},
                },
                "required": ["action"],
            },
        )

    _PARSE_FMTS = [
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y",
        "%d %B %Y", "%d %b %Y", "%B %d, %Y",
    ]

    async def execute(
        self,
        action: str,
        date_str: str = "",
        date_str2: str = "",
        fmt: str = "%Y-%m-%d",
        days: int = 0,
        weeks: int = 0,
        months: int = 0,
        **_: Any,
    ) -> Any:
        try:
            if action == "now":
                return self._now()
            if action == "parse":
                return self._parse(date_str)
            if action == "format":
                return self._format(date_str, fmt)
            if action == "diff":
                return self._diff(date_str, date_str2)
            if action == "add":
                return self._add(date_str, days, weeks, months)
            if action == "weekday":
                return self._weekday(date_str)
            if action == "quarter":
                return self._quarter(date_str)
            if action == "iso_week":
                return self._iso_week(date_str)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _now(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "result": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "iso_week": now.strftime("%Y-W%V"),
            "quarter": f"Q{(now.month - 1) // 3 + 1}",
            "timestamp": int(now.timestamp()),
            "error": None,
        }

    def _parse_dt(self, s: str) -> datetime:
        for fmt in self._PARSE_FMTS:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {s!r}")

    def _parse(self, s: str) -> dict:
        if not s:
            return {"result": None, "error": "date_str is required"}
        dt = self._parse_dt(s)
        return {
            "result": dt.isoformat(),
            "year": dt.year, "month": dt.month, "day": dt.day,
            "weekday": dt.strftime("%A"),
            "iso_week": dt.strftime("%Y-W%V"),
            "quarter": f"Q{(dt.month - 1) // 3 + 1}",
            "error": None,
        }

    def _format(self, s: str, fmt: str) -> dict:
        dt = self._parse_dt(s) if s else datetime.now(timezone.utc)
        return {"result": dt.strftime(fmt), "error": None}

    def _diff(self, s1: str, s2: str) -> dict:
        dt1 = self._parse_dt(s1)
        dt2 = self._parse_dt(s2)
        delta = dt2 - dt1
        total_days = delta.days
        return {
            "result": total_days,
            "days": abs(total_days),
            "weeks": abs(total_days) // 7,
            "months_approx": round(abs(total_days) / 30.44, 1),
            "years_approx": round(abs(total_days) / 365.25, 2),
            "earlier": s1 if total_days > 0 else s2,
            "later": s2 if total_days > 0 else s1,
            "error": None,
        }

    def _add(self, s: str, days: int, weeks: int, months: int) -> dict:
        dt = self._parse_dt(s) if s else datetime.now(timezone.utc)
        dt += timedelta(days=days, weeks=weeks)
        if months:
            month = dt.month + months
            year = dt.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            last_day = [0,31,28+int((year%4==0 and year%100!=0) or year%400==0),
                        31,30,31,30,31,31,30,31,30,31][month]
            dt = dt.replace(year=year, month=month, day=min(dt.day, last_day))
        return {"result": dt.strftime("%Y-%m-%d"), "iso": dt.isoformat(), "error": None}

    def _weekday(self, s: str) -> dict:
        dt = self._parse_dt(s) if s else datetime.now(timezone.utc)
        return {
            "result": dt.strftime("%A"),
            "weekday_num": dt.weekday(),
            "is_weekend": dt.weekday() >= 5,
            "error": None,
        }

    def _quarter(self, s: str) -> dict:
        dt = self._parse_dt(s) if s else datetime.now(timezone.utc)
        q = (dt.month - 1) // 3 + 1
        q_start = date(dt.year, (q - 1) * 3 + 1, 1)
        q_end_month = q * 3
        q_end_day = [0,31,28+int((dt.year%4==0 and dt.year%100!=0) or dt.year%400==0),
                     31,30,31,30,31,31,30,31,30,31][q_end_month]
        return {
            "result": f"Q{q} {dt.year}",
            "quarter": q,
            "year": dt.year,
            "start": str(q_start),
            "end": str(date(dt.year, q_end_month, q_end_day)),
            "error": None,
        }

    def _iso_week(self, s: str) -> dict:
        dt = self._parse_dt(s) if s else datetime.now(timezone.utc)
        iso = dt.isocalendar()
        return {
            "result": f"{iso[0]}-W{iso[1]:02d}",
            "year": iso[0], "week": iso[1], "weekday": iso[2],
            "error": None,
        }
