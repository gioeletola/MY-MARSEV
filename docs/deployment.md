# SOVEREIGN AI OS — Deployment & Startup Guide

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/gioeletola/MY-MARSEV
cd MY-MARSEV
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env: add ANTHROPIC_API_KEY at minimum

# 3. Run
python main.py demo        # CLI smoke test (no server)
python main.py status      # System health check
python main.py serve       # Start web UI on :8080
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Claude API access |
| `SOVEREIGN_PASSWORD` | No | `sovereign` | Web UI login password |
| `AUTH_SECRET_KEY` | No | `sovereign-change-me` | JWT signing key |
| `SECRET_MANAGER_KEY` | No | — | AES-256 encryption key for secrets vault |
| `OPENAI_API_KEY` | No | — | OpenAI fallback provider |
| `GEMINI_API_KEY` | No | — | Google Gemini fallback |
| `PERPLEXITY_API_KEY` | No | — | Perplexity search provider |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot integration |
| `TELEGRAM_WHITELIST_CHAT_IDS` | No | — | Comma-separated allowed chat IDs |
| `SOVEREIGN_CONFIG` | No | `config/sovereign.yaml` | Config file path |

## Docker

```dockerfile
# Dockerfile (example)
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[dev]"
ENV ANTHROPIC_API_KEY=""
EXPOSE 8080
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
docker build -t sovereign-ai .
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -p 8080:8080 sovereign-ai
```

## Local-Only Mode (No Cloud)

```bash
# Start Ollama with Qwen
ollama pull qwen2.5:14b
ollama serve &

# Configure offline mode
export ANTHROPIC_API_KEY=""   # leave empty to force local

# Run
python main.py serve
# Select mode: local_offline in UI
```

## Web UI URLs

| URL | Description |
|---|---|
| `http://localhost:8080/` | Main chat interface |
| `http://localhost:8080/dashboard` | Executive dashboard |
| `http://localhost:8080/finance` | Finance cockpit |
| `http://localhost:8080/business` | Business wall |
| `http://localhost:8080/approvals` | Approval queue |
| `http://localhost:8080/hud` | Jarvis HUD (full-screen) |
| `http://localhost:8080/expansion` | Expansion / capability gaps |
| `http://localhost:8080/entities` | Connected entities |
| `http://localhost:8080/settings` | User settings |
| `http://localhost:8080/admin` | System admin |
| `http://localhost:8080/health` | JSON health endpoint |

## Telegram Bot

```bash
# 1. Create a bot via @BotFather on Telegram → get BOT_TOKEN
# 2. Get your chat ID via @userinfobot
# 3. Configure:
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_WHITELIST_CHAT_IDS="123456789"

# 4. Run (long-poll mode)
python main.py telegram
```

## CLI Commands

```bash
python main.py serve --host 0.0.0.0 --port 8080   # Web server
python main.py demo                                  # Interactive CLI demo
python main.py status                               # System health summary
python main.py telegram                             # Telegram bot
python main.py run "Analyze my portfolio"           # Single request
```

## Data Directories

```
data/
├── memory/          # 14 domain JSON stores
│   ├── identity.json
│   ├── financial.json
│   ├── project.json
│   ├── user_settings.json   # User preferences
│   └── …
├── ledger/          # Append-only audit logs
│   ├── decisions.jsonl
│   └── evals.jsonl
└── builder/         # BuilderStudio blueprints
    ├── agent_blueprints.json
    └── workflow_blueprints.json
```

## Health & Monitoring

```bash
# JSON health endpoint
curl http://localhost:8080/health

# Expected response:
{
  "overall": "ok",
  "checks": {"token_budget": "ok", "tools": "ok"},
  "agents_registered": 215,
  "tools_registered": 18,
  "provider_health": {
    "anthropic": {"available": true, "circuit_open": false, "error_count": 0},
    "qwen": {"available": true, "circuit_open": false, "error_count": 0},
    ...
  }
}
```

## Production Checklist

- [ ] Set `ANTHROPIC_API_KEY` from secure vault (not plaintext .env)
- [ ] Set `AUTH_SECRET_KEY` to a random 64-char string
- [ ] Set `SOVEREIGN_PASSWORD` to a strong password
- [ ] Enable HTTPS (reverse proxy with nginx/caddy)
- [ ] Set `TELEGRAM_WHITELIST_CHAT_IDS` if using Telegram
- [ ] Configure `budget_daily_usd` in user settings
- [ ] Enable PII safe mode if processing sensitive data
- [ ] Set up Qwen/Ollama as local fallback
- [ ] Configure log retention and rotation
- [ ] Set memory retention days in privacy settings
