# Quick Start (5 minutes)

Assumes you have completed [Installation](installation.md) and have `ANTHROPIC_API_KEY` set.

---

## 1. Check system health

```bash
python main.py status
```

Prints a table of health checks and current token usage:

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

Sends a fixed briefing request through the full pipeline and prints a rich output panel:

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

## 3. Send a one-shot request

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

Drops into a persistent session where context carries over between messages:

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

Shows urgent tasks, open decisions, mood average, and daily non-negotiables. Optionally sends to Telegram if `TELEGRAM_BOT_TOKEN` is set:

```bash
python main.py brief --telegram
```

---

## 6. Start the web UI

```bash
python main.py serve --port 8080
```

Open `http://localhost:8080`. The web UI includes:

- **Chat panel** — type a message, press Enter, watch streaming tokens
- **Mode selector** — switch between 16 operating modes
- **Memory viewer** — browse all 14 memory domains
- **Health panel** — live token usage, agent status, latency

| URL | Template | Description |
|---|---|---|
| `/` | `index.html` | Main chat interface |
| `/dashboard` | `executive_dashboard` | Executive KPI dashboard |
| `/finance` | `finance_cockpit` | Finance cockpit |
| `/business` | `business_wall` | Business operations wall |
| `/approvals` | `approvals_center` | Pending approval queue |
| `/hud` | `jarvis_hud` | Jarvis full-screen HUD |
| `/expansion` | `expansion_dashboard` | Capability gaps + expansion |
| `/entities` | `entities_panel` | Connected entity management |
| `/settings` | `settings_panel` | User preferences |
| `/admin` | `admin_panel` | System administration |
| `/health` | — | JSON health endpoint |

---

## 7. Browse connectors

```bash
python main.py connector list
```

Shows all 41 connectors with status (`connected` / `beta` / `stub`) and last sync time.

```bash
# Trigger a manual sync
python main.py connector sync github

# Health check all connectors
python main.py connector health
```

---

## 8. List experimental labs

```bash
python main.py lab list
```

Shows all 21 labs with their IDs. To inspect a specific lab:

```bash
python main.py lab status finance
python main.py lab experiments finance
python main.py lab run finance --template 0
```

---

## Full CLI Reference

### Core commands

```bash
python main.py run [PROMPT] [--mode MODE] [--interactive] [--verbose]
python main.py demo                          # pipeline smoke test
python main.py status                        # health + token usage
python main.py serve [--host HOST] [--port PORT] [--reload]
python main.py telegram [--token TOKEN]      # Telegram bot (long-poll)
python main.py brief [--telegram]            # morning briefing
python main.py report [--print]              # weekly life report
python main.py health [--engines]            # quick health check
```

### Agent sub-commands

```bash
python main.py agent list
python main.py agent info <agent_id>
```

### Connector sub-commands

```bash
python main.py connector list
python main.py connector sync <connector_id>
python main.py connector health
```

### Lab sub-commands

```bash
python main.py lab list
python main.py lab status <lab_id>
python main.py lab experiments <lab_id>
python main.py lab run <lab_id> --template 0
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
| `local_offline` | Full local mode — Ollama only, no cloud |
| `survival` | Minimal mode — bare essentials only |
| `founder` | Startup ops — fundraising, team, GTM |
| `war` | High-stakes decision-making |
| `prestige` | Brand, luxury, high-touch service |
| `silent` | Background processing, no interruptions |
| `recovery` | Post-crisis stabilisation |
| `emergency` | Critical incident response |

Set the default mode in `config/sovereign.yaml`:

```yaml
default_mode: command
```
