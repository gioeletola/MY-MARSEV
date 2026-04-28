"""Memory domain: research — research projects, findings, sources, hypotheses."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/research.json")
DOMAIN_NAME = "research"


@dataclass
class ResearchProject:
    project_id: str
    title: str
    status: str = "active"             # planning | active | paused | completed | archived
    research_type: str = "exploratory" # exploratory | confirmatory | applied | literature_review
    objective: str = ""
    hypothesis: str = ""
    methodology: str = ""
    domains: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchFinding:
    finding_id: str
    project_id: str
    title: str
    content: str = ""
    confidence: float = 0.7            # 0–1
    source_ids: list[str] = field(default_factory=list)
    implications: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchSource:
    source_id: str
    title: str
    source_type: str = "web"           # web | paper | book | interview | dataset | patent
    url: str = ""
    authors: list[str] = field(default_factory=list)
    published_date: str = ""
    credibility: float = 0.8           # 0–1
    summary: str = ""
    key_quotes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    added_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchMemoryStore:
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
        return {"projects": {}, "findings": {}, "sources": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_project(self, project: ResearchProject) -> None:
        if not project.created_at:
            project.created_at = self._now()
        project.updated_at = self._now()
        self._data["projects"][project.project_id] = project.to_dict()
        self._save()

    def active_projects(self) -> list[ResearchProject]:
        return [
            ResearchProject(**{k: v for k, v in p.items() if k in ResearchProject.__dataclass_fields__})
            for p in self._data["projects"].values()
            if p.get("status") == "active"
        ]

    def add_finding(self, finding: ResearchFinding) -> None:
        if not finding.created_at:
            finding.created_at = self._now()
        self._data["findings"][finding.finding_id] = finding.to_dict()
        self._save()

    def findings_for_project(self, project_id: str) -> list[ResearchFinding]:
        return [
            ResearchFinding(**{k: v for k, v in f.items() if k in ResearchFinding.__dataclass_fields__})
            for f in self._data["findings"].values()
            if f.get("project_id") == project_id
        ]

    def add_source(self, source: ResearchSource) -> None:
        if not source.added_at:
            source.added_at = self._now()
        self._data["sources"][source.source_id] = source.to_dict()
        self._save()

    def high_credibility_sources(self, threshold: float = 0.8) -> list[ResearchSource]:
        return [
            ResearchSource(**{k: v for k, v in s.items() if k in ResearchSource.__dataclass_fields__})
            for s in self._data["sources"].values()
            if s.get("credibility", 0.0) >= threshold
        ]

    def to_context_string(self) -> str:
        active = len(self.active_projects())
        findings = len(self._data["findings"])
        sources = len(self._data["sources"])
        return f"Research: {active} active projects | {findings} findings | {sources} sources"


store = ResearchMemoryStore()
