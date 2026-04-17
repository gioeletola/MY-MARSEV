# SOVEREIGN AI OS — API Specification

## Base URL

```
http://localhost:8080
```

---

## REST Endpoints

### `GET /`

Returns the single-page web UI (`index.html`).

### `GET /health`

Returns system health status.

**Response:**
```json
{
  "status": "healthy",
  "session_id": "abc12345",
  "operating_mode": "command",
  "agents_registered": 200,
  "uptime_seconds": 3600,
  "memory_domains": 14,
  "token_usage": {
    "total_input": 50000,
    "total_output": 12000,
    "cache_read": 35000,
    "cache_write": 15000
  }
}
```

**Example:**
```bash
curl http://localhost:8080/health | jq
```

---

## WebSocket `/ws`

Real-time bidirectional channel for chat, streaming, and system events.

Connect: `ws://localhost:8080/ws`

---

### Client → Server Messages

All messages are JSON objects with a `type` field.

#### `chat`
Send a user message for processing.
```json
{
  "type": "chat",
  "content": "Analyse my cashflow for the last 3 months",
  "mode": "finance"
}
```

#### `memory_fetch`
Request data from a memory domain.
```json
{
  "type": "memory_fetch",
  "domain": "financial"
}
```
Valid domains: `identity`, `operational`, `project`, `relationship`, `financial`, `learning`, `inventory`, `health_routine`, `diary`, `legal_compliance`, `decision`, `research`, `content`, `brand`

#### `health_poll`
Request an immediate health snapshot.
```json
{ "type": "health_poll" }
```

#### `mode_switch`
Change the active operating mode.
```json
{
  "type": "mode_switch",
  "mode": "business"
}
```
Valid modes: `command`, `business`, `personal`, `finance`, `study`, `travel`, `research`, `builder`, `local_offline`, `survival`

#### `cancel`
Cancel the current in-progress request.
```json
{ "type": "cancel" }
```

---

### Server → Client Messages

#### `stream_delta`
Incremental token during streaming response.
```json
{
  "type": "stream_delta",
  "content": " cashflow"
}
```

#### `stream_done`
Signals completion of a response.
```json
{
  "type": "stream_done",
  "session_id": "abc12345",
  "tokens": 1450,
  "confidence": 0.86,
  "requires_human_review": false
}
```

#### `agent_status`
Real-time agent activity update.
```json
{
  "type": "agent_status",
  "agent_id": "cashflow_analyst",
  "status": "running"
}
```
Status values: `running`, `done`, `failed`, `waiting_approval`

#### `task_start`
A task has been dispatched to an agent.
```json
{
  "type": "task_start",
  "task_id": "t-abc123",
  "agent_id": "cashflow_analyst",
  "objective": "Analyse cashflow for Q1"
}
```

#### `task_done`
A task has completed.
```json
{
  "type": "task_done",
  "task_id": "t-abc123",
  "agent_id": "cashflow_analyst",
  "status": "success"
}
```

#### `tool_call`
An agent is invoking a tool.
```json
{
  "type": "tool_call",
  "agent_id": "cashflow_analyst",
  "tool": "code_exec",
  "input": "..."
}
```

#### `health`
System health snapshot (response to `health_poll`).
```json
{
  "type": "health",
  "data": { "status": "healthy", "agents_registered": 200 }
}
```

#### `memory_data`
Response to `memory_fetch`.
```json
{
  "type": "memory_data",
  "domain": "financial",
  "data": { "net_worth": 150000, "monthly_cashflow": 3200 }
}
```

#### `error`
An error occurred.
```json
{
  "type": "error",
  "message": "Agent cashflow_analyst failed: timeout"
}
```

---

## Authentication

Currently unauthenticated (local use). Set `AUTH_SECRET_KEY` environment variable to enable HMAC-SHA256 JWT token validation via `sovereign.infra.auth.AuthManager`.

Future: pass `Authorization: Bearer <token>` header on WebSocket upgrade.

---

## Error Codes

| HTTP | Meaning |
|------|---------|
| 200 | OK |
| 400 | Bad request (malformed WebSocket message) |
| 500 | Internal server error |
| 503 | Orchestrator not initialized |
