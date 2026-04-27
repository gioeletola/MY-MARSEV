# Model Routing — SOVEREIGN AI OS v0.3.0

SOVEREIGN routes each task to the most appropriate model using a multi-factor decision process implemented in `sovereign/router/model_router.py`.

---

## Default Model Assignment

| Role / Use case | Model | Rationale |
|---|---|---|
| CEOAgent (strategic intent, mode selection) | `claude-opus-4-6` | Highest reasoning quality for executive decisions |
| ChiefOfStaff, Coordinator (task decomposition) | `claude-sonnet-4-6` | Balanced speed and quality for planning |
| Worker agents (default) | `claude-sonnet-4-6` | General-purpose, cost-effective for most tasks |
| Fast classification / routing | `claude-haiku-4-5-20251001` | Minimal latency and cost for lightweight tasks |
| Bulk processing / batch ops | `claude-haiku-4-5-20251001` | High throughput at low cost |
| Offline / local mode | `qwen3:32b` → `qwen2.5:14b` → `qwen2.5:7b` | Privacy-preserving, no cloud required |

---

## Decision Factors

| Factor | Signal | Effect |
|---|---|---|
| Task complexity | `action_class` (READ → EXECUTE) | Higher class → stronger model |
| Privacy / offline mode | `offline_mode = True` in config | Forces local Ollama models only |
| Cost budget | `budget_mode` flag | Prefers Haiku or GPT-4o-mini |
| Latency target | `max_latency_ms` hint | Prefers fast-tier models |
| Tool use required | non-empty `tools` list | Must support tool use |
| Multimodal input | image/audio in messages | Must support multimodal |

---

## Routing Rules (simplified)

```
task.action_class == EXECUTE AND task.domain == "strategy"
    → claude-opus-4-6

task.action_class == EXECUTE AND task.domain == "coding"
    → claude-sonnet-4-6  (or qwen2.5-coder:14b if offline)

task.action_class in (READ, SUGGEST)
    → claude-haiku-4-5-20251001

task.bulk == True OR task.classification == True
    → claude-haiku-4-5-20251001  (or gpt-4o-mini)

config.offline_mode == True
    → qwen3:32b → qwen2.5:14b → qwen2.5:7b → ollama-mistral
```

---

## Model Catalog

Defined in `sovereign/intelligence/model_catalog.py`.

| Model | Provider | Tier | Context | Private |
|---|---|---|---|---|
| `claude-opus-4-6` | Anthropic | FRONTIER | 200k | No |
| `claude-sonnet-4-6` | Anthropic | BALANCED | 200k | No |
| `claude-haiku-4-5-20251001` | Anthropic | FAST | 200k | No |
| `gpt-4o` | OpenAI | FRONTIER | 128k | No |
| `gpt-4o-mini` | OpenAI | FAST | 128k | No |
| `gemini-1.5-pro` | Google | FRONTIER | 1M | No |
| `gemini-1.5-flash` | Google | FAST | 1M | No |
| `qwen3:32b` | Qwen/Ollama | FRONTIER | 32k | Yes |
| `qwen2.5:14b` | Qwen/Ollama | BALANCED | 32k | Yes |
| `qwen2.5:7b` | Qwen/Ollama | FAST | 32k | Yes |
| `qwen2.5-coder:14b` | Qwen/Ollama | BALANCED | 32k | Yes |
| `ollama-mistral` | Ollama | LOCAL | 8k | Yes |

Browse the catalog:

```bash
python main.py model list
python main.py model list --tier frontier
python main.py model list --local
python main.py model list --provider anthropic
```

---

## Engine Adapters

Each provider is wrapped by an engine adapter in `sovereign/engine/`:

| Engine | File | Notes |
|---|---|---|
| `AnthropicEngine` | `anthropic_engine.py` | Anthropic SDK with prompt caching + streaming |
| `OpenAICompatEngine` | `openai_engine.py` | OpenAI SDK; also works with vLLM and LM Studio |
| `GeminiEngine` | `gemini_engine.py` | Gemini via OpenAI-compat endpoint |
| `OllamaEngine` | `ollama_engine.py` | Ollama REST API with streaming |
| `QwenLocalEngine` | `qwen_engine.py` | Qwen-specific Ollama adapter with preset temperatures |
| `MultiEngine` | `multi_engine.py` | Routes to the correct engine based on `model_id` |

---

## Prompt Caching

All Anthropic Claude calls set `cache_control: ephemeral` on the static portion of every system prompt. The cached section includes:

- **Constitutional kernel** (~1,500 tokens) — the agent's core values and stop conditions
- **Agent persona** — agent-specific instructions

After the first call in a session, the Anthropic API serves the static section from cache, reducing billable input tokens by approximately **70%**.

Implementation: `sovereign/claude/client.py` and `sovereign/claude/prompt_builder.py`.

```python
# How the system prompt is structured for caching:
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": STATIC_SYSTEM_PROMPT,        # ~1500 tokens
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": dynamic_task_context,         # not cached
            },
        ],
    }
]
```

---

## Offline / Local Mode

Set `OLLAMA_BASE_URL` in `.env` and leave `ANTHROPIC_API_KEY` empty (or select `local_offline` mode):

```env
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b
```

The `MultiEngine` detects the empty Anthropic key and automatically falls through to `OllamaEngine`. Model quality degrades gracefully: `qwen3:32b` → `qwen2.5:14b` → `qwen2.5:7b` based on availability.

Recommended local models:

| Model | VRAM | Use case |
|---|---|---|
| `qwen3:32b` | ~20 GB | Best quality — strategy/research |
| `qwen2.5:14b` | ~10 GB | Balanced — most tasks |
| `qwen2.5:7b` | ~5 GB | Fast — classification, summaries |
| `qwen2.5-coder:14b` | ~10 GB | Coding tasks |
