"""Intent radar — classifies raw input into structured intents before routing."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DetectedIntent:
    intent: str
    confidence: float
    mode_hint: str
    entities: dict[str, str] = field(default_factory=dict)
    raw: str = ""


_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, intent, mode_hint)
    (r"\b(cashflow|revenue|profit|expense|budget|invoice|tax)\b", "finance_query", "finance"),
    (r"\b(email|send|reply|draft|inbox|calendar|meeting|schedule)\b", "communication_task", "business"),
    (r"\b(research|analyse|summarise|summarize|report|study|learn)\b", "research_task", "research"),
    (r"\b(code|debug|deploy|build|test|fix|implement|refactor)\b", "engineering_task", "builder"),
    (r"\b(habit|health|exercise|sleep|diary|journal|mood)\b", "personal_task", "personal"),
    (r"\b(buy|sell|invest|portfolio|crypto|stock|asset)\b", "investment_query", "finance"),
    (r"\b(security|threat|breach|vulnerability|audit|lockdown)\b", "security_task", "command"),
    (r"\b(legal|contract|compliance|regulation|risk)\b", "legal_query", "business"),
    (r"\b(status|health|report|what.*running|show.*agents)\b", "system_status", "command"),
    (r"\b(travel|flight|hotel|visa|trip|destination)\b", "travel_task", "travel"),
]


class IntentRadar:
    def __init__(self) -> None:
        self._compiled = [
            (re.compile(pat, re.IGNORECASE), intent, mode)
            for pat, intent, mode in _PATTERNS
        ]

    def classify(self, text: str) -> DetectedIntent:
        scores: dict[str, float] = {}
        mode_map: dict[str, str] = {}
        for pat, intent, mode in self._compiled:
            matches = pat.findall(text)
            if matches:
                scores[intent] = scores.get(intent, 0.0) + len(matches) * 0.2
                mode_map[intent] = mode

        if not scores:
            return DetectedIntent(intent="general", confidence=0.5, mode_hint="command", raw=text)

        best_intent = max(scores, key=lambda k: scores[k])
        conf = min(scores[best_intent], 1.0)
        return DetectedIntent(
            intent=best_intent,
            confidence=conf,
            mode_hint=mode_map.get(best_intent, "command"),
            raw=text,
        )

    def classify_many(self, texts: list[str]) -> list[DetectedIntent]:
        return [self.classify(t) for t in texts]
