"""File-based project store: data/projects/<id>/project.json plus asset folders."""
from __future__ import annotations
import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class ProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _meta(self, project_id: int) -> Path:
        return self.root / str(project_id) / "project.json"

    def create(self, topic: str) -> int:
        with self._lock:
            ids = [int(p.name) for p in self.root.iterdir() if p.is_dir() and p.name.isdigit()]
            pid = max(ids, default=0) + 1
            self.folder(pid)
            self._write(pid, {"id": pid, "topic": topic,
                              "created_at": datetime.now(timezone.utc).isoformat(), "state": {}})
        return pid

    def folder(self, project_id: int, *parts: str) -> Path:
        p = self.root.joinpath(str(project_id), *parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_project(self, project_id: int) -> dict:
        path = self._meta(project_id)
        if not path.exists():
            raise KeyError(f"Project {project_id} not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_state(self, project_id: int, state: dict) -> None:
        with self._lock:
            data = self.get_project(project_id)
            data["state"] = state
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write(project_id, data)

    def _write(self, project_id: int, data: dict) -> None:
        path = self._meta(project_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
