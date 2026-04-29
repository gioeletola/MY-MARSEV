"""Communication superpower pack — writing, speaking, storytelling, executive presence."""
from __future__ import annotations

COMMUNICATION_PACK = {
    "id": "communication",
    "name": "Master Communicator",
    "version": "1.0",
    "description": "Executive writing, storytelling, public speaking, feedback frameworks, persuasion.",
    "writing": {
        "pyramid_principle": {
            "description": "Start with the conclusion, then support it (McKinsey method)",
            "structure": [
                "Answer first: lead with your recommendation or conclusion",
                "Support: 3 key arguments (rule of three)",
                "Evidence: Data, examples, proof for each argument",
            ],
            "use_case": "Executive memos, board updates, consulting decks",
        },
        "clear_writing_rules": [
            "Subject + Verb + Object — active voice, short sentences",
            "Remove every word that doesn't earn its place",
            "One idea per paragraph; first sentence is the point",
            "Use concrete nouns and active verbs — avoid nominalisation",
            "Read aloud: if you stumble, rewrite",
            "Hemingway rule: write drunk, edit sober (draft fast, revise ruthlessly)",
        ],
        "email_framework": {
            "subject": "What decision/action is needed + deadline",
            "opening": "Bottom line upfront (BLUF) — what you need from them",
            "body": "Context → Details → Options → Recommendation",
            "CTA": "Specific request with deadline",
        },
    },
    "storytelling": {
        "hero_journey_business": [
            "The world as it was (status quo)",
            "The challenge/disruption",
            "The hero (customer) struggling",
            "The guide with a plan (your product/service)",
            "The transformation",
        ],
        "pixar_story_spine": [
            "Once upon a time...",
            "Every day...",
            "Until one day...",
            "Because of that...",
            "Until finally...",
            "And ever since then...",
        ],
        "data_storytelling": [
            "Numbers don't persuade — stories with numbers do",
            "One key insight, not 15 metrics",
            "Show the trend, not just the point",
            "Benchmark against something familiar (e.g. '3x the size of Manhattan')",
        ],
    },
    "public_speaking": {
        "rule_of_three": "Humans remember 3 things; structure every talk around 3 key points",
        "opening_hooks": [
            "Provocative question the audience can't answer yet",
            "Surprising statistic that challenges a belief",
            "Brief story with sensory detail",
            "Bold claim you'll spend the talk proving",
        ],
        "delivery": {
            "pace": "Slower than you think — 120-150 WPM for complex ideas",
            "pause": "Strategic silence signals confidence and gives ideas space to land",
            "gestures": "Open palm = openness; steepled fingers = confidence; fidgeting = anxiety",
            "eye_contact": "4-5 second connection with one person; then move to another",
        },
        "handling_nerves": [
            "Reframe anxiety as excitement (physiology is identical)",
            "Power pose 2 minutes before stage",
            "Breathe: 4 counts in, 7 hold, 8 out (parasympathetic activation)",
            "Focus on giving, not performing",
        ],
    },
    "feedback": {
        "SBI_model": {
            "S": "Situation: 'In last Tuesday's stand-up...'",
            "B": "Behaviour: 'When you interrupted three times...'",
            "I": "Impact: 'I noticed the team stopped contributing.'",
        },
        "radical_candour": {
            "quadrants": {
                "ruinous_empathy": "Care personally but don't challenge — feels kind, isn't",
                "obnoxious_aggression": "Challenge directly but don't care personally — brutal",
                "manipulative_insincerity": "Neither care nor challenge — political and useless",
                "radical_candour": "Care personally AND challenge directly — ideal",
            },
        },
        "receiving_feedback": [
            "Listen without defending — treat it as data, not attack",
            "Ask for specific examples",
            "Separate impact from intent",
            "Thank the giver — it took courage",
            "Decide what to act on after reflection, not in the moment",
        ],
    },
}


def get_pack() -> dict:
    return COMMUNICATION_PACK


def writing_framework(name: str) -> dict | list | None:
    return COMMUNICATION_PACK["writing"].get(name)


def speaking_tip(category: str) -> dict | list | None:
    return COMMUNICATION_PACK["public_speaking"].get(category)
