"""Translation Tool — language detection, phrase lookup, translation prompts."""
from __future__ import annotations

import re
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

_PHRASES: dict[str, dict[str, str]] = {
    "hello": {"it": "ciao", "es": "hola", "fr": "bonjour", "de": "hallo", "pt": "olá", "ja": "こんにちは"},
    "goodbye": {"it": "arrivederci", "es": "adiós", "fr": "au revoir", "de": "auf wiedersehen", "pt": "adeus"},
    "thank you": {"it": "grazie", "es": "gracias", "fr": "merci", "de": "danke", "pt": "obrigado"},
    "yes": {"it": "sì", "es": "sí", "fr": "oui", "de": "ja", "pt": "sim", "ja": "はい"},
    "no": {"it": "no", "es": "no", "fr": "non", "de": "nein", "pt": "não", "ja": "いいえ"},
    "please": {"it": "per favore", "es": "por favor", "fr": "s'il vous plaît", "de": "bitte", "pt": "por favor"},
    "sorry": {"it": "mi dispiace", "es": "lo siento", "fr": "désolé", "de": "entschuldigung", "pt": "desculpe"},
    "help": {"it": "aiuto", "es": "ayuda", "fr": "aide", "de": "hilfe", "pt": "ajuda"},
    "money": {"it": "denaro", "es": "dinero", "fr": "argent", "de": "geld", "pt": "dinheiro"},
    "work": {"it": "lavoro", "es": "trabajo", "fr": "travail", "de": "arbeit", "pt": "trabalho"},
    "time": {"it": "tempo", "es": "tiempo", "fr": "temps", "de": "zeit", "pt": "tempo"},
    "food": {"it": "cibo", "es": "comida", "fr": "nourriture", "de": "essen", "pt": "comida"},
    "water": {"it": "acqua", "es": "agua", "fr": "eau", "de": "wasser", "pt": "água"},
    "today": {"it": "oggi", "es": "hoy", "fr": "aujourd'hui", "de": "heute", "pt": "hoje"},
    "tomorrow": {"it": "domani", "es": "mañana", "fr": "demain", "de": "morgen", "pt": "amanhã"},
}

_LANG_PATTERNS: list[tuple[str, str]] = [
    (r"\b(il|la|le|lo|gli|un|una|è|sono|che|per|con|nel|della)\b", "it"),
    (r"\b(el|la|los|las|un|una|es|son|que|para|con|en|del)\b", "es"),
    (r"\b(le|la|les|un|une|est|sont|que|pour|avec|en|du|au)\b", "fr"),
    (r"\b(der|die|das|ein|eine|ist|sind|für|mit|und|oder|auch)\b", "de"),
    (r"\b(o|a|os|as|um|uma|é|são|que|para|com|em|do|da)\b", "pt"),
    (r"[぀-ゟ゠-ヿ]", "ja"),
    (r"[一-鿿]", "zh"),
    (r"[Ѐ-ӿ]", "ru"),
    (r"\b(the|is|are|was|were|have|has|will|would|can|could|this|that)\b", "en"),
]

_LANG_NAMES = {
    "en": "English", "it": "Italian", "es": "Spanish", "fr": "French",
    "de": "German", "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese", "ru": "Russian",
}


def _detect_language(text: str) -> str:
    lower = text.lower()
    scores: dict[str, int] = {}
    for pattern, lang in _LANG_PATTERNS:
        matches = re.findall(pattern, lower, re.IGNORECASE)
        if matches:
            scores[lang] = scores.get(lang, 0) + len(matches)
    return max(scores, key=lambda k: scores[k]) if scores else "en"


class TranslationTool(BaseTool):
    """Language utilities: detect language, phrase lookup, and translation prompt generation."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="translation_tool",
            description="Detect language, look up common phrase translations, and generate Claude translation prompts.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["detect", "lookup", "list_phrases", "translate_prompt", "supported_languages"],
                    },
                    "text": {"type": "string", "description": "Text to detect or phrase to look up"},
                    "target_lang": {"type": "string", "description": "ISO 639-1 target language code"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        text: str = "",
        target_lang: str = "en",
        **_: Any,
    ) -> Any:
        target = target_lang.lower()
        try:
            if action == "detect":
                return self._detect(text)
            if action == "lookup":
                return self._lookup(text, target)
            if action == "list_phrases":
                return {"result": sorted(_PHRASES.keys()), "count": len(_PHRASES), "error": None}
            if action == "translate_prompt":
                return self._translate_prompt(text, target)
            if action == "supported_languages":
                langs = [{"code": k, "name": v} for k, v in _LANG_NAMES.items()]
                return {"result": langs, "count": len(langs), "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _detect(self, text: str) -> dict:
        if not text.strip():
            return {"result": None, "error": "text is required for detection"}
        lang = _detect_language(text)
        return {"result": lang, "language_name": _LANG_NAMES.get(lang, lang), "error": None}

    def _lookup(self, phrase: str, target: str) -> dict:
        key = phrase.strip().lower()
        if key in _PHRASES:
            translations = _PHRASES[key]
            result = translations.get(target)
            return {
                "result": result,
                "phrase": phrase,
                "target_lang": target,
                "found": result is not None,
                "all_translations": translations,
                "error": None if result else f"No '{target}' translation for '{phrase}'",
            }
        return {"result": None, "phrase": phrase, "found": False, "error": f"Phrase '{phrase}' not in dictionary"}

    def _translate_prompt(self, text: str, target: str) -> dict:
        lang_name = _LANG_NAMES.get(target, target.upper())
        prompt = (
            f"Translate the following text to {lang_name}. "
            f"Preserve tone, formatting, and meaning exactly. "
            f"Return only the translated text, no explanations.\n\nText:\n{text}"
        )
        return {"result": prompt, "target_lang": target, "target_language": lang_name, "error": None}
