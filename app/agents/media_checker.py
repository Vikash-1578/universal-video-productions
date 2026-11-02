"""Agent 8: Media Checker."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging
from pathlib import Path

log = logging.getLogger("app.agents.media_checker")

class MediaCheckerAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        media_map = input_data.get("media_map", {})
        all_valid = True
        for sid, path in media_map.items():
            if not Path(path).exists(): all_valid = False
        return {"media_map": media_map, "all_valid": all_valid, "script": input_data.get("script", "")}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("all_valid", False)
