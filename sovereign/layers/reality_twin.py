"""
Reality Twin Layer — living digital model of the user's current state.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/reality_twin.json")


@dataclass
class DomainState:
    """Snapshot of one life domain."""
    domain: str
    score: float          # 0.0 – 1.0 subjective health
    status: str           # "healthy" | "attention" | "critical"
    notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RealityTwinSnapshot:
    """Full twin snapshot."""
    session_id: str
    domains: dict[str, DomainState] = field(default_factory=dict)
    overall_score: float = 0.0
    last_calibration: str = ""
    version: int = 0


class RealityTwinLayer:
    """
    Maintains the user's digital twin.

    Stores domain-level health scores and notes.
    Persists to disk as JSON. Computes overall score as mean of domain scores.
    """

    DEFAULT_DOMAINS = [
        "health", "energy", "finance", "career", "relationships",
        "learning", "projects", "mindset", "environment", "legacy",
    ]

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._snapshot: RealityTwinSnapshot | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, session_id: str) -> RealityTwinSnapshot:
        """Load twin from disk (or create fresh)."""
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text("utf-8"))
                domains = {
                    k: DomainState(**v) for k, v in raw.get("domains", {}).items()
                }
                self._snapshot = RealityTwinSnapshot(
                    session_id=session_id,
                    domains=domains,
                    overall_score=raw.get("overall_score", 0.0),
                    last_calibration=raw.get("last_calibration", ""),
                    version=raw.get("version", 0),
                )
                logger.info("RealityTwin loaded %d domains", len(domains))
                return self._snapshot
            except Exception as exc:
                logger.warning("Could not load twin: %s", exc)

        self._snapshot = self._fresh(session_id)
        return self._snapshot

    def update_domain(self, domain: str, score: float, notes: str = "") -> None:
        """Update a single domain's health score."""
        if self._snapshot is None:
            raise RuntimeError("Call load() first")
        status = "healthy" if score >= 0.7 else ("attention" if score >= 0.4 else "critical")
        self._snapshot.domains[domain] = DomainState(
            domain=domain, score=score, status=status, notes=notes
        )
        self._recompute_overall()
        self._persist()

    def get_snapshot(self) -> dict[str, Any]:
        """Return twin snapshot as a plain dict."""
        if self._snapshot is None:
            return {}
        snap = asdict(self._snapshot)
        return snap

    def domains_needing_attention(self) -> list[DomainState]:
        """Return domains with status 'attention' or 'critical'."""
        if self._snapshot is None:
            return []
        return [d for d in self._snapshot.domains.values() if d.status != "healthy"]

    def calibrate(self) -> None:
        """Mark twin as freshly calibrated."""
        if self._snapshot:
            self._snapshot.last_calibration = datetime.now(timezone.utc).isoformat()
            self._snapshot.version += 1
            self._persist()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fresh(self, session_id: str) -> RealityTwinSnapshot:
        domains = {
            d: DomainState(domain=d, score=0.5, status="attention")
            for d in self.DEFAULT_DOMAINS
        }
        return RealityTwinSnapshot(
            session_id=session_id, domains=domains, overall_score=0.5
        )

    def _recompute_overall(self) -> None:
        if self._snapshot and self._snapshot.domains:
            scores = [d.score for d in self._snapshot.domains.values()]
            self._snapshot.overall_score = sum(scores) / len(scores)

    def _persist(self) -> None:
        if not self._snapshot:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(self._snapshot), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("RealityTwin persist failed: %s", exc)
