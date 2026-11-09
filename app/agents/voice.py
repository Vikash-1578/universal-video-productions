"""Agent 6: Voice Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.voice")


class VoiceAgent(BaseAgent):
    async def execute(self, project_id: int, state: dict) -> dict:
        audio_dir = self.hub.projects.folder(project_id, "assets", "audio")
        scenes = []
        for scene in state.get("scenes", []):
            path = audio_dir / f"scene_{scene['index']}.mp3"
            await self.hub.tts.synthesize(scene["narration"], path)
            scenes.append({**scene, "audio": str(path)})
        return {"scenes": scenes}

    async def verify(self, project_id: int, output: dict) -> bool:
        scenes = output.get("scenes", [])
        if scenes and all(s.get("audio") for s in scenes):
            return True
        output["feedback"] = "no narration audio was produced"
        return False
