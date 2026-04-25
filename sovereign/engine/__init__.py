"""SOVEREIGN Engine Layer — uniform model backend adapters."""
from sovereign.engine.base import (
    BaseEngine,
    CompletionRequest,
    CompletionResponse,
    EngineHealth,
    EngineStatus,
)
from sovereign.engine.cloud import AnthropicEngine
from sovereign.engine.discovery import discover_engines, get_engine, init_engine
from sovereign.engine.multi import MultiEngine
from sovereign.engine.ollama import OllamaEngine
from sovereign.engine.openai_compat import GeminiEngine, OpenAICompatEngine
from sovereign.engine.qwen_local import QwenLocalEngine

__all__ = [
    "BaseEngine", "CompletionRequest", "CompletionResponse", "EngineHealth", "EngineStatus",
    "AnthropicEngine", "OllamaEngine", "OpenAICompatEngine", "GeminiEngine", "QwenLocalEngine",
    "MultiEngine",
    "discover_engines", "get_engine", "init_engine",
]
