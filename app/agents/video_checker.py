"""Agent 10: Video Checker."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging
from pathlib import Path

log = logging.getLogger("app.agents.video_checker")

class VideoCheckerAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        path = input_data.get("video_path")
        return {"status": "success" if path and Path(path).exists() else "fail", "video_path": path}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("status") == "success"
