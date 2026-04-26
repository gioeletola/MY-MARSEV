"""
NotebookLM connector — syncs notebooks, sources, and generated notes via
Google Drive (where NotebookLM stores its data) and the Google Docs API.
Auth: Google OAuth access token or GOOGLE_ACCESS_TOKEN env var.
Falls back to reading exported markdown files from a local sync folder.
"""
from __future__ import annotations

import logging
import os
import pathlib
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_DRIVE_API = "https://www.googleapis.com/drive/v3"
_DOCS_API = "https://docs.googleapis.com/v1"


class NotebookLMConnector(ConnectorBase):
    connector_id = "notebooklm"
    connector_name = "NotebookLM"
    connector_description = (
        "Syncs NotebookLM notebooks and AI-generated notes via Google Drive "
        "integration. Falls back to local exported markdown files."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = True
    required_scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = self._config.get("access_token") or os.getenv("GOOGLE_ACCESS_TOKEN", "")
        self._local_path = pathlib.Path(
            self._config.get("local_export_path", "data/notebooklm")
        )
        self._data: dict[str, Any] = {"notebooks": [], "notes": []}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def connect(self) -> bool:
        if self._local_path.exists():
            self._logger.info("NotebookLMConnector: using local export path %s", self._local_path)
            return True
        if not self._token:
            self._logger.warning("NotebookLMConnector: no token and no local path")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_DRIVE_API}/about",
                    headers=self._headers(),
                    params={"fields": "user"},
                )
                if resp.status_code == 200:
                    user = resp.json().get("user", {})
                    self._logger.info("NotebookLMConnector: connected as %s", user.get("emailAddress"))
                    return True
                return False
        except Exception as exc:
            self._logger.error("NotebookLMConnector connect error: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._data = {"notebooks": [], "notes": []}

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []

        # Try local export first
        if self._local_path.exists():
            md_files = list(self._local_path.glob("**/*.md"))
            notebooks = []
            for f in md_files:
                try:
                    content = f.read_text(encoding="utf-8")
                    notebooks.append({"title": f.stem, "content": content[:2000], "path": str(f)})
                    records += 1
                except Exception as exc:
                    errors.append(f"file {f.name}: {exc}")
            self._data["notebooks"] = notebooks
            result = SyncResult(self.connector_id, not errors, records, errors)
            self._mark_sync(result)
            return result

        # Google Drive API fallback
        if not self._token:
            return SyncResult(self.connector_id, False, errors=["No token and no local path"])

        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Search for NotebookLM-created documents
                r = await client.get(
                    f"{_DRIVE_API}/files",
                    headers=self._headers(),
                    params={
                        "q": "mimeType='application/vnd.google-apps.document' and name contains 'Notebook'",
                        "fields": "files(id,name,modifiedTime)",
                        "pageSize": 50,
                    },
                )
                if r.status_code == 200:
                    files = r.json().get("files", [])
                    self._data["notebooks"] = files
                    records += len(files)
                else:
                    errors.append(f"drive files: {r.status_code}")
        except Exception as exc:
            errors.append(str(exc))

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        connected = bool(self._token) or self._local_path.exists()
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.CONNECTED if connected else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            metadata={
                "notebook_count": len(self._data.get("notebooks", [])),
                "local_path": str(self._local_path),
                "local_exists": self._local_path.exists(),
            },
        )

    def get_notebooks(self) -> list[dict]:
        return self._data.get("notebooks", [])

    def search_notes(self, query: str) -> list[dict]:
        """Simple keyword search across synced notebooks."""
        q = query.lower()
        return [
            nb for nb in self._data.get("notebooks", [])
            if q in nb.get("title", "").lower() or q in nb.get("content", "").lower()
        ]
