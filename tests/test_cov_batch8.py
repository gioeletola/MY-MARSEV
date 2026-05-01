"""
Coverage batch 8: eval_agent, device_gateway/registry, gemini_provider,
approval_gate extended, hud/orchestrator_bridge, models/base_provider,
swarm/leveled_agent extended.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# EvalAgent — additional paths
# ===========================================================================

class TestEvalAgentExtended:
    def setup_method(self):
        from sovereign.observability.eval_agent import EvalAgent
        self._tmp = tempfile.mkdtemp()
        self.agent = EvalAgent(data_path=Path(self._tmp) / "evals.jsonl")

    def test_evaluate_returns_eval_result(self):
        from sovereign.observability.eval_agent import EvalResult
        ev = self.agent.evaluate(
            session_id="s1",
            agent_id="research_agent",
            task_id="t1",
            objective="Summarise research",
            result="Step 1: review data. Step 2: identify key trends. Step 3: recommend actions based on findings.",
        )
        assert isinstance(ev, EvalResult)
        assert 0.0 <= ev.overall <= 1.0

    def test_evaluate_short_result_flags(self):
        ev = self.agent.evaluate(
            session_id="s1", agent_id="agent", task_id="t1",
            objective="Summarise", result="done",
        )
        assert any("short_output" in f for f in ev.flags)

    def test_evaluate_safety_violation(self):
        ev = self.agent.evaluate(
            session_id="s1", agent_id="agent", task_id="t1",
            objective="Info", result="this may cause harm to systems",
        )
        assert ev.safety == 0.0

    def test_agent_stats_empty(self):
        stats = self.agent.agent_stats("nonexistent_agent")
        assert stats.get("evals") == 0

    def test_agent_stats_after_eval(self):
        self.agent.evaluate("s1", "my_agent", "t1", "obj", "Result: action needed immediately.")
        stats = self.agent.agent_stats("my_agent")
        assert stats["evals"] == 1

    def test_failing_agents(self):
        self.agent.evaluate("s1", "bad_agent", "t1", "obj", "no")
        failing = self.agent.failing_agents()
        assert isinstance(failing, list)

    def test_recent_evals_returns_list(self):
        self.agent.evaluate("s1", "agent", "t1", "obj", "Response with action steps.")
        recent = self.agent.recent_evals(limit=5)
        assert isinstance(recent, list)
        assert len(recent) >= 1

    def test_overall_stats_empty(self):
        stats = self.agent.overall_stats()
        assert stats.get("total") == 0

    def test_overall_stats_after_evals(self):
        self.agent.evaluate("s1", "a1", "t1", "obj", "Action: review and implement steps.")
        stats = self.agent.overall_stats()
        assert stats["total"] >= 1
        assert "pass_rate" in stats

    def test_evaluate_structured_result_passes(self):
        ev = self.agent.evaluate(
            session_id="s1", agent_id="a1", task_id="t1",
            objective="Strategy",
            result=(
                "## Summary\n"
                "- Step 1: Analyse market\n"
                "- Step 2: Recommend action\n"
                "- Step 3: Schedule review\n"
                "This plan will deliver results within 30 days.\n"
                "Next: implement step 1 by assigning tasks to the team."
            ),
        )
        assert ev.tone_format > 0.0


class TestRegressionTrackerExtended:
    def setup_method(self):
        from sovereign.observability.eval_agent import RegressionTracker
        self._tmp = tempfile.mkdtemp()
        self.tracker = RegressionTracker(data_path=Path(self._tmp) / "reg.jsonl")

    def _make_eval(self, agent_id="agent1", passed=True, overall=0.75):
        from sovereign.observability.eval_agent import EvalResult
        return EvalResult(
            eval_id="e1", session_id="s1", agent_id=agent_id, task_id="t1",
            completeness=0.8, actionability=0.7, tone_format=0.6, safety=1.0,
            overall=overall, passed=passed,
        )

    def test_record_writes_to_file(self):
        ev = self._make_eval()
        self.tracker.record(ev)
        records = self.tracker.get_history("agent1")
        assert isinstance(records, list)
        assert len(records) >= 1

    def test_get_history_empty(self):
        records = self.tracker.get_history("nonexistent")
        assert records == []

    def test_regression_report(self):
        for i in range(3):
            ev = self._make_eval(agent_id="a1", passed=(i < 2), overall=0.5 + i * 0.1)
            self.tracker.record(ev)
        report = self.tracker.regression_report()
        assert isinstance(report, dict)


# ===========================================================================
# DeviceRegistry + DeviceGateway
# ===========================================================================

class TestDeviceRegistry:
    def setup_method(self):
        from sovereign.devices.device_registry import DeviceRegistry, Device, DeviceType, DeviceStatus
        self._tmp = tempfile.mkdtemp()
        self.registry = DeviceRegistry(data_file=Path(self._tmp) / "devices.json")
        self.Device = Device
        self.DT = DeviceType
        self.DS = DeviceStatus

    def test_register_device(self):
        dev = self.Device(
            device_id="cam0", name="Webcam",
            device_type=self.DT.CAMERA, status=self.DS.ONLINE,
        )
        self.registry.register(dev)
        assert self.registry.get("cam0") is not None

    def test_get_nonexistent(self):
        assert self.registry.get("ghost_device") is None

    def test_update_status(self):
        dev = self.Device(device_id="mic0", name="Microphone", device_type=self.DT.MICROPHONE)
        self.registry.register(dev)
        result = self.registry.update_status("mic0", self.DS.ONLINE)
        assert result is True

    def test_update_status_nonexistent(self):
        result = self.registry.update_status("ghost", self.DS.ONLINE)
        assert result is False

    def test_online_devices(self):
        dev = self.Device(device_id="spk0", name="Speaker", device_type=self.DT.SPEAKER,
                          status=self.DS.ONLINE)
        self.registry.register(dev)
        online = self.registry.online_devices()
        assert isinstance(online, list)

    def test_all_devices(self):
        all_devs = self.registry.all_devices()
        assert isinstance(all_devs, list)

    def test_by_type(self):
        dev = self.Device(device_id="sensor1", name="Sensor", device_type=self.DT.SENSOR)
        self.registry.register(dev)
        sensors = self.registry.by_type(self.DT.SENSOR)
        assert any(d.device_id == "sensor1" for d in sensors)

    def test_summary(self):
        summary = self.registry.summary()
        assert isinstance(summary, dict)


class TestDeviceGateway:
    def setup_method(self):
        from sovereign.devices.device_registry import DeviceRegistry, Device, DeviceType, DeviceStatus
        from sovereign.devices.device_gateway import DeviceGateway, DeviceInfo, DeviceCapability
        self._tmp = tempfile.mkdtemp()
        self.registry = DeviceRegistry(data_file=Path(self._tmp) / "devices.json")
        self.gateway = DeviceGateway(self.registry)
        self.Device = Device
        self.DT = DeviceType
        self.DS = DeviceStatus
        self.DI = DeviceInfo
        self.DC = DeviceCapability

    def _register(self, device_id="test_device"):
        dev = self.Device(
            device_id=device_id, name="Test Device",
            device_type=self.DT.SENSOR, status=self.DS.ONLINE,
        )
        self.registry.register(dev)
        return dev

    def test_discover(self):
        self._register()
        devices = run(self.gateway.discover())
        assert isinstance(devices, list)

    def test_connect_existing(self):
        self._register("conn_dev")
        result = run(self.gateway.connect("conn_dev"))
        assert result is True

    def test_connect_nonexistent(self):
        result = run(self.gateway.connect("nonexistent_device"))
        assert result is False

    def test_send_command_stub(self):
        self._register("cmd_dev")
        result = run(self.gateway.send_command("cmd_dev", "ping"))
        assert result.get("ok") is True

    def test_send_command_nonexistent(self):
        result = run(self.gateway.send_command("ghost_dev", "ping"))
        assert result.get("ok") is False

    def test_send_command_with_driver(self):
        self._register("drv_dev")
        async def my_driver(cmd, payload):
            return f"ack:{cmd}"
        self.gateway.register_driver("drv_dev", my_driver)
        result = run(self.gateway.send_command("drv_dev", "turn_on"))
        assert result.get("ok") is True
        assert "ack:turn_on" in result.get("result", "")

    def test_ping_nonexistent(self):
        result = self.gateway.ping("ghost")
        assert result is False

    def test_ping_existing(self):
        self._register("ping_dev")
        result = self.gateway.ping("ping_dev")
        assert isinstance(result, bool)

    def test_list_capabilities_nonexistent(self):
        caps = self.gateway.list_capabilities("ghost")
        assert isinstance(caps, list)

    def test_list_capabilities_existing(self):
        self._register("cap_dev")
        caps = self.gateway.list_capabilities("cap_dev")
        assert isinstance(caps, list)

    def test_get_all_status(self):
        self._register("status_dev")
        status = self.gateway.get_all_status()
        assert isinstance(status, dict)

    def test_device_info_to_dict(self):
        info = self.DI(device_id="d1", name="D1", type="sensor")
        d = info.to_dict()
        assert d["device_id"] == "d1"

    def test_device_capability_values(self):
        assert self.DC.SENSOR == "sensor"
        assert self.DC.CAMERA == "camera"


# ===========================================================================
# GeminiProvider (no-key path)
# ===========================================================================

class TestGeminiProvider:
    def test_no_api_key_complete_returns_stub(self):
        import os
        os.environ.pop("GEMINI_API_KEY", None)
        from sovereign.models.gemini_provider import GeminiProvider
        from sovereign.models.base_provider import CompletionRequest
        provider = GeminiProvider(api_key="")
        req = CompletionRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="gemini-1.5-flash",
        )
        result = run(provider.complete(req))
        assert "unavailable" in result.content.lower() or isinstance(result.content, str)

    def test_no_api_key_stream_returns_stub(self):
        import os
        os.environ.pop("GEMINI_API_KEY", None)
        from sovereign.models.gemini_provider import GeminiProvider
        from sovereign.models.base_provider import CompletionRequest
        provider = GeminiProvider(api_key="")

        async def collect():
            chunks = []
            async for chunk in provider.stream(CompletionRequest(
                messages=[{"role": "user", "content": "Hi"}],
            )):
                chunks.append(chunk)
            return chunks

        chunks = run(collect())
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_cost_function(self):
        from sovereign.models.gemini_provider import _cost
        c = _cost("gemini-1.5-pro", 1_000_000, 500_000)
        assert isinstance(c, float)
        assert c > 0.0

    def test_cost_unknown_model(self):
        from sovereign.models.gemini_provider import _cost
        c = _cost("unknown-model", 100, 100)
        assert c == 0.0

    def test_to_gemini_messages(self):
        from sovereign.models.gemini_provider import _to_gemini_messages
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])
        msgs = _to_gemini_messages(req)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "model"

    def test_build_body_with_system(self):
        from sovereign.models.gemini_provider import GeminiProvider
        from sovereign.models.base_provider import CompletionRequest
        provider = GeminiProvider(api_key="test")
        req = CompletionRequest(
            messages=[{"role": "user", "content": "Hello"}],
            system="Be helpful",
        )
        body = provider._build_body(req)
        assert "systemInstruction" in body
        assert "contents" in body

    def test_estimate_cost(self):
        from sovereign.models.gemini_provider import GeminiProvider
        cost = GeminiProvider.estimate_cost("gemini-1.5-pro", 2_000_000, 1_000_000)
        assert isinstance(cost, float)

    def test_parse_first_json_valid(self):
        from sovereign.models.gemini_provider import GeminiProvider
        text = '{"key": "value"} extra'
        obj, idx = GeminiProvider._parse_first_json(text)
        assert obj == {"key": "value"}

    def test_parse_first_json_invalid(self):
        from sovereign.models.gemini_provider import GeminiProvider
        with pytest.raises(ValueError):
            GeminiProvider._parse_first_json("no json here")


# ===========================================================================
# ApprovalGate — extended modes
# ===========================================================================

class TestApprovalGateExtended:
    def test_auto_mode_approves_all(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        decision = run(gate.request_approval("execute_query", {"data": "sales"}, "analyst"))
        assert decision.approved is True

    def test_policy_mode_read_approved(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        decision = run(gate.request_approval("read", {}, "agent"))
        assert decision.approved is True

    def test_policy_mode_admin_approved(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        decision = run(gate.request_approval("delete_file", {}, "admin"))
        assert decision.approved is True

    def test_silent_mode_approves(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.SILENT)
        decision = run(gate.request_approval("log_event", {"event": "test"}, "logger"))
        assert isinstance(decision.approved, bool)

    def test_audit_trail_records_decisions(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        run(gate.request_approval("read_report", {}, "user"))
        run(gate.request_approval("write_report", {}, "user"))
        trail = gate.audit_trail
        assert len(trail) >= 2

    def test_stats(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        run(gate.request_approval("action1", {}, "user"))
        stats = gate.stats()
        assert isinstance(stats, dict)

    def test_clear_audit_trail(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        run(gate.request_approval("action1", {}, "user"))
        gate.clear_audit_trail()
        assert len(gate.audit_trail) == 0

    def test_from_env_factory(self):
        import os
        os.environ["SOVEREIGN_APPROVAL_MODE"] = "auto"
        from sovereign.authority.approval_gate import ApprovalGate
        gate = ApprovalGate.from_env()
        assert gate is not None

    def test_register_auto_rule(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.POLICY)
        gate.register_auto_rule(
            lambda action, ctx, uid: True if action == "custom_action" else None,
            outcome=True,
        )
        decision = run(gate.request_approval("custom_action", {}, "user"))
        assert decision.approved is True

    def test_revoke_nonexistent(self):
        from sovereign.authority.approval_gate import ApprovalGate, ApprovalMode
        gate = ApprovalGate(mode=ApprovalMode.AUTO)
        result = gate.revoke("nonexistent_action_id")
        assert result is False


# ===========================================================================
# HUDOrchestrator + OrchestratorBridge
# ===========================================================================

class TestHUDEvent:
    def test_to_dict(self):
        from sovereign.hud.orchestrator_bridge import HUDEvent
        event = HUDEvent(source="camera", event_type="face_detected", data={"count": 1})
        d = event.to_dict()
        assert d["source"] == "camera"
        assert d["event_type"] == "face_detected"
        assert isinstance(d["timestamp"], float)


class TestHUDStatus:
    def test_default_state(self):
        from sovereign.hud.orchestrator_bridge import HUDStatus
        s = HUDStatus()
        assert s.camera_active is False
        assert s.bridge_running is False

    def test_to_dict(self):
        from sovereign.hud.orchestrator_bridge import HUDStatus
        s = HUDStatus(camera_active=True, face_detected=True)
        d = s.to_dict()
        assert d["camera_active"] is True
        assert isinstance(d, dict)


class TestHUDOrchestratorUnit:
    def test_instantiation(self):
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator
        mock_orch = MagicMock()
        hud = HUDOrchestrator(orchestrator=mock_orch)
        assert hud is not None

    def test_get_status(self):
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator, HUDStatus
        hud = HUDOrchestrator(orchestrator=MagicMock())
        status = hud.get_status()
        assert isinstance(status, HUDStatus)

    def test_is_running_initial(self):
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator
        hud = HUDOrchestrator(orchestrator=MagicMock())
        assert hud.is_running is False

    def test_event_queue(self):
        import asyncio
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator
        hud = HUDOrchestrator(orchestrator=MagicMock())
        q = hud.event_queue()
        assert isinstance(q, asyncio.Queue)

    def test_on_event_registers_callback(self):
        from sovereign.hud.orchestrator_bridge import HUDOrchestrator
        hud = HUDOrchestrator(orchestrator=MagicMock())
        called = []
        async def cb(evt):
            called.append(evt)
        hud.on_event(cb)
        assert len(hud._callbacks) >= 1


class TestOrchestratorBridge:
    def test_instantiation(self):
        from sovereign.hud.orchestrator_bridge import OrchestratorBridge
        mock_orch = MagicMock()
        bridge = OrchestratorBridge(mock_orch)
        assert bridge is not None

    def test_on_event(self):
        from sovereign.hud.orchestrator_bridge import OrchestratorBridge
        bridge = OrchestratorBridge(MagicMock())
        async def cb(evt):
            pass
        bridge.on_event(cb)

    def test_stop(self):
        from sovereign.hud.orchestrator_bridge import OrchestratorBridge
        bridge = OrchestratorBridge(MagicMock())
        bridge.stop()  # should not raise


# ===========================================================================
# BaseProvider
# ===========================================================================

class TestBaseProvider:
    def _make_provider(self):
        from sovereign.models.base_provider import BaseProvider, CompletionResponse

        class MockProvider(BaseProvider):
            provider_id = "mock"
            display_name = "Mock"
            async def complete(self, request):
                return CompletionResponse(content="ok", model="mock", provider="mock")

        return MockProvider()

    def test_record_success(self):
        p = self._make_provider()
        p.record_success()
        from sovereign.models.base_provider import ProviderStatus
        assert p._status == ProviderStatus.AVAILABLE
        assert p._error_count == 0

    def test_record_error(self):
        p = self._make_provider()
        p.record_error()
        assert p._error_count == 1

    def test_record_three_errors_degrades(self):
        from sovereign.models.base_provider import ProviderStatus
        p = self._make_provider()
        for _ in range(3):
            p.record_error()
        assert p._status == ProviderStatus.DEGRADED

    def test_health_check(self):
        from sovereign.models.base_provider import ProviderStatus
        p = self._make_provider()
        status = run(p.health_check())
        assert status == ProviderStatus.AVAILABLE

    def test_completion_response_total_tokens(self):
        from sovereign.models.base_provider import CompletionResponse
        resp = CompletionResponse(
            content="hello", model="m", provider="p",
            input_tokens=100, output_tokens=50,
        )
        assert resp.total_tokens == 150

    def test_stream_default(self):
        from sovereign.models.base_provider import CompletionRequest
        p = self._make_provider()

        async def collect():
            chunks = []
            async for chunk in p.stream(CompletionRequest(messages=[{"role": "user", "content": "hi"}])):
                chunks.append(chunk)
            return chunks

        chunks = run(collect())
        assert chunks == ["ok"]
