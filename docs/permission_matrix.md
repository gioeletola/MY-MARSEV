# SOVEREIGN AI OS — Permission Matrix

## Role Definitions

| Role | Description |
|------|-------------|
| `owner` | Full system access — you |
| `admin` | Full access except system config changes |
| `operator` | Execute non-sensitive actions, approve workflows |
| `analyst` | Read and view only, can generate suggestions |
| `automation` | Execute only (for automated workflows) |
| `readonly` | Read data only |

---

## Permission Matrix

| Permission | owner | admin | operator | analyst | automation | readonly |
|---|---|---|---|---|---|---|
| READ_DATA | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| WRITE_DATA | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| EXECUTE_ACTION | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| APPROVE_ACTION | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| MANAGE_AGENTS | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| MANAGE_SYSTEM | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| VIEW_FINANCE | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| MANAGE_FINANCE | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| VIEW_SECURITY | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| MANAGE_SECURITY | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## Action Classes vs Roles

| Action Class | Allowed Roles | Description |
|---|---|---|
| READ | all | Read data, retrieve memory, view status |
| SUGGEST | analyst, operator, admin, owner | Propose but not act |
| DRAFT | operator, admin, owner | Generate drafts for human review |
| EXECUTE | operator (non-financial), admin, owner | Take direct action |

### Finance-Specific Execute

For any EXECUTE action involving financial operations:
- Requires `admin` or `owner` role
- Always requires `ApprovalGate` confirmation
- Logged to `DecisionLedger`

---

## Agent-Level Approval Requirements

### Always Requires Human Review
These agents set `requires_human_review=True` by default:

| Agent ID | Reason |
|---|---|
| `finance_os_chief` | Financial decisions |
| `cashflow_analyst` | Financial analysis |
| `budget_manager` | Spending decisions |
| `portfolio_manager` | Investment decisions |
| `investment_research` | Investment recommendations |
| `asset_allocation` | Portfolio changes |
| `financial_risk` | Risk decisions |
| `insurance_auditor` | Coverage changes |
| `tax_optimizer` | Tax strategy |
| `crypto_portfolio` | High-risk asset |
| `real_estate_analyst` | Property decisions |
| `allocation_agent` | Asset allocation |
| `scenario_finance` | Financial scenarios |
| `blackmap_georisk` | Geopolitical risk |
| `opportunity_radar` | Opportunity execution |
| `macro_news` | Market-moving events |
| `predictive_research` | Forward-looking models |
| `asset_watch` | Asset value alerts |
| `due_diligence` | Investment due diligence |
| `security_sentinel` | Security decisions |
| `incident_response` | Incident handling |
| `permission_auditor` | Permission changes |
| `data_leak_monitor` | Security alerts |
| `backup_integrity` | Backup operations |
| `legal_review` | Legal matters |
| `compliance_agent` | Regulatory matters |
| `deployment_assistant` | Production deployments |

### Auto-Approved (no review required)
Informational and read-only agents auto-approve:
- `expense_tracker`, `emergency_fund`, `wealth_builder`, `financial_independence`
- All personal agents (habit, diary, lifestyle, etc.)
- All offline agents
- Research and synthesis agents

---

## Escalation Thresholds by Mode

| Mode | Auto-Approve Threshold | Escalate Threshold |
|---|---|---|
| `command` | risk < 0.3 | risk > 0.7 |
| `business` | risk < 0.4 | risk > 0.8 |
| `finance` | risk < 0.2 | risk > 0.5 |
| `personal` | risk < 0.5 | risk > 0.85 |
| `survival` | risk < 0.8 | risk > 0.95 |
| `local_offline` | risk < 0.7 | risk > 0.90 |

---

## Constitutional Kill Switch

The `Guardian Agent` enforces the constitutional kill switch. Any agent attempting actions outside its `ActionClass` is blocked. The `LockdownManager` (sovereign/security/lockdown.py) can escalate to `EMERGENCY` level, blocking all `EXECUTE`/`DRAFT`/`SUGGEST` actions system-wide.

Activate via: `python main.py --kill-switch` or via the `LockdownManager.activate(LockdownLevel.EMERGENCY, ...)` API.
