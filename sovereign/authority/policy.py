"""Authority policy rules — governs autonomous vs. escalation decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sovereign.kernel.action_classes import ActionClass


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
