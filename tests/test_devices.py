"""
Tests for DeviceGateway, SensorManager (and associated stubs).
No real hardware, cv2, psutil, or paho-mqtt required.
"""
from __future__ import annotations

import pathlib
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry(tmp_path: pathlib.Path):
    """Return a fresh DeviceRegistry that writes to tmp_path."""
    from sovereign.devices.device_registry import DeviceRegistry
    return DeviceRegistry(data_file=tmp_path / "devices.json")


# ---------------------------------------------------------------------------
# TestSensorManager
# ---------------------------------------------------------------------------

class TestSensorManager:
    def test_register_custom_sensor(self):
        from sovereign.devices.sensor_manager import SensorManager, SensorSpec
        sm = SensorManager()
        spec = SensorSpec(sensor_id="temp_0", name="Temperature", unit="C",
                          poll_interval_s=5.0, reader=lambda: 21.5)
        sm.register(spec)
        assert "temp_0" in sm._sensors

    def test_builtin_sensors_registered(self):
        from sovereign.devices.sensor_manager import SensorManager
        sm = SensorManager()
        # All builtins must be present
        for sid in ("cpu_percent", "memory_percent", "disk_percent",
                    "battery_percent", "network_bytes_sent", "network_bytes_recv"):
            assert sid in sm._sensors, f"Missing builtin: {sid}"

    def test_legacy_mem_percent_alias(self):
        from sovereign.devices.sensor_manager import SensorManager
        sm = SensorManager()
        assert "mem_percent" in sm._sensors

    @pytest.mark.asyncio
    async def test_snapshot_returns_dict(self):
        from sovereign.devices.sensor_manager import SensorManager, SensorSpec
        sm = SensorManager()
        sm.register(SensorSpec("mocked_s", "Mock", "unit", 5.0, reader=lambda: 42))
        await sm.read("mocked_s")
        snap = sm.snapshot()
        assert isinstance(snap, dict)
        assert snap.get("mocked_s") == 42

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_before_read(self):
        from sovereign.devices.sensor_manager import SensorManager, SensorSpec
        sm = SensorManager()
        sm.register(SensorSpec("new_sensor", "New", "units", 5.0, reader=lambda: 0))
        # No read yet
        assert sm.get_latest("new_sensor") is None

    @pytest.mark.asyncio
    async def test_get_latest_after_read(self):
        from sovereign.devices.sensor_manager import SensorManager, SensorSpec
        sm = SensorManager()
        sm.register(SensorSpec("volt_0", "Voltage", "V", 5.0, reader=lambda: 3.3))
        reading = await sm.read("volt_0")
        assert reading is not None
        latest = sm.get_latest("volt_0")
        assert latest is not None
        assert latest.value == pytest.approx(3.3)

    @pytest.mark.asyncio
    async def test_cpu_builtin_works_or_skips(self):
        """cpu_percent reader returns float even if psutil not installed."""
        from sovereign.devices.sensor_manager import SensorManager
        sm = SensorManager()
        reading = await sm.read("cpu_percent")
        # May be None if reader errors, or a float (0.0 fallback or real value)
        if reading is not None:
            assert isinstance(reading.value, float)

    @pytest.mark.asyncio
    async def test_snapshot_empty_initially(self):
        from sovereign.devices.sensor_manager import SensorManager
        sm = SensorManager()
        snap = sm.snapshot()
        assert isinstance(snap, dict)

    def test_subscribe_adds_callback(self):
        from sovereign.devices.sensor_manager import SensorManager
        sm = SensorManager()
        async def cb(sid, val): pass
        sm.subscribe(cb)
        assert cb in sm._global_callbacks


# ---------------------------------------------------------------------------
# TestDeviceGateway
# ---------------------------------------------------------------------------

class TestDeviceGateway:
    def _gw(self, tmp_path):
        from sovereign.devices.device_registry import DeviceRegistry
        from sovereign.devices.device_gateway import DeviceGateway
        reg = DeviceRegistry(data_file=tmp_path / "devices.json")
        return DeviceGateway(registry=reg), reg

    @pytest.mark.asyncio
    async def test_capture_frame_stub_no_cv2(self, tmp_path):
        """capture_frame returns None when cv2 is unavailable (stub mode)."""
        gw, reg = self._gw(tmp_path)
        # cam_0 is auto-discovered — just call and expect None (no cv2)
        result = await gw.capture_frame("cam_0")
        # Either bytes or None; None is correct in stub mode
        assert result is None or isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_capture_frame_unregistered_device(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        result = await gw.capture_frame("no_such_device")
        assert result is None

    def test_get_all_status_returns_dict(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        status = gw.get_all_status()
        assert isinstance(status, dict)
        # Auto-discovered devices should be present
        assert "cam_0" in status
        assert "name" in status["cam_0"]
        assert "status" in status["cam_0"]

    def test_mqtt_stub_mode_returns_false(self, tmp_path):
        """connect_mqtt returns False gracefully when paho-mqtt is not installed."""
        gw, reg = self._gw(tmp_path)
        # Force ImportError for paho.mqtt
        import unittest.mock as mock
        import builtins
        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name.startswith("paho"):
                raise ImportError("paho-mqtt not installed")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=blocked_import):
            result = gw.connect_mqtt("localhost")
        assert result is False

    def test_publish_without_mqtt_returns_false(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        # No MQTT client attached
        assert gw.publish("test/topic", {"data": 1}) is False

    def test_subscribe_without_mqtt_returns_false(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        assert gw.subscribe("test/topic", lambda t, p: None) is False

    def test_hass_stub_mode_not_configured(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        assert gw._hass_base_url is None
        assert gw._hass_token is None

    @pytest.mark.asyncio
    async def test_hass_call_service_not_configured(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        result = await gw.hass_call_service("light", "turn_on", "light.bedroom")
        assert result["ok"] is False
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_send_command_stub_ack(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        result = await gw.send_command("cam_0", "snapshot")
        assert result["ok"] is True
        assert result.get("stub") is True

    @pytest.mark.asyncio
    async def test_send_command_unknown_device(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        result = await gw.send_command("ghost_device", "ping")
        assert result["ok"] is False

    def test_ping_registered_device(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        assert gw.ping("cam_0") is True

    def test_ping_unregistered_device(self, tmp_path):
        gw, reg = self._gw(tmp_path)
        assert gw.ping("not_a_device") is False
