"""Operating mode: silent — privacy-first, local-only, no logging, no cloud."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class SilentMode(BaseMode):
    """
    Maximum privacy mode. Routes all computation to local models.
    No API calls to external services. No logging. No data egress.
    Memory writes suspended during session (in-memory only).

    Use for: sensitive personal matters, confidential business, health data,
    legal strategy, anything not intended to leave the device.
    """

    def __init__(self) -> None:
        super().__init__(
            name="silent",
            description="Privacy-first — local model only, no logging, no cloud calls",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.9,
            preferred_model="claude-haiku-4-5-20251001",
            offline_capable=True,
            require_approval_for=["WRITE_DATA", "EXECUTE_ACTION", "send"],
        )

    NO_LOGGING = True
    NO_CLOUD = True
    NO_MEMORY_WRITES = True
    PRIVACY_LEVEL = "paranoid"

    ACTIVE_AGENTS = [
        "ceo_agent", "chief_of_staff", "personal_assistant", "diary_agent",
    ]

    SYSTEM_CONTEXT = (
        "You are operating in SILENT MODE. All data stays local. "
        "No external calls, no logging, no persistence. "
        "Be helpful but discreet. Do not reference external services."
    )
