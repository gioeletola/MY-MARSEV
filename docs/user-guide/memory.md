# Memory System — SOVEREIGN AI OS v0.3.0

SOVEREIGN's memory system provides persistent, structured storage across **14 domains**. All domains share a common read/write/search interface. Data is stored as JSON files under `data/memory/` and loaded lazily into in-memory caches.

---

## The 14 Memory Domains

| Domain | File | Purpose |
|---|---|---|
| `identity` | `identity.json` | Who you are: name, values, goals, personality, biometrics |
| `financial` | `financial.json` | Accounts, budgets, investments, income, expenses, net worth |
| `project` | `project.json` | Active and archived projects, milestones, blockers |
| `decision` | `decision.json` | Important decisions, reasoning, outcome tracking |
| `diary` | `diary.json` | Daily journal entries, mood logs, reflections |
| `health_routine` | `health_routine.json` | Sleep, exercise, nutrition, supplements, habits |
| `learning` | `learning.json` | Courses, notes, books, insights, skill progression |
| `relationship` | `relationship.json` | Contacts, interaction history, relationship health |
| `brand` | `brand.json` | Personal/business brand assets, positioning, tone of voice |
| `business_idea` | `business_idea.json` | Startup ideas, business concepts, market research |
| `content` | `content.json` | Blog posts, videos, newsletters, content calendar |
| `inventory` | `inventory.json` | Physical and digital assets, equipment, stock |
| `legal_compliance` | `legal_compliance.json` | Contracts, compliance notes, legal obligations |
| `personal_constitution` | `personal_constitution.json` | Core principles, rules-of-life, commitments, red lines |

---

## Semantic Search

The memory system supports two search backends:

| Backend | When used | Quality |
|---|---|---|
| **TF-IDF** (default) | Always available, no extra install | Good for keyword matching |
| **sentence-transformers** | When `pip install -e ".[embeddings]"` is installed | Dense vector similarity — better for semantic meaning |

The backend is selected automatically at startup. TF-IDF uses character + word n-grams as a fallback so search always works even without GPU.

Enable dense embeddings:

```bash
pip install -e ".[embeddings]"
```

---

## Python API

```python
from sovereign.memory.memory_manager import MemoryManager

mm = MemoryManager(data_dir="data")
```

### Reading a record

```python
record = await mm.read("identity", "core_values")
# Returns the stored dict, or None if the key doesn't exist
```

### Writing a record

```python
await mm.write("identity", "core_values", {
    "values": ["integrity", "curiosity", "discipline"],
    "updated_at": "2026-04-27T09:00:00Z",
})
```

### Listing all keys in a domain

```python
keys = await mm.list_keys("project")
# ["my_startup", "sovereign_dev", "newsletter"]
```

### Deleting a record

```python
deleted = await mm.delete("diary", "2026-01-01")
# Returns True if the key existed
```

### Semantic search — single domain

```python
results = await mm.semantic_search(
    query="investment strategy for volatile markets",
    domain="financial",
    top_k=5,
)
for hit in results:
    print(hit["key"], hit["score"], hit["value"])
```

### Semantic search — all domains

```python
results = await mm.semantic_search(
    query="morning routine habits",
    top_k=5,
)
for hit in results:
    print(hit["domain"], hit["key"], hit["score"])
```

### Rebuilding the semantic index

After bulk writes, force-rebuild the index for faster subsequent searches:

```python
await mm.rebuild_semantic_index("financial")
```

---

## REST API Access

The web server exposes memory via authenticated endpoints:

```
GET  /api/memory/{domain}             — returns all records in a domain
GET  /api/memory/{domain}/{key}       — returns a single record
POST /api/memory/{domain}/{key}       — write a record (JWT required)
DELETE /api/memory/{domain}/{key}     — delete a record (JWT required)
```

Example:

```bash
# Read the identity domain (requires JWT token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/memory/identity

# Write a record
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"values": ["integrity", "curiosity"]}' \
     http://localhost:8080/api/memory/identity/core_values
```

---

## Tool Access (from agents)

Agents access memory through the `memory_tool` builtin:

```python
# Agents with tools=["memory_tool"] can call:
await memory_tool.execute({
    "action": "read",
    "domain": "financial",
    "key": "monthly_budget",
}, context={})

await memory_tool.execute({
    "action": "write",
    "domain": "diary",
    "key": "2026-04-27",
    "value": {"entry": "Good day, focused work session."},
}, context={})

await memory_tool.execute({
    "action": "search",
    "query": "portfolio risk",
    "domain": "financial",
}, context={})
```

---

## Storage Format

Each domain is stored as a flat JSON object keyed by string:

```json
{
  "monthly_budget": {
    "income": 5000,
    "expenses": {"rent": 1200, "food": 400},
    "updated_at": "2026-04-27T08:00:00Z"
  },
  "savings_goal": {
    "target": 20000,
    "current": 8400,
    "deadline": "2026-12-31"
  }
}
```

Files live at `data/memory/<domain>.json` and are created automatically on first write.

---

## Configuration

Memory behaviour is controlled in `config/sovereign.yaml`:

```yaml
memory:
  data_dir: data                    # base directory
  semantic_search_top_k: 5         # default results per query
  retention_days: 365              # set to 0 for unlimited
  pii_safe_mode: false             # when true, strips PII before storing
```
