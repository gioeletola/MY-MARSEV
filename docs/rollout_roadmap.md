# SOVEREIGN AI OS — Rollout Roadmap

## Current State (as of April 2026)

All skeleton code is complete and tested. 191 tests passing on `claude/sovereign-ai-os-23Mu6`.

### What's Live

| Layer | Status | Files |
|---|---|---|
| Kernel (constitution, action classes, stop conditions) | ✅ Complete | `sovereign/kernel/` |
| Claude API client (caching, tool loop, streaming, retry) | ✅ Complete | `sovereign/claude/` |
| Orchestrator (10-step session flow, parallel dispatch) | ✅ Complete | `sovereign/orchestrator.py` |
| Agent swarm (200+ agents, factory pattern) | ✅ Complete | `sovereign/swarm/` |
| Memory system (14 domains, semantic search) | ✅ Complete | `sovereign/memory/` |
| 16 operating modes | ✅ Complete | `sovereign/modes/` |
| Tool ecosystem (15+ tools) | ✅ Complete | `sovereign/tools/` |
| Governance (RBAC, spending limits, risk scoring, escalation) | ✅ Complete | `sovereign/governance/` |
| Security (lockdown, quarantine, session monitor, access control) | ✅ Complete | `sovereign/security/` |
| Registries (agent, tool, decision ledger, workflow, policy) | ✅ Complete | `sovereign/registries/` |
| Observability (metrics, eval agent, health monitor) | ✅ Complete | `sovereign/observability/` |
| Multi-model provider layer | ✅ Complete | `sovereign/models/` |
| Web UI + 5 dashboards | ✅ Complete | `sovereign/api/templates/` |
| Perception layer | ✅ Complete | `sovereign/perception/` |
| Proactive layer | ✅ Complete | `sovereign/proactive/` |
| Forecasting layer | ✅ Complete | `sovereign/forecasting/` |
| Privacy layer | ✅ Complete | `sovereign/privacy/` |
| Expansion engine | ✅ Complete | `sovereign/expansion/` |
| HUD (Jarvis overlay) | ✅ Complete | `sovereign/hud/` |
| Devices layer | ✅ Complete | `sovereign/devices/` |
| Telegram bidirectional connector | ✅ Complete | `sovereign/integrations/telegram_integration.py` |
| Telegram bot (orchestrator bridge) | ✅ Complete | `sovereign/integrations/telegram_bot.py` |
| 8 superpower knowledge packs | ✅ Complete | `sovereign/superpower_files/` |
| 27 operational centers | ✅ Complete | `sovereign/centers/` |
| 21 specialist labs | ✅ Complete | `sovereign/labs/` |
| 7 reality layers | ✅ Complete | `sovereign/layers/` |
| Infra (queue, scheduler, auth, worker manager, notifications) | ✅ Complete | `sovereign/infra/` |
| Integrations (email, calendar, CRM, analytics stubs) | ✅ Stubs | `sovereign/integrations/` |

---

## Rollout Phases

### V1 — Personal Command Centre (Weeks 1–4)

**Goal:** Single-user, local setup, Claude API connected, all core features working.

**Week 1–2: Bootstrap**
- [ ] Copy `.env.example` → `.env`, add `ANTHROPIC_API_KEY`
- [ ] `pip install -e ".[dev]"`
- [ ] `python main.py demo` — verify API connectivity
- [ ] `python main.py status` — confirm 200+ agents registered
- [ ] `python main.py serve` — open `http://localhost:8080`

**Week 3: Personalisation**
- [ ] Populate identity memory: `memory/domains/identity.json`
- [ ] Set default mode in `config/sovereign.yaml`
- [ ] Configure spending limits in `sovereign/governance/spending_limits.py`
- [ ] Add emergency contacts to `EmergencyMode.EMERGENCY_CONTACTS`
- [ ] Test all 5 dashboards: `/dashboard`, `/finance`, `/business`, `/approvals`, `/hud`

**Week 4: Telegram**
- [ ] Create bot via @BotFather → get token
- [ ] Add `TELEGRAM_BOT_TOKEN` to `.env`
- [ ] Add your chat ID to `TELEGRAM_ALLOWED_CHAT_IDS`
- [ ] `python main.py telegram` — verify `/start` responds
- [ ] Test `/mode finance`, then send a financial query

**V1 Success Criteria:**
- Web UI operational, all dashboards loading
- CLI chat working: `python main.py run "analyse my finances" --mode finance`
- Telegram bot responding to commands
- Memory persisting between sessions
- Approval gate prompting for high-risk actions

---

### V2 — Business Operations (Weeks 5–10)

**Goal:** Multi-domain agentic workflows, financial tracking, team-ready.

**Week 5–6: Finance Layer**
- [ ] Populate `memory/financial` with real net worth / cashflow data
- [ ] Wire `cashflow_analyst` agent to real bank data (CSV import)
- [ ] Set up `SpendingLimitsEngine` with real budget caps
- [ ] Enable `portfolio_manager` with current holdings
- [ ] Schedule daily cashflow digest via `Scheduler`

**Week 7–8: Business Layer**
- [ ] Populate `memory/project` with active projects
- [ ] Configure `ceo_agent` system prompt with company context in `prompts/system/`
- [ ] Enable `morning_brief` scheduled task (daily 07:30 via Scheduler)
- [ ] Connect `email_integration` to real email provider (IMAP/SMTP)
- [ ] Wire `crm_integration` if using HubSpot/Salesforce

**Week 9–10: Automation**
- [ ] Configure `SilentOps` background tasks
- [ ] Set up `GoalMonitor` with quarterly goals
- [ ] Enable `SuggestionEngine` proactive alerts
- [ ] Configure `EventEngine` for time-triggered digests
- [ ] Enable `WorkerManager` H24 pool for critical agents

**V2 Success Criteria:**
- Morning brief arriving on Telegram every day
- Finance cockpit showing real portfolio data
- Project board reflecting active projects
- Approval queue capturing high-risk decisions
- Goals tracking progress automatically

---

### V3 — Full Operating System (Weeks 11–20)

**Goal:** Voice, HUD, live integrations, expansion engine, production-hardened.

**Week 11–12: Perception & Voice**
- [ ] Install `whisper`, `pyaudio`, `pvporcupine`
- [ ] Configure wake word in `WakeTrigger`
- [ ] Test `VoiceListener` transcription accuracy
- [ ] Wire voice commands → orchestrator → Telegram reply
- [ ] Enable `PresenceDetector` for auto-pause when away

**Week 13–14: HUD & Devices**
- [ ] Install `mediapipe`, `opencv-python`
- [ ] Open `http://localhost:8080/hud` in full-screen browser
- [ ] Configure `FaceTracker` for presence detection
- [ ] Test `ClapSystem` double-clap activation
- [ ] Set up `SensorManager` for CPU/battery monitoring

**Week 15–16: Expansion Engine**
- [ ] Monitor `CapabilityGapDetector` after 2 weeks of use
- [ ] Review `top_gaps()` — scaffold missing agents
- [ ] Promote top agents from SANDBOX → SHADOW → PRODUCTION
- [ ] Use `AgentScaffolder` to generate and test new agents

**Week 17–18: Privacy & Security**
- [ ] Test `SilentMode` for sensitive sessions
- [ ] Configure `SecureStorage` for critical secrets
- [ ] Enable `PrivacyMode.PRIVATE` for health/legal data
- [ ] Audit `AccessControlLayer` policies
- [ ] Test `LockdownManager` emergency activation

**Week 19–20: Production Hardening**
- [ ] Set up `CavemanMode` monthly token budget
- [ ] Configure `TokenBudgetEnforcer` hard limits
- [ ] Enable `EvalAgent` continuous quality monitoring
- [ ] Review `ConfidenceTracker` calibration per agent
- [ ] Set up backup schedule for `data/` directory
- [ ] Enable `AuthManager` JWT tokens for remote access

**V3 Success Criteria:**
- Voice commands working hands-free
- HUD active during desk sessions
- Budget never exceeded (CavemanMode enforcing)
- Eval score > 0.75 across all active agents
- Zero unresolved ADMIN/OWNER escalations pending > 24h

---

## Dependency Map

```
ANTHROPIC_API_KEY
    └─▶ ClaudeClient (claude/client.py)
            ├─▶ TokenBudgetEnforcer (infra/)
            ├─▶ All BaseAgent subclasses (swarm/)
            └─▶ Orchestrator (orchestrator.py)
                    ├─▶ MemoryManager (memory/)
                    ├─▶ CEOAgent + ChiefOfStaff (executive/)
                    ├─▶ GuardianAgent + ApprovalGate (executive/, authority/)
                    ├─▶ EscalationChain → NotificationService (governance/, infra/)
                    ├─▶ DecisionLedger (registries/)
                    └─▶ InputPipeline → IntentRadar (input_fabric/, perception/)

TELEGRAM_BOT_TOKEN
    └─▶ TelegramBot (integrations/telegram_bot.py)
            └─▶ Orchestrator (same pipeline as web UI)
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API key exposed in logs | Low | Critical | `SECRET_MANAGER_KEY` env var, `strip_pii` in SilentMode |
| Token budget overrun | Medium | High | CavemanMode + TokenBudgetEnforcer hard gates |
| Agent returns low-quality output | Medium | Medium | EvalAgent continuous scoring, ConfidenceTracker |
| Escalation queue backlog | Low | High | NotificationService alerts, SuggestionEngine reminders |
| Memory corruption on crash | Low | High | JSONL append-only ledger, daily backup cron |
| Telegram bot unauthorised access | Low | Critical | TELEGRAM_ALLOWED_CHAT_IDS whitelist |
| Local model unavailable (Ollama) | Medium | Low | FallbackChain → cloud automatically |

---

## Configuration Quick-Reference

```yaml
# config/sovereign.yaml
operating_mode: command
default_model: claude-sonnet-4-6
memory_dir: data/memory
ledger_dir: data/ledger

# Spending limits
daily_token_limit: 500_000
monthly_token_limit: 10_000_000
daily_cost_limit_usd: 5.00
monthly_cost_limit_usd: 80.00
```

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_ALLOWED_CHAT_IDS=12345678
SECRET_MANAGER_KEY=your-32-char-secret
AUTH_SECRET_KEY=your-jwt-signing-secret
```

---

## CLI Command Reference

```bash
python main.py run "Your request"          # Single request
python main.py run --interactive           # REPL mode
python main.py run --mode finance "..."    # With mode
python main.py demo                        # API connectivity test
python main.py status                      # System health
python main.py serve --port 8080           # Web UI
python main.py telegram                    # Telegram bot
python main.py telegram --token "..." --allowed "12345"
```

---

## File Count Summary

| Directory | Files | Purpose |
|---|---|---|
| `sovereign/swarm/` | ~20 | 200+ agent classes |
| `sovereign/centers/` | 28 | 27 operational centers |
| `sovereign/labs/` | 22 | 21 specialist labs |
| `sovereign/modes/` | 17 | 16 operating modes |
| `sovereign/tools/builtin/` | 15+ | Built-in tools |
| `sovereign/superpower_files/` | 10 | 8 knowledge packs |
| `sovereign/api/templates/` | 6 | Web UI + 5 dashboards |
| `sovereign/governance/` | 5 | RBAC, risk, escalation |
| `sovereign/security/` | 5 | Lockdown, quarantine, auth |
| `sovereign/models/` | 8 | Multi-model providers |
| `tests/` | 10 | 191 passing tests |
