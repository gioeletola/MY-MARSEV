# Installation

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 recommended |
| pip | latest | bundled with Python |
| ANTHROPIC_API_KEY | — | required for all cloud modes |
| Ollama | optional | required for `local_offline` / `survival` modes |

---

## Step-by-Step Installation

### 1. Clone the repository

```bash
git clone https://github.com/gioeletola/MY-MARSEV
cd MY-MARSEV
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

This installs SOVEREIGN and all dependencies (FastAPI, uvicorn, anthropic, typer, rich, httpx, etc.) in editable mode. The `[dev]` extra adds pytest, ruff, and mypy.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

For production or web-exposed deployments also set the security keys:

```env
SOVEREIGN_PASSWORD=strong_password_here
AUTH_SECRET_KEY=random_64_char_string_here
SECRET_MANAGER_KEY=another_random_key_for_vault_encryption
```

### 4. Verify the installation

```bash
python main.py status
```

Expected output: a health table showing all checks as `ok` and token budget available.

### 5. Run the demo

```bash
python main.py demo
```

Sends a fixed prompt through the full pipeline (InputPipeline → CEOAgent → Worker → StructuredOutput) and prints a rich panel with the result, token usage, and confidence score.

### 6. (Optional) Start the web UI

```bash
python main.py serve --port 8080
# Open http://localhost:8080
```

---

## Environment Variable Reference

Copy `.env.example` to `.env`. All variables are optional except `ANTHROPIC_API_KEY`.

### Required

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key — get one at console.anthropic.com |

### Security (set before exposing to the internet)

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_PASSWORD` | `sovereign` | Web UI login password |
| `AUTH_SECRET_KEY` | `sovereign-change-me` | JWT signing secret for session tokens |
| `SECRET_MANAGER_KEY` | — | AES-256 key for the local secrets vault |

### Runtime

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_LOG_LEVEL` | `INFO` | Log verbosity: DEBUG / INFO / WARNING / ERROR |
| `SOVEREIGN_DATA_DIR` | `data` | Directory for memory, ledger, and builder data |
| `SOVEREIGN_APPROVAL_MODE` | `cli` | How approvals are presented: `cli` or `telegram` |
| `SOVEREIGN_DEFAULT_MODEL` | `claude-sonnet-4-6` | Default model for worker agents |
| `SOVEREIGN_CONFIG` | `config/sovereign.yaml` | Path to the main config file |

### Optional AI Providers

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI fallback (GPT-4o) |
| `GEMINI_API_KEY` | Google Gemini fallback |
| `PERPLEXITY_API_KEY` | Perplexity search provider |
| `OLLAMA_BASE_URL` | Ollama endpoint (default: `http://localhost:11434`) |
| `OLLAMA_DEFAULT_MODEL` | Local model to use (default: `qwen2.5:7b`) |

See `.env.example` for the full list of connector-specific variables (41 connectors each have their own keys).

---

## Offline / Local Mode

To run without any cloud API:

1. Install [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull qwen2.5:14b` (or `qwen3:32b` for best quality)
3. Start Ollama: `ollama serve`
4. Leave `ANTHROPIC_API_KEY` empty in `.env`
5. Select `local_offline` mode in the web UI or pass `--mode local_offline` to `python main.py run`

---

## Development Setup

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
python -m ruff check sovereign/

# Type check
python -m mypy sovereign/ --ignore-missing-imports
```

---

## Data Directories

SOVEREIGN stores persistent data under `data/` (configurable via `SOVEREIGN_DATA_DIR`):

```
data/
├── memory/          # 14+ domain JSON stores (identity.json, financial.json, …)
├── ledger/          # Append-only audit logs (decisions.jsonl, evals.jsonl)
├── labs/            # Experiment registry (experiments.json)
└── builder/         # BuilderStudio blueprints
```

This directory is created automatically on first run.
