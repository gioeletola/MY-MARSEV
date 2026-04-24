# Installation

## Prerequisites

- Python 3.11+
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- Optional: Ollama running locally for offline/privacy mode

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/sovereign.git
cd sovereign

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 4. Verify installation
python main.py status

# 5. Run the CLI demo
python main.py demo

# 6. Start the web UI
python main.py serve --port 8080
# Open http://localhost:8080
```

## Environment Variables

Copy `.env.example` to `.env` and set the variables you need:

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API access |
| `OPENAI_API_KEY` | No | GPT-4o fallback |
| `GOOGLE_API_KEY` | No | Gemini fallback |
| `OLLAMA_HOST` | No | Ollama endpoint (default: localhost:11434) |
| `NOTION_TOKEN` | No | Notion connector |
| `GITHUB_TOKEN` | No | GitHub connector |
| `GMAIL_ACCESS_TOKEN` | No | Gmail connector (OAuth2) |
| `SECRET_MANAGER_KEY` | No | Secret obfuscation key |
| `AUTH_SECRET_KEY` | No | JWT signing key for web UI |

## Offline / Privacy Mode

To run entirely locally without any cloud API:

1. Install [Ollama](https://ollama.ai)
2. Pull a Qwen model: `ollama pull qwen2.5:14b`
3. Set `offline_mode: true` in `config/sovereign.yaml`
4. Run normally — all completions will use the local model

## Development Setup

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m ruff check sovereign/
python -m mypy sovereign/ --ignore-missing-imports
```
