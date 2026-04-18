"""Entity Vault Manager — per-entity isolated storage namespace."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_VAULTS_ROOT = Path("data/memory/vaults")


class EntityVault:
    """Provides isolated key/value and file storage for each ConnectedEntity.

    Each entity gets its own sub-directory under *vaults_root*:
      ``<vaults_root>/<entity_id>.json``   — key/value store
      ``<vaults_root>/<entity_id>/files/`` — attached files
    """

    def __init__(self, vaults_root: str | Path = _DEFAULT_VAULTS_ROOT) -> None:
        self._root = Path(vaults_root)

    # ------------------------------------------------------------------
    # Vault lifecycle
    # ------------------------------------------------------------------

    def create_vault(self, entity_id: str, category: str = "") -> bool:
        """Create storage namespace for *entity_id*.

        Idempotent — safe to call if vault already exists.
        Returns True.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        vault_path = self._vault_path(entity_id)
        if not vault_path.exists():
            vault_path.write_text(
                json.dumps({"_meta": {"entity_id": entity_id, "category": category}}, indent=2),
                encoding="utf-8",
            )
        files_dir = self._files_dir(entity_id)
        files_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("EntityVault: created vault for %s", entity_id)
        return True

    def delete_vault(self, entity_id: str) -> bool:
        """Remove all vault data (kv + files) for *entity_id*."""
        removed = False
        vault_path = self._vault_path(entity_id)
        if vault_path.exists():
            vault_path.unlink()
            removed = True
        files_dir = self._files_dir(entity_id)
        if files_dir.exists():
            shutil.rmtree(files_dir, ignore_errors=True)
            removed = True
        logger.debug("EntityVault: deleted vault for %s", entity_id)
        return removed

    # ------------------------------------------------------------------
    # Key/value operations
    # ------------------------------------------------------------------

    def write(self, entity_id: str, key: str, value: object) -> bool:
        """Write *key=value* into the entity's vault.

        Creates the vault if it does not already exist.
        """
        data = self._load(entity_id)
        data[key] = value
        self._save(entity_id, data)
        return True

    def read(self, entity_id: str, key: str) -> object:
        """Read *key* from the entity's vault. Returns None if missing."""
        data = self._load(entity_id)
        return data.get(key)

    def list_keys(self, entity_id: str) -> list[str]:
        """Return all user keys (excludes internal ``_meta``)."""
        data = self._load(entity_id)
        return [k for k in data if not k.startswith("_")]

    # ------------------------------------------------------------------
    # File attachments
    # ------------------------------------------------------------------

    def attach_file(self, entity_id: str, filepath: str | Path) -> str | None:
        """Copy *filepath* into the entity's files directory.

        Returns the destination filename, or None on error.
        """
        src = Path(filepath)
        if not src.exists():
            logger.warning("EntityVault.attach_file: source not found — %s", filepath)
            return None
        dest_dir = self._files_dir(entity_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        try:
            shutil.copy2(str(src), str(dest))
            logger.debug("EntityVault: attached file %s → %s", src.name, dest)
            return src.name
        except OSError as exc:
            logger.error("EntityVault.attach_file: copy failed — %s", exc)
            return None

    def list_files(self, entity_id: str) -> list[str]:
        """Return filenames of all attachments for *entity_id*."""
        files_dir = self._files_dir(entity_id)
        if not files_dir.exists():
            return []
        return [f.name for f in files_dir.iterdir() if f.is_file()]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_vault_summary(self, entity_id: str) -> dict:
        """Return ``{entity_id, key_count, file_count, size_bytes}``."""
        keys = self.list_keys(entity_id)
        files = self.list_files(entity_id)

        size_bytes = 0
        vault_path = self._vault_path(entity_id)
        if vault_path.exists():
            size_bytes += vault_path.stat().st_size
        files_dir = self._files_dir(entity_id)
        if files_dir.exists():
            for f in files_dir.iterdir():
                if f.is_file():
                    try:
                        size_bytes += f.stat().st_size
                    except OSError:
                        pass

        return {
            "entity_id": entity_id,
            "key_count": len(keys),
            "file_count": len(files),
            "size_bytes": size_bytes,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _vault_path(self, entity_id: str) -> Path:
        return self._root / f"{entity_id}.json"

    def _files_dir(self, entity_id: str) -> Path:
        return self._root / entity_id / "files"

    def _load(self, entity_id: str) -> dict:
        path = self._vault_path(entity_id)
        if not path.exists():
            # Auto-create empty vault
            self.create_vault(entity_id)
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("EntityVault._load: could not read vault %s — %s", entity_id, exc)
            return {}

    def _save(self, entity_id: str, data: dict) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._vault_path(entity_id)
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.error("EntityVault._save: failed for %s — %s", entity_id, exc)
