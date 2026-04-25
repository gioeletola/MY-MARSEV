"""
Weekly Report Generator — compiles a life summary and sends it via Telegram.

Aggregates data from all memory domains to produce a Markdown report:
  - Financial snapshot
  - Projects & tasks
  - Health & training
  - Learning & skills
  - Decisions & decisions log
  - Red flags & constitution checks
  - Next actions
  - Personal version comparison

Delivery: Telegram Bot API or print to stdout if no token configured.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_week(dt: datetime | None = None) -> str:
    dt = dt or _now()
    return dt.strftime("%Y-W%V")


def build_weekly_report(data_dir: str = "data") -> str:
    """Build a Markdown weekly report string from all memory domains."""
    import pathlib
    base = pathlib.Path(data_dir)

    now = _now()
    week = _iso_week(now)
    date_str = now.strftime("%A %d %B %Y")

    lines: list[str] = [
        "# 📊 SOVEREIGN Weekly Report",
        f"**Week {week}** — {date_str}",
        "",
    ]

    # --- Finance ---
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        fin = FinancialMemoryStore(base / "memory" / "financial.json")
        snap = fin.snapshot()
        lines += [
            "## 💰 Finance",
            f"- Net worth: **€{snap.get('net_worth', 0):,.0f}**",
            f"- Cash: €{snap.get('cash', 0):,.0f}",
            f"- Income (30d): €{snap.get('income_30d', 0):,.0f}",
            f"- Expenses (30d): €{snap.get('expenses_30d', 0):,.0f}",
            "",
        ]
    except Exception as e:
        lines += [f"## 💰 Finance\n_(unavailable: {e})_\n"]

    # --- Projects ---
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        proj = ProjectMemoryStore(base / "memory" / "projects.json")
        active = proj.list_projects(status="active")
        lines += [
            "## 🗂 Projects",
            f"- Active projects: **{len(active)}**",
        ]
        for p in active[:5]:
            lines.append(f"  • {p.get('name', '?')} — {p.get('progress', 0):.0f}%")
        lines.append("")
    except Exception:
        pass

    # --- Next Actions ---
    try:
        from sovereign.memory.domains.next_action import NextActionStore
        na = NextActionStore(base / "memory" / "next_action.json")
        urgent = na.urgent()
        overdue = na.overdue()
        lines += [
            "## ⚡ Next Actions",
            f"- Pending: {len(na.pending())}",
            f"- Urgent: **{len(urgent)}**",
            f"- Overdue: {'⚠️ ' + str(len(overdue)) if overdue else '0'}",
        ]
        if urgent:
            for a in urgent[:3]:
                lines.append(f"  • {a.title}")
        lines.append("")
    except Exception:
        pass

    # --- Health ---
    try:
        from sovereign.memory.domains.health_routine import HealthRoutineMemoryStore
        hr = HealthRoutineMemoryStore(base / "memory" / "health_routine.json")
        profile = hr.get_profile()
        recent_weight = hr.recent_metrics("weight", n=1)
        lines += [
            "## 💪 Health & Training",
            f"- Fitness level: {profile.fitness_level}",
            f"- Active routines: {len(hr.active_routines())}",
        ]
        if recent_weight:
            lines.append(f"- Weight: {recent_weight[0].value} {recent_weight[0].unit}")
        lines.append("")
    except Exception:
        pass

    # --- Learning ---
    try:
        from sovereign.memory.domains.learning import LearningMemoryStore
        lrn = LearningMemoryStore(base / "memory" / "learning.json")
        in_progress = lrn.by_status("in_progress")
        skills = lrn.all_skills()
        lines += [
            "## 📚 Learning",
            f"- In progress: {', '.join(i.title for i in in_progress[:3]) or 'none'}",
            f"- Total skills tracked: {len(skills)}",
            "",
        ]
    except Exception:
        pass

    # --- Decisions ---
    try:
        from sovereign.memory.domains.decision import DecisionMemoryStore
        dec = DecisionMemoryStore(base / "memory" / "decision.json")
        open_dec = dec.by_status("open")
        review_dec = dec.pending_review()
        lines += [
            "## 🧭 Decisions",
            f"- Open: {len(open_dec)}",
            f"- Pending review: {len(review_dec)}",
        ]
        for d in open_dec[:3]:
            lines.append(f"  • {d.title}")
        lines.append("")
    except Exception:
        pass

    # --- Diary mood avg ---
    try:
        from sovereign.memory.domains.diary import DiaryMemoryStore
        diary = DiaryMemoryStore(base / "memory" / "diary.json")
        avg = diary.average_mood(7)
        recent = diary.recent(3)
        lines += [
            "## 📓 Diary",
            f"- Mood avg (7d): {avg:.1f}/10",
        ]
        if recent:
            lines.append(f"- Latest entry: {recent[0].date} — {recent[0].mood or '?'}")
        lines.append("")
    except Exception:
        pass

    # --- Personal Version ---
    try:
        from sovereign.memory.domains.personal_version import PersonalVersionStore
        pvs = PersonalVersionStore(base / "memory" / "personal_version.json")
        latest = pvs.latest()
        if latest:
            lines += [
                "## 🔄 Personal Version",
                f"- Current: {latest.version_label or latest.period}",
                f"- Overall rating: {latest.overall_rating}/10",
                f"- Net worth trend: {pvs.to_context_string()}",
                "",
            ]
    except Exception:
        pass

    # --- Red Flags ---
    try:
        from sovereign.memory.domains.personal_constitution import PersonalConstitutionStore
        pcs = PersonalConstitutionStore(base / "memory" / "personal_constitution.json")
        critical = pcs.red_flags_by_severity("critical")
        high = pcs.red_flags_by_severity("high")
        if critical or high:
            lines += [
                "## 🚩 Red Flags",
                f"- Critical: {len(critical)}",
                f"- High: {len(high)}",
            ]
            for f in critical[:3]:
                lines.append(f"  🔴 {f.title}")
            lines.append("")
    except Exception:
        pass

    lines.append(f"\n---\n_Generated by SOVEREIGN AI OS · {now.strftime('%H:%M UTC')}_")
    return "\n".join(lines)


async def send_telegram_report(
    report_text: str,
    token: str | None = None,
    chat_id: int | None = None,
) -> bool:
    """Send the report to a Telegram chat. Returns True on success."""
    bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id = chat_id or int(os.getenv("TELEGRAM_REPORT_CHAT_ID", "0"))

    if not bot_token or not tg_chat_id:
        logger.warning(
            "Telegram report: no TELEGRAM_BOT_TOKEN or TELEGRAM_REPORT_CHAT_ID set — "
            "printing to stdout instead."
        )
        print(report_text)
        return False

    try:
        import httpx
        # Telegram messages max 4096 chars; split if needed
        chunks = [report_text[i:i + 4000] for i in range(0, len(report_text), 4000)]
        async with httpx.AsyncClient(timeout=15.0) as client:
            for chunk in chunks:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": tg_chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                    },
                )
                if not resp.json().get("ok"):
                    logger.error("Telegram send failed: %s", resp.text[:200])
                    return False
        logger.info("Weekly report sent to Telegram chat_id=%d", tg_chat_id)
        return True
    except Exception as exc:
        logger.error("Telegram report error: %s", exc)
        return False


async def run_weekly_report(data_dir: str = "data") -> str:
    """Build + send weekly report. Returns the report text."""
    report = build_weekly_report(data_dir)
    await send_telegram_report(report)
    return report
