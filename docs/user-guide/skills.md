# Skills

Skills are TOML-declarative mini-workflows that extend SOVEREIGN's capabilities
without writing Python. Each skill defines its inputs, outputs, permissions,
and a prompt template.

## Built-in Skills

| Skill ID | Description | Approval |
|---|---|---|
| `email-draft` | Draft an email from bullet points | No |
| `daily-digest` | Generate daily briefing | No |
| `meeting-notes` | Structure meeting transcripts | No |
| `knowledge-extract` | Extract key facts from text | No |
| `web-summarize` | Fetch and summarize a URL | No |
| `calendar-prep` | Prep for upcoming events | No |
| `topic-research` | Multi-source topic research | No |
| `file-organizer` | Organize files by category | **Yes** |
| `dependency-audit` | Audit project dependencies | **Yes** |

## Using Skills

```bash
# List all skills
python main.py skill list

# Run a skill
python main.py skill run email-draft --input '{"topic": "Q1 results", "tone": "professional"}'

# Enable / disable
python main.py skill enable web-summarize
python main.py skill disable file-organizer
```

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

[[outputs]]
name = "result"
type = "string"
description = "Processed output"

[prompt_template]
system = "You are a helpful assistant."
user = "Process this topic: {{ topic }}"
```

## Permissions

Skills declare the permissions they need. High-risk permissions automatically
set `requires_approval = true`:

| Permission | Risk | Notes |
|---|---|---|
| `read` | Low | Read memory/files |
| `write` | Low | Write memory |
| `network` | Medium | HTTP requests |
| `files` | Medium | Filesystem access |
| `execute` | High | Shell commands → approval required |
| `code` | High | Code execution → approval required |
| `approval_required` | — | Always asks user before running |
