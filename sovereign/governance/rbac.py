"""
Role-Based Access Control for SOVEREIGN AI OS.

Manages roles, permissions, and entity→role assignments.
Persists state to data/memory/rbac.json.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_RBAC_PATH = Path("data/memory/rbac.json")


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class Permission(str, Enum):
    READ_DATA = "read_data"
    WRITE_DATA = "write_data"
    EXECUTE_ACTION = "execute_action"
    APPROVE_ACTION = "approve_action"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_SYSTEM = "manage_system"
    VIEW_FINANCE = "view_finance"
    MANAGE_FINANCE = "manage_finance"
    VIEW_SECURITY = "view_security"
    MANAGE_SECURITY = "manage_security"


@dataclass
class Role:
    """A named collection of permissions."""

    role_id: str
    name: str
    permissions: set[Permission]
    description: str = ""

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions

    # Serialisation helpers ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "permissions": [p.value for p in self.permissions],
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Role:
        return cls(
            role_id=data["role_id"],
            name=data["name"],
            permissions={Permission(p) for p in data.get("permissions", [])},
            description=data.get("description", ""),
        )


# ---------------------------------------------------------------------------
# Pre-seeded role definitions
# ---------------------------------------------------------------------------

def _build_default_roles() -> dict[str, Role]:
    all_perms = set(Permission)
    return {
        "owner": Role(
            role_id="owner",
            name="Owner",
            permissions=all_perms,
            description="Full control over the entire system.",
        ),
        "admin": Role(
            role_id="admin",
            name="Admin",
            permissions=all_perms - {Permission.MANAGE_SYSTEM},
            description="Administrative access excluding low-level system management.",
        ),
        "operator": Role(
            role_id="operator",
            name="Operator",
            permissions={Permission.EXECUTE_ACTION, Permission.APPROVE_ACTION,
                         Permission.READ_DATA, Permission.VIEW_FINANCE,
                         Permission.VIEW_SECURITY},
            description="Can execute and approve actions; read-only on finance and security.",
        ),
        "analyst": Role(
            role_id="analyst",
            name="Analyst",
            permissions={Permission.READ_DATA, Permission.VIEW_FINANCE,
                         Permission.VIEW_SECURITY},
            description="Read and view access only; no write or execution rights.",
        ),
        "automation": Role(
            role_id="automation",
            name="Automation",
            permissions={Permission.EXECUTE_ACTION, Permission.READ_DATA},
            description="Automation agents: execute actions and read data.",
        ),
        "readonly": Role(
            role_id="readonly",
            name="Read-Only",
            permissions={Permission.READ_DATA},
            description="Strictly read-only access.",
        ),
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RBACRegistry:
    """
    Manages role definitions and entity→role assignments.

    Thread safety: single-process only; no locking.
    Persistence: JSON snapshot at data/memory/rbac.json.
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        self._path: Path = persist_path or _RBAC_PATH
        self._roles: dict[str, Role] = _build_default_roles()
        # entity_id → set of role_ids
        self._assignments: dict[str, set[str]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign_role(self, entity_id: str, role_id: str) -> None:
        """Assign a role to an entity (agent, user, service)."""
        if role_id not in self._roles:
            raise ValueError(f"Unknown role '{role_id}'. "
                             f"Available: {list(self._roles.keys())}")
        self._assignments.setdefault(entity_id, set()).add(role_id)
        logger.info("RBAC: assigned role '%s' to entity '%s'", role_id, entity_id)
        self._save()

    def revoke_role(self, entity_id: str, role_id: str) -> None:
        """Remove a role assignment from an entity."""
        if entity_id in self._assignments:
            self._assignments[entity_id].discard(role_id)
            self._save()

    def check_permission(self, entity_id: str, permission: Permission) -> bool:
        """Return True if the entity holds any role that grants *permission*."""
        for role in self.get_roles(entity_id):
            if role.has_permission(permission):
                return True
        return False

    def get_roles(self, entity_id: str) -> list[Role]:
        """Return all Role objects assigned to an entity."""
        return [
            self._roles[rid]
            for rid in self._assignments.get(entity_id, set())
            if rid in self._roles
        ]

    def add_custom_role(self, role: Role) -> None:
        """Register a custom role. Overwrites if the role_id already exists."""
        self._roles[role.role_id] = role
        logger.info("RBAC: registered custom role '%s'", role.role_id)
        self._save()

    def list_roles(self) -> list[Role]:
        """Return all registered roles."""
        return list(self._roles.values())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "roles": {rid: r.to_dict() for rid, r in self._roles.items()},
            "assignments": {eid: list(rids)
                            for eid, rids in self._assignments.items()},
        }
        self._path.write_text(json.dumps(snapshot, indent=2))

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            snapshot = json.loads(self._path.read_text())
            for rid, rdata in snapshot.get("roles", {}).items():
                self._roles[rid] = Role.from_dict(rdata)
            for eid, role_list in snapshot.get("assignments", {}).items():
                self._assignments[eid] = set(role_list)
        except Exception as exc:
            logger.warning("RBAC: could not load persisted state: %s", exc)
