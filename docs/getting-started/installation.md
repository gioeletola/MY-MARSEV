# Installation — SOVEREIGN AI OS v0.3.0

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 recommended |
| pip | latest | bundled with Python |
| `ANTHROPIC_API_KEY` | — | required for all cloud modes |
| Ollama | optional | required for `local_offline` / `survival` modes only |

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

This installs SOVEREIGN and all core dependencies (FastAPI, uvicorn, anthropic, typer, rich, httpx, etc.) in editable mode. The `[dev]` extra adds pytest, ruff, and mypy.

**Optional extras:**

```bash
# Dense embedding support for better semantic memory search
pip install -e ".[embeddings]"   # adds sentence-transformers

# PDF parsing support
pip install -e ".[pdf]"

# Everything at once
pip install -e ".[full,dev]"
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

For production or internet-exposed deployments, also set the security keys:

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

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Check              ┃ Status  ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ token_budget       │ ok      │
│ tools              │ ok      │
│ memory             │ ok      │
│ constitution       │ ok      │
└────────────────────┴─────────┘
Overall: OK
```

### 5. Run the demo

```bash
python main.py demo
```

Sends a fixed prompt through the full pipeline (InputPipeline → CEOAgent → Workers → StructuredOutput) and prints a rich panel with the result, token usage, and confidence score.

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
| `ANTHROPIC_API_KEY` | Claude API key — obtain at console.anthropic.com |

### Security (set before exposing to the internet)

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_PASSWORD` | `sovereign` | Web UI login password |
| `AUTH_SECRET_KEY` | `sovereign-change-me` | JWT signing secret for session tokens |
| `SECRET_MANAGER_KEY` | — | AES-256 key for the local secrets vault |

### Runtime

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG` / `INFO` / `WARNING` / `ERROR` |
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

See `.env.example` for the full list — 50+ connector-specific keys across 41 integrations.

---

## Offline / Local Mode

To run without any cloud API:

1. Install [Ollama](https://ollama.ai)
2. Pull a model: `ollama pull qwen2.5:14b` (or `qwen3:32b` for highest quality)
3. Start Ollama: `ollama serve`
4. Leave `ANTHROPIC_API_KEY` empty in `.env`
5. Select `local_offline` mode in the web UI or pass `--mode local_offline` to `python main.py run`

---

## Data Directories

SOVEREIGN stores persistent data under `data/` (configurable via `SOVEREIGN_DATA_DIR`):

```
data/
├── memory/          # 14 domain JSON stores (identity.json, financial.json, …)
├── ledger/          # Append-only audit logs (decisions.jsonl, evals.jsonl)
├── labs/            # Experiment registry (experiments.json)
└── builder/         # BuilderStudio blueprints
```

This directory is created automatically on first run.

---

## Troubleshooting

### `ANTHROPIC_API_KEY not set` error

```
Error: ANTHROPIC_API_KEY is not set. Set it in your .env file or as an environment variable.
```

Make sure you copied `.env.example` to `.env` and added your key. You can also export it directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python main.py status
```

### Port already in use

```
ERROR: [Errno 98] Address already in use: ('0.0.0.0', 8080)
```

Another process is using port 8080. Either stop that process or run SOVEREIGN on a different port:

```bash
python main.py serve --port 9090
```

### `ModuleNotFoundError` after install

Ensure you ran `pip install -e ".[dev]"` from inside the `MY-MARSEV` directory, and that your virtual environment is activated if you are using one.

### `sentence_transformers` not found (memory search degraded)

TF-IDF fallback is used automatically. For full dense-embedding search:

```bash
pip install -e ".[embeddings]"
```

### Ollama not responding

Check Ollama is running and reachable:

```bash
curl http://localhost:11434/api/tags
```

If using a non-default URL, set `OLLAMA_BASE_URL` in your `.env`.
