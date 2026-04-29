"""
Sales superpower pack — frameworks, scripts, and playbooks for closing deals.
"""
from __future__ import annotations

PACK = {
    "id": "sales",
    "title": "Sales & Closing",
    "version": "1.0",
    "sections": {
        "discovery_framework": {
            "description": "SPIN Selling questions to uncover genuine need",
            "types": {
                "Situation": "Understand current state — 'What does your current process look like?'",
                "Problem": "Surface pain — 'What challenges does that create?'",
                "Implication": "Amplify impact — 'What happens if this isn't solved in Q1?'",
                "Need-payoff": "Get them to articulate value — 'How valuable would it be if...'",
            },
        },
        "objection_handling": {
            "description": "Common objections and proven responses",
            "objections": [
                {
                    "objection": "It's too expensive",
                    "reframe": "What's the cost of NOT solving this for another 12 months?",
                    "technique": "ROI reframe + loss aversion",
                },
                {
                    "objection": "We need to think about it",
                    "reframe": "Of course. What specific information would help you decide?",
                    "technique": "Isolate true objection",
                },
                {
                    "objection": "We're happy with our current solution",
                    "reframe": "That's great. What would make you even happier?",
                    "technique": "Gap identification",
                },
                {
                    "objection": "Send me more information",
                    "reframe": "Happy to. What specifically would be most useful — pricing, case studies, or technical specs?",
                    "technique": "Qualify intent, avoid dump-and-chase",
                },
                {
                    "objection": "We don't have budget",
                    "reframe": "If budget weren't a constraint, is this something you'd move forward with?",
                    "technique": "Isolate: budget objection vs real objection",
                },
                {
                    "objection": "Your competitor is cheaper",
                    "reframe": "Cost is one factor. What's your decision criteria beyond price?",
                    "technique": "Shift to value, expose TCO difference",
                },
            ],
        },
        "closing_techniques": {
            "items": [
                {
                    "name": "Assumptive Close",
                    "script": "When would you like to get started — this week or next?",
                    "use_when": "Strong buying signals, warm prospect",
                },
                {
                    "name": "Summary Close",
                    "script": "So we have X, Y, Z — that solves A, B, C for you. Shall we move forward?",
                    "use_when": "Long complex deal, multiple stakeholders",
                },
                {
                    "name": "Trial Close",
                    "script": "If we can solve [specific concern], is there any reason we couldn't proceed?",
                    "use_when": "One remaining objection to isolate",
                },
                {
                    "name": "Urgency Close",
                    "script": "Our Q4 pricing ends Friday — I'd hate for you to pay more for the same outcome",
                    "use_when": "Genuine urgency, not manufactured",
                },
                {
                    "name": "Puppy Dog Close",
                    "script": "Why don't you try it for 14 days, no commitment — you'll see the value firsthand",
                    "use_when": "Low-friction trial available",
                },
            ],
        },
        "pipeline_management": {
            "stages": [
                {"stage": "Prospecting", "criteria": "ICP match identified", "conversion_benchmark": "10-20%"},
                {"stage": "Discovery", "criteria": "Pain confirmed, budget exists", "conversion_benchmark": "30-50%"},
                {"stage": "Proposal", "criteria": "Decision criteria known, stakeholders mapped", "conversion_benchmark": "50-70%"},
                {"stage": "Negotiation", "criteria": "Verbal commitment, terms discussion", "conversion_benchmark": "70-85%"},
                {"stage": "Closed Won", "criteria": "Contract signed", "conversion_benchmark": "100%"},
            ],
            "velocity_formula": "Revenue = Deals × ACV × Win_Rate / Sales_Cycle_Days × 365",
        },
        "account_expansion": {
            "description": "Expand revenue within existing accounts",
            "tactics": [
                "QBRs (Quarterly Business Reviews) to surface new pain",
                "Champion-building: create multiple internal advocates",
                "Usage-based expansion triggers",
                "Cross-sell timing: post-success milestone",
                "Upsell: present at renewal + 60 days before",
            ],
        },
    },
    "metrics": {
        "key_ratios": {
            "LTV_CAC": "Target >3x; measure by cohort",
            "magic_number": "(New ARR / Sales + Marketing Spend) — target >0.75",
            "payback_period": "Target <18 months for SaaS",
            "win_rate": "Benchmark: 20-30% from qualified pipeline",
        },
    },
}


def get_pack() -> dict:
    return PACK


def handle_objection(objection_keyword: str) -> dict | None:
    keyword = objection_keyword.lower()
    for obj in PACK["sections"]["objection_handling"]["objections"]:
        if any(w in obj["objection"].lower() for w in keyword.split()):
            return obj
    return None


def closing_script(technique_name: str) -> str | None:
    for t in PACK["sections"]["closing_techniques"]["items"]:
        if t["name"].lower() == technique_name.lower():
            return t["script"]
    return None
