"""Operating mode: study."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class StudyMode(BaseMode):
    """Learning, research assistance, second brain."""

    def __init__(self) -> None:
        super().__init__(
            name="study",
            description="Learning, research assistance, second brain",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.8,
            preferred_model="claude-sonnet-4-6",
        )
