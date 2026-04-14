"""Operating mode: travel."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class TravelMode(BaseMode):
    """Travel planning, bookings, itineraries, logistics."""

    def __init__(self) -> None:
        super().__init__(
            name="travel",
            description="Travel planning, bookings, itineraries, logistics",
            default_action_class=ActionClass.DRAFT,
            escalation_threshold=0.5,
            preferred_model="claude-sonnet-4-6",
        )
