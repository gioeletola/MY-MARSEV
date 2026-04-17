"""Superpower pack: product management frameworks and execution."""

PACK = {
    "title": "Product Management Mastery",
    "version": "1.0",
    "sections": {
        "Product Discovery": [
            "Talk to customers weekly — 1 hour of user research beats 10 hours of debate",
            "Jobs to Be Done: what job is the customer hiring your product to do?",
            "Pain > Solution — find and validate the pain before building the solution",
            "Opportunity scoring = (importance + satisfaction gap) / feasibility",
            "Kano model: basic needs (must-have), performance (linear), delighters (surprise + delight)",
            "Problem framing: How might we [verb] [object] so that [outcome]?",
        ],
        "Prioritisation Frameworks": {
            "RICE": "Reach × Impact × Confidence / Effort — data-driven backlog ranking",
            "ICE": "Impact × Confidence × Ease — simpler version of RICE",
            "MoSCoW": "Must-have, Should-have, Could-have, Won't-have — for sprint planning",
            "Value vs Effort Matrix": "2x2 — prioritise high value, low effort first",
            "OKR alignment": "Feature must ladder up to a Key Result — if it doesn't, deprioritise",
        },
        "PRD Structure": [
            "1. Problem statement (1 sentence)",
            "2. User stories / Jobs to Be Done",
            "3. Success metrics (measurable)",
            "4. Non-goals (what we are NOT building)",
            "5. Design mockups / user flows",
            "6. Technical requirements",
            "7. Launch plan (A/B test, staged rollout, flags)",
            "8. Open questions and decisions needed",
        ],
        "Metrics Framework": {
            "North Star Metric": "The one metric that captures the value you deliver to users",
            "Input metrics": "Actions teams can directly influence (e.g. feature adoption)",
            "Output metrics": "Business outcomes (revenue, retention) — lagging indicators",
            "Guardrail metrics": "Metrics you must not harm (e.g. latency, churn)",
            "Activation rate": "% of users who reach the 'aha moment' within first session",
            "D7/D30 retention": "% of users still active after 7/30 days — best engagement signal",
        },
        "Execution": [
            "Ship weekly — slow release cycles kill product intuition and team morale",
            "Feature flags: enable safe incremental rollout; never big-bang release",
            "A/B testing: minimum 2 weeks, 95% confidence, pre-registered hypothesis",
            "Measure everything before and after launch — retrospective analysis is weak",
            "Kill features that underperform — simplicity compounds",
            "Post-launch retrospective: what would we do differently?",
        ],
    },
}
