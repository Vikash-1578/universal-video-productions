"""Agent 10: Video Checker."""
from __future__ import annotations
from app.core.agent import BaseAgent
import asyncio
import logging
from pathlib import Path

log = logging.getLogger("app.agents.video_checker")


def _duration(path: str) -> float:
    from moviepy import VideoFileClip
    with VideoFileClip(path) as clip:
        return float(clip.duration or 0)


class VideoCheckerAgent(BaseAgent):
    max_attempts = 1

    async def execute(self, project_id: int, state: dict) -> dict:
        path = state.get("video_path")
        if not path or not Path(path).is_file() or Path(path).stat().st_size < 1024:
            return {"video_check": {"ok": False}, "feedback": f"video file missing or empty: {path}"}
        try:
            duration = await asyncio.to_thread(_duration, path)
        except Exception as e:
            return {"video_check": {"ok": False}, "feedback": f"video cannot be opened: {e}"}
        if duration < 1:
            return {"video_check": {"ok": False}, "feedback": f"video is only {duration:.1f}s long"}
        return {"video_check": {"ok": True, "duration": round(duration, 2)}}

    async def verify(self, project_id: int, output: dict) -> bool:
        return output["video_check"]["ok"]
