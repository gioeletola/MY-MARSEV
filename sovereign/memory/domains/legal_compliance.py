"""Memory domain: legal_compliance — contracts, obligations, deadlines, regulations."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/legal_compliance.json")
DOMAIN_NAME = "legal_compliance"


@dataclass
class Contract:
    contract_id: str
    title: str
    contract_type: str = "general"     # nda | employment | service | vendor | partnership | lease
    status: str = "active"             # draft | active | expired | terminated | pending_signature
    counterparty: str = ""
    start_date: str = ""
    end_date: str = ""
    renewal_date: str = ""
    key_obligations: list[str] = field(default_factory=list)
    key_rights: list[str] = field(default_factory=list)
    value: float = 0.0
    currency: str = "USD"
    auto_renew: bool = False
    jurisdiction: str = ""
    file_path: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceRequirement:
    req_id: str
    title: str
    regulation: str = ""              # GDPR | CCPA | SOC2 | ISO27001 | HIPAA | custom
    status: str = "pending"           # pending | compliant | non_compliant | reviewing
    deadline: str = ""
    responsible_party: str = ""
    description: str = ""
    evidence: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegalComplianceMemoryStore:
    def __init__(self, data_file: pathlib.Path = _DATA_FILE) -> None:
        self._path = data_file
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {"contracts": {}, "compliance": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_contract(self, contract: Contract) -> None:
        if not contract.created_at:
            contract.created_at = self._now()
        contract.updated_at = self._now()
        self._data["contracts"][contract.contract_id] = contract.to_dict()
        self._save()

    def active_contracts(self) -> list[Contract]:
        return [
            Contract(**{k: v for k, v in c.items() if k in Contract.__dataclass_fields__})
            for c in self._data["contracts"].values()
            if c.get("status") == "active"
        ]

    def expiring_contracts(self, days: int = 60) -> list[Contract]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
        return [
            Contract(**{k: v for k, v in c.items() if k in Contract.__dataclass_fields__})
            for c in self._data["contracts"].values()
            if c.get("end_date") and c["end_date"] <= cutoff and c.get("status") == "active"
        ]

    def add_compliance_req(self, req: ComplianceRequirement) -> None:
        if not req.created_at:
            req.created_at = self._now()
        self._data["compliance"][req.req_id] = req.to_dict()
        self._save()

    def non_compliant(self) -> list[ComplianceRequirement]:
        return [
            ComplianceRequirement(**{k: v for k, v in r.items() if k in ComplianceRequirement.__dataclass_fields__})
            for r in self._data["compliance"].values()
            if r.get("status") == "non_compliant"
        ]

    def to_context_string(self) -> str:
        active = len(self.active_contracts())
        expiring = len(self.expiring_contracts(60))
        non_comp = len(self.non_compliant())
        parts = [f"Active contracts: {active}"]
        if expiring:
            parts.append(f"Expiring (60d): {expiring}")
        if non_comp:
            parts.append(f"Non-compliant: {non_comp}")
        return " | ".join(parts)


store = LegalComplianceMemoryStore()
