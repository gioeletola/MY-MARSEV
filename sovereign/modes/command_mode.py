"""Operating mode: command."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class CommandMode(BaseMode):
    """Direct task execution and system management."""

    def __init__(self) -> None:
        super().__init__(
            name="command",
            description="Direct task execution and system management",
            default_action_class=ActionClass.EXECUTE,
            escalation_threshold=0.5,
            preferred_model="claude-sonnet-4-6",
        )
