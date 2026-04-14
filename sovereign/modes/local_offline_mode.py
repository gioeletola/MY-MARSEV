"""Operating mode: local_offline."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class Local_offlineMode(BaseMode):
    """Offline-first with local memory and deferred sync."""

    def __init__(self) -> None:
        super().__init__(
            name="local_offline",
            description="Offline-first with local memory and deferred sync",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.7,
            preferred_model="claude-haiku-4-5-20251001",
        )
