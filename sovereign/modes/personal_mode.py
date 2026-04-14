"""Operating mode: personal."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class PersonalMode(BaseMode):
    """Personal assistant: diary, routines, social, concierge."""

    def __init__(self) -> None:
        super().__init__(
            name="personal",
            description="Personal assistant: diary, routines, social, concierge",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.6,
            preferred_model="claude-sonnet-4-6",
        )
