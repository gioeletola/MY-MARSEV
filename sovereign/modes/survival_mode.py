"""Operating mode: survival."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class SurvivalMode(BaseMode):
    """Emergency mode with minimal resources and offline packs."""

    def __init__(self) -> None:
        super().__init__(
            name="survival",
            description="Emergency mode with minimal resources and offline packs",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.9,
            preferred_model="claude-haiku-4-5-20251001",
        )
