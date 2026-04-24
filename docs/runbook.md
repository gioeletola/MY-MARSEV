# SOVEREIGN AI OS — Operations Runbook

## Health Checks

### System Health
```bash
curl http://localhost:8080/health
# Check "overall": "ok" | "degraded" | "critical"
```

### Provider Health
```bash
curl http://localhost:8080/api/providers
# Check all providers "available": true, "circuit_open": false
```

### CLI Status
```bash
python main.py status
```

---

## Common Issues

### API Key Not Found
**Symptom**: `anthropic.AuthenticationError` or `overall: critical`
**Fix**:
```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
# Restart server
python main.py serve
```

### Provider Circuit Breaker Open
**Symptom**: Responses from wrong provider, `circuit_open: true` in health
**Cause**: Provider had 3+ errors in 60s
**Fix**: Wait 120s for auto-recovery, or restart server to reset

### All Providers Down (Caveman Mode)
**Symptom**: Responses from `qwen` or `local` model only
**Cause**: All cloud providers unavailable
**Fix**:
1. Check internet connectivity
2. Verify API keys in .env
3. Check provider status pages
4. Start Ollama for local fallback: `ollama serve`

### Out of Budget
**Symptom**: Requests rejected with budget error
**Fix**:
- Update `providers.budget_daily_usd` in Settings → Providers
- Check usage at `GET /api/budget`

### Memory Store Corruption
**Symptom**: `MemoryManager load error` in logs
**Fix**:
```bash
# Backup current data
cp -r data/memory data/memory.bak
# Remove corrupted domain
rm data/memory/financial.json   # example
# Restart — will recreate with defaults
```

### Approval Queue Stuck
**Symptom**: Many escalations pending, agents blocked
**Fix**:
```bash
# View pending
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/escalations

# Resolve one
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"resolution":"approved"}' \
  http://localhost:8080/api/escalations/{event_id}/resolve
```

### WebSocket Disconnects
**Symptom**: UI shows "disconnected", requests fail
**Cause**: Network issue, server restart, or idle timeout
**Fix**: The client auto-reconnects with exponential backoff (1s→16s). If persistent:
1. Hard refresh browser (Ctrl+Shift+R)
2. Check server logs for errors
3. Verify server is running: `curl http://localhost:8080/api/status`

### Telegram Bot Not Responding
**Symptom**: Bot doesn't reply to messages
**Fix**:
```bash
# Check token
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"

# Check whitelist — if set, your chat_id must be in the list
echo $TELEGRAM_WHITELIST_CHAT_IDS

# Restart bot
python main.py telegram
```

### Qwen Not Responding
**Symptom**: qwen provider shows `available: false`
**Fix**:
```bash
# Check Ollama
curl http://localhost:11434/api/tags
# If not running:
ollama serve &
# Pull model if missing:
ollama pull qwen2.5:14b
```

---

## Monitoring Watchdog

The orchestrator runs a watchdog every 60s that logs:
- `WARNING: system degraded — overall=degraded alerts=[...]`
- `WARNING: providers with open circuit: ['openai', 'gemini']`
- `INFO: N escalations pending`

Check logs:
```bash
tail -f sovereign.log | grep -E "Watchdog|degraded|circuit"
```

---

## Backups

```bash
# Backup all persistent data
tar -czf sovereign-backup-$(date +%Y%m%d).tar.gz data/ config/ .env

# Restore
tar -xzf sovereign-backup-YYYYMMDD.tar.gz
```

---

## Reset to Defaults

```bash
# Reset user settings (keeps memory)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/settings/reset

# Full data wipe (DESTRUCTIVE)
rm -rf data/
python main.py serve   # recreates data/ with defaults
```

---

## Log Levels

```bash
# Set in .env
LOG_LEVEL=DEBUG    # verbose — all agent calls, tool calls
LOG_LEVEL=INFO     # default — session starts, health events
LOG_LEVEL=WARNING  # quiet — only problems
LOG_LEVEL=ERROR    # minimal — failures only
```

---

## Performance Tuning

| Setting | Where | Effect |
|---|---|---|
| `Semaphore(5)` → increase | `orchestrator.py:_dispatch` | More parallel agents |
| `budget_daily_usd` | Settings → Providers | Daily cost ceiling |
| `max_cost_per_request_usd` | Settings → Providers | Per-request ceiling |
| `memory_retention_days` | Settings → Privacy | Memory store size |
| `preferred_provider="qwen"` | Settings → Providers | No cloud costs |
| `local_first=true` | Settings → Providers | Cloud only as fallback |
