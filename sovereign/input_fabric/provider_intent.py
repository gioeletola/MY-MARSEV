"""
Provider intent parser — detects explicit model/provider requests in user text.

Examples caught:
  "usa GPT-4o"  →  preferred_provider="openai", preferred_model="gpt-4o"
  "rispondi con Kimi"  →  preferred_provider="kimi"
  "use Claude Opus"  →  preferred_provider="anthropic", preferred_model="claude-opus-4-7"
  "modalità economica" / "caveman"  →  mode_override="caveman"
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProviderIntent:
    preferred_provider: str | None = None
    preferred_model: str | None = None
    mode_override: str | None = None
    detected: bool = False


# ── Pattern table ─────────────────────────────────────────────────────────────
# Each entry: (compiled_regex, provider, model_or_None)
_VERB = r"(usa|use|con|with|tramite|via|switch.*?to|voglio|vorrei|fammi|rispondi)\s+"

_PROVIDER_PATTERNS: list[tuple[re.Pattern, str, str | None]] = [
    # OpenAI
    (re.compile(rf"\b{_VERB}gpt[-\s]?4o[-\s]?mini\b", re.I), "openai", "gpt-4o-mini"),
    (re.compile(rf"\b{_VERB}gpt[-\s]?4o\b", re.I),           "openai", "gpt-4o"),
    (re.compile(rf"\b{_VERB}openai\b", re.I),                 "openai", None),
    (re.compile(rf"\b{_VERB}chatgpt\b", re.I),                "openai", "gpt-4o"),
    # Google Gemini — also bare model names
    (re.compile(rf"\b({_VERB})?gemini[-\s]?(1\.5[-\s]?flash|flash)\b", re.I), "gemini", "gemini-1.5-flash"),
    (re.compile(rf"\b({_VERB})?gemini[-\s]?(1\.5[-\s]?pro|pro)?\b", re.I),   "gemini", "gemini-1.5-pro"),
    (re.compile(rf"\b{_VERB}google\b", re.I),                                 "gemini", None),
    # Perplexity
    (re.compile(rf"\b{_VERB}perplexity\b", re.I),        "perplexity", "sonar-pro"),
    (re.compile(rf"\b{_VERB}sonar\b", re.I),             "perplexity", "sonar-pro"),
    # Kimi / Moonshot — bare names also caught
    (re.compile(rf"\b({_VERB})?kimi[-\s]?128k\b", re.I),       "kimi", "moonshot-v1-128k"),
    (re.compile(rf"\b({_VERB})?kimi[-\s]?(thinking)?\b", re.I),"kimi", "kimi-latest"),
    (re.compile(rf"\b{_VERB}moonshot\b", re.I),                 "kimi", "kimi-latest"),
    # Anthropic / Claude
    (re.compile(rf"\b({_VERB})?claude[-\s]?opus\b", re.I),     "anthropic", "claude-opus-4-7"),
    (re.compile(rf"\b({_VERB})?opus\b", re.I),                 "anthropic", "claude-opus-4-7"),
    (re.compile(rf"\b({_VERB})?claude[-\s]?sonnet\b", re.I),   "anthropic", "claude-sonnet-4-6"),
    (re.compile(rf"\b({_VERB})?claude[-\s]?haiku\b", re.I),    "anthropic", "claude-haiku-4-5-20251001"),
    (re.compile(rf"\b({_VERB})?haiku\b", re.I),                "anthropic", "claude-haiku-4-5-20251001"),
    (re.compile(rf"\b{_VERB}claude\b", re.I),                  "anthropic", None),
    # Qwen / local
    (re.compile(rf"\b{_VERB}qwen\b", re.I),                    "qwen", "qwen2.5:14b"),
    (re.compile(rf"\b{_VERB}(modello\s+)?locale\b", re.I),     "local", "ollama-mistral"),
    (re.compile(rf"\b{_VERB}ollama\b", re.I),                  "local", None),
]

# Mode overrides detected from text
_MODE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(modalit[àa]|mode)\s+caveman\b", re.I),       "caveman"),
    (re.compile(r"\b(modalit[àa]|mode)\s+economica?\b", re.I),    "caveman"),
    (re.compile(r"\bcaveman\b", re.I),                             "caveman"),
    (re.compile(r"\b(modalit[àa]|mode)\s+ricerca\b", re.I),       "research"),
    (re.compile(r"\b(modalit[àa]|mode)\s+finanza\b", re.I),       "finance"),
    (re.compile(r"\b(modalit[àa]|mode)\s+business\b", re.I),      "business"),
    (re.compile(r"\b(modalit[àa]|mode)\s+costruttore?\b", re.I),  "builder"),
    (re.compile(r"\b(modalit[àa]|mode)\s+silenziosa?\b", re.I),   "silent"),
    (re.compile(r"\b(modalit[àa]|mode)\s+guerra\b", re.I),        "war"),
    (re.compile(r"\b(modalit[àa]|mode)\s+sopravvivenza\b", re.I), "survival"),
    (re.compile(r"\b(modalit[àa]|mode)\s+offline\b", re.I),       "local_offline"),
    (re.compile(r"\b(modalit[àa]|mode)\s+personale\b", re.I),     "personal"),
    (re.compile(r"\b(modalit[àa]|mode)\s+viaggio\b", re.I),       "travel"),
    (re.compile(r"\b(modalit[àa]|mode)\s+studio\b", re.I),        "study"),
]


def parse_provider_intent(text: str) -> ProviderIntent:
    """
    Scan user text for explicit provider/model/mode requests.
    Returns a ProviderIntent with the first match found (provider patterns
    take priority over mode patterns).
    """
    for pattern, provider, model in _PROVIDER_PATTERNS:
        if pattern.search(text):
            return ProviderIntent(
                preferred_provider=provider,
                preferred_model=model,
                detected=True,
            )

    for pattern, mode in _MODE_PATTERNS:
        if pattern.search(text):
            return ProviderIntent(mode_override=mode, detected=True)

    return ProviderIntent()
