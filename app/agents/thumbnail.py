"""Agent 11: Thumbnail Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.media.images import is_valid_image
import logging

log = logging.getLogger("app.agents.thumbnail")


class ThumbnailAgent(BaseAgent):
    async def execute(self, project_id: int, state: dict) -> dict:
        topic = state.get("topic") or "Mystery"
        path = self.hub.projects.folder(project_id, "exports") / "thumbnail.jpg"
        await self.hub.images.generate(
            f"Viral YouTube thumbnail about {topic}, cinematic, dramatic lighting, bold focal subject, "
            "high contrast, no text", path, 1280, 720)
        return {"thumbnail_path": str(path)}

    async def verify(self, project_id: int, output: dict) -> bool:
        return is_valid_image(output.get("thumbnail_path", ""))
