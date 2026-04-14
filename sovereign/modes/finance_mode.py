"""Operating mode: finance."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class FinanceMode(BaseMode):
    """Financial analysis, budgeting, portfolio management."""

    def __init__(self) -> None:
        super().__init__(
            name="finance",
            description="Financial analysis, budgeting, portfolio management",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.2,
            preferred_model="claude-opus-4-6",
        )
