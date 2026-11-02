"""Agent 6: Voice Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging
from pathlib import Path
import re

log = logging.getLogger("app.agents.voice")

class VoiceAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        script = input_data.get("script", "")
        export_dir = self.hub.projects.folder(project_id, "assets", "audio")
        export_dir.mkdir(parents=True, exist_ok=True)
        scenes = re.split(r"\[Scene \d+.*?\]", script)
        scenes = [s.strip() for s in scenes if s.strip()]
        audio_files = []
        for idx, text in enumerate(scenes):
            path = export_dir / f"scene_{idx+1}.mp3"
            await self.hub.tts.synthesize(text, path)
            audio_files.append(str(path))
        return {"audio_files": audio_files, "script": script}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return len(output_data.get("audio_files", [])) > 0
