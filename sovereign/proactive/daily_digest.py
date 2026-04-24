"""
Daily Digest — generates a morning briefing summary for the user.

Pulls from memory domains, decision ledger, goal monitor, and budget tracker.
Runs at the configured hour (default: 08:00 UTC) via SilentOps.
Optionally delivers via Telegram.
"""
from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_LEDGER_PATH = pathlib.Path("data/ledger/decisions.jsonl")


class DailyDigest:
    """
    Generates a daily summary report from all system data sources.

    Usage (standalone):
        digest = DailyDigest(orchestrator)
        report = await digest.generate()
        print(report.text)

    Usage (via SilentOps):
        Register as a SilentTask with interval_s=3600 and check
        the current UTC hour matches the configured digest_hour.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orch = orchestrator

    # ------------------------------------------------------------------

    async def generate(self) -> "DigestReport":
        """Collect all data sources and compile the daily digest."""
        now = datetime.now(timezone.utc)
        sections: list[str] = []

        sections.append(f"# SOVEREIGN Daily Digest — {now.strftime('%A, %d %B %Y')}")
        sections.append("")

        # 1. System health
        sections += self._section_health()

        # 2. Budget
        sections += self._section_budget()

        # 3. Goals
        sections += self._section_goals()

        # 4. Financial snapshot
        sections += await self._section_financial()

        # 5. Active projects
        sections += await self._section_projects()

        # 6. Yesterday's decisions
        sections += self._section_decisions()

        # 7. Pending approvals
        sections += self._section_approvals()

        text = "\n".join(sections)
        return DigestReport(text=text, generated_at=now.isoformat())

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _section_health(self) -> list[str]:
        lines = ["## System Health"]
        try:
            h = self._orch.health()
            status = h.get("overall", "?").upper()
            lines.append(f"Status: **{status}**")
            lines.append(f"Agents: {h.get('agents_registered', 0)} | Tools: {h.get('tools_registered', 0)}")
            ph = h.get("provider_health", {})
            healthy = [p for p, s in ph.items() if s.get("available")]
            lines.append(f"Healthy providers: {', '.join(healthy) or 'none'}")
        except Exception as exc:
            lines.append(f"_(health unavailable: {exc})_")
        return lines + [""]

    def _section_budget(self) -> list[str]:
        lines = ["## Budget"]
        try:
            budget = self._orch.get_budget_summary()
            d = budget.get("daily", {})
            m = budget.get("monthly", {})
            lines.append(f"Daily spent: ${d.get('spent_usd', 0):.4f} / limit ${d.get('limit_usd', 0):.2f}")
            lines.append(f"Monthly spent: ${m.get('spent_usd', 0):.4f} / limit ${m.get('limit_usd', 0):.2f}")
            top = budget.get("top_consumers", [])
            if top:
                lines.append("Top consumers: " + ", ".join(
                    f"{c.get('agent_id','?')} (${c.get('cost_usd', 0):.4f})" for c in top[:3]
                ))
        except Exception as exc:
            lines.append(f"_(budget unavailable: {exc})_")
        return lines + [""]

    def _section_goals(self) -> list[str]:
        lines = ["## Goals"]
        try:
            monitor = self._orch.goal_monitor
            active = monitor.active_goals()
            if not active:
                lines.append("No active goals.")
            else:
                for g in active[:5]:
                    bar = "█" * int(g.progress_pct / 10) + "░" * (10 - int(g.progress_pct / 10))
                    lines.append(f"- **{g.title}** [{bar}] {g.progress_pct:.0f}% — {g.status.value}")
                if len(active) > 5:
                    lines.append(f"  _(+{len(active)-5} more goals)_")
        except Exception as exc:
            lines.append(f"_(goals unavailable: {exc})_")
        return lines + [""]

    async def _section_financial(self) -> list[str]:
        lines = ["## Financial Snapshot"]
        try:
            from sovereign.memory.domains.financial import FinancialMemoryStore
            store = FinancialMemoryStore()
            summary = store.get_summary()
            lines.append(f"Net worth: ${summary.get('net_worth', 0):,.2f}")
            lines.append(f"Monthly cashflow: ${summary.get('monthly_cashflow', 0):,.2f}")
            lines.append(f"Portfolio: ${summary.get('portfolio_total', 0):,.2f}")
        except Exception as exc:
            lines.append(f"_(financial data unavailable: {exc})_")
        return lines + [""]

    async def _section_projects(self) -> list[str]:
        lines = ["## Active Projects"]
        try:
            from sovereign.memory.domains.project import ProjectMemoryStore
            store = ProjectMemoryStore()
            projects = store.get_projects(status="active")
            if not projects:
                lines.append("No active projects.")
            else:
                for p in projects[:5]:
                    prog = p.get("progress", 0)
                    bar = "█" * (prog // 10) + "░" * (10 - prog // 10)
                    lines.append(f"- **{p.get('name','?')}** [{bar}] {prog}%")
                if len(projects) > 5:
                    lines.append(f"  _(+{len(projects)-5} more projects)_")
        except Exception as exc:
            lines.append(f"_(projects unavailable: {exc})_")
        return lines + [""]

    def _section_decisions(self) -> list[str]:
        lines = ["## Yesterday's Decisions"]
        try:
            records = self._load_recent_decisions(n=10)
            if not records:
                lines.append("No decisions recorded.")
            else:
                for rec in records[-5:]:
                    agent = rec.get("agent_id", "?")
                    desc = rec.get("description", rec.get("outcome", ""))[:80]
                    lines.append(f"- [{agent}] {desc}")
        except Exception as exc:
            lines.append(f"_(decisions unavailable: {exc})_")
        return lines + [""]

    def _section_approvals(self) -> list[str]:
        lines = ["## Pending Approvals"]
        try:
            pending = self._orch.get_pending_escalations()
            if not pending:
                lines.append("No pending approvals. ✓")
            else:
                lines.append(f"⚠ **{len(pending)} pending**")
                for p in pending[:3]:
                    lines.append(f"- {p.get('event_id','?')[:8]}: {str(p.get('description',''))[:60]}")
        except Exception as exc:
            lines.append(f"_(approvals unavailable: {exc})_")
        return lines + [""]

    # ------------------------------------------------------------------

    def _load_recent_decisions(self, n: int = 10) -> list[dict]:
        records: list[dict] = []
        if not _LEDGER_PATH.exists():
            return records
        try:
            with _LEDGER_PATH.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        return records[-n:]


class DigestReport:
    """The result of a daily digest run."""

    def __init__(self, text: str, generated_at: str) -> None:
        self.text = text
        self.generated_at = generated_at

    def to_telegram(self) -> str:
        """Format for Telegram HTML (strip markdown headers)."""
        lines = []
        for line in self.text.split("\n"):
            if line.startswith("## "):
                lines.append(f"\n<b>{line[3:]}</b>")
            elif line.startswith("# "):
                lines.append(f"<b>{line[2:]}</b>")
            elif line.startswith("- **") and "**" in line[4:]:
                lines.append("• " + line[4:].replace("**", "<b>", 1).replace("**", "</b>", 1))
            else:
                lines.append(line)
        return "\n".join(lines)[:4096]   # Telegram message limit


def build_daily_digest_task(orchestrator: Any, digest_hour: int = 8):
    """
    Factory function that returns an async callback for use as a SilentTask.
    The callback checks the current UTC hour and fires once per day at digest_hour.
    """
    _last_run_date: list[str] = [""]

    async def _run():
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        if now.hour != digest_hour:
            return
        if _last_run_date[0] == today:
            return  # already ran today
        _last_run_date[0] = today
        logger.info("DailyDigest: generating for %s", today)
        try:
            digest = DailyDigest(orchestrator)
            report = await digest.generate()
            logger.info("DailyDigest: generated (%d chars)", len(report.text))
            # Optionally send via Telegram
            tg = getattr(orchestrator, "_telegram_bot", None)
            if tg is not None:
                try:
                    await tg.send_alert(report.to_telegram(), level="info")
                    logger.info("DailyDigest: sent via Telegram")
                except Exception as exc:
                    logger.warning("DailyDigest: Telegram send failed: %s", exc)
        except Exception as exc:
            logger.error("DailyDigest: generation failed: %s", exc)

    return _run
