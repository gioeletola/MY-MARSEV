"""Operating mode: builder."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class BuilderMode(BaseMode):
    """Code generation, architecture, system building."""

    def __init__(self) -> None:
        super().__init__(
            name="builder",
            description="Code generation, architecture, system building",
            default_action_class=ActionClass.DRAFT,
            escalation_threshold=0.5,
            preferred_model="claude-sonnet-4-6",
        )
