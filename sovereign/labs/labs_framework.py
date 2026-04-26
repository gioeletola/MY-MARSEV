"""
Labs Framework — experimental sandbox for hypothesis-driven AI OS improvements.

Enables:
- A/B experiments across agent configurations
- Hypothesis logging and validation
- Metric collection per experiment
- Graduation of successful experiments to production
"""
from __future__ import annotations

import json
import logging
import pathlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/labs/experiments.json")


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    GRADUATED = "graduated"   # promoted to production
    FAILED = "failed"


@dataclass
class Hypothesis:
    """A testable hypothesis."""
    statement: str          # "If X then Y because Z"
    metric: str             # what to measure
    success_threshold: float  # value that constitutes success
    baseline: float = 0.0   # current baseline value


@dataclass
class Experiment:
    """A single A/B or multivariate experiment."""
    experiment_id: str
    name: str
    description: str
    hypothesis: Hypothesis
    status: ExperimentStatus = ExperimentStatus.DRAFT
    control_config: dict[str, Any] = field(default_factory=dict)
    treatment_config: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    tags: list[str] = field(default_factory=list)


class LabsFramework:
    """
    Experimental sandbox for SOVEREIGN AI OS improvements.

    Lifecycle: DRAFT → RUNNING → COMPLETED → GRADUATED (or FAILED)
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._experiments: dict[str, Experiment] = {}
        self._load()

    # ------------------------------------------------------------------
    # Experiment management
    # ------------------------------------------------------------------

    def create_experiment(
        self,
        name: str,
        description: str,
        hypothesis: Hypothesis,
        control_config: dict[str, Any] | None = None,
        treatment_config: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Experiment:
        exp = Experiment(
            experiment_id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            hypothesis=hypothesis,
            control_config=control_config or {},
            treatment_config=treatment_config or {},
            tags=tags or [],
        )
        self._experiments[exp.experiment_id] = exp
        self._persist()
        logger.info("Labs: created experiment '%s' (id=%s)", name, exp.experiment_id)
        return exp

    def start(self, experiment_id: str) -> None:
        exp = self._get(experiment_id)
        exp.status = ExperimentStatus.RUNNING
        exp.started_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        logger.info("Labs: started experiment %s", experiment_id)

    def pause(self, experiment_id: str) -> None:
        exp = self._get(experiment_id)
        exp.status = ExperimentStatus.PAUSED
        self._persist()

    def record_observation(self, experiment_id: str, observation: str) -> None:
        exp = self._get(experiment_id)
        exp.observations.append(
            f"[{datetime.now(timezone.utc).isoformat()}] {observation}"
        )
        self._persist()

    def record_result(self, experiment_id: str, metric: str, value: float, extra: dict | None = None) -> None:
        exp = self._get(experiment_id)
        exp.results[metric] = {"value": value, "extra": extra or {}, "ts": datetime.now(timezone.utc).isoformat()}
        self._persist()

    def complete(self, experiment_id: str) -> dict[str, Any]:
        """Mark experiment complete and evaluate hypothesis."""
        exp = self._get(experiment_id)
        exp.status = ExperimentStatus.COMPLETED
        exp.completed_at = datetime.now(timezone.utc).isoformat()

        # Evaluate hypothesis
        metric_result = exp.results.get(exp.hypothesis.metric, {})
        measured_value = metric_result.get("value", exp.hypothesis.baseline)
        success = measured_value >= exp.hypothesis.success_threshold
        exp.results["__evaluation__"] = {
            "success": success,
            "measured": measured_value,
            "threshold": exp.hypothesis.success_threshold,
        }
        if not success:
            exp.status = ExperimentStatus.FAILED

        self._persist()
        logger.info("Labs: experiment %s completed success=%s", experiment_id, success)
        return exp.results["__evaluation__"]

    def graduate(self, experiment_id: str) -> None:
        """Promote a successful experiment to production."""
        exp = self._get(experiment_id)
        if exp.status not in (ExperimentStatus.COMPLETED,):
            raise ValueError(f"Cannot graduate experiment in status {exp.status}")
        exp.status = ExperimentStatus.GRADUATED
        self._persist()
        logger.info("Labs: experiment %s GRADUATED to production", experiment_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)

    def list_experiments(self, status: ExperimentStatus | None = None) -> list[Experiment]:
        exps = list(self._experiments.values())
        if status:
            exps = [e for e in exps if e.status == status]
        return exps

    def running_experiments(self) -> list[Experiment]:
        return self.list_experiments(ExperimentStatus.RUNNING)

    def dashboard(self) -> dict[str, Any]:
        all_exp = list(self._experiments.values())
        by_status: dict[str, int] = {}
        for e in all_exp:
            by_status[e.status.value] = by_status.get(e.status.value, 0) + 1
        return {
            "total": len(all_exp),
            "by_status": by_status,
            "graduated": [e.name for e in all_exp if e.status == ExperimentStatus.GRADUATED],
        }

    # ------------------------------------------------------------------
    # High-level lab operations (use class attributes from subclasses)
    # ------------------------------------------------------------------

    # Subclasses can override these class-level attributes
    lab_id: str = "base"
    lab_name: str = "Base Lab"
    description: str = ""
    agents: list[str] = []
    tools: list[str] = ["memory_tool"]
    benchmarks: dict[str, float] = {}
    output_standards: dict[str, str] = {}
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates: list[dict[str, Any]] = []  # subclasses populate

    def quick_experiment(self, template_index: int = 0) -> Experiment:
        """
        Create and start an experiment from the lab's built-in templates.
        Falls back to a generic template if none are defined.
        """
        templates = getattr(self, "experiment_templates", [])
        if templates and template_index < len(templates):
            tmpl = templates[template_index]
        else:
            tmpl = {
                "name": f"{self.lab_name} — Quick Experiment",
                "description": f"Auto-generated experiment for {self.lab_name}.",
                "hypothesis": {
                    "statement": f"Applying {self.lab_name} methods will improve output quality",
                    "metric": "quality_score",
                    "success_threshold": 0.75,
                    "baseline": 0.5,
                },
                "tags": [self.lab_id, "quick"],
            }
        hyp = Hypothesis(**tmpl["hypothesis"])
        exp = self.create_experiment(
            name=tmpl["name"],
            description=tmpl["description"],
            hypothesis=hyp,
            control_config=tmpl.get("control_config", {}),
            treatment_config=tmpl.get("treatment_config", {}),
            tags=tmpl.get("tags", [self.lab_id]),
        )
        self.start(exp.experiment_id)
        return exp

    def suggest_experiments(self) -> list[str]:
        """Return a list of experiment ideas specific to this lab domain."""
        templates = getattr(self, "experiment_templates", [])
        if templates:
            return [t["name"] for t in templates]
        return [f"{self.lab_name}: hypothesis-driven experiment (no templates defined)"]

    def status_report(self) -> dict[str, Any]:
        """Rich status report for this lab instance."""
        db = self.dashboard()
        running = self.running_experiments()
        return {
            "lab_id": self.lab_id,
            "lab_name": self.lab_name,
            "description": self.description,
            "agents": self.agents,
            "tools": self.tools,
            "benchmarks": self.benchmarks,
            "experiment_summary": db,
            "running": [{"id": e.experiment_id, "name": e.name} for e in running],
            "templates_available": len(getattr(self, "experiment_templates", [])),
        }

    async def run_analysis(
        self,
        topic: str,
        context: str = "",
        claude_client: Any = None,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """
        Run a Claude-powered analysis on a topic within this lab's domain.

        Returns a dict with keys: analysis, lab_id, topic, model, tokens_used.
        Falls back to a stub if no claude_client is provided.
        """
        context_block = f"Context:\n{context}\n\n" if context else ""
        prompt = (
            f"You are the {self.lab_name} of the SOVEREIGN AI OS.\n\n"
            f"Lab Description: {self.description}\n\n"
            f"Available Agents: {', '.join(self.agents)}\n"
            f"Success Benchmarks: {self.benchmarks}\n\n"
            f"{context_block}"
            f"Topic to Analyse:\n{topic}\n\n"
            "Provide a structured, actionable analysis. Include:\n"
            "1. Key findings (3-5 bullet points)\n"
            "2. Recommended experiments to run\n"
            "3. Risk factors\n"
            "4. Expected outcomes\n"
            "5. Next steps"
        )

        if claude_client is None:
            return {
                "analysis": f"[{self.lab_name} stub — no Claude client provided]\nTopic: {topic}",
                "lab_id": self.lab_id,
                "topic": topic,
                "model": self.model,
                "tokens_used": 0,
            }

        try:
            response = await claude_client.complete(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=max_tokens,
            )
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return {
                "analysis": text,
                "lab_id": self.lab_id,
                "topic": topic,
                "model": self.model,
                "tokens_used": tokens,
            }
        except Exception as exc:
            logger.error("LabsFramework.run_analysis failed: %s", exc)
            return {"analysis": f"[Error: {exc}]", "lab_id": self.lab_id, "topic": topic, "model": self.model, "tokens_used": 0}

    # ------------------------------------------------------------------

    def _get(self, experiment_id: str) -> Experiment:
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"Experiment not found: {experiment_id}")
        return exp

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text("utf-8"))
            for eid, data in raw.items():
                # Reconstruct nested Hypothesis
                hyp_data = data.pop("hypothesis", {})
                hyp = Hypothesis(**hyp_data)
                data["hypothesis"] = hyp
                data["status"] = ExperimentStatus(data.get("status", "draft"))
                self._experiments[eid] = Experiment(**data)
            logger.info("Labs: loaded %d experiments", len(self._experiments))
        except Exception as exc:
            logger.warning("Labs load error: %s", exc)

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)

            def _serialize(exp: Experiment) -> dict:
                d = asdict(exp)
                d["status"] = exp.status.value
                return d

            self._path.write_text(
                json.dumps({k: _serialize(v) for k, v in self._experiments.items()}, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Labs persist failed: %s", exc)
