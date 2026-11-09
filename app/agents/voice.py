"""Agent 6: Voice Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.assets import fingerprint, remove_stale, scene_asset
import asyncio
import logging
from pathlib import Path

log = logging.getLogger("app.agents.voice")


def _done(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


class VoiceAgent(BaseAgent):
    concurrency = 3

    async def execute(self, project_id: int, state: dict) -> dict:
        audio_dir = self.hub.projects.folder(project_id, "assets", "audio")
        tts = self.hub.tts
        voice = (getattr(tts, "default_voice", ""), getattr(tts, "rate", ""), getattr(tts, "pitch", ""))
        sem = asyncio.Semaphore(self.concurrency)
        reused = 0

        async def one(scene: dict) -> dict:
            nonlocal reused
            path = scene_asset(audio_dir, scene["index"], fingerprint(scene["narration"], *voice), ".mp3")
            if _done(path):
                reused += 1  # already made by an earlier (interrupted) run
            else:
                async with sem:
                    await tts.synthesize(scene["narration"], path)
            return {**scene, "audio": str(path)}

        scenes = list(await asyncio.gather(*(one(s) for s in state.get("scenes", []))))
        remove_stale(audio_dir, {Path(s["audio"]).name for s in scenes}, "scene_*.mp3")
        if reused:
            log.info("Project %s: reused %d/%d existing voiceovers", project_id, reused, len(scenes))
        return {"scenes": scenes}

    async def verify(self, project_id: int, output: dict) -> bool:
        scenes = output.get("scenes", [])
        if scenes and all(s.get("audio") for s in scenes):
            return True
        output["feedback"] = "no narration audio was produced"
        return False
