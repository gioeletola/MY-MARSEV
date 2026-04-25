"""
Memory Schema Registry — defines and validates schemas for all 14 memory domains.

Each domain has a JSON-Schema-compatible descriptor that the MemoryManager
uses to validate writes and guide the memory tool.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemorySchema:
    """Schema descriptor for one memory domain."""
    domain: str
    description: str
    required_keys: list[str]
    optional_keys: list[str] = field(default_factory=list)
    versioned: bool = True
    max_entries: int = 10_000


# ---------------------------------------------------------------------------
# Domain schemas (all 14 domains from the blueprint)
# ---------------------------------------------------------------------------

_SCHEMAS: list[MemorySchema] = [
    MemorySchema(
        domain="identity",
        description="Core identity: name, values, goals, personas, strengths, bio.",
        required_keys=["name", "values"],
        optional_keys=["goals", "strengths", "weaknesses", "personas", "life_vision", "north_star"],
    ),
    MemorySchema(
        domain="project",
        description="Active and archived projects with status, tasks, and context.",
        required_keys=["project_id", "title", "status"],
        optional_keys=["description", "tasks", "owner", "deadline", "milestones", "tags"],
    ),
    MemorySchema(
        domain="financial",
        description="Financial data: accounts, budgets, net worth, cashflow, investments.",
        required_keys=["category"],
        optional_keys=["amount", "account", "date", "notes", "currency"],
        versioned=True,
    ),
    MemorySchema(
        domain="relationship",
        description="People: contacts, relationships, interaction history, commitments.",
        required_keys=["person_id", "name"],
        optional_keys=["relationship_type", "last_contact", "notes", "commitments", "context"],
    ),
    MemorySchema(
        domain="health",
        description="Health metrics, habits, medical records, energy logs.",
        required_keys=["metric_type", "value"],
        optional_keys=["unit", "date", "source", "notes", "trend"],
    ),
    MemorySchema(
        domain="knowledge",
        description="Captured knowledge: notes, summaries, insights, sources.",
        required_keys=["title", "content"],
        optional_keys=["source", "tags", "category", "linked_concepts", "review_date"],
    ),
    MemorySchema(
        domain="decision",
        description="Decision log with context, options, rationale, and outcomes.",
        required_keys=["decision_id", "title", "choice_made"],
        optional_keys=["context", "options", "rationale", "outcome", "outcome_score", "date"],
    ),
    MemorySchema(
        domain="preference",
        description="User preferences, settings, and personalization data.",
        required_keys=["key"],
        optional_keys=["value", "category", "updated_at"],
    ),
    MemorySchema(
        domain="goal",
        description="Goal hierarchy: life → 5yr → 1yr → quarterly → weekly → daily.",
        required_keys=["goal_id", "title", "horizon"],
        optional_keys=["description", "progress", "deadline", "parent_goal", "sub_goals", "status"],
    ),
    MemorySchema(
        domain="habit",
        description="Habit tracking: streaks, completion rates, cue-routine-reward.",
        required_keys=["habit_id", "name"],
        optional_keys=["frequency", "streak", "completion_rate", "cue", "reward", "status"],
    ),
    MemorySchema(
        domain="temporal",
        description="Time-anchored events: past decisions, future plans, milestones.",
        required_keys=["event_id", "description", "timestamp"],
        optional_keys=["event_type", "outcome", "horizon", "tags"],
    ),
    MemorySchema(
        domain="asset",
        description="Physical and digital asset inventory.",
        required_keys=["asset_id", "name", "category"],
        optional_keys=["value", "location", "purchase_date", "expiry", "status", "notes"],
    ),
    MemorySchema(
        domain="learning",
        description="Learning resources, paths, notes, and spaced repetition data.",
        required_keys=["item_id", "title"],
        optional_keys=["type", "status", "progress", "next_review", "tags", "source"],
    ),
    MemorySchema(
        domain="meta",
        description="System meta-data: session history, agent performance, config.",
        required_keys=["key"],
        optional_keys=["value", "category", "session_id", "agent_id"],
        versioned=False,
    ),
]


class MemorySchemaRegistry:
    """
    Registry for memory domain schemas.

    Provides:
    - Schema lookup by domain name
    - Key validation (required keys present)
    - List of all registered domains
    """

    def __init__(self) -> None:
        self._schemas: dict[str, MemorySchema] = {s.domain: s for s in _SCHEMAS}

    def get(self, domain: str) -> MemorySchema | None:
        return self._schemas.get(domain)

    def list_domains(self) -> list[str]:
        return list(self._schemas.keys())

    def validate(self, domain: str, data: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate data against domain schema.
        Returns (valid: bool, message: str).
        """
        schema = self._schemas.get(domain)
        if schema is None:
            return False, f"Unknown memory domain: '{domain}'"
        missing = [k for k in schema.required_keys if k not in data]
        if missing:
            return False, f"Missing required keys for domain '{domain}': {missing}"
        return True, "OK"

    def register(self, schema: MemorySchema) -> None:
        """Register a custom domain schema."""
        self._schemas[schema.domain] = schema
        logger.info("MemorySchemaRegistry: registered domain '%s'", schema.domain)

    def schema_summary(self) -> dict[str, Any]:
        return {
            domain: {
                "required": s.required_keys,
                "optional": s.optional_keys,
                "versioned": s.versioned,
            }
            for domain, s in self._schemas.items()
        }
