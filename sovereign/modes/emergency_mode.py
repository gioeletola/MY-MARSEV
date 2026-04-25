"""Operating mode: emergency — life-safety situations, lockdown, immediate action."""
from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode


class EmergencyMode(BaseMode):
    """
    Life-safety emergency mode. Activates when the user signals a physical emergency,
    medical crisis, or immediate safety threat.

    Guardian agent locks down non-essential agents.
    Only safety-critical, offline-capable agents remain active.
    All decisions logged. Human review bypassed for life-safety actions only.

    Activate: python main.py --mode emergency
    """

    def __init__(self) -> None:
        super().__init__(
            name="emergency",
            description="Life-safety emergency — lockdown, immediate action, first responder protocol",
            default_action_class=ActionClass.EXECUTE,
            escalation_threshold=0.1,
            preferred_model="claude-haiku-4-5-20251001",
            offline_capable=True,
            require_approval_for=[],
        )

    LOCKDOWN_NON_ESSENTIAL = True
    BYPASS_APPROVAL_FOR_SAFETY = True
    ALERT_ALL_CHANNELS = True

    ACTIVE_AGENTS = [
        "guardian_agent", "incident_response", "emergency_contacts",
        "health_agent", "location_agent",
    ]

    EMERGENCY_CONTACTS: list[str] = []

    SYSTEM_CONTEXT = (
        "EMERGENCY MODE ACTIVE. This is a life-safety situation. "
        "Respond immediately with: 1) Immediate action steps. "
        "2) Emergency contacts to call. 3) Location/safety information. "
        "Be extremely brief and clear. No analysis paralysis."
    )
