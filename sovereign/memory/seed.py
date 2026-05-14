"""Memory seed — populates core domains on first run."""
from __future__ import annotations

import datetime
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sovereign.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)
_SEED_FLAG = "_seeded"


async def run_seed(memory: "MemoryManager") -> bool:
    """Write default entries into identity / operational / financial domains.

    Safe to call multiple times — skips if already seeded.
    Returns True when seed was applied for the first time.
    """
    if await memory.read("identity", _SEED_FLAG):
        return False

    now = datetime.datetime.utcnow().isoformat() + "Z"
    name  = os.getenv("SOVEREIGN_OWNER_NAME", "Owner")
    email = os.getenv("SOVEREIGN_OWNER_EMAIL", "")
    tz    = os.getenv("SOVEREIGN_TIMEZONE", "UTC")

    await memory.write("identity", "owner", {
        "name": name, "email": email, "timezone": tz,
        "language": os.getenv("SOVEREIGN_LANGUAGE", "en"),
        "created_at": now,
    })
    await memory.write("identity", "system", {
        "name": "SOVEREIGN AI OS", "version": "1.0",
        "mission": "Act as a personal AI operating system — proactive, precise, private.",
        "created_at": now,
    })
    await memory.write("identity", "preferences", {
        "default_mode": os.getenv("SOVEREIGN_DEFAULT_MODE", "command"),
        "voice_enabled": os.getenv("SOVEREIGN_VOICE", "false").lower() == "true",
        "morning_brief": os.getenv("SOVEREIGN_MORNING_BRIEF", "true").lower() == "true",
        "created_at": now,
    })
    await memory.write("operational", "working_hours", {
        "start": os.getenv("SOVEREIGN_WORK_START", "09:00"),
        "end":   os.getenv("SOVEREIGN_WORK_END",   "18:00"),
        "timezone": tz,
        "work_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "created_at": now,
    })
    await memory.write("project", "_welcome", {
        "title": "Welcome to SOVEREIGN",
        "description": "Your first project. Rename or delete via memory API.",
        "status": "active", "created_at": now,
    })
    await memory.write("financial", "preferences", {
        "currency": os.getenv("SOVEREIGN_CURRENCY", "USD"),
        "budget_alert_threshold": float(os.getenv("SOVEREIGN_BUDGET_ALERT", "10.0")),
        "created_at": now,
    })
    await memory.write("personal_constitution", "core_values", {
        "values": ["effectiveness", "clarity", "privacy", "ownership"],
        "guiding_principle": "Maximise signal, minimise noise.",
        "created_at": now,
    })
    await memory.write("identity", _SEED_FLAG, {"ts": now, "version": 1})
    logger.info("Memory seed applied for owner=%s", name)
    return True
