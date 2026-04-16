"""
Human Layer — coordinates human collaborators within the SOVEREIGN AI OS.

Manages: human roles, access levels, task assignments to real people,
handoff protocols, and human-in-the-loop workflows.
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

_DEFAULT_PATH = pathlib.Path("data/memory/human_layer.json")


@dataclass
class HumanCollaborator:
    """A registered human collaborator in the system."""
    human_id: str
    name: str
    role: str              # "assistant" | "contractor" | "advisor" | "partner" | "developer"
    access_level: str      # "read" | "suggest" | "draft" | "execute"
    email: str = ""
    phone: str = ""
    timezone: str = "UTC"
    skills: list[str] = field(default_factory=list)
    active: bool = True
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HumanTask:
    """A task assigned to a human collaborator."""
    task_id: str
    human_id: str
    title: str
    description: str
    priority: int = 2      # 1 = urgent, 2 = normal, 3 = low
    deadline: str = ""
    status: str = "pending"  # "pending" | "in_progress" | "done" | "blocked" | "cancelled"
    context: dict[str, Any] = field(default_factory=dict)
    deliverable: str = ""  # what to hand back
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    notes: str = ""


@dataclass
class HandoffBrief:
    """Context brief for handing a task to a human."""
    brief_id: str
    task_id: str
    human_id: str
    background: str
    objective: str
    deliverable: str
    constraints: list[str]
    resources: list[str]
    deadline: str
    contact_on_blocker: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanLayer:
    """
    Manages human collaborators and human-AI workflows.

    Supports:
    - Registering human collaborators with roles and access
    - Assigning tasks to humans with context briefs
    - Tracking task status and handoffs
    - Generating handoff briefs for complex tasks
    - Aggregating human task load
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._humans: dict[str, HumanCollaborator] = {}
        self._tasks: dict[str, HumanTask] = {}
        self._briefs: dict[str, HandoffBrief] = {}
        self._load()

    # ------------------------------------------------------------------
    # Human management
    # ------------------------------------------------------------------

    def register_human(self, human: HumanCollaborator) -> None:
        self._humans[human.human_id] = human
        self._persist()
        logger.info("HumanLayer: registered collaborator %s (%s)", human.name, human.role)

    def get_human(self, human_id: str) -> HumanCollaborator | None:
        return self._humans.get(human_id)

    def list_humans(self, active_only: bool = True) -> list[HumanCollaborator]:
        humans = list(self._humans.values())
        return [h for h in humans if h.active] if active_only else humans

    def deactivate_human(self, human_id: str) -> None:
        if h := self._humans.get(human_id):
            h.active = False
            self._persist()

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def assign_task(self, task: HumanTask) -> HumanTask:
        """Assign a task to a human collaborator."""
        self._tasks[task.task_id] = task
        self._persist()
        logger.info("HumanLayer: assigned task '%s' to human %s", task.title, task.human_id)
        return task

    def create_and_assign(
        self,
        human_id: str,
        title: str,
        description: str,
        deliverable: str,
        priority: int = 2,
        deadline: str = "",
        context: dict[str, Any] | None = None,
    ) -> HumanTask:
        task = HumanTask(
            task_id=str(uuid.uuid4())[:8],
            human_id=human_id,
            title=title,
            description=description,
            deliverable=deliverable,
            priority=priority,
            deadline=deadline,
            context=context or {},
        )
        return self.assign_task(task)

    def update_task_status(self, task_id: str, status: str, notes: str = "") -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = status
        task.notes = notes
        if status == "done":
            task.completed_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return True

    def get_tasks_for_human(self, human_id: str, status: str | None = None) -> list[HumanTask]:
        tasks = [t for t in self._tasks.values() if t.human_id == human_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.priority)

    def pending_tasks(self) -> list[HumanTask]:
        return [t for t in self._tasks.values() if t.status in ("pending", "in_progress")]

    # ------------------------------------------------------------------
    # Handoff briefs
    # ------------------------------------------------------------------

    def create_handoff_brief(
        self,
        task_id: str,
        human_id: str,
        background: str,
        objective: str,
        deliverable: str,
        constraints: list[str] | None = None,
        resources: list[str] | None = None,
        deadline: str = "",
        contact_on_blocker: str = "",
    ) -> HandoffBrief:
        brief = HandoffBrief(
            brief_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            human_id=human_id,
            background=background,
            objective=objective,
            deliverable=deliverable,
            constraints=constraints or [],
            resources=resources or [],
            deadline=deadline,
            contact_on_blocker=contact_on_blocker,
        )
        self._briefs[brief.brief_id] = brief
        self._persist()
        return brief

    def format_brief(self, brief_id: str) -> str:
        """Render a handoff brief as a human-readable string."""
        brief = self._briefs.get(brief_id)
        if not brief:
            return ""
        human = self._humans.get(brief.human_id)
        human_name = human.name if human else brief.human_id
        lines = [
            f"# HANDOFF BRIEF — {brief.brief_id}",
            f"**To:** {human_name}",
            f"**Task ID:** {brief.task_id}",
            f"**Deadline:** {brief.deadline or 'TBD'}",
            "",
            f"## Background\n{brief.background}",
            f"## Objective\n{brief.objective}",
            f"## Deliverable\n{brief.deliverable}",
        ]
        if brief.constraints:
            lines += ["## Constraints"] + [f"- {c}" for c in brief.constraints]
        if brief.resources:
            lines += ["## Resources"] + [f"- {r}" for r in brief.resources]
        if brief.contact_on_blocker:
            lines += [f"\n**On blocker:** {brief.contact_on_blocker}"]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def dashboard(self) -> dict[str, Any]:
        pending = self.pending_tasks()
        return {
            "collaborators": len(self.list_humans()),
            "pending_tasks": len(pending),
            "tasks_by_human": {
                h.human_id: len(self.get_tasks_for_human(h.human_id, "pending"))
                for h in self.list_humans()
            },
            "overdue_tasks": [
                t.title for t in pending
                if t.deadline and t.deadline < datetime.now(timezone.utc).isoformat()
            ],
        }

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text("utf-8"))
            self._humans = {k: HumanCollaborator(**v) for k, v in raw.get("humans", {}).items()}
            self._tasks = {k: HumanTask(**v) for k, v in raw.get("tasks", {}).items()}
            self._briefs = {k: HandoffBrief(**v) for k, v in raw.get("briefs", {}).items()}
            logger.info("HumanLayer loaded: %d humans, %d tasks", len(self._humans), len(self._tasks))
        except Exception as exc:
            logger.warning("HumanLayer load error: %s", exc)

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({
                "humans": {k: asdict(v) for k, v in self._humans.items()},
                "tasks": {k: asdict(v) for k, v in self._tasks.items()},
                "briefs": {k: asdict(v) for k, v in self._briefs.items()},
            }, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.error("HumanLayer persist failed: %s", exc)
