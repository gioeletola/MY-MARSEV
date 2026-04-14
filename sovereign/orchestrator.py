"""
Master orchestrator — wires all layers together and handles every user session.

Session flow (10 steps):
 1.  InputPipeline.process(raw_input)
 2.  MemoryManager.get_snapshot()
 3.  CEOAgent.run() → select mode, build strategic brief
 4.  ChiefOfStaff.run() → decompose into task list
 5.  Dispatch first task to WorkerAgent (with tool loop if needed)
 6.  GuardianAgent.review_action() for any EXECUTE-class actions
 7.  ApprovalGate.request_approval() if guardian flags escalation
 8.  Aggregate results into StructuredOutput
 9.  DecisionLedger.record()
10.  MemoryManager.write() relevant updates
"""
from __future__ import annotations

import uuid
import logging

from sovereign.kernel.action_classes import ActionClass
from sovereign.kernel.constitution import default_constitution
from sovereign.kernel.stop_conditions import StopConditionEvaluator
from sovereign.claude.client import ClaudeClient
from sovereign.claude.prompt_builder import PromptBuilder
from sovereign.tools.tool_registry import ToolRegistry
from sovereign.tools.builtin.web_search import WebSearchTool
from sovereign.tools.builtin.file_ops import FileOpsTool
from sovereign.tools.builtin.code_exec import CodeExecTool
from sovereign.tools.builtin.memory_tool import MemoryTool
from sovereign.memory.memory_manager import MemoryManager
from sovereign.registries.agent_registry import AgentRegistry
from sovereign.registries.prompt_registry import PromptRegistry
from sovereign.registries.decision_ledger import DecisionLedger, DecisionRecord
from sovereign.authority.approval_gate import ApprovalGate, ApprovalRequest
from sovereign.authority.thresholds import EscalationThresholds
from sovereign.executive.ceo_agent import CEOAgent
from sovereign.executive.chief_of_staff import ChiefOfStaff
from sovereign.executive.guardian import GuardianAgent
from sovereign.executive.coordinator import CoordinatorAgent
from sovereign.executive.task_setter import TaskSetterAgent
from sovereign.executive.decision_brief import DecisionBriefAgent
from sovereign.swarm.worker_agent import WorkerAgent
from sovereign.swarm.system_agent import SystemAgent
from sovereign.swarm.base_agent import AgentContext, AgentTask
from sovereign.factory.agent_factory import AgentFactory
from sovereign.input_fabric.pipeline import InputPipeline
from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.observability.health_monitor import HealthMonitor
from sovereign.router.cost_estimator import estimate_from_usage

logger = logging.getLogger(__name__)


class SovereignOrchestrator:
    """
    Top-level runtime. Owns all subsystem instances.

    Instantiate via bootstrap.create_orchestrator() rather than directly.
    """

    def __init__(self, config: "SovereignConfig") -> None:  # type: ignore[name-defined]
        self.config = config
        self._session_counter = 0

        self._init_claude_client()
        self._init_registries()
        self._init_memory()
        self._init_tools()
        self._init_prompt_builder()
        self._init_executive()
        self._init_factory()
        self._init_input_pipeline()
        self._init_health()

        logger.info(
            "SOVEREIGN AI OS started",
            mode=config.default_operating_mode,
            model=config.default_model,
            action_class=config.max_action_class,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle_request(self, user_input: str) -> StructuredOutput:
        """
        Main public entry point. Takes a raw user string, runs the full
        10-step session pipeline, and returns a StructuredOutput.
        """
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self._session_counter += 1
        logger.info("Session started", session_id=session_id)

        # --- Step 1: Input pipeline ---
        pipeline_out = await self._pipeline.process(user_input)
        if pipeline_out.warnings:
            for w in pipeline_out.warnings:
                logger.warning("Pipeline warning", warning=w, session=session_id)
        normalized = pipeline_out.normalized_text

        # --- Step 2: Memory snapshot ---
        snapshot = await self._memory.get_snapshot(
            domains=["identity", "operational", "project", "decision"]
        )

        ctx = AgentContext(
            session_id=session_id,
            operating_mode=self.config.default_operating_mode,
            memory_snapshot=snapshot,
            constitution_hash=self._constitution.constitution_hash(),
        )

        # --- Step 3: CEO agent — interpret intent, select mode ---
        ceo_task = AgentTask(
            objective=normalized,
            action_class=ActionClass.from_str(self.config.max_action_class),
        )
        ceo_output = await self._ceo.run(ceo_task, ctx)
        if ceo_output.data.get("operating_mode"):
            ctx.operating_mode = ceo_output.data["operating_mode"]

        # --- Step 4: Chief of Staff — decompose into tasks ---
        cos_task = AgentTask(
            objective=ceo_output.result,
            action_class=ActionClass.SUGGEST,
        )
        cos_output = await self._cos.run(cos_task, ctx)
        task_list: list[dict] = cos_output.data.get("tasks", [
            {"objective": normalized, "priority": 3, "agent_hint": "worker"}
        ])

        # --- Step 5: Dispatch first task to worker ---
        first_task_desc = task_list[0].get("objective", normalized) if task_list else normalized
        worker_task = AgentTask(
            objective=first_task_desc,
            action_class=ActionClass.from_str(self.config.max_action_class),
            context={"agent_hint": task_list[0].get("agent_hint", "worker")} if task_list else {},
        )

        # --- Step 6: Guardian review (for EXECUTE-class) ---
        action_class = ActionClass.from_str(self.config.max_action_class)
        requires_escalation = False

        if action_class >= ActionClass.EXECUTE:
            approved, risk, rationale = await self._guardian.review_action(
                agent_id="worker",
                action_description=first_task_desc,
                action_class=action_class,
                context={},
                ctx=ctx,
            )
            if not approved:
                requires_escalation = True

        # --- Step 7: Approval gate if needed ---
        if requires_escalation:
            req = ApprovalRequest(
                request_id=f"appr_{uuid.uuid4().hex[:8]}",
                agent_id="guardian",
                action_class=action_class,
                action_description=first_task_desc,
                context={"session_id": session_id},
                risk_score=risk,  # type: ignore[possibly-undefined]
            )
            result = await self._gate.request_approval(req)
            if result.decision.value != "approved":
                await self._ledger.record(DecisionRecord(
                    session_id=session_id,
                    agent_id="approval_gate",
                    decision_type="approval_rejected",
                    description=f"Action rejected: {first_task_desc[:100]}",
                    outcome=result.rationale,
                ))
                return StructuredOutput.escalated(
                    session_id=session_id,
                    agent_id="approval_gate",
                    task_id=worker_task.task_id,
                    reason=result.rationale,
                )

        # --- Step 5 (execute): Run worker ---
        worker_output = await self._worker.run(worker_task, ctx)

        # --- Step 8: Aggregate result ---
        final_output = StructuredOutput(
            session_id=session_id,
            agent_id="orchestrator",
            task_id=worker_task.task_id,
            status=worker_output.status,
            result=worker_output.result,
            data={
                "operating_mode": ctx.operating_mode,
                "ceo_brief": ceo_output.result,
                "tasks_generated": len(task_list),
                **(worker_output.data or {}),
            },
            reasoning=ceo_output.reasoning,
            confidence=worker_output.confidence,
            tokens_used=self._claude.get_usage(),
            requires_human_review=worker_output.requires_human_review,
        )

        # --- Step 9: Decision ledger ---
        await self._ledger.record(DecisionRecord(
            session_id=session_id,
            agent_id="orchestrator",
            decision_type="session_complete",
            description=f"Handled: {normalized[:100]}",
            outcome=final_output.status.value,
            confidence=final_output.confidence,
        ))

        # --- Step 10: Memory update ---
        await self._memory.write("operational", f"last_session_{session_id}", {
            "objective": normalized[:200],
            "mode": ctx.operating_mode,
            "status": final_output.status.value,
            "tokens": final_output.tokens_used,
        })

        # Health update
        total_tokens = sum(final_output.tokens_used.values())
        self._health.record_call(
            tokens=total_tokens,
            error=final_output.error if final_output.status == OutputStatus.FAILED else None,
        )

        logger.info(
            "Session complete",
            session_id=session_id,
            status=final_output.status.value,
            tokens=total_tokens,
            cost_usd=estimate_from_usage(self.config.default_model, final_output.tokens_used),
        )
        return final_output

    # ------------------------------------------------------------------
    # System queries
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """Return current system health status."""
        status = self._health.check(
            tool_registry=self._tool_registry,
            factory=self._factory,
        )
        return {
            "overall": status.overall,
            "checks": status.checks,
            "metrics": status.metrics,
            "alerts": status.alerts,
        }

    def get_usage(self) -> dict:
        """Return cumulative token usage."""
        return self._claude.get_usage()

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
        )

    def _init_registries(self) -> None:
        self._agent_registry = AgentRegistry()
        self._prompt_registry = PromptRegistry(self.config.prompts_dir)
        self._ledger = DecisionLedger(self.config.data_dir)

    def _init_memory(self) -> None:
        self._memory = MemoryManager(self.config.data_dir)

    def _init_tools(self) -> None:
        self._tool_registry = ToolRegistry()
        self._tool_registry.register(WebSearchTool())
        self._tool_registry.register(FileOpsTool(self.config.data_dir))
        self._tool_registry.register(CodeExecTool())
        self._tool_registry.register(MemoryTool(self._memory))

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
        self._ceo = CEOAgent(**shared)
        self._cos = ChiefOfStaff(**shared)
        self._guardian = GuardianAgent(**shared)
        self._coordinator = CoordinatorAgent(**shared)
        self._task_setter = TaskSetterAgent(**shared)
        self._decision_brief = DecisionBriefAgent(**shared)
        self._worker = WorkerAgent(**shared)
        self._system = SystemAgent(**shared)

        thresholds = EscalationThresholds.for_mode(self.config.default_operating_mode)
        self._gate = ApprovalGate(
            mode=self.config.approval_mode,
            thresholds=thresholds,
        )

        for agent in [
            self._ceo, self._cos, self._guardian, self._coordinator,
            self._task_setter, self._decision_brief, self._worker, self._system,
        ]:
            self._agent_registry.register(agent)

    def _init_factory(self) -> None:
        self._factory = AgentFactory(
            claude_client=self._claude,
            tool_registry=self._tool_registry,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
            agent_registry=self._agent_registry,
        )

    def _init_input_pipeline(self) -> None:
        self._pipeline = InputPipeline(config={
            "pii_filter": False,
            "max_chars": 50_000,
        })

    def _init_health(self) -> None:
        self._health = HealthMonitor()
