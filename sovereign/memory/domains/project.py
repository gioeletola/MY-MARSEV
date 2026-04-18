"""
Memory domain: project — project board, task tracking, milestones.
Stores data in data/memory/projects.json.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/projects.json")
DOMAIN_NAME = "project"
PROJECT_STATUSES = ("active", "review", "blocked", "done", "archived")


class ProjectMemoryStore:
    """
    Persistent project board.
    Projects: id, name, description, status, progress, owner, deadline, tags, tasks, kpis
    Tasks: task_id, title, status (todo/in_progress/done/blocked), assignee, due_date, priority, notes
    """

    def __init__(self, data_file: Path = _DATA_FILE) -> None:
        self._path = data_file
        self._projects: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._projects = {p["project_id"]: p for p in raw}
        except Exception:
            pass

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(list(self._projects.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── project CRUD ─────────────────────────────────────────────────────

    def create_project(
        self,
        name: str,
        description: str = "",
        status: str = "active",
        owner: str = "",
        deadline: str = "",
        tags: list[str] | None = None,
        kpis: list[dict] | None = None,
    ) -> dict[str, Any]:
        project = {
            "project_id":  str(uuid.uuid4())[:8],
            "name":        name,
            "description": description,
            "status":      status,
            "progress":    0,
            "owner":       owner,
            "deadline":    deadline,
            "tags":        tags or [],
            "tasks":       [],
            "kpis":        kpis or [],
            "created_at":  datetime.now(timezone.utc).isoformat(),
            "updated_at":  datetime.now(timezone.utc).isoformat(),
        }
        self._projects[project["project_id"]] = project
        self._save()
        logger.info("project.create: '%s'", name)
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._projects.get(project_id)

    def update_project(self, project_id: str, **updates: Any) -> bool:
        project = self._projects.get(project_id)
        if not project:
            return False
        project.update({k: v for k, v in updates.items() if k != "project_id"})
        project["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def delete_project(self, project_id: str) -> bool:
        if project_id not in self._projects:
            return False
        del self._projects[project_id]
        self._save()
        return True

    def get_projects(self, status: str = "") -> list[dict[str, Any]]:
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.get("status") == status]
        return sorted(projects, key=lambda p: p.get("updated_at", ""), reverse=True)

    # ── task CRUD ─────────────────────────────────────────────────────────

    def add_task(
        self,
        project_id: str,
        title: str,
        assignee: str = "",
        due_date:  str = "",
        priority:  int = 2,
        notes:     str = "",
    ) -> dict[str, Any] | None:
        project = self._projects.get(project_id)
        if not project:
            return None
        task = {
            "task_id":      str(uuid.uuid4())[:8],
            "title":        title,
            "status":       "todo",
            "assignee":     assignee,
            "due_date":     due_date,
            "priority":     priority,
            "notes":        notes,
            "created_at":   datetime.now(timezone.utc).isoformat(),
            "completed_at": "",
        }
        project.setdefault("tasks", []).append(task)
        self._recalc_progress(project)
        self._save()
        return task

    def complete_task(self, project_id: str, task_id: str) -> bool:
        project = self._projects.get(project_id)
        if not project:
            return False
        for task in project.get("tasks", []):
            if task.get("task_id") == task_id:
                task["status"]       = "done"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._recalc_progress(project)
                self._save()
                return True
        return False

    def update_task(self, project_id: str, task_id: str, **updates: Any) -> bool:
        project = self._projects.get(project_id)
        if not project:
            return False
        for task in project.get("tasks", []):
            if task.get("task_id") == task_id:
                task.update({k: v for k, v in updates.items() if k != "task_id"})
                self._recalc_progress(project)
                self._save()
                return True
        return False

    def _recalc_progress(self, project: dict) -> None:
        tasks = project.get("tasks", [])
        if not tasks:
            return
        done = sum(1 for t in tasks if t.get("status") == "done")
        project["progress"]    = round(done / len(tasks) * 100)
        project["updated_at"]  = datetime.now(timezone.utc).isoformat()

    # ── summary ───────────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        projects = list(self._projects.values())
        return {
            "total":        len(projects),
            "active":       sum(1 for p in projects if p.get("status") == "active"),
            "blocked":      sum(1 for p in projects if p.get("status") == "blocked"),
            "done":         sum(1 for p in projects if p.get("status") == "done"),
            "review":       sum(1 for p in projects if p.get("status") == "review"),
            "avg_progress": round(sum(p.get("progress",0) for p in projects) / max(len(projects),1), 1),
        }
