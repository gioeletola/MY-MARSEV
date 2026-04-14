"""Operating mode: business."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class BusinessMode(BaseMode):
    """Business ops, communications, CRM, marketing, partnerships."""

    def __init__(self) -> None:
        super().__init__(
            name="business",
            description="Business ops, communications, CRM, marketing, partnerships",
            default_action_class=ActionClass.DRAFT,
            escalation_threshold=0.4,
            preferred_model="claude-sonnet-4-6",
        )
