"""Agent 8: Media Checker."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.media.images import is_valid_image
import logging
from pathlib import Path

log = logging.getLogger("app.agents.media_checker")


class MediaCheckerAgent(BaseAgent):
    max_attempts = 1

    async def execute(self, project_id: int, state: dict) -> dict:
        problems = []
        for s in state.get("scenes", []):
            if not s.get("image") or not is_valid_image(s["image"]):
                problems.append(f"scene {s['index']}: image missing or corrupt")
            audio = Path(s.get("audio") or "")
            if not audio.is_file() or audio.stat().st_size == 0:
                problems.append(f"scene {s['index']}: audio missing or empty")
        if not state.get("scenes"):
            problems.append("no scenes")
        out = {"media_check": {"ok": not problems, "problems": problems}}
        if problems:
            out["feedback"] = "; ".join(problems)
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return output["media_check"]["ok"]
