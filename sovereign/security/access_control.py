"""
Access Control Layer — policy-based authorisation for SOVEREIGN AI OS.

Evaluation order:
  1. Explicit deny  (deny_agents list on matching policy)
  2. Explicit allow (allowed_roles / allowed_agents on matching policy)
  3. Default deny   (no matching allow policy found)

All decisions are written to an in-memory ring buffer (1 000 entries) and
policies are persisted to data/memory/access_policies.json.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_POLICY_PATH = Path("data/memory/access_policies.json")
_AUDIT_RING_SIZE = 1_000
_AUDIT_EXPORT_SIZE = 100


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class AccessPolicy:
    """Declarative authorisation rule for a resource."""

    policy_id: str
    resource: str
    allowed_roles: list[str] = field(default_factory=list)
    allowed_agents: list[str] = field(default_factory=list)
    deny_agents: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> AccessPolicy:
        return AccessPolicy(**d)


@dataclass
class AccessDecision:
    """Result of a single access check."""

    allowed: bool
    reason: str
    policy_id: str = ""


# ---------------------------------------------------------------------------
# Access Control Layer
# ---------------------------------------------------------------------------


class AccessControlLayer:
    """Evaluate access requests against registered policies.

    Decisions are logged in a ring buffer; policies survive restarts via
    JSON persistence.
    """

    def __init__(self, policy_path: Path = _POLICY_PATH) -> None:
        self._path = policy_path
        self._policies: dict[str, AccessPolicy] = {}   # policy_id -> policy
        self._audit: deque[dict] = deque(maxlen=_AUDIT_RING_SIZE)
        self._load()

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register_policy(self, policy: AccessPolicy) -> None:
        """Add or replace a policy."""
        self._policies[policy.policy_id] = policy
        self._save()
        logger.info("Policy registered: id=%s resource=%s", policy.policy_id, policy.resource)

    def list_policies(self) -> list[AccessPolicy]:
        """Return all registered policies."""
        return list(self._policies.values())

    # ------------------------------------------------------------------
    # Access check
    # ------------------------------------------------------------------

    def check(
        self,
        requester_id: str,
        resource: str,
        action: str,
        context: dict | None = None,
    ) -> AccessDecision:
        """Evaluate whether *requester_id* may perform *action* on *resource*.

        *context* may carry a ``role`` key used for role-based checks.
        """
        if context is None:
            context = {}

        requester_role: str = context.get("role", "")

        # Collect policies that match the requested resource (exact or prefix).
        matching = [
            p for p in self._policies.values()
            if resource == p.resource or resource.startswith(p.resource.rstrip("*"))
        ]

        decision: AccessDecision

        # --- Phase 1: explicit deny ----------------------------------------
        for policy in matching:
            if requester_id in policy.deny_agents:
                decision = AccessDecision(
                    allowed=False,
                    reason=f"Explicit deny for agent '{requester_id}' in policy '{policy.policy_id}'",
                    policy_id=policy.policy_id,
                )
                self._record_audit(requester_id, resource, action, decision)
                return decision

        # --- Phase 2: explicit allow ----------------------------------------
        for policy in matching:
            agent_allowed = requester_id in policy.allowed_agents
            role_allowed = bool(requester_role) and requester_role in policy.allowed_roles

            if agent_allowed or role_allowed:
                # Evaluate optional conditions.
                if policy.conditions and not self._evaluate_conditions(
                    policy.conditions, context
                ):
                    continue
                decision = AccessDecision(
                    allowed=True,
                    reason=(
                        f"Allowed by policy '{policy.policy_id}' "
                        f"({'agent' if agent_allowed else 'role'} match)"
                    ),
                    policy_id=policy.policy_id,
                )
                self._record_audit(requester_id, resource, action, decision)
                return decision

        # --- Phase 3: default deny ------------------------------------------
        decision = AccessDecision(
            allowed=False,
            reason=f"No matching allow policy for resource '{resource}' action '{action}'",
        )
        self._record_audit(requester_id, resource, action, decision)
        return decision

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def audit_log(self) -> list[dict]:
        """Return the last *_AUDIT_EXPORT_SIZE* access decisions."""
        entries = list(self._audit)
        return entries[-_AUDIT_EXPORT_SIZE:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_conditions(self, conditions: dict, context: dict) -> bool:
        """Check that every key in *conditions* matches the same key in *context*.

        Supports simple equality checks only; unknown condition keys pass.
        """
        for key, expected in conditions.items():
            actual = context.get(key)
            if actual is None:
                continue
            if actual != expected:
                return False
        return True

    def _record_audit(
        self, requester_id: str, resource: str, action: str, decision: AccessDecision
    ) -> None:
        """Append a decision to the ring-buffer audit log."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "requester_id": requester_id,
            "resource": resource,
            "action": action,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "policy_id": decision.policy_id,
        }
        self._audit.append(entry)
        logger.debug(
            "Access %s: requester=%s resource=%s action=%s reason=%s",
            "ALLOWED" if decision.allowed else "DENIED",
            requester_id,
            resource,
            action,
            decision.reason,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._policies = {
                pid: AccessPolicy.from_dict(p) for pid, p in data.items()
            }
        except Exception:
            logger.exception("Failed to load access policies; starting empty")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {pid: p.to_dict() for pid, p in self._policies.items()}
        self._path.write_text(json.dumps(payload, indent=2))
