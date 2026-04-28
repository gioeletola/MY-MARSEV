"""Memory domain: content — articles, posts, scripts, campaigns, content calendar."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/content.json")
DOMAIN_NAME = "content"


@dataclass
class ContentPiece:
    content_id: str
    title: str
    content_type: str = "article"      # article | post | video | podcast | newsletter | ad | script
    status: str = "draft"              # idea | draft | review | approved | published | archived
    platform: str = ""                 # blog | linkedin | twitter | youtube | instagram | email
    body: str = ""
    excerpt: str = ""
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    author: str = ""
    scheduled_at: str = ""
    published_at: str = ""
    url: str = ""
    performance: dict[str, Any] = field(default_factory=dict)  # views, likes, shares, conversions
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContentCalendarEntry:
    entry_id: str
    date: str                          # YYYY-MM-DD
    content_id: str = ""
    platform: str = ""
    content_type: str = ""
    title: str = ""
    status: str = "planned"            # planned | ready | published | skipped
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContentMemoryStore:
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
        return {"pieces": {}, "calendar": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_piece(self, piece: ContentPiece) -> None:
        if not piece.created_at:
            piece.created_at = self._now()
        piece.updated_at = self._now()
        self._data["pieces"][piece.content_id] = piece.to_dict()
        self._save()

    def by_status(self, status: str) -> list[ContentPiece]:
        return [
            ContentPiece(**{k: v for k, v in p.items() if k in ContentPiece.__dataclass_fields__})
            for p in self._data["pieces"].values()
            if p.get("status") == status
        ]

    def by_platform(self, platform: str) -> list[ContentPiece]:
        return [
            ContentPiece(**{k: v for k, v in p.items() if k in ContentPiece.__dataclass_fields__})
            for p in self._data["pieces"].values()
            if p.get("platform") == platform
        ]

    def add_calendar_entry(self, entry: ContentCalendarEntry) -> None:
        self._data["calendar"][entry.entry_id] = entry.to_dict()
        self._save()

    def calendar_range(self, from_date: str, to_date: str) -> list[ContentCalendarEntry]:
        return [
            ContentCalendarEntry(**{k: v for k, v in e.items() if k in ContentCalendarEntry.__dataclass_fields__})
            for e in self._data["calendar"].values()
            if from_date <= e.get("date", "") <= to_date
        ]

    def to_context_string(self) -> str:
        drafts = len(self.by_status("draft"))
        approved = len(self.by_status("approved"))
        published = len(self.by_status("published"))
        return f"Content: {drafts} drafts | {approved} approved | {published} published"


store = ContentMemoryStore()
