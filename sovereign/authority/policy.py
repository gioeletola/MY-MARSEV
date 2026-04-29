"""Authority policy rules — governs autonomous vs. escalation decisions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from sovereign.kernel.action_classes import ActionClass

logger = logging.getLogger(__name__)


@dataclass
class AuthorityPolicy:
    """
    Policy that determines whether a given action can proceed autonomously.

    Evaluated by the GuardianAgent before any EXECUTE-class action.
    """

    allowed_action_classes: set[ActionClass]
    blocked_domains: set[str]                   # Memory domains the agent cannot write
    max_financial_threshold: float = 0.0        # 0 = no financial actions without approval
    allow_external_apis: bool = False
    allow_file_delete: bool = False

    def is_permitted(self, context: dict[str, Any]) -> tuple[bool, str]:
        """
        Evaluate whether an action described by context is permitted.

        Returns (permitted: bool, reason: str).
        """
        action_class_str = context.get("action_class", "READ")
        try:
            ac = ActionClass.from_str(action_class_str)
        except ValueError:
            return False, f"Unknown action class: {action_class_str}"

        if ac not in self.allowed_action_classes:
            return False, (
                f"Action class '{ac.name}' not in allowed classes: "
                f"{[a.name for a in self.allowed_action_classes]}"
            )

        domain = context.get("memory_domain", "")
        if domain and domain in self.blocked_domains:
            return False, f"Memory domain '{domain}' is blocked by policy."

        if context.get("is_external_api") and not self.allow_external_apis:
            return False, "External API calls not permitted by policy."

        if context.get("is_file_delete") and not self.allow_file_delete:
            return False, "File deletion not permitted by policy."

        return True, "Permitted by policy."

    @classmethod
    def default_suggest(cls) -> AuthorityPolicy:
        """Safe default — allows only up to SUGGEST."""
        return cls(
            allowed_action_classes={ActionClass.READ, ActionClass.SUGGEST},
            blocked_domains={"financial", "legal_compliance"},
        )

    @classmethod
    def default_execute(cls) -> AuthorityPolicy:
        """Permissive — allows EXECUTE. Use in command mode with human oversight."""
        return cls(
            allowed_action_classes=set(ActionClass),
            blocked_domains=set(),
            allow_external_apis=True,
        )


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """Result of a PolicyEngine.evaluate() call."""

    allowed: bool
    reason: str
    policy_id: str
    severity: str = "low"       # low | medium | high | critical


# ---------------------------------------------------------------------------
# Built-in policy functions
# ---------------------------------------------------------------------------

def _no_destructive_in_production(
    action: str, context: dict, user_id: str
) -> PolicyDecision | None:
    """Block DELETE/EXECUTE destructive operations in production environment."""
    env = context.get("environment", "")
    if env == "production" and action.lower() in ("delete", "drop", "truncate", "destroy"):
        return PolicyDecision(
            allowed=False,
            reason="Destructive actions are blocked in production environment.",
            policy_id="no_destructive_in_production",
            severity="critical",
        )
    return None


def _financial_limit_1000(
    action: str, context: dict, user_id: str
) -> PolicyDecision | None:
    """Deny financial operations above $1000."""
    if action.lower() in ("payment", "transfer", "invest", "withdraw", "financial_op"):
        amount = context.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > 1000:
            return PolicyDecision(
                allowed=False,
                reason=f"Financial operation of {amount} exceeds the $1000 limit.",
                policy_id="financial_limit_1000",
                severity="high",
            )
    return None


def _read_only_guests(
    action: str, context: dict, user_id: str
) -> PolicyDecision | None:
    """Guest users may only perform read operations."""
    guest_users = context.get("guest_users", set())
    if user_id in guest_users or context.get("role") == "guest":
        if action.lower() not in ("read", "list", "get", "view", "search", "query"):
            return PolicyDecision(
                allowed=False,
                reason=f"Guest user '{user_id}' may only perform read operations.",
                policy_id="read_only_guests",
                severity="medium",
            )
    return None


def _block_external_in_offline_mode(
    action: str, context: dict, user_id: str
) -> PolicyDecision | None:
    """Block all external API calls when mode is local_offline."""
    operating_mode = context.get("mode", "")
    if operating_mode == "local_offline" and context.get("is_external_api"):
        return PolicyDecision(
            allowed=False,
            reason="External API calls are blocked in local_offline mode.",
            policy_id="block_external_in_offline_mode",
            severity="medium",
        )
    return None


def _require_2fa_sensitive(
    action: str, context: dict, user_id: str
) -> PolicyDecision | None:
    """Require 2FA for sensitive actions (finance, delete, admin)."""
    sensitive_actions = ("payment", "transfer", "withdraw", "delete", "admin_op")
    if action.lower() in sensitive_actions and not context.get("two_fa_verified", False):
        return PolicyDecision(
            allowed=False,
            reason=f"Action '{action}' requires two-factor authentication.",
            policy_id="require_2fa_sensitive",
            severity="high",
        )
    return None


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

_BUILTIN_POLICIES: list[tuple[str, Callable]] = [
    ("no_destructive_in_production", _no_destructive_in_production),
    ("financial_limit_1000", _financial_limit_1000),
    ("read_only_guests", _read_only_guests),
    ("block_external_in_offline_mode", _block_external_in_offline_mode),
    ("require_2fa_sensitive", _require_2fa_sensitive),
]


@dataclass
class PolicyEngine:
    """Evaluates a sequence of policy functions against an (action, context, user_id) triple.

    Usage::

        engine = PolicyEngine()
        decision = engine.evaluate("payment", {"amount": 5000}, "alice")
        if not decision.allowed:
            raise PermissionError(decision.reason)
    """

    _policies: list[tuple[str, Callable]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        # Register built-in policies on construction
        self._policies = list(_BUILTIN_POLICIES)

    def add_policy(self, policy_id: str, fn: Callable[[str, dict, str], PolicyDecision | None]) -> None:
        """Register a custom policy function.

        fn(action, context, user_id) must return a PolicyDecision (deny) or None (pass).
        """
        # Remove existing policy with same ID before re-adding
        self._policies = [(pid, f) for pid, f in self._policies if pid != policy_id]
        self._policies.append((policy_id, fn))
        logger.debug("PolicyEngine: registered policy '%s'", policy_id)

    def evaluate(self, action: str, context: dict, user_id: str = "unknown") -> PolicyDecision:
        """Run all policies in order.  First denial wins.  Returns allow-all if none deny."""
        for policy_id, fn in self._policies:
            try:
                result = fn(action, context, user_id)
                if result is not None:
                    logger.debug(
                        "PolicyEngine: policy '%s' returned %s for action '%s'",
                        policy_id, "DENY" if not result.allowed else "ALLOW", action,
                    )
                    return result
            except Exception as exc:
                logger.warning("PolicyEngine: policy '%s' raised %s", policy_id, exc)

        return PolicyDecision(
            allowed=True,
            reason="No policy denied this action.",
            policy_id="default_allow",
            severity="low",
        )

    def list_policies(self) -> list[str]:
        """Return IDs of all registered policies."""
        return [pid for pid, _ in self._policies]
