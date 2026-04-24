"""
Engine discovery — probes available backends and returns a configured MultiEngine.
Called once at startup; results are cached in the module singleton.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.engine.base import BaseEngine, EngineStatus
from sovereign.engine.cloud import AnthropicEngine
from sovereign.engine.multi import MultiEngine
from sovereign.engine.ollama import OllamaEngine
from sovereign.engine.openai_compat import GeminiEngine, OpenAICompatEngine
from sovereign.engine.qwen_local import QwenLocalEngine

logger = logging.getLogger(__name__)

_multi_engine: MultiEngine | None = None


async def discover_engines(config: dict[str, Any] | None = None) -> MultiEngine:
    """Probe all backends and return a MultiEngine containing available ones."""
    cfg = config or {}
    engines: list[BaseEngine] = []

    # 1. Anthropic (always try if key present)
    if os.getenv("ANTHROPIC_API_KEY"):
        anthropic = AnthropicEngine(cfg.get("anthropic"))
        h = await anthropic.health()
        if h.status == EngineStatus.AVAILABLE:
            engines.append(anthropic)
            logger.info("Engine discovered: anthropic (%d models)", len(h.available_models))
        else:
            logger.warning("AnthropicEngine unavailable: %s", h.error)
    else:
        logger.info("ANTHROPIC_API_KEY not set — skipping Anthropic engine")

    # 2. Qwen / Ollama local (check Ollama daemon)
    qwen = QwenLocalEngine(cfg.get("qwen_local"))
    h_qwen = await qwen.health()
    if h_qwen.status == EngineStatus.AVAILABLE:
        engines.append(qwen)
        logger.info("Engine discovered: qwen_local (%s)", h_qwen.available_models[:3])
    else:
        # Fallback: generic Ollama
        ollama = OllamaEngine(cfg.get("ollama"))
        h_ollama = await ollama.health()
        if h_ollama.status == EngineStatus.AVAILABLE:
            engines.append(ollama)
            logger.info("Engine discovered: ollama (%s)", h_ollama.available_models[:3])
        else:
            logger.info("Ollama not running — local engines unavailable")

    # 3. OpenAI
    if os.getenv("OPENAI_API_KEY"):
        openai = OpenAICompatEngine(cfg.get("openai"))
        h = await openai.health()
        if h.status == EngineStatus.AVAILABLE:
            engines.append(openai)
            logger.info("Engine discovered: openai_compat")

    # 4. Google Gemini
    if os.getenv("GOOGLE_API_KEY"):
        gemini = GeminiEngine(cfg.get("gemini"))
        h = await gemini.health()
        if h.status == EngineStatus.AVAILABLE:
            engines.append(gemini)
            logger.info("Engine discovered: gemini")

    if not engines:
        logger.warning("No engines available — all completions will fail")

    return MultiEngine(engines)


def get_engine() -> MultiEngine:
    """Return cached MultiEngine (must call init_engine() first)."""
    global _multi_engine
    if _multi_engine is None:
        # Return an empty MultiEngine — caller must run discover_engines()
        _multi_engine = MultiEngine([])
    return _multi_engine


async def init_engine(config: dict[str, Any] | None = None) -> MultiEngine:
    global _multi_engine
    _multi_engine = await discover_engines(config)
    return _multi_engine
