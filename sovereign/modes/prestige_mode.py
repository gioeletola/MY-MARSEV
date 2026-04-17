"""Operating mode: prestige — ultra-high-quality output, executive-level polish."""
from sovereign.modes.base_mode import BaseMode
from sovereign.kernel.action_classes import ActionClass


class PrestigeMode(BaseMode):
    """
    Elite output quality mode. Every response uses Opus, multi-step reasoning,
    and is reviewed for tone/polish before delivery.

    Use for: board presentations, investor memos, public announcements,
    high-stakes negotiations, legacy documentation.

    Slower but exceptional quality. Confidence threshold: 0.92+.
    """

    def __init__(self) -> None:
        super().__init__(
            name="prestige",
            description="Ultra-high-quality output — board decks, investor memos, public statements",
            default_action_class=ActionClass.DRAFT,
            escalation_threshold=0.4,
            preferred_model="claude-opus-4-7",
            offline_capable=False,
            require_approval_for=["publish", "send", "EXECUTE_ACTION"],
        )

    ACTIVE_AGENTS = [
        "ceo_agent", "chief_of_staff", "presentation_agent", "business_writer",
        "legal_review", "brand_strategist", "financial_modeler",
    ]

    SYSTEM_CONTEXT = (
        "You are operating in PRESTIGE MODE. Every output must be executive-quality: "
        "precise, polished, authoritative. No filler. Use sophisticated vocabulary. "
        "Structure rigorously. This output may go to a board or investor audience."
    )

    MIN_CONFIDENCE = 0.92
