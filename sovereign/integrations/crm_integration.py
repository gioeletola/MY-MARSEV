"""
CRM integration — local JSON contact/deal store with optional HubSpot/Salesforce API.

Out-of-the-box behaviour (no credentials):
  - Contacts stored in data/memory/crm_contacts.json
  - Deals stored in data/memory/crm_deals.json
  - Activity log in data/memory/crm_activity.json

With credentials (IntegrationConfig.credentials):
  - hubspot_api_key → HubSpot REST stub (extend as needed)
"""
from __future__ import annotations

import json
import logging
import pathlib
import uuid
from datetime import datetime, timezone

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_CONTACTS_FILE = pathlib.Path("data/memory/crm_contacts.json")
_DEALS_FILE    = pathlib.Path("data/memory/crm_deals.json")
_ACTIVITY_FILE = pathlib.Path("data/memory/crm_activity.json")


def _load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(path: pathlib.Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class CRMIntegration(BaseIntegration):
    """
    CRM connector with local-first JSON storage.

    Contacts: id, name, email, phone, company, tags, created_at, updated_at
    Deals: id, title, value, stage, contact_id, created_at, updated_at
    Activity: id, contact_id, type, note, created_at
    """

    integration_id = "crm"
    name = "CRM Integration"

    # Pipeline stages (ordered)
    STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]

    def __init__(self) -> None:
        super().__init__()
        self._api_key: str = ""

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        self._api_key = (config.credentials or {}).get("hubspot_api_key", "")
        self._status = IntegrationStatus.CONNECTED
        logger.info("crm.connect: hubspot=%s", bool(self._api_key))
        return True

    def disconnect(self) -> bool:
        self._api_key = ""
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return True  # local store always available

    def fetch(self, resource: str, params: dict) -> dict:
        if resource == "contacts":
            return {"contacts": self.get_contacts(params.get("limit", 50))}
        if resource == "pipeline":
            return {"pipeline": self.get_pipeline()}
        return {}

    def push(self, resource: str, data: dict) -> dict:
        if resource == "contact":
            return self.create_contact(data)
        if resource == "deal":
            return self.create_deal(data)
        return {}

    # ------------------------------------------------------------------
    # Contact API
    # ------------------------------------------------------------------

    def get_contacts(self, limit: int = 50) -> list[dict]:
        """Return up to *limit* contacts, most recently created first."""
        contacts = _load(_CONTACTS_FILE)
        return list(reversed(contacts))[:limit]

    def create_contact(self, data: dict) -> dict:
        """Create a new contact record."""
        contact = {
            "id":         str(uuid.uuid4())[:8],
            "name":       data.get("name", ""),
            "email":      data.get("email", ""),
            "phone":      data.get("phone", ""),
            "company":    data.get("company", ""),
            "tags":       data.get("tags", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        contacts = _load(_CONTACTS_FILE)
        contacts.append(contact)
        _save(_CONTACTS_FILE, contacts)
        logger.info("crm.create_contact: '%s' <%s>", contact["name"], contact["email"])
        return contact

    def update_contact(self, contact_id: str, data: dict) -> bool:
        """Apply *data* updates to contact *contact_id*."""
        contacts = _load(_CONTACTS_FILE)
        for c in contacts:
            if c.get("id") == contact_id:
                c.update({k: v for k, v in data.items() if k != "id"})
                c["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save(_CONTACTS_FILE, contacts)
                return True
        return False

    def get_contact(self, contact_id: str) -> dict | None:
        for c in _load(_CONTACTS_FILE):
            if c.get("id") == contact_id:
                return c
        return None

    def search_contacts(self, query: str) -> list[dict]:
        q = query.lower()
        return [
            c for c in _load(_CONTACTS_FILE)
            if q in c.get("name", "").lower()
            or q in c.get("email", "").lower()
            or q in c.get("company", "").lower()
        ]

    # ------------------------------------------------------------------
    # Deal / Pipeline API
    # ------------------------------------------------------------------

    def get_pipeline(self) -> list[dict]:
        """Return all deals grouped by stage."""
        deals = _load(_DEALS_FILE)
        pipeline: dict[str, list] = {s: [] for s in self.STAGES}
        for d in deals:
            stage = d.get("stage", "lead")
            if stage in pipeline:
                pipeline[stage].append(d)
        return [{"stage": s, "deals": pipeline[s]} for s in self.STAGES]

    def create_deal(self, data: dict) -> dict:
        """Create a new deal record."""
        deal = {
            "id":         str(uuid.uuid4())[:8],
            "title":      data.get("title", ""),
            "value":      float(data.get("value", 0.0)),
            "stage":      data.get("stage", "lead"),
            "contact_id": data.get("contact_id", ""),
            "notes":      data.get("notes", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        deals = _load(_DEALS_FILE)
        deals.append(deal)
        _save(_DEALS_FILE, deals)
        logger.info("crm.create_deal: '%s' at stage '%s'", deal["title"], deal["stage"])
        return deal

    def advance_deal(self, deal_id: str) -> bool:
        """Move a deal to the next pipeline stage."""
        deals = _load(_DEALS_FILE)
        for d in deals:
            if d.get("id") == deal_id:
                try:
                    idx = self.STAGES.index(d["stage"])
                    if idx < len(self.STAGES) - 1:
                        d["stage"] = self.STAGES[idx + 1]
                        d["updated_at"] = datetime.now(timezone.utc).isoformat()
                        _save(_DEALS_FILE, deals)
                        return True
                except (ValueError, KeyError):
                    pass
        return False

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------

    def log_activity(self, contact_id: str, activity: dict) -> bool:
        """Append an activity record for *contact_id*."""
        entry = {
            "id":         str(uuid.uuid4())[:8],
            "contact_id": contact_id,
            "type":       activity.get("type", "note"),
            "note":       activity.get("note", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        log = _load(_ACTIVITY_FILE)
        log.append(entry)
        _save(_ACTIVITY_FILE, log)
        return True

    def get_activity(self, contact_id: str) -> list[dict]:
        """Return all activity records for *contact_id*."""
        return [a for a in _load(_ACTIVITY_FILE) if a.get("contact_id") == contact_id]
