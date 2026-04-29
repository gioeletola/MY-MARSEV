"""Text Analysis Tool — sentiment, readability, word stats, keyword extraction."""
from __future__ import annotations

import re
import string
from collections import Counter
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

_STOP_WORDS = frozenset([
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","being","have","has","had",
    "do","does","did","will","would","could","should","may","might","must",
    "that","this","these","those","it","its","i","you","he","she","we","they",
    "not","no","so","as","if","then","than","when","where","how","what","which",
])

_POSITIVE_WORDS = frozenset([
    "good","great","excellent","amazing","wonderful","fantastic","outstanding",
    "best","love","happy","positive","success","win","achieve","profit","growth",
    "improve","benefit","opportunity","strong","efficient","innovative","reliable",
])

_NEGATIVE_WORDS = frozenset([
    "bad","terrible","awful","horrible","worst","hate","negative","fail","loss",
    "problem","issue","risk","danger","poor","weak","slow","error","bug","broken",
    "difficult","complex","expensive","costly","waste","delay","decline","drop",
])


class TextAnalysisTool(BaseTool):
    """Analyse text: sentiment, readability, statistics, keyword extraction."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="text_analysis_tool",
            description="Analyse text for sentiment, readability (Flesch score), word frequency, keyword extraction, and structural statistics.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["sentiment", "readability", "word_stats", "keywords", "summarise_stats"],
                        "description": "sentiment|readability|word_stats|keywords|summarise_stats",
                    },
                    "text": {"type": "string", "description": "Text to analyse"},
                    "top_n": {"type": "integer", "description": "Top N keywords to return (default 10)"},
                },
                "required": ["action", "text"],
            },
        )

    async def execute(self, action: str, text: str = "", top_n: int = 10, **_: Any) -> Any:
        if not text.strip():
            return {"result": None, "error": "text is required"}
        try:
            if action == "sentiment":
                return self._sentiment(text)
            if action == "readability":
                return self._readability(text)
            if action == "word_stats":
                return self._word_stats(text, top_n)
            if action == "keywords":
                return self._keywords(text, top_n)
            if action == "summarise_stats":
                return self._summarise_stats(text, top_n)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _tokenise(self, text: str) -> list[str]:
        return [w.lower().strip(string.punctuation) for w in text.split() if w.strip(string.punctuation)]

    def _sentiment(self, text: str) -> dict:
        words = self._tokenise(text)
        pos = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
        total = max(len(words), 1)
        score = (pos - neg) / total
        label = "positive" if score > 0.02 else ("negative" if score < -0.02 else "neutral")
        return {
            "result": label,
            "score": round(score, 4),
            "positive_words": pos,
            "negative_words": neg,
            "confidence": round(min(abs(score) * 10, 1.0), 2),
            "note": "Lexicon-based heuristic — use Claude for nuanced sentiment",
            "error": None,
        }

    def _readability(self, text: str) -> dict:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        words = text.split()
        syllables = sum(self._count_syllables(w) for w in words)
        n_sent = max(len(sentences), 1)
        n_words = max(len(words), 1)
        flesch = 206.835 - 1.015 * (n_words / n_sent) - 84.6 * (syllables / n_words)
        flesch = max(0, min(100, flesch))
        if flesch >= 70:
            level = "Easy (high school)"
        elif flesch >= 50:
            level = "Standard (college)"
        elif flesch >= 30:
            level = "Difficult (professional)"
        else:
            level = "Very difficult (academic)"
        return {
            "result": round(flesch, 1),
            "level": level,
            "sentences": n_sent,
            "words": n_words,
            "avg_words_per_sentence": round(n_words / n_sent, 1),
            "avg_syllables_per_word": round(syllables / n_words, 2),
            "error": None,
        }

    def _count_syllables(self, word: str) -> int:
        word = word.lower().strip(string.punctuation)
        if not word:
            return 1
        vowels = "aeiouy"
        count = sum(1 for i, c in enumerate(word) if c in vowels and (i == 0 or word[i-1] not in vowels))
        if word.endswith("e") and count > 1:
            count -= 1
        return max(count, 1)

    def _word_stats(self, text: str, top_n: int) -> dict:
        words = self._tokenise(text)
        content_words = [w for w in words if w and w not in _STOP_WORDS and len(w) > 2]
        freq = Counter(content_words).most_common(top_n)
        chars = len(text)
        return {
            "result": freq,
            "total_words": len(words),
            "unique_words": len(set(words)),
            "characters": chars,
            "characters_no_spaces": len(text.replace(" ", "")),
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            "lexical_diversity": round(len(set(words)) / max(len(words), 1), 4),
            "error": None,
        }

    def _keywords(self, text: str, top_n: int) -> dict:
        words = self._tokenise(text)
        content = [w for w in words if w and w not in _STOP_WORDS and len(w) > 3]
        freq = Counter(content)
        total = max(sum(freq.values()), 1)
        keywords = [{"keyword": w, "count": c, "tfidf_proxy": round(c / total, 4)}
                    for w, c in freq.most_common(top_n)]
        bigrams = Counter(zip(content, content[1:])).most_common(5)
        return {
            "result": keywords,
            "bigrams": [{"phrase": f"{a} {b}", "count": c} for (a, b), c in bigrams],
            "error": None,
        }

    def _summarise_stats(self, text: str, top_n: int) -> dict:
        s = self._sentiment(text)
        r = self._readability(text)
        w = self._word_stats(text, top_n)
        k = self._keywords(text, top_n)
        return {
            "result": {
                "sentiment": s["result"],
                "sentiment_score": s["score"],
                "readability": r["result"],
                "readability_level": r["level"],
                "words": w["total_words"],
                "unique_words": w["unique_words"],
                "top_keywords": [kw["keyword"] for kw in k["result"][:5]],
            },
            "error": None,
        }
