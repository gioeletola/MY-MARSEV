# SOVEREIGN AI OS — Multi-Provider Model Guide

## Supported Providers

| Provider | Models | Cost | Privacy | Use Case |
|---|---|---|---|---|
| **Anthropic** | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 | $$–$$$$ | Cloud (enterprise) | Default for all tasks |
| **OpenAI** | gpt-4o, gpt-4o-mini | $$–$$$ | Cloud | Fallback / budget tasks |
| **Google Gemini** | gemini-1.5-pro, gemini-1.5-flash | $–$$ | Cloud | Large context / free tier |
| **Qwen (Local)** | qwen2.5:7b/14b/32b/72b, qwen3:8b/14b/32b | Free | **Local** | Offline / privacy-safe |
| **Perplexity** | sonar, sonar-pro | $ | Cloud | Real-time web search |
| **Local (Ollama)** | ollama-mistral, ollama-llama3 | Free | **Local** | Offline / caveman mode |

## Routing Logic

```
RoutingCriteria → _select_provider_model()
  │
  ├── contains_pii=True    → anthropic (or local/qwen)
  ├── budget < $0.001      → openai/gpt-4o-mini
  ├── latency < 500ms      → local/qwen
  ├── complexity >= 0.8    → anthropic/claude-opus-4-6
  ├── preferred="openai"   → openai/{gpt-4o or gpt-4o-mini}
  ├── preferred="gemini"   → gemini/{pro or flash}
  ├── preferred="qwen"     → qwen/{3:32b, 2.5:14b, 2.5:7b}
  └── default              → anthropic/claude-sonnet-4-6

Fallback chain (standard):
  anthropic → openai → gemini → qwen → local

Fallback chain (PII-safe):
  anthropic → qwen → local

Fallback chain (offline_only):
  local

All providers down (caveman mode):
  qwen (if healthy) → local
```

## Qwen Local Setup

### Option A — Ollama
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull qwen2.5:7b      # fast, low VRAM
ollama pull qwen2.5:14b     # balanced
ollama pull qwen3:32b       # frontier-class

# Verify
ollama serve
curl http://localhost:11434/api/tags
```

### Option B — vLLM
```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-14B-Instruct \
  --port 8000
```

### Configuration
Update `data/memory/user_settings.json` or use the Settings UI (`/settings → Providers`):
```json
{
  "providers": {
    "preferred_provider": "qwen",
    "qwen_backend": "ollama",
    "qwen_base_url": "http://localhost:11434",
    "offline_default_model": "qwen2.5:14b",
    "local_first": true
  }
}
```

Or set in `config/sovereign.yaml`:
```yaml
preferred_provider: qwen
local_first: true
```

## Provider Health Monitoring

Provider health is tracked in real-time via `ProviderHealthTracker`:
- Circuit breaker opens after **3 errors in 60 seconds**
- Circuit auto-recovers after **120 seconds**
- Health visible at: `GET /api/providers` and `GET /admin → Provider Health`

```python
from sovereign.router.model_router import ModelRouter, RoutingCriteria

router = ModelRouter()
provider, model, chain = router.route_with_fallback(
    RoutingCriteria(
        task_complexity=0.7,
        preferred_provider="qwen",
        contains_pii=True,
    )
)
# → ("qwen", "qwen2.5:14b", [("qwen", ...), ("local", ...)])
```

## Cost Estimation

```python
from sovereign.router.model_router import ModelRouter

cost = ModelRouter.estimate_cost(
    provider="anthropic",
    model="claude-sonnet-4-6",
    input_tokens=1000,
    output_tokens=500,
)
# → $0.0105 USD

# Qwen is always free
cost_qwen = ModelRouter.estimate_cost("qwen", "qwen2.5:14b", 1000, 500)
# → $0.000000
```

## Model Tiers

| Tier | Claude | Use Case |
|---|---|---|
| FRONTIER | claude-opus-4-6 | CEO agent, strategic decisions, complex reasoning |
| BALANCED | claude-sonnet-4-6 | General tasks, coordination, guardian review |
| FAST | claude-haiku-4-5-20251001 | Ephemeral agents, classification, bulk ops |

## Adding a New Provider

1. Create `sovereign/models/my_provider.py` extending `BaseProvider`
2. Add to `_PROVIDER_PRICING` in `sovereign/router/model_router.py`
3. Add models to `sovereign/models/model_capability_registry.py`
4. Add to fallback chain in `build_fallback_chain()`
5. Handle in `_select_provider_model()` for `preferred_provider`
6. Export from `sovereign/models/__init__.py`
