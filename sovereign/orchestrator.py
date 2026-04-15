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
import uuid
import logging
from typing import Any, AsyncIterator, Callable

from sovereign.kernel.action_classes import ActionClass
from sovereign.kernel.constitution import default_constitution
from sovereign.kernel.stop_conditions import StopConditionEvaluator
from sovereign.claude.client import ClaudeClient
from sovereign.claude.prompt_builder import PromptBuilder
from sovereign.tools.tool_registry import ToolRegistry
from sovereign.tools.tool_router import ToolRouter
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
from sovereign.swarm.domain_chiefs import ResearchChief, FinanceChief, ContentChief, LegalChief
from sovereign.factory.agent_factory import AgentFactory
from sovereign.input_fabric.pipeline import InputPipeline
from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.observability.health_monitor import HealthMonitor
from sovereign.router.model_router import ModelRouter
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
        # Streaming event callbacks registered by the UI layer
        self._event_callbacks: list[Callable[[dict[str, Any]], None]] = []

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
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle_request(
        self,
        user_input: str,
        operating_mode: str | None = None,
    ) -> StructuredOutput:
        """
        Main public entry point. Takes a raw user string, runs the full
        10-step session pipeline, and returns a StructuredOutput.
        """
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        self._session_counter += 1
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
            domains=["identity", "operational", "project", "decision"]
        )

        mode = operating_mode or self.config.default_operating_mode
        ctx = AgentContext(
            session_id=session_id,
            operating_mode=mode,
            memory_snapshot=snapshot,
            constitution_hash=self._constitution.constitution_hash(),
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
        self._emit("session_complete", {
            "session_id": session_id,
            "status": final_output.status.value,
            "tokens": total_tokens,
            "cost_usd": estimate_from_usage(self.config.default_model, token_usage),
            "result_preview": final_output.result[:300],
        })

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
            "ceo":       self._ceo,
            "research":  self._research_chief,
            "finance":   self._finance_chief,
            "content":   self._content_chief,
            "legal":     self._legal_chief,
            "guardian":  self._guardian,
            "system":    self._system,
            "worker":    self._worker,
        }
        return mapping.get(hint.lower(), self._worker)

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
        }

    def get_usage(self) -> dict:
        return self._claude.get_usage()

    def get_session_count(self) -> int:
        return self._session_counter

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
        self._model_router = ModelRouter()

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

        thresholds = EscalationThresholds.for_mode(self.config.default_operating_mode)
        self._gate = ApprovalGate(
            mode=self.config.approval_mode,
            thresholds=thresholds,
        )
        for agent in [
            self._ceo, self._cos, self._guardian, self._coordinator,
            self._task_setter, self._decision_brief, self._worker, self._system,
            self._research_chief, self._finance_chief,
            self._content_chief, self._legal_chief,
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
        self._pipeline = InputPipeline(config={"pii_filter": False, "max_chars": 50_000})

    def _init_health(self) -> None:
        self._health = HealthMonitor()
