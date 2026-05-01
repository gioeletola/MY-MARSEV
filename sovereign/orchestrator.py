"""
Master orchestrator — wires all layers together and handles every user session.

Session flow (10 steps):
 1.  InputPipeline.process(raw_input)
 2.  MemoryManager.get_snapshot()
 3.  CEOAgent.run() → select mode, build strategic brief
 4.  ChiefOfStaff.run() → decompose into task list
 5.  Dispatch ALL tasks in parallel (asyncio.gather) with Guardian gating
 6.  GuardianAgent.review_action() for any EXECUTE-class actions
 7.  ApprovalGate.request_approval() if guardian flags escalation
 8.  Aggregate results into StructuredOutput
 9.  DecisionLedger.record()
10.  MemoryManager.write() relevant updates
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import time
import uuid
from typing import Any, Awaitable, Callable

from sovereign.authority.approval_gate import ApprovalGate, ApprovalRequest
from sovereign.authority.thresholds import EscalationThresholds
from sovereign.builder.builder_studio import BuilderStudio
from sovereign.centers.business_center import BusinessCenter
from sovereign.centers.personal_center import PersonalCenter
from sovereign.centers.strategic_center import StrategicCenter
from sovereign.claude.client import ClaudeClient
from sovereign.claude.prompt_builder import PromptBuilder
from sovereign.executive.ceo_agent import CEOAgent
from sovereign.executive.chief_of_staff import ChiefOfStaff
from sovereign.executive.coordinator import CoordinatorAgent
from sovereign.executive.decision_brief import DecisionBriefAgent
from sovereign.executive.executive_assistant import ExecutiveAssistantAgent
from sovereign.executive.guardian import GuardianAgent
from sovereign.executive.task_setter import TaskSetterAgent
from sovereign.factory.agent_factory import AgentFactory
from sovereign.governance.escalation import EscalationChain, EscalationLevel
from sovereign.governance.risk_scoring import RiskScoringEngine
from sovereign.governance.spending_limits import SpendingLimitsEngine
from sovereign.infra.notification_service import NotificationService
from sovereign.infra.scheduler import ScheduleFrequency, Scheduler
from sovereign.infra.token_budget_enforcer import TokenBudgetEnforcer
from sovereign.infra.watchdog import ProcessWatchdog
from sovereign.infra.webhooks import WebhookRouter
from sovereign.infra.worker_manager import WorkerManager, WorkerSpec
from sovereign.input_fabric.pipeline import InputPipeline
from sovereign.integrations.integration_manager import IntegrationManager
from sovereign.kernel.action_classes import ActionClass
from sovereign.kernel.constitution import default_constitution
from sovereign.labs.labs_framework import LabsFramework
from sovereign.layers.attention_engine import AttentionEngineLayer
from sovereign.layers.human_layer import HumanLayer
from sovereign.layers.legacy_layer import LegacyLayer
from sovereign.layers.reality_twin import RealityTwinLayer
from sovereign.layers.sovereign_exit import SovereignExitLayer
from sovereign.layers.time_machine import TimeMachineLayer
from sovereign.layers.trust_engine import TrustEngineLayer
from sovereign.memory.memory_manager import MemoryManager
from sovereign.observability.eval_agent import EvalAgent
from sovereign.observability.health_monitor import HealthMonitor
from sovereign.observability.metrics import MetricsCollector, record_session
from sovereign.observability.model_performance_tracker import ModelPerformanceTracker
from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.proactive.event_engine import EventEngine
from sovereign.proactive.goal_monitor import Goal, GoalMonitor
from sovereign.proactive.silent_ops import SilentOps, SilentTask
from sovereign.proactive.suggestion_engine import SuggestionEngine
from sovereign.registries.agent_registry import AgentRegistry
from sovereign.registries.approval_rule_registry import ApprovalRuleRegistry
from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
from sovereign.registries.experiment_registry import Experiment, ExperimentRegistry
from sovereign.registries.incident_registry import IncidentRegistry
from sovereign.registries.integration_registry import IntegrationRegistry
from sovereign.registries.memory_schema_registry import MemorySchemaRegistry
from sovereign.registries.model_routing_registry import ModelRoutingRegistry
from sovereign.registries.policy_registry import build_default_policy_registry
from sovereign.registries.prompt_registry import VersionedPromptRegistry
from sovereign.registries.workflow_registry import WorkflowRegistry
from sovereign.router.cost_estimator import estimate_from_usage
from sovereign.router.model_router import ModelRouter
from sovereign.security.security_stack import SecurityStack
from sovereign.swarm.base_agent import AgentContext, AgentTask
from sovereign.swarm.black_tier_agents import BLACK_TIER_AGENTS
from sovereign.swarm.business_agents import BUSINESS_AGENTS
from sovereign.swarm.decision_networking_agents import DECISION_NETWORKING_AGENTS
from sovereign.swarm.domain_chiefs import ContentChief, FinanceChief, LegalChief, ResearchChief
from sovereign.swarm.finance_agents import FINANCE_AGENTS
from sovereign.swarm.imperial_agents import IMPERIAL_AGENTS
from sovereign.swarm.offline_agents import OFFLINE_AGENTS
from sovereign.swarm.personal_agents import PERSONAL_AGENTS
from sovereign.swarm.personal_workers import PERSONAL_WORKERS
from sovereign.swarm.security_agents import SECURITY_AGENTS
from sovereign.swarm.system_agent import SystemAgent
from sovereign.swarm.worker_agent import WorkerAgent
from sovereign.tools.builtin.bookmark_tool import BookmarkTool
from sovereign.tools.builtin.browser_tool import BrowserTool
from sovereign.tools.builtin.calculator_tool import CalculatorTool
from sovereign.tools.builtin.calendar_tool import CalendarTool
from sovereign.tools.builtin.cli_exec import CLITool
from sovereign.tools.builtin.clipboard_tool import ClipboardTool
from sovereign.tools.builtin.code_exec import CodeExecTool
from sovereign.tools.builtin.csv_import_tool import CSVImportTool
from sovereign.tools.builtin.file_ops import FileOpsTool
from sovereign.tools.builtin.mcp_tool import MCPTool
from sovereign.tools.builtin.memory_tool import MemoryTool
from sovereign.tools.builtin.notes_tool import NotesTool
from sovereign.tools.builtin.notification_tool import NotificationTool
from sovereign.tools.builtin.screenshot_tool import ScreenshotTool
from sovereign.tools.builtin.transcriber_tool import TranscriberTool
from sovereign.tools.builtin.web_search import WebSearchTool
from sovereign.tools.tool_registry import ToolRegistry
from sovereign.tools.tool_router import ToolRouter

logger = logging.getLogger(__name__)


class SovereignOrchestrator:
    """
    Top-level runtime. Owns all subsystem instances.
    Instantiate via bootstrap.create_orchestrator() rather than directly.
    """

    def __init__(self, config: "SovereignConfig") -> None:  # type: ignore[name-defined]
        self.config = config
        self._session_counter = 0
        # Streaming event callbacks registered by the UI layer
        self._event_callbacks: list[Callable[[dict[str, Any]], None]] = []

        self._init_governance()
        self._init_claude_client()
        self._init_registries()
        self._init_memory()
        self._init_tools()
        self._init_prompt_builder()
        self._init_executive()
        self._init_swarm()
        self._init_centers()
        self._init_layers()
        self._init_security()
        self._init_labs()
        self._init_factory()
        self._init_input_pipeline()
        self._init_health()
        self._init_v2()
        self._init_entities()

        logger.info(
            "SOVEREIGN AI OS started mode=%s model=%s action_class=%s",
            config.default_operating_mode,
            config.default_model,
            config.max_action_class,
        )

    # ------------------------------------------------------------------
    # Event streaming (for UI)
    # ------------------------------------------------------------------

    def add_event_callback(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback that receives live session events."""
        self._event_callbacks.append(cb)

    def remove_event_callback(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self._event_callbacks.discard(cb) if hasattr(self._event_callbacks, 'discard') else None
        if cb in self._event_callbacks:
            self._event_callbacks.remove(cb)

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all registered callbacks."""
        payload = {"type": event_type, **data}
        for cb in self._event_callbacks:
            try:
                cb(payload)
            except Exception as exc:
                logger.debug("Event callback error (%s): %s", event_type, exc)

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    _VALID_MODES = frozenset({
        "command", "business", "personal", "finance",
        "study", "travel", "research", "builder", "local_offline", "survival",
        # Extended modes
        "founder", "war", "prestige", "silent", "recovery", "emergency",
    })

    def set_mode(self, mode_name: str) -> bool:
        """Switch operating mode at runtime. Returns True if valid."""
        if mode_name not in self._VALID_MODES:
            logger.warning("set_mode: unknown mode %r", mode_name)
            return False
        self.config.default_operating_mode = mode_name
        logger.info("Operating mode switched to %s", mode_name)
        self._emit("mode_changed", {"mode": mode_name})
        return True

    @property
    def current_mode(self) -> str:
        return self.config.default_operating_mode

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle_request(
        self,
        user_input: str,
        operating_mode: str | None = None,
        user_id: str = "default",
        on_token: Callable[[str], Awaitable[None]] | None = None,
    ) -> StructuredOutput:
        """
        Main public entry point. Takes a raw user string, runs the full
        10-step session pipeline, and returns a StructuredOutput.
        """
        # Persist user turn
        self._conversations.append(
            conversation_id=user_id,
            role="user",
            content=user_input,
            mode=operating_mode or self.config.default_operating_mode,
        )
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self._session_counter += 1
        _t0 = time.monotonic()
        self._emit("session_start", {"session_id": session_id, "input": user_input[:200]})
        logger.info("Session started", session_id=session_id)

        # --- Step 1: Input pipeline ---
        self._emit("step", {"step": 1, "name": "input_pipeline", "session_id": session_id})
        pipeline_out = await self._pipeline.process(user_input)
        normalized = pipeline_out.normalized_text
        if pipeline_out.warnings:
            for w in pipeline_out.warnings:
                self._emit("warning", {"message": w, "session_id": session_id})

        # --- Step 2: Memory snapshot ---
        self._emit("step", {"step": 2, "name": "memory_snapshot", "session_id": session_id})
        snapshot = await self._memory.get_snapshot(
            domains=["identity", "operational", "project", "decision",
                     "financial", "next_action", "personal_constitution"]
        )
        # Inject recent conversation history into snapshot
        snapshot["conversation_history"] = self._conversations.to_context_string(
            user_id, n=8
        )

        mode = operating_mode or self.config.default_operating_mode
        ctx = AgentContext(
            session_id=session_id,
            operating_mode=mode,
            memory_snapshot=snapshot,
            constitution_hash=self._constitution.constitution_hash(),
            memory_manager=self._memory,
        )

        # --- Step 3: CEO agent — interpret intent, select mode ---
        self._emit("step", {"step": 3, "name": "ceo_agent", "session_id": session_id})
        ceo_task = AgentTask(
            objective=normalized,
            action_class=ActionClass.from_str(self.config.max_action_class),
        )
        ceo_output = await self._ceo.run(ceo_task, ctx)
        if ceo_output.data.get("operating_mode"):
            ctx.operating_mode = ceo_output.data["operating_mode"]
        self._emit("agent_output", {
            "agent": "ceo", "session_id": session_id,
            "mode": ctx.operating_mode, "preview": ceo_output.result[:200],
        })

        # --- Step 4: Chief of Staff — decompose into tasks ---
        self._emit("step", {"step": 4, "name": "chief_of_staff", "session_id": session_id})
        cos_task = AgentTask(
            objective=ceo_output.result,
            action_class=ActionClass.SUGGEST,
        )
        cos_output = await self._cos.run(cos_task, ctx)
        task_list: list[dict] = cos_output.data.get("tasks") or [
            {"objective": normalized, "priority": 3, "agent_hint": "worker"}
        ]
        self._emit("tasks_created", {
            "session_id": session_id,
            "count": len(task_list),
            "tasks": [t.get("objective", "")[:80] for t in task_list],
        })

        # --- Step 5+6: Parallel dispatch with Guardian gating ---
        self._emit("step", {"step": 5, "name": "parallel_dispatch", "session_id": session_id})
        action_class = ActionClass.from_str(self.config.max_action_class)

        task_outputs = await self._dispatch_tasks(task_list, action_class, ctx)

        # --- Step 7: Check if any task needs escalation ---
        escalated = [o for o in task_outputs if o.requires_human_review]
        if escalated and action_class >= ActionClass.EXECUTE:
            first_escalated = escalated[0]
            req = ApprovalRequest(
                request_id=f"appr_{uuid.uuid4().hex[:8]}",
                agent_id="guardian",
                action_class=action_class,
                action_description=first_escalated.result[:200],
                context={"session_id": session_id},
                risk_score=0.8,
            )
            gate_result = await self._gate.request_approval(req)
            if gate_result.decision.value != "approved":
                await self._ledger.record(DecisionRecord(
                    session_id=session_id, agent_id="approval_gate",
                    decision_type="approval_rejected",
                    description="Action rejected by approval gate",
                    outcome=gate_result.rationale,
                ))
                return StructuredOutput.escalated(
                    session_id=session_id,
                    agent_id="approval_gate",
                    task_id=ceo_task.task_id,
                    reason=gate_result.rationale,
                )

        # --- Step 8: Aggregate results ---
        self._emit("step", {"step": 8, "name": "aggregate", "session_id": session_id})
        merged_result = self._merge_outputs(task_outputs, normalized)
        token_usage = self._claude.get_usage()

        final_output = StructuredOutput(
            session_id=session_id,
            agent_id="orchestrator",
            task_id=ceo_task.task_id,
            status=merged_result["status"],
            result=merged_result["result"],
            data={
                "operating_mode": ctx.operating_mode,
                "ceo_brief": ceo_output.result,
                "tasks_dispatched": len(task_list),
                "tasks_completed": len(task_outputs),
                "per_task": [o.to_dict() for o in task_outputs],
            },
            reasoning=ceo_output.reasoning,
            confidence=merged_result["confidence"],
            tokens_used=token_usage,
            requires_human_review=any(o.requires_human_review for o in task_outputs),
        )

        # --- Step 9: Decision ledger ---
        self._emit("step", {"step": 9, "name": "decision_ledger", "session_id": session_id})
        await self._ledger.record(DecisionRecord(
            session_id=session_id, agent_id="orchestrator",
            decision_type="session_complete",
            description=f"Handled: {normalized[:100]}",
            outcome=final_output.status.value,
            confidence=final_output.confidence,
        ))

        # --- Step 10: Memory update ---
        self._emit("step", {"step": 10, "name": "memory_update", "session_id": session_id})
        await self._memory.write("operational", f"last_session_{session_id}", {
            "objective": normalized[:200],
            "mode": ctx.operating_mode,
            "status": final_output.status.value,
            "tokens": token_usage,
        })

        total_tokens = sum(token_usage.values())
        self._health.record_call(
            tokens=total_tokens,
            error=final_output.error if final_output.status == OutputStatus.FAILED else None,
        )

        # --- Experiment registry: record session metrics (Section 16) ---
        self._experiment_registry.record_metric(
            "live_sessions",
            session_id,
            {
                "mode": ctx.operating_mode,
                "status": final_output.status.value,
                "confidence": final_output.confidence,
                "tokens": total_tokens,
                "tasks": len(task_list),
                "request_class": ceo_output.data.get("request_class", "unknown"),
                "internet_used": ceo_output.data.get("internet_needed", False),
            },
        )

        # Record metrics
        latency_ms = (time.monotonic() - _t0) * 1000
        record_session(
            self._metrics,
            mode=ctx.operating_mode,
            latency_ms=latency_ms,
            tokens=total_tokens,
            tasks=len(task_list),
        )
        self._metrics.inc("sessions_total")

        self._emit("session_complete", {
            "session_id": session_id,
            "status": final_output.status.value,
            "tokens": total_tokens,
            "cost_usd": estimate_from_usage(self.config.default_model, token_usage),
            "result_preview": final_output.result[:300],
        })

        # Persist assistant turn
        self._conversations.append(
            conversation_id=user_id,
            role="assistant",
            content=final_output.result or "",
            session_id=session_id,
            mode=ctx.operating_mode,
        )

        # Stream result token-by-token if a callback was provided
        if on_token is not None and final_output.result:
            words = final_output.result.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                try:
                    await on_token(chunk)
                except Exception:
                    break
                # Yield to event loop between chunks for real-time delivery
                await asyncio.sleep(0)

        logger.info(
            "Session complete",
            session_id=session_id,
            status=final_output.status.value,
            tokens=total_tokens,
        )
        return final_output

    # ------------------------------------------------------------------
    # Parallel task dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tasks(
        self,
        task_list: list[dict],
        action_class: ActionClass,
        ctx: AgentContext,
    ) -> list[StructuredOutput]:
        """
        Dispatch all tasks from ChiefOfStaff in parallel using asyncio.gather.

        Each task is routed to the appropriate agent based on agent_hint.
        Guardian review is applied to EXECUTE-class tasks.
        """
        async def run_single(task_dict: dict) -> StructuredOutput:
            objective   = task_dict.get("objective", "")
            agent_hint  = task_dict.get("agent_hint", "worker")
            tools_needed = self._tool_router.suggest_tools(objective)

            agent_task = AgentTask(
                objective=objective,
                action_class=action_class,
                tools_allowed=tools_needed,
                context={"agent_hint": agent_hint},
            )

            # Auto risk-score every task
            risk_score = self._risk_scorer.score(
                objective=objective,
                agent_id=agent_hint,
                action_class=action_class.name,
            )
            if risk_score.is_high_risk():
                self._escalation.create_event(
                    trigger=f"high_risk_task: {objective[:80]}",
                    agent_id=agent_hint,
                    action_class=action_class.name,
                    risk_score=risk_score.overall,
                    level=EscalationLevel.ADMIN if risk_score.overall >= 0.7 else EscalationLevel.OPERATOR,
                )

            # Guardian gate for EXECUTE class
            if action_class >= ActionClass.EXECUTE:
                approved, risk, rationale = await self._guardian.review_action(
                    agent_id=agent_hint,
                    action_description=objective,
                    action_class=action_class,
                    context={},
                    ctx=ctx,
                )
                if not approved:
                    return StructuredOutput.escalated(
                        session_id=ctx.session_id,
                        agent_id="guardian",
                        task_id=agent_task.task_id,
                        reason=rationale,
                    )

            # Route to domain agent
            agent = self._route_to_agent(agent_hint)
            self._emit("task_start", {
                "session_id": ctx.session_id,
                "agent": agent.agent_id,
                "objective": objective[:100],
            })
            output = await agent.run(agent_task, ctx)
            self._emit("task_done", {
                "session_id": ctx.session_id,
                "agent": agent.agent_id,
                "status": output.status.value,
            })
            return output

        # Run all tasks concurrently (max 5 parallel to stay within token budget)
        sem = asyncio.Semaphore(5)

        async def run_with_sem(t: dict) -> StructuredOutput:
            async with sem:
                return await run_single(t)

        results = await asyncio.gather(
            *[run_with_sem(t) for t in task_list],
            return_exceptions=False,
        )
        return list(results)

    def _route_to_agent(self, hint: str):
        """Return the best matching agent instance for the given hint."""
        mapping = {
            "ceo":                self._ceo,
            "research":           self._research_chief,
            "finance":            self._finance_chief,
            "content":            self._content_chief,
            "legal":              self._legal_chief,
            "guardian":           self._guardian,
            "system":             self._system,
            "worker":             self._worker,
            "executive_assistant": self._executive_assistant,
        }
        agent = mapping.get(hint.lower())
        if agent:
            return agent
        # Fall back to full agent registry (covers all swarm agents)
        agent = self._agent_registry.get(hint.lower())
        if agent:
            return agent
        return self._worker

    @staticmethod
    def _merge_outputs(outputs: list[StructuredOutput], fallback: str) -> dict:
        """Merge multiple task outputs into a single result."""
        if not outputs:
            return {"result": fallback, "status": OutputStatus.FAILED, "confidence": 0.0}

        # Combine results
        parts = [o.result for o in outputs if o.result]
        combined = "\n\n---\n\n".join(parts) if len(parts) > 1 else (parts[0] if parts else fallback)

        failed = sum(1 for o in outputs if o.status == OutputStatus.FAILED)
        if failed == len(outputs):
            status = OutputStatus.FAILED
        elif failed > 0:
            status = OutputStatus.PARTIAL
        else:
            status = OutputStatus.SUCCESS

        avg_conf = sum(o.confidence for o in outputs) / len(outputs)
        return {"result": combined, "status": status, "confidence": round(avg_conf, 3)}

    # ------------------------------------------------------------------
    # System queries
    # ------------------------------------------------------------------

    def health(self) -> dict:
        status = self._health.check(
            tool_registry=self._tool_registry,
            factory=self._factory,
        )
        return {
            "overall": status.overall,
            "checks": status.checks,
            "metrics": status.metrics,
            "alerts": status.alerts,
            "budget": self._budget.daily_summary(),
            "escalations_pending": len(self._escalation.pending_events()),
            "tools_registered": self._tool_registry.count(),
            "agents_registered": self._agent_registry.count(),
            "provider_health": self._model_router.provider_health_report(),
        }

    def get_budget_summary(self) -> dict:
        """Return daily and monthly token/cost budget summary."""
        return {
            "daily": self._budget.daily_summary(),
            "monthly": self._budget.monthly_summary(),
            "top_consumers": self._budget.top_consumers(5),
        }

    def get_pending_escalations(self) -> list[dict]:
        """Return all unresolved escalation events."""
        return [e.to_dict() for e in self._escalation.pending_events()]

    def resolve_escalation(self, event_id: str, resolution: str) -> bool:
        """Mark an escalation event as resolved."""
        return self._escalation.resolve(event_id, resolution)

    def get_scheduler(self) -> "Scheduler":
        """Return the scheduler for registering background jobs."""
        return self._scheduler

    def get_usage(self) -> dict:
        return self._claude.get_usage()

    def get_session_count(self) -> int:
        return self._session_counter

    def register_mcp_server(
        self, name: str, command: list[str],
        env: dict | None = None, description: str = ""
    ) -> None:
        """Register an external MCP server for use by agents."""
        self._mcp_tool.register_server(name, command, env, description)

    async def run_workflow(
        self, name: str, variables: dict | None = None
    ) -> Any:
        """Execute a named workflow. Variables are substituted into step templates."""
        return await self._workflow_registry.execute(
            name=name,
            variables=variables or {},
            agent_resolver=self._route_to_agent,
            ctx=AgentContext(
                session_id=f"wf_{name}",
                operating_mode=self.config.default_operating_mode,
            ),
        )

    def get_experiment_metrics(self, name: str = "live_sessions") -> dict:
        """Return recorded metrics for an experiment."""
        try:
            exp = self._experiment_registry.get(name)
            return {"name": exp.name, "metrics": exp.metrics, "status": exp.status}
        except KeyError:
            return {}

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_claude_client(self) -> None:
        self._constitution = default_constitution(
            max_action_class=ActionClass.from_str(self.config.max_action_class)
        )
        self._claude = ClaudeClient(
            api_key=self.config.api_key,
            default_model=self.config.default_model,
            budget_enforcer=self._budget,
        )
        self._model_router = ModelRouter()

    def _init_registries(self) -> None:
        self._agent_registry = AgentRegistry()
        self._prompt_registry = VersionedPromptRegistry(self.config.prompts_dir)
        self._ledger = DecisionLedger(self.config.data_dir)
        self._experiment_registry = ExperimentRegistry()
        self._workflow_registry = WorkflowRegistry()
        self._integration_registry = IntegrationRegistry()
        self._incident_registry = IncidentRegistry()
        self._memory_schema_registry = MemorySchemaRegistry()
        self._approval_rule_registry = ApprovalRuleRegistry()
        self._model_routing_registry = ModelRoutingRegistry()
        # Seed the live-session experiment for ongoing metric collection
        self._experiment_registry.register(Experiment(
            name="live_sessions",
            description="Tracks real-time session metrics: tokens, latency, confidence, mode",
            variants=["default"],
        ))

    def _init_memory(self) -> None:
        self._memory = MemoryManager(self.config.data_dir)
        from sovereign.memory.conversation_store import ConversationStore
        self._conversations = ConversationStore(
            pathlib.Path(self.config.data_dir) / "conversations"
        )

    def _init_tools(self) -> None:
        self._tool_registry = ToolRegistry()
        self._tool_registry.register(WebSearchTool())
        self._tool_registry.register(FileOpsTool(self.config.data_dir))
        self._tool_registry.register(CodeExecTool())
        self._tool_registry.register(MemoryTool(self._memory))
        self._tool_registry.register(CLITool())
        self._tool_registry.register(BrowserTool())
        self._mcp_tool = MCPTool()
        self._tool_registry.register(self._mcp_tool)
        self._tool_registry.register(NotesTool())
        self._tool_registry.register(CalendarTool())
        self._tool_registry.register(BookmarkTool())
        self._tool_registry.register(ScreenshotTool())
        self._tool_registry.register(TranscriberTool())
        self._tool_registry.register(NotificationTool())
        self._tool_registry.register(CalculatorTool())
        self._tool_registry.register(ClipboardTool())
        self._tool_registry.register(CSVImportTool())
        self._tool_router = ToolRouter(self._tool_registry)

    def _init_prompt_builder(self) -> None:
        self._prompt_builder = PromptBuilder(
            constitution=self._constitution,
            prompt_registry=self._prompt_registry,
        )

    def _init_executive(self) -> None:
        shared = dict(
            claude_client=self._claude,
            tool_registry=self._tool_registry,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
        )
        self._ceo            = CEOAgent(**shared)
        self._cos            = ChiefOfStaff(**shared)
        self._guardian       = GuardianAgent(**shared)
        self._coordinator    = CoordinatorAgent(**shared)
        self._task_setter    = TaskSetterAgent(**shared)
        self._decision_brief = DecisionBriefAgent(**shared)
        self._worker         = WorkerAgent(**shared)
        self._system         = SystemAgent(**shared)
        self._research_chief = ResearchChief(**shared)
        self._finance_chief  = FinanceChief(**shared)
        self._content_chief  = ContentChief(**shared)
        self._legal_chief    = LegalChief(**shared)

        self._executive_assistant = ExecutiveAssistantAgent(**shared)

        thresholds = EscalationThresholds.for_mode(self.config.default_operating_mode)
        self._gate = ApprovalGate(
            mode=self.config.approval_mode,
            thresholds=thresholds,
        )
        # Wire policy registry into guardian for pre-flight rule evaluation
        self._policy_registry = build_default_policy_registry()
        self._guardian.set_policy_registry(self._policy_registry)
        for agent in [
            self._ceo, self._cos, self._guardian, self._coordinator,
            self._task_setter, self._decision_brief, self._worker, self._system,
            self._research_chief, self._finance_chief,
            self._content_chief, self._legal_chief,
            self._executive_assistant,
        ]:
            self._agent_registry.register(agent)

    def _init_swarm(self) -> None:
        """Instantiate and register all swarm agents."""
        shared = dict(
            claude_client=self._claude,
            tool_registry=self._tool_registry,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
        )
        all_agent_classes = (
            BUSINESS_AGENTS + PERSONAL_AGENTS + PERSONAL_WORKERS +
            FINANCE_AGENTS + BLACK_TIER_AGENTS + IMPERIAL_AGENTS +
            DECISION_NETWORKING_AGENTS + SECURITY_AGENTS + OFFLINE_AGENTS
        )
        for AgentClass in all_agent_classes:
            try:
                agent = AgentClass(**shared)
                self._agent_registry.register(agent)
            except Exception as exc:
                logger.warning("Failed to instantiate agent %s: %s", AgentClass.__name__, exc)
        logger.info("Swarm initialized: %d agents registered", self._agent_registry.count())

    def _init_centers(self) -> None:
        """Initialize operational centers."""
        self._business_center = BusinessCenter(self._agent_registry)
        self._personal_center = PersonalCenter(self._agent_registry)
        self._strategic_center = StrategicCenter(self._agent_registry)

    def _init_layers(self) -> None:
        """Initialize advanced intelligence layers."""
        self._reality_twin = RealityTwinLayer()
        self._time_machine = TimeMachineLayer()
        self._attention_engine = AttentionEngineLayer()
        self._trust_engine = TrustEngineLayer()
        self._sovereign_exit = SovereignExitLayer()
        self._legacy_layer = LegacyLayer()
        self._human_layer = HumanLayer()

    def _init_security(self) -> None:
        """Initialize the security stack."""
        self._security = SecurityStack(incident_registry=self._incident_registry)

    def _init_labs(self) -> None:
        """Initialize Labs and Builder Studio."""
        self._labs = LabsFramework()
        self._builder = BuilderStudio(
            agent_factory=None,  # set post-factory init
            workflow_registry=self._workflow_registry,
        )

    def _init_factory(self) -> None:
        self._factory = AgentFactory(
            claude_client=self._claude,
            tool_registry=self._tool_registry,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
            agent_registry=self._agent_registry,
        )
        # Wire factory into builder studio now that it's available
        self._builder._agent_factory = self._factory

    def _init_governance(self) -> None:
        """Initialize budget, notification, escalation, risk, and scheduling subsystems."""
        self._budget = TokenBudgetEnforcer()
        self._notif = NotificationService()
        self._escalation = EscalationChain(notification_service=self._notif)
        self._spending = SpendingLimitsEngine()
        self._risk_scorer = RiskScoringEngine()
        self._scheduler = Scheduler()

    def _init_input_pipeline(self) -> None:
        self._pipeline = InputPipeline(config={"pii_filter": False, "max_chars": 50_000})

    def _init_health(self) -> None:
        self._health = HealthMonitor()
        self._eval_agent = EvalAgent()
        self._metrics = MetricsCollector()
        self._model_perf_tracker = ModelPerformanceTracker()

    def _init_v2(self) -> None:
        """Initialize V2 proactive intelligence layer."""
        self._goal_monitor = GoalMonitor()
        self._suggestion_engine = SuggestionEngine()
        self._event_engine = EventEngine()
        self._silent_ops = SilentOps()
        self._worker_manager = WorkerManager()
        self._integration_manager = IntegrationManager()
        self._bg_stop_event = asyncio.Event()
        self._webhook_router = WebhookRouter()
        self._process_watchdog = ProcessWatchdog(
            alert_callback=lambda name, exc: logger.error(
                "Watchdog alert: %s crashed: %s", name, exc
            )
        )
        # Wire webhook events as agent tasks
        self._webhook_router.register("*", "*", self._on_webhook_event)

        # Schedule nightly eval regression job
        self._eval_agent.schedule_nightly(self._scheduler)

        # Schedule weekly capability gap analysis job
        from sovereign.expansion.capability_gap_detector import CapabilityGapDetector
        _gap_detector = CapabilityGapDetector()
        _gap_detector.schedule_weekly(self._scheduler)

        # Seed scheduler with V2 daily jobs (idempotent)
        existing = {j.name for j in self._scheduler.list_jobs()}
        if "morning_brief" not in existing:
            self._scheduler.schedule(
                "morning_brief", "ceo_agent",
                "Prepare a concise morning briefing: top priorities, risks, and 3 recommended actions for today.",
                ScheduleFrequency.DAILY,
            )
        if "cashflow_digest" not in existing:
            self._scheduler.schedule(
                "cashflow_digest", "cashflow_analyst",
                "Analyze recent transactions and produce a daily cashflow digest with key spending insights.",
                ScheduleFrequency.DAILY,
            )

        # Seed default quarterly goals (only if store is empty)
        import time as _time
        if not self._goal_monitor.active_goals():
            q2_deadline = _time.mktime((2026, 6, 30, 23, 59, 0, 0, 0, -1))
            self._goal_monitor.add(Goal(
                goal_id="q2_revenue",
                title="Q2 Revenue Target",
                description="Reach $500K revenue by end of Q2 2026",
                target_value=500_000.0, unit="USD", deadline=q2_deadline,
                tags=["finance", "q2"],
            ))
            self._goal_monitor.add(Goal(
                goal_id="q2_savings",
                title="Monthly Savings Rate",
                description="Maintain 30%+ monthly savings rate through Q2 2026",
                target_value=30.0, unit="%", deadline=q2_deadline,
                tags=["finance", "savings"],
            ))
            self._goal_monitor.add(Goal(
                goal_id="q2_agents",
                title="Agent Coverage Expansion",
                description="Deploy all 200+ swarm agents and verify orchestration",
                target_value=200.0, unit="agents", deadline=q2_deadline,
                tags=["ops", "swarm"],
            ))

        # Register SilentOps background tasks
        async def _noop_health():
            logger.debug("SilentOps: health ping")

        self._silent_ops.register(SilentTask(
            task_id="bg_health_ping", name="Background Health Ping",
            interval_s=300.0, callback=_noop_health,
        ))


        # Register WorkerManager workers (wrapping async run_loops)
        self._worker_manager.register(WorkerSpec(
            worker_id="event_engine",
            coro_factory=lambda: self._event_engine.run_loop(self._bg_stop_event),
            description="Time-triggered proactive event dispatcher",
        ))
        self._worker_manager.register(WorkerSpec(
            worker_id="silent_ops",
            coro_factory=lambda: self._silent_ops.run_loop(self._bg_stop_event),
            description="Low-priority background maintenance tasks",
        ))

        logger.info("V2 proactive layer initialised")

    # ------------------------------------------------------------------
    # Background task lifecycle (called by FastAPI lifespan)
    # ------------------------------------------------------------------

    async def start_background_tasks(self) -> None:
        """Start all V2 background workers (EventEngine, SilentOps, watchdog)."""
        import asyncio
        try:
            self._bg_stop_event.clear()

            # Register daily digest (done here so the orchestrator is fully initialised)
            from sovereign.proactive.daily_digest import build_daily_digest_task
            digest_hour = getattr(self.config, "digest_hour", 8)
            digest_cb = build_daily_digest_task(self, digest_hour=digest_hour)
            if not any(t.task_id == "daily_digest" for t in self._silent_ops._tasks.values()):
                self._silent_ops.register(SilentTask(
                    task_id="daily_digest", name="Daily Morning Digest",
                    interval_s=3600.0, callback=digest_cb,
                ))

            await self._worker_manager.start_all()
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())
            logger.info("SOVEREIGN V2 background tasks started")
        except Exception as exc:
            logger.warning("Background task startup warning: %s", exc)

    async def stop_background_tasks(self) -> None:
        """Gracefully stop all V2 background workers."""
        try:
            self._bg_stop_event.set()
            self._event_engine.stop()
            self._silent_ops.stop()
            await self._worker_manager.stop_all()
            watchdog = getattr(self, "_watchdog_task", None)
            if watchdog:
                watchdog.cancel()
            logger.info("SOVEREIGN V2 background tasks stopped")
        except Exception as exc:
            logger.warning("Background task shutdown warning: %s", exc)

    async def _watchdog_loop(self) -> None:
        """Periodic watchdog: logs health warnings every 60 s."""
        import asyncio
        try:
            while not self._bg_stop_event.is_set():
                await asyncio.sleep(60)
                try:
                    h = self.health()
                    if h.get("overall") != "ok":
                        logger.warning(
                            "Watchdog: system degraded — overall=%s alerts=%s",
                            h.get("overall"), h.get("alerts", [])
                        )
                    # Check provider health
                    ph = h.get("provider_health", {})
                    down = [p for p, s in ph.items() if s.get("circuit_open")]
                    if down:
                        logger.warning("Watchdog: providers with open circuit: %s", down)
                    if h.get("escalations_pending", 0) > 0:
                        logger.info(
                            "Watchdog: %d escalations pending", h["escalations_pending"]
                        )
                except Exception as exc:
                    logger.warning("Watchdog check error: %s", exc)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # V2 public properties
    # ------------------------------------------------------------------

    @property
    def goal_monitor(self) -> GoalMonitor:
        return self._goal_monitor

    @property
    def suggestion_engine(self) -> SuggestionEngine:
        return self._suggestion_engine

    @property
    def integration_manager(self) -> IntegrationManager:
        return self._integration_manager

    @property
    def entity_provisioner(self) -> "EntityProvisioner":  # type: ignore[name-defined]
        return self._entity_provisioner

    @property
    def webhook_router(self) -> WebhookRouter:
        return self._webhook_router

    @property
    def process_watchdog(self) -> ProcessWatchdog:
        return self._process_watchdog

    def _on_webhook_event(self, event: Any) -> None:
        """Convert an inbound webhook event into an async AgentTask and queue it."""
        try:
            source = getattr(event, "source", "unknown")
            event_type = getattr(event, "event_type", "unknown")
            payload = getattr(event, "payload", {})
            logger.info("Webhook received: %s/%s", source, event_type)
            # Fire-and-forget: schedule the agent task in the running event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                objective = (
                    f"Process inbound webhook from {source}: event_type={event_type}. "
                    f"Payload summary: {str(payload)[:300]}"
                )
                asyncio.ensure_future(
                    self.handle_request(objective, operating_mode="command")
                )
        except Exception as exc:
            logger.warning("Webhook event handler error: %s", exc)

    # ------------------------------------------------------------------
    # Entity provisioning
    # ------------------------------------------------------------------

    def _init_entities(self) -> None:
        """Initialize the Connected Entity Provisioning System."""
        from sovereign.entities.entity_registry import EntityRegistry
        from sovereign.entities.provisioner import EntityProvisioner
        from sovereign.entities.vault_manager import EntityVault

        self._entity_registry = EntityRegistry()
        self._entity_vault = EntityVault()
        self._entity_provisioner = EntityProvisioner(
            self._entity_registry,
            self._entity_vault,
            self._integration_manager,
            self._agent_registry,
            self._scheduler,
        )
        logger.info("Connected Entity Provisioning System initialised")
