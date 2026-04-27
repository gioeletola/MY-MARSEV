# Deployment — SOVEREIGN AI OS v0.3.0

---

## Local Development

```bash
# 1. Clone and install
git clone https://github.com/gioeletola/MY-MARSEV
cd MY-MARSEV
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum

# 3. Smoke test
python main.py demo
python main.py status

# 4. Start the web UI (hot-reload)
python main.py serve --port 8080 --reload
# Open http://localhost:8080
```

---

## Production Checklist

Before exposing SOVEREIGN to the internet or a multi-user environment:

- [ ] Set `ANTHROPIC_API_KEY` from a secure vault (not a plain-text `.env` file)
- [ ] Set `SOVEREIGN_PASSWORD` to a strong password (default `sovereign` is insecure)
- [ ] Set `AUTH_SECRET_KEY` to a random 64-character string
- [ ] Set `SECRET_MANAGER_KEY` to a random AES-256-compatible key
- [ ] Enable HTTPS via an nginx/Caddy reverse proxy (see config below)
- [ ] Set `TELEGRAM_WHITELIST_CHAT_IDS` if using the Telegram bot
- [ ] Configure `budget_daily_usd` in `config/sovereign.yaml` to cap spend
- [ ] Enable PII safe mode if processing sensitive data
- [ ] Set up Qwen/Ollama as a local fallback
- [ ] Configure log rotation (default logs to stdout)
- [ ] Set memory `retention_days` in `config/sovereign.yaml`

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Claude API access |
| `SOVEREIGN_PASSWORD` | Recommended | `sovereign` | Web UI login password |
| `AUTH_SECRET_KEY` | Recommended | `sovereign-change-me` | JWT signing key (use 64+ random chars) |
| `SECRET_MANAGER_KEY` | Recommended | — | AES-256 key for the secrets vault |
| `SOVEREIGN_LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `SOVEREIGN_DATA_DIR` | No | `data` | Root directory for memory, ledger, labs data |
| `SOVEREIGN_APPROVAL_MODE` | No | `cli` | `cli` (interactive) or `telegram` |
| `SOVEREIGN_DEFAULT_MODEL` | No | `claude-sonnet-4-6` | Default model for worker agents |
| `SOVEREIGN_CONFIG` | No | `config/sovereign.yaml` | Path to main config file |
| `OPENAI_API_KEY` | No | — | OpenAI fallback provider |
| `GEMINI_API_KEY` | No | — | Google Gemini fallback |
| `PERPLEXITY_API_KEY` | No | — | Perplexity search provider |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama endpoint for local models |
| `OLLAMA_DEFAULT_MODEL` | No | `qwen2.5:7b` | Default local model |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot integration |
| `TELEGRAM_WHITELIST_CHAT_IDS` | No | — | Comma-separated allowed chat IDs |
| `SLACK_BOT_TOKEN` | No | — | Slack integration |

See `.env.example` for the full list including all 41 connector-specific keys.

---

## Web UI URLs

| URL | Template | Description |
|---|---|---|
| `http://localhost:8080/` | `index.html` | Main chat interface |
| `http://localhost:8080/dashboard` | `executive_dashboard` | Executive KPI dashboard |
| `http://localhost:8080/finance` | `finance_cockpit` | Finance cockpit |
| `http://localhost:8080/business` | `business_wall` | Business operations wall |
| `http://localhost:8080/approvals` | `approvals_center` | Pending approval queue |
| `http://localhost:8080/hud` | `jarvis_hud` | Jarvis full-screen HUD |
| `http://localhost:8080/expansion` | `expansion_dashboard` | Capability gaps + expansion |
| `http://localhost:8080/entities` | `entities_panel` | Connected entity management |
| `http://localhost:8080/settings` | `settings_panel` | User preferences |
| `http://localhost:8080/admin` | `admin_panel` | System administration |
| `http://localhost:8080/health` | — | JSON health endpoint |

---

## Docker

The repository ships with a `Dockerfile` and `docker-compose.yml`.

```bash
# Build and start (foreground)
docker-compose up --build

# Detached mode
docker-compose up -d

# Follow logs
docker-compose logs -f

# Stop
docker-compose down
```

**Dockerfile snippet** (for custom builds):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[dev]"
ENV ANTHROPIC_API_KEY=""
EXPOSE 8080
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
```

Pass environment variables at runtime:

```bash
docker build -t sovereign-ai .
docker run \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e SOVEREIGN_PASSWORD="$SOVEREIGN_PASSWORD" \
  -e AUTH_SECRET_KEY="$AUTH_SECRET_KEY" \
  -p 8080:8080 \
  -v "$(pwd)/data:/app/data" \
  sovereign-ai
```

Mount `./data` as a volume so memory, ledger, and lab data persist across container restarts.

---

## Nginx Reverse Proxy

Example configuration for HTTPS with Let's Encrypt:

```nginx
server {
    listen 80;
    server_name sovereign.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name sovereign.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/sovereign.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sovereign.yourdomain.com/privkey.pem;

    # WebSocket support (required for real-time chat streaming)
    location /ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Telegram Bot

```bash
# 1. Create a bot via @BotFather on Telegram → get BOT_TOKEN
# 2. Get your chat ID via @userinfobot
# 3. Configure in .env:
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_WHITELIST_CHAT_IDS=123456789

# 4. Run (long-poll mode)
python main.py telegram
```

---

## Local-Only Mode (No Cloud)

```bash
# Install and start Ollama
ollama pull qwen2.5:14b   # or qwen3:32b for best quality
ollama serve &

# Configure .env
ANTHROPIC_API_KEY=        # leave empty to force local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:14b

# Run and select local_offline mode
python main.py serve
# In the web UI, select mode: local_offline
# Or via CLI:
python main.py run "Analyse my goals" --mode local_offline
```

---

## Health Monitoring

```bash
# CLI check
python main.py status
python main.py health --engines

# JSON endpoint
curl http://localhost:8080/health
```

Expected response:

```json
{
  "overall": "ok",
  "checks": {"token_budget": "ok", "tools": "ok", "memory": "ok"},
  "agents_registered": 280,
  "tools_registered": 18,
  "provider_health": {
    "anthropic": {"available": true, "circuit_open": false, "error_count": 0},
    "ollama": {"available": true, "circuit_open": false, "error_count": 0}
  }
}
```

---

## Data Directory Layout

```
data/
├── memory/          # 14 domain JSON stores
│   ├── identity.json
│   ├── financial.json
│   ├── project.json
│   └── ...
├── ledger/          # Append-only audit logs
│   ├── decisions.jsonl
│   └── evals.jsonl
├── labs/            # Experiment registry
│   └── experiments.json
└── builder/         # BuilderStudio blueprints
    ├── agent_blueprints.json
    └── workflow_blueprints.json
```

Back up the entire `data/` directory regularly. It is excluded from `.gitignore` by default to prevent accidental secret commits.
