"""
Productivity superpower pack — systems, methods, and tactics for extreme output.
"""
from __future__ import annotations

PACK = {
    "id": "productivity",
    "title": "Productivity & Systems",
    "version": "1.0",
    "sections": {
        "systems": {
            "GTD": {
                "name": "Getting Things Done (David Allen)",
                "steps": ["Capture everything", "Clarify (is it actionable?)", "Organise by context",
                          "Review weekly", "Engage — just do it"],
                "key_insight": "Your brain is for having ideas, not storing them",
            },
            "Time Blocking": {
                "name": "Time Blocking",
                "steps": ["Categorise tasks (deep / shallow / admin)", "Block deep work in peak energy",
                          "Protect blocks like meetings", "Leave buffer (20% of day)"],
                "key_insight": "Schedule your priorities or someone else will",
            },
            "PKM": {
                "name": "Personal Knowledge Management (Zettelkasten)",
                "components": ["Inbox", "Literature notes", "Permanent notes", "Index / MOC (Map of Content)"],
                "key_insight": "Write to think — ideas become clear when externalised",
            },
            "Eat the Frog": {
                "name": "Eat the Frog (Brian Tracy)",
                "rule": "Do the most important and dreaded task first thing every morning",
                "key_insight": "Momentum from hard tasks cascades through the day",
            },
        },
        "deep_work": {
            "title": "Deep Work (Cal Newport)",
            "definition": "Professional activities performed in a state of distraction-free concentration that push cognitive capabilities to their limit",
            "rules": [
                "Work deeply: create rituals, choose a philosophy (monastic/bimodal/rhythmic/journalistic)",
                "Embrace boredom: don't switch to stimulation at every gap",
                "Quit social media: or use it intentionally — is the benefit > cost?",
                "Drain the shallows: minimise low-value tasks, batch email",
            ],
            "metrics": {
                "deep_work_hours_per_day": "Target 4h for knowledge workers",
                "sessions_per_week": "Target 5 × 90-min blocks",
                "distraction_free": "Phone in another room, all notifications off",
            },
        },
        "decision_making_speed": {
            "title": "Decide Faster",
            "frameworks": [
                {"name": "Two-way vs One-way Door", "rule": "Reversible = decide fast and learn; Irreversible = go slow"},
                {"name": "70% Information Rule", "rule": "Decide at 70% confidence — waiting for 90% costs more than occasional wrong decisions"},
                {"name": "Disagree and Commit", "rule": "Once decided, commit fully regardless of personal preference"},
                {"name": "Decision Journal", "rule": "Record decisions + rationale + expected outcome; review quarterly"},
            ],
        },
        "energy_management": {
            "title": "Manage Energy, Not Just Time",
            "pillars": {
                "Physical": "Sleep, exercise, nutrition (foundation)",
                "Emotional": "Positive relationships, stress management, purpose",
                "Mental": "Focus, novelty, challenging work",
                "Spiritual": "Values alignment, meaning, vision",
            },
            "recovery": [
                "Deliberate breaks every 90 min",
                "Full days off (no work) weekly",
                "Annual 2-week disconnect",
                "Quarterly strategy days (no execution)",
            ],
        },
        "weekly_review": {
            "title": "Weekly Review Protocol",
            "steps": [
                "Clear inbox to zero",
                "Review calendar (past week): what went well, what to improve",
                "Review calendar (next week): reschedule, block time",
                "Review project list: next actions for each",
                "Review someday/maybe list",
                "Review goals: any drift?",
                "Set top 3 priorities for the week",
            ],
            "duration": "45-90 min, same time weekly (Friday or Sunday)",
        },
    },
    "quick_wins": [
        "Two-minute rule: if < 2 min, do it now",
        "Process email twice daily max — not continuously",
        "Single-tasking: close all tabs except what you're working on",
        "End each day with tomorrow's top 3 tasks defined",
        "Physical inbox: every piece of paper gets processed once",
        "Say no to 80% of requests to protect deep work capacity",
    ],
}


def get_pack() -> dict:
    return PACK


def system_info(name: str) -> dict | None:
    for k, v in PACK["sections"]["systems"].items():
        if k.lower() == name.lower() or v.get("name", "").lower() == name.lower():
            return v
    return None


def quick_wins() -> list[str]:
    return PACK["quick_wins"]
