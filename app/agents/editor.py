"""Agent 9: Editor Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.editor")


class EditorAgent(BaseAgent):
    max_attempts = 2

    async def execute(self, project_id: int, state: dict) -> dict:
        output = self.hub.projects.folder(project_id, "exports") / "final_video.mp4"
        path = await self.hub.renderer.render(state.get("scenes", []), output)
        return {"video_path": str(path)}

    async def verify(self, project_id: int, output: dict) -> bool:
        return bool(output.get("video_path"))
