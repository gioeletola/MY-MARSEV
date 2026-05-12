"""Morning briefing generator — compiles a daily brief and optionally speaks it via TTS."""
from __future__ import annotations

import logging
import pathlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_brief_text(data: dict) -> str:
    lines = [f"SOVEREIGN MORNING BRIEF — {_now().strftime('%A %d %B %Y')}", ""]

    if data.get("mission"):
        lines += [f"Mission: {data['mission']}", ""]

    urgent = data.get("urgent_actions", [])
    if urgent:
        lines.append("TOP PRIORITIES")
        for a in urgent[:5]:
            lines.append(f"  • [{a.get('priority','').upper()}] {a.get('title','')}")
        lines.append("")

    overdue = data.get("overdue_actions", 0)
    if overdue:
        lines.append(f"Overdue actions: {overdue}")
        lines.append("")

    open_dec = data.get("open_decisions", [])
    if open_dec:
        lines.append("OPEN DECISIONS")
        for d in open_dec[:5]:
            lines.append(f"  • {d.get('title','')}")
        lines.append("")

    mood = data.get("mood_avg_7d")
    if mood is not None:
        lines.append(f"7-day mood average: {mood}/10")

    budget = data.get("budget", {})
    if budget:
        cost = budget.get("daily_cost_usd", 0)
        limit = budget.get("daily_limit_usd", 0)
        lines.append(f"Today's AI spend: ${cost:.4f} / ${limit:.2f}")

    approvals = data.get("pending_approvals", 0)
    if approvals:
        lines.append(f"Pending approvals: {approvals}")

    return "\n".join(lines)


async def generate_morning_brief(data: dict) -> str:
    """Build briefing text from a data dict (same shape as /api/brief returns)."""
    return _build_brief_text(data)


async def run_morning_brief(data: dict, speak: bool = True) -> str:
    """Generate the brief, optionally write an mp3 to data/morning_brief.mp3."""
    brief_text = await generate_morning_brief(data)

    if speak:
        try:
            from sovereign.hud.tts_engine import TTSEngine
            tts_engine = TTSEngine()
            if tts_engine.available:
                mp3_path = pathlib.Path("data/morning_brief.mp3")
                ok = await tts_engine.speak_to_file(brief_text, mp3_path)
                if ok:
                    logger.info("Morning brief audio saved to %s", mp3_path)
        except Exception as exc:
            logger.warning("Morning brief TTS failed: %s", exc)

    return brief_text
