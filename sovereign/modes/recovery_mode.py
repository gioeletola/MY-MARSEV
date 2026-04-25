"""Operating mode: recovery — post-crisis stabilisation, health, resilience rebuild."""
from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode


class RecoveryMode(BaseMode):
    """
    Post-crisis recovery mode. Focuses on stabilising systems, rebuilding confidence,
    restoring routines, and conducting post-mortems.

    Lower urgency than war mode. Thoughtful, structured, forward-looking.
    Agents: health, diary, financial recovery, systems review, legal cleanup.
    """

    def __init__(self) -> None:
        super().__init__(
            name="recovery",
            description="Post-crisis stabilisation — health, finances, systems, confidence rebuild",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.7,
            preferred_model="claude-sonnet-4-6",
            offline_capable=False,
            require_approval_for=["MANAGE_FINANCE", "EXECUTE_ACTION"],
        )

    ACTIVE_AGENTS = [
        "ceo_agent", "chief_of_staff", "health_coach", "diary_agent",
        "cashflow_analyst", "legal_review", "incident_response",
        "resilience_agent", "financial_risk", "scenario_finance",
    ]

    SYSTEM_CONTEXT = (
        "You are operating in RECOVERY MODE. The user is stabilising after a difficult period. "
        "Be supportive, structured, and forward-looking. Focus on: what went wrong (post-mortem), "
        "immediate stabilisation steps, health metrics, financial recovery path, and rebuilt routines. "
        "Avoid overwhelming the user — prioritise ruthlessly."
    )
