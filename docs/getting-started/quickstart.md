# Quick Start (5 minutes)

Assumes you have completed [Installation](installation.md) and have `ANTHROPIC_API_KEY` set.

---

## 1. Check system health

```bash
python main.py status
```

Output shows a table of health checks and token usage:

```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Check              ┃ Status  ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ token_budget       │ ok      │
│ tools              │ ok      │
│ memory             │ ok      │
│ constitution       │ ok      │
└────────────────────┴─────────┘

Token usage: {'input': 0, 'output': 0, 'cache_read': 0}
Overall: OK
```

---

## 2. Run the demo

```bash
python main.py demo
```

Sends a fixed briefing request through the full pipeline and prints a rich panel:

```
╭─ SUCCESS  ceo_agent · abc12345 ──────────────────────────────────────╮
│ SOVEREIGN AI OS is a 280+ agent multi-agent operating system...      │
│                                                                       │
│ Your top 3 next actions:                                              │
│ 1. Set ANTHROPIC_API_KEY in your .env file                           │
│ 2. Configure your identity profile in data/memory/identity.json      │
│ 3. Try: python main.py run --interactive                              │
╰───────────────────────────────────────────────────────────────────────╯
Tokens — in:1240 out:387 cache_read:890 confidence:88%
```

---

## 3. Run a single request

```bash
python main.py run "Summarize the latest developments in AI safety"
```

With verbose output (full JSON):

```bash
python main.py run "Draft a project plan for launching a newsletter" --verbose
```

In a specific operating mode:

```bash
python main.py run "Analyse my monthly expenses" --mode finance
python main.py run "Write a blog post about productivity" --mode business
python main.py run "Plan a 5-day trip to Tokyo" --mode travel
```

---

## 4. Interactive REPL

```bash
python main.py run --interactive
```

Drops into a persistent session where the context carries over between messages:

```
╭─ SOVEREIGN AI OS — Interactive Mode ─────────────────────────────────╮
│ Type exit or quit to end the session.                                 │
│ Type status to check system health.                                   │
╰───────────────────────────────────────────────────────────────────────╯

▶ What can you do for me today?
... (processing) ...

▶ Analyse my portfolio risk
... (processing) ...

▶ exit
Goodbye.
```

---

## 5. Morning briefing

```bash
python main.py brief
```

Shows urgent tasks, open decisions, 7-day mood average, and your daily non-negotiables. Optionally sends to Telegram:

```bash
python main.py brief --telegram
```

---

## 6. Start the web UI

```bash
python main.py serve --port 8080
```

Open `http://localhost:8080` — the single-page web UI includes:

- **Chat panel** — type a message, press Enter, watch streaming tokens
- **Mode selector** — switch between command / business / finance / etc.
- **Memory viewer** — browse all 14 memory domains in the left sidebar
- **Health panel** — live token usage, agent status, latency, circuit breakers

Other web UI routes:

| URL | Description |
|---|---|
| `/` | Main chat interface |
| `/dashboard` | Executive dashboard |
| `/finance` | Finance cockpit |
| `/business` | Business wall |
| `/approvals` | Pending approval queue |
| `/hud` | Jarvis HUD (full-screen overlay) |
| `/settings` | User preferences |
| `/admin` | System administration |
| `/health` | JSON health endpoint |

---

## All CLI Commands

### Top-level commands

```bash
python main.py run [PROMPT] [--mode MODE] [--interactive] [--verbose]
python main.py demo                          # pipeline smoke test
python main.py status                        # health + token usage
python main.py serve [--host HOST] [--port PORT] [--reload]
python main.py telegram [--token TOKEN]      # Telegram bot (long-poll)
python main.py brief [--telegram]            # morning briefing
python main.py report [--print]             # weekly life report
python main.py health [--engines]           # quick health check
```

### Agent sub-commands

```bash
python main.py agent list
python main.py agent info <agent_id>
```

### Connector sub-commands

```bash
python main.py connector list               # all 41 connectors + status
python main.py connector sync <id>          # trigger immediate sync
python main.py connector health             # health of all connectors
```

### Skill sub-commands

```bash
python main.py skill list
python main.py skill enable <skill_id>
python main.py skill disable <skill_id>
python main.py skill run <skill_id> --input '{"key": "value"}'
```

### Model sub-commands

```bash
python main.py model list
python main.py model list --provider anthropic
python main.py model list --local
python main.py model list --tier frontier
```

### Vault sub-commands

```bash
python main.py vault set MY_KEY "secret_value"
python main.py vault get MY_KEY
python main.py vault list
python main.py vault delete MY_KEY
```

---

## Operating Modes

Pass `--mode MODE` to `python main.py run` or switch in the web UI.

| Mode | Best for |
|---|---|
| `command` | General-purpose, no restrictions |
| `business` | CRM, documents, strategy, B2B tasks |
| `personal` | Diary, habits, health, personal decisions |
| `finance` | Portfolio analysis, budgeting, transactions |
| `study` | Learning, research, note-taking, citations |
| `travel` | Trip planning, itineraries, bookings |
| `research` | Deep multi-source research with citations |
| `builder` | Code generation, architecture, prototyping |
| `local_offline` | Full local mode — Ollama/Qwen only, no cloud |
| `survival` | Minimal mode — bare essentials only |

Set the default in `config/sovereign.yaml`:

```yaml
default_mode: command
```
