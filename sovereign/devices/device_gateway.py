"""Device gateway — unified interface for reading/writing to registered devices."""
from __future__ import annotations

import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable

from sovereign.devices.device_registry import DeviceRegistry, DeviceStatus

logger = logging.getLogger(__name__)


# ── Device capability enum ────────────────────────────────────────────────────

class DeviceCapability(str, Enum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    DISPLAY = "display"
    AUDIO = "audio"
    CAMERA = "camera"
    NETWORK = "network"
    STORAGE = "storage"


# ── DeviceInfo ────────────────────────────────────────────────────────────────

@dataclass
class DeviceInfo:
    device_id: str
    name: str
    type: str                                   # DeviceType.value string
    capabilities: list[str] = field(default_factory=list)
    status: str = "unknown"                     # DeviceStatus.value string
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.type,
            "capabilities": self.capabilities,
            "status": self.status,
            "last_seen": self.last_seen,
        }


# ── Device Gateway ────────────────────────────────────────────────────────────

class DeviceGateway:
    """
    Single access point for all device I/O.
    Routes commands to the correct device driver stub.
    Supports MQTT, Home Assistant REST API, barcode scanning, and sensor reads.
    """

    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry
        self._drivers: dict[str, Any] = {}
        self._mqtt_client: Any = None
        self._mqtt_connected: bool = False
        self._hass_base_url: str | None = None
        self._hass_token: str | None = None

    # ── Discovery & connection ────────────────────────────────────────────

    async def discover(self) -> list[DeviceInfo]:
        """Scan for connected devices and return their descriptors."""
        discovered: list[DeviceInfo] = []
        for dev in self._registry.all_devices():
            info = DeviceInfo(
                device_id=dev.device_id,
                name=dev.name,
                type=dev.device_type.value,
                capabilities=list(dev.capabilities),
                status=dev.status.value,
                last_seen=dev.last_seen_at,
            )
            discovered.append(info)

        # Probe for camera
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()
                cam_id = "cam_0"
                if not any(d.device_id == cam_id for d in discovered):
                    discovered.append(DeviceInfo(
                        device_id=cam_id, name="Default Camera",
                        type="camera",
                        capabilities=[DeviceCapability.CAMERA, DeviceCapability.SENSOR],
                        status="online",
                    ))
        except Exception:
            pass

        logger.info("DeviceGateway.discover: found %d devices", len(discovered))
        return discovered

    async def connect(self, device_id: str) -> bool:
        """Attempt to connect / verify a device.  Returns True on success."""
        dev = self._registry.get(device_id)
        if not dev:
            logger.warning("DeviceGateway.connect: device %s not registered", device_id)
            return False
        # Mark as online — driver-level connectivity is checked via send_command
        self._registry.update_status(device_id, DeviceStatus.ONLINE)
        logger.info("DeviceGateway.connect: %s set to ONLINE", device_id)
        return True

    async def send_command(
        self, device_id: str, command: str, payload: dict | None = None
    ) -> dict:
        """Dispatch a command to a device driver."""
        dev = self._registry.get(device_id)
        if not dev:
            logger.warning("send_command: device %s not registered", device_id)
            return {"ok": False, "error": f"Device {device_id!r} not registered"}

        driver = self._drivers.get(device_id)
        if driver:
            try:
                result = await driver(command, payload or {})
                self._registry.update_status(device_id, DeviceStatus.ONLINE)
                return {"ok": True, "result": result}
            except Exception as exc:
                logger.warning("Driver error for %s: %s", device_id, exc)
                self._registry.update_status(device_id, DeviceStatus.ERROR)
                return {"ok": False, "error": str(exc)}

        logger.debug(
            "send_command(device=%s, cmd=%s, payload=%s) — stub ACK",
            device_id, command, payload,
        )
        self._registry.update_status(device_id, DeviceStatus.ONLINE)
        return {"ok": True, "result": None, "stub": True}

    # ── Core device I/O ───────────────────────────────────────────────────

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

    async def read_sensor(self, device_id: str, sensor_key: str) -> Any:
        dev = self._registry.get(device_id)
        if not dev:
            logger.warning("read_sensor: device %s not registered", device_id)
            return None
        driver = self._drivers.get(device_id)
        if driver:
            try:
                return await driver(f"read:{sensor_key}", {})
            except Exception as exc:
                logger.warning("Sensor read error (%s/%s): %s", device_id, sensor_key, exc)
                return None
        logger.debug("read_sensor(device=%s, key=%s) — stub None", device_id, sensor_key)
        return None

    def register_driver(self, device_id: str, driver_fn: Callable) -> None:
        """Register an async callable as the driver for a device."""
        self._drivers[device_id] = driver_fn

    # ── MQTT ──────────────────────────────────────────────────────────────

    def connect_mqtt(
        self,
        broker: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
    ) -> bool:
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError:
            logger.warning("paho-mqtt not installed — MQTT disabled")
            return False

        def _on_connect(client, userdata, flags, rc):
            if rc == 0:
                self._mqtt_connected = True
                logger.info("MQTT connected to %s:%d", broker, port)
            else:
                logger.warning("MQTT connect failed, rc=%d", rc)

        def _on_disconnect(client, userdata, rc):
            self._mqtt_connected = False

        try:
            client = mqtt.Client()
            client.on_connect = _on_connect
            client.on_disconnect = _on_disconnect
            if username:
                client.username_pw_set(username, password)
            client.connect(broker, port, keepalive=60)
            client.loop_start()
            self._mqtt_client = client
            return True
        except Exception as exc:
            logger.warning("MQTT connection error: %s", exc)
            return False

    def publish(self, topic: str, payload: Any) -> bool:
        if self._mqtt_client is None:
            return False
        try:
            import json as _json
            msg = payload if isinstance(payload, (str, bytes)) else _json.dumps(payload)
            result = self._mqtt_client.publish(topic, msg)
            return result.rc == 0
        except Exception as exc:
            logger.warning("MQTT publish error: %s", exc)
            return False

    def subscribe(self, topic: str, callback: Callable[[str, Any], None]) -> bool:
        if self._mqtt_client is None:
            return False
        try:
            import json as _json

            def _on_message(client, userdata, msg):
                try:
                    data = msg.payload.decode("utf-8")
                    try:
                        data = _json.loads(data)
                    except Exception:
                        pass
                    callback(msg.topic, data)
                except Exception as exc:
                    logger.warning("MQTT message handler error: %s", exc)

            self._mqtt_client.subscribe(topic)
            self._mqtt_client.message_callback_add(topic, _on_message)
            return True
        except Exception as exc:
            logger.warning("MQTT subscribe error: %s", exc)
            return False

    # ── Home Assistant ─────────────────────────────────────────────────────

    def connect_hass(self, base_url: str, token: str) -> None:
        self._hass_base_url = base_url.rstrip("/")
        self._hass_token = token

    async def hass_call_service(
        self,
        domain: str,
        service: str,
        entity_id: str | None = None,
        data: dict | None = None,
    ) -> dict:
        if not self._hass_base_url or not self._hass_token:
            return {"ok": False, "error": "Home Assistant not configured"}
        url = f"{self._hass_base_url}/api/services/{domain}/{service}"
        body: dict = dict(data or {})
        if entity_id:
            body["entity_id"] = entity_id
        try:
            import httpx  # type: ignore
            headers = {
                "Authorization": f"Bearer {self._hass_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, headers=headers)
                resp.raise_for_status()
                return {"ok": True, "status": resp.status_code, "result": resp.json()}
        except ImportError:
            return {"ok": False, "error": "httpx not installed"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def hass_get_state(self, entity_id: str) -> dict:
        if not self._hass_base_url or not self._hass_token:
            return {"ok": False, "error": "Home Assistant not configured"}
        url = f"{self._hass_base_url}/api/states/{entity_id}"
        try:
            import httpx  # type: ignore
            headers = {"Authorization": f"Bearer {self._hass_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return {"ok": True, "state": resp.json()}
        except ImportError:
            return {"ok": False, "error": "httpx not installed"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ── Barcode / QR scanner ───────────────────────────────────────────────

    def scan_barcode(self, image_bytes: bytes) -> str | None:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
            from pyzbar import pyzbar  # type: ignore
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            codes = pyzbar.decode(img)
            if codes:
                return codes[0].data.decode("utf-8", errors="replace")
            return None
        except ImportError:
            return None
        except Exception as exc:
            logger.warning("scan_barcode error: %s", exc)
            return None

    # ── Status overview ────────────────────────────────────────────────────

    def get_all_status(self) -> dict:
        return {
            dev.device_id: {
                "name": dev.name,
                "type": dev.device_type.value,
                "status": dev.status.value,
                "last_seen_at": dev.last_seen_at,
                "trusted": dev.trusted,
                "capabilities": dev.capabilities,
            }
            for dev in self._registry.all_devices()
        }
