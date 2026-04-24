# Model Routing

SOVEREIGN routes each task to the most appropriate model using a multi-factor
decision process implemented in `sovereign/router/model_router.py`.

## Decision Factors

| Factor | Signal | Effect |
|---|---|---|
| Task complexity | `action_class` (READ → EXECUTE) | Higher class → stronger model |
| Privacy mode | `offline_mode = True` in config | Local-only (Qwen / Ollama) |
| Cost budget | `budget_mode` flag | Prefer Haiku / GPT-4o-mini |
| Latency target | `max_latency_ms` hint | Prefer fast-tier models |
| Tool use required | `tools` list non-empty | Must support tool use |
| Multimodal input | image/audio in messages | Must support multimodal |

## Default Routing Rules

```
EXECUTE + strategic      → claude-opus-4-6
EXECUTE + coding         → claude-sonnet-4-6 or qwen2.5-coder:14b (local)
READ / SUGGEST           → claude-haiku-4-5-20251001
bulk / classification    → claude-haiku-4-5-20251001 or gpt-4o-mini
offline                  → qwen3:32b → qwen2.5:14b → qwen2.5:7b → ollama-mistral
```

## Model Catalog

Defined in `sovereign/intelligence/model_catalog.py`.

| Model | Provider | Tier | Context | Privacy |
|---|---|---|---|---|
| claude-opus-4-6 | Anthropic | FRONTIER | 200k | ✗ |
| claude-sonnet-4-6 | Anthropic | BALANCED | 200k | ✗ |
| claude-haiku-4-5-20251001 | Anthropic | FAST | 200k | ✗ |
| gpt-4o | OpenAI | FRONTIER | 128k | ✗ |
| gpt-4o-mini | OpenAI | FAST | 128k | ✗ |
| gemini-1.5-pro | Google | FRONTIER | 1M | ✗ |
| gemini-1.5-flash | Google | FAST | 1M | ✗ |
| qwen3:32b | Qwen/Ollama | FRONTIER | 32k | ✓ |
| qwen2.5:14b | Qwen/Ollama | BALANCED | 32k | ✓ |
| qwen2.5:7b | Qwen/Ollama | FAST | 32k | ✓ |
| qwen2.5-coder:14b | Qwen/Ollama | BALANCED | 32k | ✓ |
| ollama-mistral | Ollama | LOCAL | 8k | ✓ |

## Engine Adapters

Each provider is wrapped by an engine adapter in `sovereign/engine/`:

- `AnthropicEngine` — Anthropic SDK with prompt caching + streaming
- `OpenAICompatEngine` — OpenAI SDK, also works with vLLM / LM Studio
- `GeminiEngine` — Gemini via OpenAI-compat endpoint
- `OllamaEngine` — Ollama REST API with streaming
- `QwenLocalEngine` — Qwen-specific Ollama adapter with preset temperatures
- `MultiEngine` — Routes to the right engine per model_id
