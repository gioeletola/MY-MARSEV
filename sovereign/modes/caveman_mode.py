"""
Operating mode: caveman.

Activates when budget is tight, providers are spotty, or the user explicitly
wants terse/cheap responses. Forces the cheapest available model and injects
a system prompt suffix that suppresses all padding.

Priority model chain:  claude-haiku-4-5-20251001 → qwen2.5:7b → local
Max output: 512 tokens per turn (hard budget cap).
"""
from __future__ import annotations

import pathlib

from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode


class CavemanMode(BaseMode):
    """
    Budget-constrained operating mode.

    - Uses only cheap / local models (Haiku, Qwen, Ollama)
    - Forces synthetic, terse replies (no markdown, no padding)
    - Hard 512-token output cap per turn
    - Fully offline-capable (falls back to local Ollama)
    - High escalation threshold — only truly risky actions escalate
    """

    # Cheapest model priority list — first available wins at routing time
    CHEAP_MODEL_CHAIN: list[tuple[str, str]] = [
        ("anthropic", "claude-haiku-4-5-20251001"),
        ("qwen",      "qwen2.5:7b"),
        ("local",     "ollama-mistral"),
    ]

    # System prompt suffix injected on every call in this mode
    TERSE_SUFFIX: str = (
        "\n\n[CAVEMAN MODE] Respond in the fewest words possible. "
        "No markdown. No examples unless explicitly requested. "
        "No padding, preamble, or sign-off. Direct answer only."
    )

    MAX_TOKENS: int = 512

    def __init__(self, data_dir: str | pathlib.Path = "data") -> None:
        super().__init__(
            name="caveman",
            description=(
                "Budget-constrained mode — forces cheap models and "
                "terse synthetic responses. Offline-capable."
            ),
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.85,
            preferred_model="claude-haiku-4-5-20251001",
            offline_capable=True,
            require_approval_for=["financial", "external_api"],
        )
        self._data_dir = pathlib.Path(data_dir)

    # ------------------------------------------------------------------
    # Routing helpers — used by ModelRouter / orchestrator
    # ------------------------------------------------------------------

    def routing_overrides(self) -> dict:
        """
        Returns kwargs to merge into RoutingCriteria when this mode is active.

        The router checks these overrides so it always routes to cheap models
        regardless of task_complexity or budget_limit_usd.
        """
        return {
            "preferred_provider": "anthropic",
            "preferred_model": "claude-haiku-4-5-20251001",
            "budget_limit_usd": 0.005,   # ≤ $0.005 per call
        }

    def system_prompt_suffix(self) -> str:
        """Suffix appended to every system prompt while in this mode."""
        return self.TERSE_SUFFIX

    def max_tokens(self) -> int:
        """Hard output token cap for this mode."""
        return self.MAX_TOKENS

    def select_model_for_provider(self, provider: str) -> str:
        """Return the cheapest model for a given provider in caveman mode."""
        _cheap = {
            "anthropic": "claude-haiku-4-5-20251001",
            "openai":    "gpt-4o-mini",
            "gemini":    "gemini-1.5-flash",
            "kimi":      "moonshot-v1-8k",
            "qwen":      "qwen2.5:7b",
            "local":     "ollama-mistral",
            "perplexity": "sonar",
        }
        return _cheap.get(provider, "claude-haiku-4-5-20251001")
