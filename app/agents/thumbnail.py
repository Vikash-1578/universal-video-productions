"""Agent 11: Thumbnail Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging
from pathlib import Path

log = logging.getLogger("app.agents.thumbnail")

class ThumbnailAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        topic = input_data.get("topic", "Mystery")
        export_dir = self.hub.projects.folder(project_id, "exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / "thumbnail.jpg"
        await self.hub.free_gen.generate(f"Viral cinematic thumbnail for {topic}", path)
        return {"thumbnail_path": str(path)}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return Path(output_data.get("thumbnail_path", "")).exists()
