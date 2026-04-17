"""Device gateway — unified interface for reading/writing to registered devices."""
from __future__ import annotations

import logging
from typing import Any

from sovereign.devices.device_registry import DeviceRegistry, DeviceStatus

logger = logging.getLogger(__name__)


class DeviceGateway:
    """
    Single access point for all device I/O.
    Routes commands to the correct device driver stub.
    """

    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry

    async def capture_frame(self, device_id: str = "cam_0") -> bytes | None:
        dev = self._registry.get(device_id)
        if not dev:
            logger.warning("Device %s not registered", device_id)
            return None
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            import cv2
            _, buf = cv2.imencode(".jpg", frame)
            self._registry.update_status(device_id, DeviceStatus.ONLINE)
            return bytes(buf)
        except Exception as exc:
            logger.warning("Camera capture failed: %s", exc)
            self._registry.update_status(device_id, DeviceStatus.ERROR)
            return None

    async def play_audio(self, text: str, device_id: str = "spk_0") -> bool:
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            self._registry.update_status(device_id, DeviceStatus.ONLINE)
            return True
        except Exception as exc:
            logger.warning("TTS failed: %s", exc)
            return False

    def ping(self, device_id: str) -> bool:
        dev = self._registry.get(device_id)
        return dev is not None

    def list_capabilities(self, device_id: str) -> list[str]:
        dev = self._registry.get(device_id)
        return dev.capabilities if dev else []
