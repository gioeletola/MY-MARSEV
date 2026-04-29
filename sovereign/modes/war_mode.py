"""Operating mode: war — crisis response, competitive battle, maximum urgency."""
from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode


class WarMode(BaseMode):
    """
    Maximum urgency mode for competitive crises, PR disasters, legal attacks,
    hostile takeovers, or business-critical emergencies requiring all-hands response.

    All agents run at full capacity. CEO has direct EXECUTE authority.
    Risk tolerance: LOW (every action logged, human review on financial ops).
    """

    def __init__(self) -> None:
        super().__init__(
            name="war",
            description="Maximum urgency — crisis, competitive battle, hostile situation",
            default_action_class=ActionClass.EXECUTE,
            escalation_threshold=0.3,
            preferred_model="claude-opus-4-7",
            offline_capable=False,
            require_approval_for=["MANAGE_FINANCE", "MANAGE_SECURITY", "external_comms"],
        )

    ACTIVE_AGENTS = [
        "ceo_agent", "guardian_agent", "legal_review", "crisis_manager",
        "security_sentinel", "incident_response", "pr_agent", "competitor_analyst",
        "financial_risk", "chief_of_staff",
    ]

    SYSTEM_CONTEXT = (
        "You are operating in WAR MODE. This is a critical situation requiring "
        "maximum urgency and precision. Every action is logged. Think in hours, not days. "
        "Be direct, decisive, and ruthless in analysis. No fluff."
    )

    ALERT_BANNER = "⚠ WAR MODE ACTIVE — All actions logged — Human review enforced on financial ops"
