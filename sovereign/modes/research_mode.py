"""Operating mode: research."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class ResearchMode(BaseMode):
    """Deep research, synthesis, analysis, citations."""

    def __init__(self) -> None:
        super().__init__(
            name="research",
            description="Deep research, synthesis, analysis, citations",
            default_action_class=ActionClass.DRAFT,
            escalation_threshold=0.6,
            preferred_model="claude-opus-4-6",
        )
