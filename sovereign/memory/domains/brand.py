"""Memory domain: brand — personal/company brand identity, assets, messaging."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/brand.json")
DOMAIN_NAME = "brand"


@dataclass
class BrandIdentity:
    name: str = ""
    tagline: str = ""
    mission: str = ""
    vision: str = ""
    tone_of_voice: str = "professional"   # professional | casual | bold | empathetic
    target_audience: list[str] = field(default_factory=list)
    brand_values: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    colors: dict[str, str] = field(default_factory=dict)
    fonts: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrandAsset:
    asset_id: str
    asset_type: str           # logo | icon | banner | template | copy | video
    name: str = ""
    url: str = ""
    local_path: str = ""
    variant: str = ""         # light | dark | color | mono
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrandMemoryStore:
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
        return {"identity": {}, "assets": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def get_identity(self) -> BrandIdentity:
        return BrandIdentity(**{
            k: v for k, v in self._data.get("identity", {}).items()
            if k in BrandIdentity.__dataclass_fields__
        })

    def update_identity(self, **kwargs: Any) -> None:
        self._data.setdefault("identity", {}).update(kwargs)
        self._save()

    def add_asset(self, asset: BrandAsset) -> None:
        self._data.setdefault("assets", {})[asset.asset_id] = asset.to_dict()
        self._save()

    def get_assets(self, asset_type: str | None = None) -> list[BrandAsset]:
        assets = [
            BrandAsset(**{k: v for k, v in a.items() if k in BrandAsset.__dataclass_fields__})
            for a in self._data.get("assets", {}).values()
        ]
        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        return assets

    def to_context_string(self) -> str:
        ident = self.get_identity()
        parts = []
        if ident.name:
            parts.append(f"Brand: {ident.name}")
        if ident.tagline:
            parts.append(f"Tagline: {ident.tagline}")
        if ident.tone_of_voice:
            parts.append(f"Tone: {ident.tone_of_voice}")
        return " | ".join(parts) if parts else "Brand not configured."


store = BrandMemoryStore()
