"""
Psychology superpower pack — cognitive biases, influence, persuasion, behavioural science.

Provides structured knowledge for AI agents to understand and apply psychological principles
in negotiation, sales, product design, leadership, and decision-making.
"""
from __future__ import annotations

PACK = {
    "id": "psychology",
    "title": "Psychology & Influence",
    "version": "1.0",
    "sections": {
        "cognitive_biases": {
            "description": "Core cognitive biases that shape human decisions",
            "items": [
                {
                    "name": "Anchoring",
                    "definition": "Over-relying on the first piece of information encountered",
                    "application": "Set the first number in any negotiation; price anchoring in sales",
                    "counter": "Gather independent data before hearing the other side's number",
                },
                {
                    "name": "Loss Aversion",
                    "definition": "Losses feel ~2x more painful than equivalent gains feel good",
                    "application": "Frame offers as avoiding loss, not gaining something",
                    "counter": "Reframe decisions around opportunity cost of inaction",
                },
                {
                    "name": "Social Proof",
                    "definition": "People follow what others do, especially in uncertainty",
                    "application": "Show customer counts, testimonials, case studies prominently",
                    "counter": "Question: are those people in the same situation as me?",
                },
                {
                    "name": "Scarcity",
                    "definition": "Perceived limited availability increases desire",
                    "application": "Limited-time offers, limited seats, waitlists",
                    "counter": "Ask: is this scarcity real or manufactured?",
                },
                {
                    "name": "Reciprocity",
                    "definition": "People feel obligated to return favours",
                    "application": "Give value first (content, gifts, help) before asking",
                    "counter": "Recognise uninvited gifts as influence tactics",
                },
                {
                    "name": "Commitment & Consistency",
                    "definition": "People align behaviour with prior commitments",
                    "application": "Get small yeses before asking for big ones (foot-in-door)",
                    "counter": "Ask: would I make this decision without my prior commitment?",
                },
                {
                    "name": "Confirmation Bias",
                    "definition": "Seeking information that confirms existing beliefs",
                    "application": "Understand opponent's worldview; speak their language",
                    "counter": "Actively seek disconfirming evidence before deciding",
                },
                {
                    "name": "Availability Heuristic",
                    "definition": "Overweighting recent/vivid events in probability estimates",
                    "application": "Use vivid examples and stories to make risks feel real",
                    "counter": "Use base rates and statistics, not anecdotes",
                },
                {
                    "name": "Dunning-Kruger Effect",
                    "definition": "Low-skill people overestimate competence; experts underestimate",
                    "application": "Identify where people are on the curve to calibrate communication",
                    "counter": "Continuous learning; seek expert feedback",
                },
                {
                    "name": "Sunk Cost Fallacy",
                    "definition": "Continuing because of past investment, not future value",
                    "application": "Recognise when targets are trapped by sunk costs",
                    "counter": "Evaluate only future costs and benefits; ignore what's already spent",
                },
            ],
        },
        "influence_frameworks": {
            "description": "Structured approaches to ethical influence and persuasion",
            "items": [
                {
                    "name": "Cialdini's 7 Principles",
                    "principles": ["Reciprocity", "Commitment", "Social Proof", "Authority",
                                   "Liking", "Scarcity", "Unity"],
                    "note": "Stack multiple principles for compound effect",
                },
                {
                    "name": "AIDA Model",
                    "stages": ["Attention", "Interest", "Desire", "Action"],
                    "application": "Structure any communication: hook → engage → create want → CTA",
                },
                {
                    "name": "SCARF Model (NeuroLeadership)",
                    "dimensions": ["Status", "Certainty", "Autonomy", "Relatedness", "Fairness"],
                    "application": "Protect these dimensions when leading or persuading",
                },
            ],
        },
        "reading_people": {
            "description": "Signals and patterns for understanding intent and state",
            "items": [
                "Baseline first: establish normal behaviour before looking for deviations",
                "Clusters matter: one signal means nothing; look for 3+ congruent signals",
                "Stress signals: hesitation, over-explanation, self-touching, pitch changes",
                "Confidence signals: open posture, eye contact, slow speech, direct answers",
                "Buying signals: leaning in, future-tense language, ROI questions, reference checking",
                "Resistance signals: crossed arms, deflecting questions, 'we'll think about it'",
            ],
        },
        "dark_patterns_to_avoid": {
            "description": "Manipulative tactics — know them to recognise and resist them",
            "items": [
                "False scarcity / urgency ('last one!', 'offer expires now')",
                "Bait and switch: promise X, deliver Y",
                "Roach motel: easy in, hard to cancel",
                "Confirmshaming: 'No thanks, I love wasting money'",
                "Hidden costs revealed late in funnel",
                "Manufactured social proof (fake reviews, inflated numbers)",
            ],
        },
    },
    "quick_reference": {
        "before_negotiation": [
            "Anchor first with a confident number",
            "Research their BATNA (Best Alternative To Negotiated Agreement)",
            "Find their loss-aversion pressure points",
            "Build rapport to activate liking principle",
        ],
        "before_sales_call": [
            "Prepare social proof relevant to their industry",
            "Have a clear scarcity element (genuine)",
            "Plan small commitment asks to build consistency",
            "Lead with value / gift before pitching",
        ],
        "self_defence": [
            "Pause before responding to urgency pressure",
            "Sleep on any large decision — scarcity fades",
            "Check base rates, not just vivid examples",
            "Separate sunk costs from future value",
        ],
    },
}


def get_pack() -> dict:
    return PACK


def biases_list() -> list[str]:
    return [b["name"] for b in PACK["sections"]["cognitive_biases"]["items"]]


def bias_info(name: str) -> dict | None:
    for b in PACK["sections"]["cognitive_biases"]["items"]:
        if b["name"].lower() == name.lower():
            return b
    return None


def quick_ref(context: str) -> list[str]:
    return PACK["quick_reference"].get(context, [])
