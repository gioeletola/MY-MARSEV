"""
Sovereign Exit Layer — continuity, succession, and graceful exit from any commitment.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/sovereign_exit.json")


@dataclass
class ExitReadinessItem:
    """A single exit-readiness checklist item."""
    item_id: str
    domain: str          # "business" | "finance" | "estate" | "knowledge" | "personal"
    description: str
    status: str          # "complete" | "in_progress" | "missing"
    priority: int        # 1 = critical
    notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SovereignExitLayer:
    """
    Maintains exit readiness across all life domains.

    Tracks: business exit documentation, estate planning, knowledge transfer,
    succession contacts, and emergency protocols.
    """

    DEFAULT_CHECKLIST: list[dict] = [
        {"item_id": "will", "domain": "estate", "description": "Will drafted and signed", "priority": 1},
        {"item_id": "poa", "domain": "estate", "description": "Power of Attorney in place", "priority": 1},
        {"item_id": "healthcare_directive", "domain": "estate", "description": "Healthcare directive signed", "priority": 1},
        {"item_id": "beneficiaries", "domain": "estate", "description": "All account beneficiaries named", "priority": 1},
        {"item_id": "business_docs", "domain": "business", "description": "Key business processes documented", "priority": 2},
        {"item_id": "succession_contact", "domain": "business", "description": "Succession contact identified", "priority": 2},
        {"item_id": "knowledge_runbook", "domain": "knowledge", "description": "Critical knowledge runbooks created", "priority": 2},
        {"item_id": "password_vault", "domain": "personal", "description": "Password vault access shared with trusted person", "priority": 1},
        {"item_id": "financial_summary", "domain": "finance", "description": "Complete financial summary document", "priority": 2},
        {"item_id": "insurance_summary", "domain": "finance", "description": "All insurance policies documented", "priority": 2},
    ]

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._items: dict[str, ExitReadinessItem] = {}
        self._load()

    # ------------------------------------------------------------------

    def update_item(self, item_id: str, status: str, notes: str = "") -> None:
        item = self._items.get(item_id)
        if item is None:
            logger.warning("SovereignExit: unknown item_id=%s", item_id)
            return
        item.status = status
        item.notes = notes
        item.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def readiness_score(self) -> float:
        """Weighted readiness score 0.0–1.0 (P1 items worth more)."""
        if not self._items:
            return 0.0
        total_weight = 0
        complete_weight = 0
        for item in self._items.values():
            w = 3 if item.priority == 1 else 1
            total_weight += w
            if item.status == "complete":
                complete_weight += w
        return complete_weight / total_weight if total_weight else 0.0

    def missing_critical(self) -> list[ExitReadinessItem]:
        return [
            i for i in self._items.values()
            if i.status != "complete" and i.priority == 1
        ]

    def by_domain(self, domain: str) -> list[ExitReadinessItem]:
        return [i for i in self._items.values() if i.domain == domain]

    def full_report(self) -> dict[str, Any]:
        return {
            "readiness_score": round(self.readiness_score(), 3),
            "missing_critical": [asdict(i) for i in self.missing_critical()],
            "items": {k: asdict(v) for k, v in self._items.items()},
        }

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text("utf-8"))
                for iid, data in raw.items():
                    self._items[iid] = ExitReadinessItem(**data)
                logger.info("SovereignExit loaded %d items", len(self._items))
                return
            except Exception as exc:
                logger.warning("SovereignExit load error: %s", exc)
        # Seed defaults
        for item_data in self.DEFAULT_CHECKLIST:
            item = ExitReadinessItem(
                item_id=item_data["item_id"],
                domain=item_data["domain"],
                description=item_data["description"],
                status="missing",
                priority=item_data["priority"],
            )
            self._items[item.item_id] = item
        self._persist()

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({k: asdict(v) for k, v in self._items.items()}, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("SovereignExit persist failed: %s", exc)
