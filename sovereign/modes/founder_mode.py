"""Operating mode: founder — startup execution, fundraising, GTM, rapid iteration."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class FounderMode(BaseMode):
    """
    Startup-optimised mode. Prioritises speed, execution, and investor-facing output.
    Agents focus on: pitch decks, GTM, metrics, fundraising, hiring, product.
    Escalation threshold raised — moves fast, approves quickly.
    """

    def __init__(self) -> None:
        super().__init__(
            name="founder",
            description="Startup execution — pitch, GTM, fundraising, product, rapid iteration",
            default_action_class=ActionClass.EXECUTE,
            escalation_threshold=0.75,
            preferred_model="claude-sonnet-4-6",
            offline_capable=False,
            require_approval_for=["MANAGE_FINANCE", "legal_review"],
        )

    ACTIVE_AGENTS = [
        "ceo_agent", "chief_of_staff", "business_strategy", "marketing_strategist",
        "investor_relations", "product_manager", "hiring_agent", "pitch_writer",
        "financial_modeler", "growth_hacker", "competitor_analyst",
    ]

    SYSTEM_CONTEXT = (
        "You are operating in FOUNDER MODE. The user is building a startup. "
        "Prioritise speed-to-market, investor narratives, and measurable traction. "
        "Be decisive. Avoid analysis paralysis. Suggest bold moves."
    )
