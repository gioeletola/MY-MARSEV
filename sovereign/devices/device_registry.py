"""Device registry — tracks all connected physical and virtual devices."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/devices.json")


class DeviceType(str, Enum):
    CAMERA = "camera"
    MICROPHONE = "microphone"
    SPEAKER = "speaker"
    DISPLAY = "display"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    SENSOR = "sensor"
    NETWORK = "network"
    STORAGE = "storage"
    VIRTUAL = "virtual"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class Device:
    device_id: str
    name: str
    device_type: DeviceType
    status: DeviceStatus = DeviceStatus.UNKNOWN
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    trusted: bool = False


class DeviceRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        self._auto_discover()

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text())
                for d in raw:
                    d["device_type"] = DeviceType(d.get("device_type", "virtual"))
                    d["status"] = DeviceStatus(d.get("status", "unknown"))
                    self._devices[d["device_id"]] = Device(**d)
            except Exception:
                pass

    def _save(self) -> None:
        data = [{**d.__dict__, "device_type": d.device_type.value, "status": d.status.value}
                for d in self._devices.values()]
        _DATA_FILE.write_text(json.dumps(data, indent=2))

    def _auto_discover(self) -> None:
        """Detect common devices on the host system."""
        candidates = [
            Device("cam_0", "Default Camera", DeviceType.CAMERA,
                   capabilities=["video_capture", "face_detection"]),
            Device("mic_0", "Default Microphone", DeviceType.MICROPHONE,
                   capabilities=["audio_capture", "wake_word"]),
            Device("spk_0", "Default Speaker", DeviceType.SPEAKER,
                   capabilities=["audio_playback", "tts"]),
            Device("disp_0", "Primary Display", DeviceType.DISPLAY,
                   capabilities=["overlay", "hud"]),
        ]
        for dev in candidates:
            if dev.device_id not in self._devices:
                self._devices[dev.device_id] = dev

    def register(self, device: Device) -> None:
        self._devices[device.device_id] = device
        self._save()

    def get(self, device_id: str) -> Device | None:
        return self._devices.get(device_id)

    def update_status(self, device_id: str, status: DeviceStatus) -> bool:
        if dev := self._devices.get(device_id):
            dev.status = status
            dev.last_seen_at = time.time()
            self._save()
            return True
        return False

    def online_devices(self) -> list[Device]:
        return [d for d in self._devices.values() if d.status == DeviceStatus.ONLINE]

    def by_type(self, device_type: DeviceType) -> list[Device]:
        return [d for d in self._devices.values() if d.device_type == device_type]

    def all_devices(self) -> list[Device]:
        return list(self._devices.values())

    def summary(self) -> dict:
        return {
            "total": len(self._devices),
            "online": sum(1 for d in self._devices.values() if d.status == DeviceStatus.ONLINE),
            "types": {dt.value: len(self.by_type(dt)) for dt in DeviceType},
        }
