"""
Health & Performance superpower pack — protocols for physical, cognitive, and emotional optimisation.
"""
from __future__ import annotations

PACK = {
    "id": "health",
    "title": "Health & Human Performance",
    "version": "1.0",
    "sections": {
        "sleep": {
            "title": "Sleep Optimisation",
            "principles": [
                "Consistent wake time is more important than consistent bedtime",
                "Morning light exposure within 30 min of waking anchors circadian rhythm",
                "Core temperature must drop ~1°C to initiate sleep — cool room (18-19°C)",
                "Caffeine half-life ~5-6h: cut off by 2pm for 10pm sleep",
                "Alcohol disrupts REM sleep even if it aids falling asleep",
                "Blue light blocking glasses 2h before bed extends melatonin window",
            ],
            "targets": {"duration": "7-9h", "deep_sleep": "20-25%", "rem": "20-25%"},
            "protocols": {
                "Wind-down (60 min before)": [
                    "Dim lights / blue-light glasses", "No screens or passive consumption only",
                    "Light stretching or breathing exercises", "Keep room cool",
                ],
            },
        },
        "training": {
            "title": "Exercise & Recovery",
            "minimum_effective_dose": {
                "strength": "3x/week compound movements (squat/deadlift/press/row) — progressive overload",
                "cardio": "150 min/week zone 2 (can hold conversation) for longevity and VO2 max",
                "mobility": "10 min/day; focus on hip flexors, thoracic spine, ankles",
            },
            "recovery_hierarchy": [
                "Sleep quality (highest priority)",
                "Nutrition and hydration",
                "Active recovery (walk, light movement)",
                "Stress management (cortisol suppresses recovery)",
                "Cold exposure / heat (sauna) — secondary benefits",
            ],
            "markers": {
                "VO2 max": "Elite longevity predictor; target top 25th percentile for age/sex",
                "Grip strength": "Mortality predictor; test annually",
                "Zone 2 pace": "Should improve over weeks at same heart rate",
            },
        },
        "nutrition": {
            "title": "Nutrition Fundamentals",
            "principles": [
                "Protein first: 1.6-2.2g per kg bodyweight for muscle preservation",
                "Calories are king for body composition — track during phases",
                "Whole foods: 80% of calories from minimally processed sources",
                "Fibre target: 30g/day minimum for gut health and satiety",
                "Hydration: bodyweight_kg × 35ml/day + 500ml per training hour",
            ],
            "cognitive_performance": {
                "caffeine": "100-200mg + L-theanine (2:1 ratio) for focused work without jitters",
                "fasting": "16:8 IF reduces insulin spikes; most people report mental clarity benefit",
                "omega_3": "2-4g EPA+DHA daily for brain health and inflammation",
                "magnesium": "Glycinate or malate 400mg before bed — sleep and recovery",
            },
        },
        "cognitive": {
            "title": "Cognitive Performance",
            "peak_states": {
                "morning": "First 2-4h after waking: analytical, deep work, writing (norepinephrine peak)",
                "midday": "Creative work, meetings, collaboration",
                "afternoon": "Administration, email, low-stakes tasks",
                "evening": "Learning consolidation, review, planning next day",
            },
            "focus_protocols": [
                "90-min deep work blocks (ultradian rhythm) — no notifications",
                "5-min transition ritual before blocks (breathing, clear desk)",
                "Cold exposure or light exercise to elevate norepinephrine pre-work",
                "NSDR (Non-Sleep Deep Rest) / yoga nidra 20 min to restore focus capacity",
            ],
            "longevity_markers": [
                "Regular learning of new skills (neuroplasticity)",
                "Social connection — strongest longevity predictor after VO2 max",
                "Purpose and meaning (reduces all-cause mortality)",
                "Stress resilience training (deliberate cold, hard exercise)",
            ],
        },
        "biometrics": {
            "to_track": [
                {"metric": "HRV (Heart Rate Variability)", "frequency": "Daily (morning)",
                 "good": ">60ms for athletes", "tool": "Whoop/Oura/Garmin"},
                {"metric": "Resting Heart Rate", "frequency": "Daily",
                 "good": "<60 bpm", "trend": "Declining RHR = improving fitness"},
                {"metric": "VO2 Max", "frequency": "Monthly estimate",
                 "good": "Top 25th percentile for age", "tool": "Garmin/Polar estimate"},
                {"metric": "Body weight + trend", "frequency": "Daily (same time)",
                 "note": "7-day average more useful than single reading"},
                {"metric": "Sleep score", "frequency": "Daily", "good": "70+"},
            ],
        },
    },
}


def get_pack() -> dict:
    return PACK


def daily_checklist() -> list[str]:
    return [
        "Morning light within 30 min of wake",
        "30g+ protein at breakfast",
        "Hydrate: 500ml water on wake",
        "90-min deep work block (phone off)",
        "Zone 2 or strength training",
        "Caffeine cut-off by 2pm",
        "Wind-down routine 60 min before sleep",
    ]


def section_info(section: str) -> dict | None:
    return PACK["sections"].get(section)
