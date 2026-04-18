"""
Builder Studio — no-code/low-code agent and workflow composition environment.

Allows the user to:
- Compose multi-step workflows from existing agents
- Spawn ephemeral agents with custom personas
- Run A/B experiments across agent configurations
- Export workflow blueprints as YAML/JSON
"""
from __future__ import annotations

import json
import logging
import pathlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentBlueprint:
    """User-defined custom agent descriptor."""
    blueprint_id: str
    name: str
    specialty: str
    instructions: str
    tools: list[str] = field(default_factory=lambda: ["memory_tool"])
    model: str = "claude-sonnet-4-6"
    requires_review: bool = False
    confidence: float = 0.80
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkflowBlueprint:
    """User-composed multi-step workflow."""
    workflow_id: str
    name: str
    description: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    # Each step: {"agent_id": str, "task_template": str, "depends_on": list[str]}
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)
    version: int = 1


class BuilderStudio:
    """
    Composition environment for agents and workflows.

    Persists blueprints to disk as JSON for portability.
    Integrates with AgentFactory and WorkflowRegistry.
    """

    def __init__(
        self,
        data_dir: str | pathlib.Path = "data/builder",
        agent_factory: Any = None,
        workflow_registry: Any = None,
    ) -> None:
        self._data_dir = pathlib.Path(data_dir)
        self._agent_factory = agent_factory
        self._workflow_registry = workflow_registry
        self._agent_blueprints: dict[str, AgentBlueprint] = {}
        self._workflow_blueprints: dict[str, WorkflowBlueprint] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Agent Blueprints
    # ------------------------------------------------------------------

    def create_agent(
        self,
        name: str,
        specialty: str,
        instructions: str,
        tools: list[str] | None = None,
        model: str = "claude-sonnet-4-6",
        requires_review: bool = False,
        tags: list[str] | None = None,
    ) -> AgentBlueprint:
        """Create and persist a custom agent blueprint."""
        bp = AgentBlueprint(
            blueprint_id=str(uuid.uuid4())[:8],
            name=name,
            specialty=specialty,
            instructions=instructions,
            tools=tools or ["memory_tool"],
            model=model,
            requires_review=requires_review,
            tags=tags or [],
        )
        self._agent_blueprints[bp.blueprint_id] = bp
        self._persist_agents()
        logger.info("BuilderStudio: created agent blueprint '%s' (id=%s)", name, bp.blueprint_id)
        return bp

    def get_agent_blueprint(self, blueprint_id: str) -> AgentBlueprint | None:
        return self._agent_blueprints.get(blueprint_id)

    def list_agent_blueprints(self) -> list[AgentBlueprint]:
        return list(self._agent_blueprints.values())

    def delete_agent_blueprint(self, blueprint_id: str) -> bool:
        if blueprint_id in self._agent_blueprints:
            del self._agent_blueprints[blueprint_id]
            self._persist_agents()
            return True
        return False

    def instantiate_agent(self, blueprint_id: str) -> Any:
        """
        Instantiate a blueprint as a live agent via the agent factory.
        Returns the agent instance or None if factory unavailable.
        """
        bp = self._agent_blueprints.get(blueprint_id)
        if bp is None:
            raise KeyError(f"Blueprint not found: {blueprint_id}")
        if self._agent_factory is None:
            logger.warning("BuilderStudio: no agent_factory set, cannot instantiate")
            return None

        from sovereign.factory.agent_spec import AgentSpec
        spec = AgentSpec(
            agent_id=f"custom_{bp.blueprint_id}",
            objective=bp.instructions,
            tools=bp.tools,
            model=bp.model,
        )
        return self._agent_factory.spawn(spec)

    # ------------------------------------------------------------------
    # Workflow Blueprints
    # ------------------------------------------------------------------

    def create_workflow(
        self,
        name: str,
        description: str,
        steps: list[dict[str, Any]],
        tags: list[str] | None = None,
    ) -> WorkflowBlueprint:
        """Create and persist a workflow blueprint."""
        wf = WorkflowBlueprint(
            workflow_id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            steps=steps,
            tags=tags or [],
        )
        self._workflow_blueprints[wf.workflow_id] = wf
        self._persist_workflows()
        # Register with workflow registry if available
        if self._workflow_registry:
            try:
                self._workflow_registry.register(
                    name=wf.name,
                    steps=[s.get("task_template", "") for s in steps],
                )
            except Exception as exc:
                logger.warning("BuilderStudio: workflow registry registration failed: %s", exc)
        logger.info("BuilderStudio: created workflow '%s' (id=%s)", name, wf.workflow_id)
        return wf

    def get_workflow_blueprint(self, workflow_id: str) -> WorkflowBlueprint | None:
        return self._workflow_blueprints.get(workflow_id)

    def list_workflow_blueprints(self) -> list[WorkflowBlueprint]:
        return list(self._workflow_blueprints.values())

    def export_workflow(self, workflow_id: str, fmt: str = "json") -> str:
        """Export a workflow as JSON or YAML string."""
        wf = self._workflow_blueprints.get(workflow_id)
        if wf is None:
            raise KeyError(f"Workflow not found: {workflow_id}")
        data = asdict(wf)
        if fmt == "yaml":
            try:
                import yaml  # type: ignore
                return yaml.dump(data, default_flow_style=False)
            except ImportError:
                logger.warning("PyYAML not installed, falling back to JSON")
        return json.dumps(data, indent=2, default=str)

    def import_workflow(self, raw: str, fmt: str = "json") -> WorkflowBlueprint:
        """Import a workflow from JSON/YAML string."""
        if fmt == "yaml":
            import yaml  # type: ignore
            data = yaml.safe_load(raw)
        else:
            data = json.loads(raw)
        wf = WorkflowBlueprint(**data)
        self._workflow_blueprints[wf.workflow_id] = wf
        self._persist_workflows()
        return wf

    # ------------------------------------------------------------------
    # Studio dashboard
    # ------------------------------------------------------------------

    def dashboard(self) -> dict[str, Any]:
        return {
            "agent_blueprints": len(self._agent_blueprints),
            "workflow_blueprints": len(self._workflow_blueprints),
            "agents": [{"id": b.blueprint_id, "name": b.name} for b in self._agent_blueprints.values()],
            "workflows": [{"id": w.workflow_id, "name": w.name, "steps": len(w.steps)} for w in self._workflow_blueprints.values()],
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        agents_path = self._data_dir / "agent_blueprints.json"
        workflows_path = self._data_dir / "workflow_blueprints.json"

        if agents_path.exists():
            try:
                raw = json.loads(agents_path.read_text("utf-8"))
                self._agent_blueprints = {k: AgentBlueprint(**v) for k, v in raw.items()}
                logger.info("BuilderStudio: loaded %d agent blueprints", len(self._agent_blueprints))
            except Exception as exc:
                logger.warning("BuilderStudio: agent blueprints load error: %s", exc)

        if workflows_path.exists():
            try:
                raw = json.loads(workflows_path.read_text("utf-8"))
                self._workflow_blueprints = {k: WorkflowBlueprint(**v) for k, v in raw.items()}
                logger.info("BuilderStudio: loaded %d workflow blueprints", len(self._workflow_blueprints))
            except Exception as exc:
                logger.warning("BuilderStudio: workflow blueprints load error: %s", exc)

    def _persist_agents(self) -> None:
        path = self._data_dir / "agent_blueprints.json"
        try:
            path.write_text(
                json.dumps({k: asdict(v) for k, v in self._agent_blueprints.items()}, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("BuilderStudio: persist agents failed: %s", exc)

    def _persist_workflows(self) -> None:
        path = self._data_dir / "workflow_blueprints.json"
        try:
            path.write_text(
                json.dumps({k: asdict(v) for k, v in self._workflow_blueprints.items()}, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("BuilderStudio: persist workflows failed: %s", exc)
