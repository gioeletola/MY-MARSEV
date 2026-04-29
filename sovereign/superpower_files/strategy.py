"""
Strategy superpower pack — frameworks for competitive positioning, planning, and execution.
"""
from __future__ import annotations

PACK = {
    "id": "strategy",
    "title": "Strategic Thinking & Execution",
    "version": "1.0",
    "sections": {
        "frameworks": {
            "Porter's Five Forces": {
                "forces": ["Competitive Rivalry", "Supplier Power", "Buyer Power",
                           "Threat of Substitution", "Threat of New Entry"],
                "use": "Assess industry attractiveness and competitive position",
            },
            "Blue Ocean": {
                "core": "Create uncontested market space by making competition irrelevant",
                "tools": ["Strategy Canvas", "ERRC Grid (Eliminate/Reduce/Raise/Create)"],
                "question": "What factors does the industry take for granted that should be eliminated?",
            },
            "Jobs to Be Done": {
                "core": "Customers hire products to do a job — focus on the job, not demographics",
                "application": "Interview: 'Walk me through the last time you tried to solve X'",
            },
            "OKR": {
                "structure": "Objective (qualitative, inspiring) + 3-5 Key Results (measurable, ambitious)",
                "cadence": "Annual O → Quarterly KRs → Weekly check-ins",
                "rule": "KRs should score 0.7 on average — if always 1.0, not ambitious enough",
            },
            "Second-Order Thinking": {
                "core": "What are the consequences of the consequences?",
                "process": ["Identify intended outcome", "List 2nd-order effects",
                            "List 3rd-order effects", "Choose action with best overall trajectory"],
            },
            "Inversion": {
                "core": "Think backward: what would guarantee failure? Avoid those things",
                "process": ["State the goal", "List all ways to fail", "Remove those failure modes"],
            },
        },
        "competitive_moats": {
            "types": [
                {"moat": "Network Effects", "example": "Marketplace, social platform", "strength": "Very High"},
                {"moat": "Switching Costs", "example": "ERP, CRM, banking", "strength": "High"},
                {"moat": "Cost Advantage", "example": "Scale manufacturing, commodity processing", "strength": "Medium"},
                {"moat": "Intangible Assets", "example": "Brand, patents, regulatory licenses", "strength": "High"},
                {"moat": "Efficient Scale", "example": "Utility with natural monopoly territory", "strength": "High"},
                {"moat": "Data Moat", "example": "AI trained on proprietary data", "strength": "Medium-High"},
            ],
        },
        "decision_frameworks": {
            "items": [
                {
                    "name": "Regret Minimisation",
                    "prompt": "At 80, will I regret NOT doing this?",
                    "use": "High-stakes, irreversible decisions",
                },
                {
                    "name": "Pre-mortem",
                    "prompt": "Imagine we failed — what went wrong?",
                    "use": "Before any major initiative",
                },
                {
                    "name": "10/10/10",
                    "prompt": "How will I feel about this in 10 minutes, 10 months, 10 years?",
                    "use": "Emotional decisions, avoiding short-termism",
                },
                {
                    "name": "Opportunity Cost",
                    "prompt": "What am I giving up to do this?",
                    "use": "Resource allocation, prioritisation",
                },
            ],
        },
        "execution_principles": {
            "items": [
                "Strategy without execution is hallucination",
                "Bottleneck first: find the constraint, fix it before everything else",
                "Default to action: bias toward trying, not perfecting",
                "80/20 ruthlessly: 20% of activities → 80% of outcomes",
                "Weekly reviews: strategy drifts without regular recalibration",
                "Single owner per initiative: committees don't execute",
                "Measure lag and lead indicators: lag shows results, leads predict them",
            ],
        },
    },
}


def get_pack() -> dict:
    return PACK


def framework_info(name: str) -> dict | None:
    return PACK["sections"]["frameworks"].get(name)


def moat_by_strength(min_strength: str = "High") -> list[dict]:
    order = {"Very High": 4, "High": 3, "Medium-High": 2, "Medium": 1}
    threshold = order.get(min_strength, 0)
    return [m for m in PACK["sections"]["competitive_moats"]["types"]
            if order.get(m["strength"], 0) >= threshold]
