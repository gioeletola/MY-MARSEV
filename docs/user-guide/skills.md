# Skills — SOVEREIGN AI OS v0.3.0

Skills are TOML-declarative mini-workflows that extend SOVEREIGN's capabilities without writing Python. Each skill defines its inputs, outputs, permissions, and a prompt template. Skills are discovered at startup from `sovereign/skills/data/`.

---

## Skill Lifecycle

| Status | Meaning |
|---|---|
| `active` | Enabled and callable by agents and the CLI |
| `stub` | Defined but not yet implemented (prompt template is a placeholder) |
| `disabled` | Exists but will not run; enable explicitly with `skill enable` |

Skills transition: `stub` → `active` (when implemented) → `disabled` (manually or on permission violation).

---

## Built-in Skills

| Skill ID | Description | Requires Approval |
|---|---|---|
| `email-draft` | Draft an email from bullet points | No |
| `daily-digest` | Generate daily briefing summary | No |
| `meeting-notes` | Structure meeting transcripts into action items | No |
| `knowledge-extract` | Extract key facts from a block of text | No |
| `web-summarize` | Fetch and summarize a URL | No |
| `calendar-prep` | Prepare briefing for upcoming calendar events | No |
| `topic-research` | Multi-source topic research with citations | No |
| `file-organizer` | Organize files by category | **Yes** |
| `dependency-audit` | Audit project dependencies for vulnerabilities | **Yes** |

---

## CLI Commands

```bash
# List all skills with their status
python main.py skill list

# Run a skill with JSON input
python main.py skill run email-draft --input '{"topic": "Q1 results", "tone": "professional"}'
python main.py skill run topic-research --input '{"query": "quantum computing 2025"}'

# Enable or disable a skill
python main.py skill enable web-summarize
python main.py skill disable file-organizer
```

---

## Writing a Custom Skill

Create a `.toml` file in `sovereign/skills/data/`:

```toml
skill_id = "my-skill"
name = "My Custom Skill"
description = "Does something useful."
version = "1.0.0"
tags = ["custom", "utility"]
status = "active"
requires_approval = false

[[inputs]]
name = "topic"
type = "string"
required = true
description = "The topic to process"

[[inputs]]
name = "depth"
type = "string"
required = false
default = "medium"
description = "Research depth: shallow / medium / deep"

[[outputs]]
name = "result"
type = "string"
description = "Processed output"

[prompt_template]
system = "You are a helpful specialist."
user = "Process this topic at {{ depth }} depth: {{ topic }}"

[permissions]
required = ["read", "network"]
```

SOVEREIGN auto-discovers `.toml` files placed in `sovereign/skills/data/` on startup — no registration step required.

---

## Permissions

Skills declare which permissions they need. High-risk permissions automatically set `requires_approval = true`:

| Permission | Risk | Notes |
|---|---|---|
| `read` | Low | Read memory / files |
| `write` | Low | Write memory |
| `network` | Medium | HTTP requests |
| `files` | Medium | Filesystem access |
| `execute` | High | Shell commands — approval required |
| `code` | High | Code execution — approval required |
| `approval_required` | — | Always prompts user before running |

If a skill requests `execute` or `code` permissions, `requires_approval` is forced to `true` regardless of the TOML setting.

---

## Calling a Skill Programmatically

```python
from sovereign.skills import SkillRegistry

registry = SkillRegistry()
skill = registry.get("email-draft")

result = await skill.run(
    inputs={"topic": "Q2 board update", "tone": "formal"},
    context={"user_id": "me"},
)
print(result.output)
```
