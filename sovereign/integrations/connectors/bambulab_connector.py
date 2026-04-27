"""
Bambu Lab connector — 3D printer management via Bambu Cloud API and local MQTT.
Auth: Bambu Cloud (BAMBULAB_EMAIL, BAMBULAB_PASSWORD) + local MQTT (BAMBULAB_PRINTER_IP).
Status: BETA — MQTT local protocol partially documented by community reverse engineering.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

logger = logging.getLogger(__name__)
_API_BASE = "https://api.bambulab.com/v1"


class BambuLabConnector(ConnectorBase):
    connector_id = "bambulab"
    connector_name = "Bambu Lab"
    connector_description = (
        "Manages Bambu Lab 3D printers via Bambu Cloud API and local MQTT. "
        "Tracks printer status, print jobs, and filament inventory."
    )
    connector_status = ConnectorStatus.BETA
    requires_oauth = False
    required_env_vars = ["BAMBULAB_EMAIL", "BAMBULAB_PASSWORD"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._email = self._config.get("email") or os.getenv("BAMBULAB_EMAIL", "")
        self._password = self._config.get("password") or os.getenv("BAMBULAB_PASSWORD", "")
        self._printer_ip = self._config.get("printer_ip") or os.getenv("BAMBULAB_PRINTER_IP", "")
        self._access_token: str = ""
        self.api_base = _API_BASE
        self._data: dict[str, Any] = {}
        self._error_count = 0

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        if not self._email or not self._password:
            self._logger.warning("BambuLabConnector: missing credentials")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.api_base}/user-service/user/login",
                    json={"account": self._email, "password": self._password},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self._access_token = data.get("accessToken", "")
                    self._logger.info("BambuLabConnector: authenticated")
                    return bool(self._access_token)
                self._logger.warning("BambuLab login returned %d", resp.status_code)
                return False
        except Exception as exc:
            self._logger.error("BambuLabConnector connect error: %s", exc)
            self._error_count += 1
            return False

    async def disconnect(self) -> None:
        self._access_token = ""
        self._data.clear()

    async def sync(self) -> SyncResult:
        records = 0
        errors: list[str] = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                # List printers / devices
                r = await client.get(
                    f"{self.api_base}/iot-service/api/user/bind",
                    headers=self._headers(),
                )
                if r.status_code == 200:
                    devices = r.json().get("devices", [])
                    self._data["printers"] = devices
                    records += len(devices)
                else:
                    errors.append(f"printers: {r.status_code}")

                # Filament/spool data (Bambu Handy API)
                r2 = await client.get(
                    f"{self.api_base}/filament-service/api/filament/list",
                    headers=self._headers(),
                )
                if r2.status_code == 200:
                    spools = r2.json().get("filaments", [])
                    self._data["filaments"] = spools
                    records += len(spools)
                else:
                    errors.append(f"filaments: {r2.status_code}")

        except Exception as exc:
            errors.append(str(exc))
            self._error_count += 1

        result = SyncResult(self.connector_id, not errors, records, errors)
        self._mark_sync(result)
        return result

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=ConnectorStatus.BETA if self._access_token else ConnectorStatus.DISCONNECTED,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
            latency_ms=0.0,
            metadata={
                "printer_count": len(self._data.get("printers", [])),
                "has_local_ip": bool(self._printer_ip),
                "error_count": self._error_count,
            },
        )

    async def get_printer_status(self, device_id: str | None = None) -> dict:
        """Get current status of a printer. Uses first printer if device_id not given."""
        printers = self._data.get("printers", [])
        if not printers:
            return {"error": "no printers found, run sync() first"}
        target = device_id or printers[0].get("dev_id", "")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/iot-service/api/user/device/version",
                    headers=self._headers(),
                    params={"dev_id": target},
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": resp.status_code}
        except Exception as exc:
            self._logger.error("get_printer_status error: %s", exc)
            return {"error": str(exc)}

    async def start_print(self, device_id: str, file_path: str, plate_id: int = 1) -> dict:
        """
        Send a print job to a Bambu printer via cloud push.
        file_path should be the path to the .3mf on Bambu Cloud storage.
        """
        try:
            import httpx
            payload = {
                "dev_id": device_id,
                "task": {
                    "taskId": f"task_{int(__import__('time').time())}",
                    "profileId": plate_id,
                    "url": file_path,
                }
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.api_base}/iot-service/api/user/task",
                    headers=self._headers(),
                    json=payload,
                )
                return resp.json()
        except Exception as exc:
            self._logger.error("start_print error: %s", exc)
            return {"error": str(exc)}

    async def get_filament_inventory(self) -> list[dict]:
        """Return list of filament spools with color, material, and remaining weight."""
        filaments = self._data.get("filaments", [])
        if filaments:
            return filaments
        # Re-fetch if not cached
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/filament-service/api/filament/list",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    self._data["filaments"] = resp.json().get("filaments", [])
                    return self._data["filaments"]
        except Exception as exc:
            self._logger.error("get_filament_inventory error: %s", exc)
        return []

    def list_printers(self) -> list[dict]:
        """Return cached printer list."""
        return self._data.get("printers", [])
