"""File-based project store: data/projects/<id>/project.json plus asset folders.

project.json holds:
  status    queued | running | success | failed | cancelled
  pipeline  {"stage": <next stage to run>, "regressions": {...}} (the resume checkpoint)
  state     the shared pipeline state
  meta      who asked for it, e.g. {"source": "telegram", "chat_id": ..., "delivered": true}
"""
from __future__ import annotations
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("app.storage.projects")

UNFINISHED = {"queued", "running"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _meta_path(self, project_id: int) -> Path:
        return self.root / str(project_id) / "project.json"

    def create(self, topic: str, meta: dict | None = None) -> int:
        with self._lock:
            ids = [int(p.name) for p in self.root.iterdir() if p.is_dir() and p.name.isdigit()]
            pid = max(ids, default=0) + 1
            self.folder(pid)
            self._write(pid, {"id": pid, "topic": topic, "status": "queued", "created_at": _now(),
                              "pipeline": {}, "state": {}, "meta": dict(meta or {})})
        return pid

    def folder(self, project_id: int, *parts: str) -> Path:
        p = self.root.joinpath(str(project_id), *parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_project(self, project_id: int) -> dict:
        path = self._meta_path(project_id)
        if not path.exists():
            raise KeyError(f"Project {project_id} not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_projects(self) -> list[dict]:
        """All readable projects, oldest first."""
        out = []
        for p in self.root.iterdir():
            if not (p.is_dir() and p.name.isdigit()):
                continue
            try:
                out.append(self.get_project(int(p.name)))
            except (KeyError, ValueError, OSError) as e:
                log.warning("Skipping unreadable project %s: %s", p.name, e)
        return sorted(out, key=lambda d: d.get("id", 0))

    def update(self, project_id: int, *, meta: dict | None = None, **fields) -> dict:
        """Set top-level fields; ``meta`` is merged into the existing meta."""
        with self._lock:
            data = self.get_project(project_id)
            data.update(fields)
            if meta:
                data["meta"] = {**data.get("meta", {}), **meta}
            data["updated_at"] = _now()
            self._write(project_id, data)
            return data

    def set_status(self, project_id: int, status: str) -> None:
        self.update(project_id, status=status)

    def save_state(self, project_id: int, state: dict, pipeline: dict | None = None) -> None:
        fields = {"state": state}
        if pipeline is not None:
            fields["pipeline"] = pipeline
        self.update(project_id, **fields)

    def _write(self, project_id: int, data: dict) -> None:
        path = self._meta_path(project_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
