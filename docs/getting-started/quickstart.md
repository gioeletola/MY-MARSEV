# Quick Start

## CLI Usage

```bash
# Show system status (agents, memory, health)
python main.py status

# Interactive demo — type a request and see SOVEREIGN respond
python main.py demo

# Run a single request non-interactively
python main.py run "Summarize the latest news about AI"

# Start the web UI
python main.py serve --port 8080
```

## CLI Sub-commands

```bash
# Agent management
python main.py agent list
python main.py agent info ceo_agent
python main.py agent run worker_agent "Write a blog post outline"

# Connector management
python main.py connector list
python main.py connector sync github
python main.py connector health

# Skill management
python main.py skill list
python main.py skill enable web-summarize
python main.py skill run email-draft --input '{"topic": "project update"}'

# Model catalog
python main.py model list
python main.py model list --provider anthropic
python main.py model list --local

# System health
python main.py health

# Secret vault
python main.py vault set MY_KEY "my_value"
python main.py vault get MY_KEY
python main.py vault list
```

## Web UI

Once the server is running at `http://localhost:8080`:

1. **Chat panel** (center) — type a message and press Enter to send
2. **Mode selector** — switch between command/business/personal/etc. modes
3. **Memory viewer** (left sidebar) — browse the 14 memory domains
4. **Health panel** (right) — live token usage, agent status, latency

## Operating Modes

| Mode | Use Case |
|---|---|
| `command` | General-purpose, unrestricted |
| `business` | Business tasks, CRM, documents |
| `personal` | Personal assistant, diary, notes |
| `finance` | Financial analysis, budgeting |
| `study` | Learning, research, note-taking |
| `travel` | Trip planning, itineraries |
| `research` | Deep research with citations |
| `builder` | Code generation, architecture |
| `local_offline` | Full local mode, no cloud |
| `survival` | Minimal mode, bare essentials |

Set the default mode in `config/sovereign.yaml`:
```yaml
default_mode: command
```
