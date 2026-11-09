"""Agent 7: Media Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.assets import fingerprint, remove_stale, scene_asset
from app.media.images import is_valid_image
import asyncio
import logging
from pathlib import Path

log = logging.getLogger("app.agents.media")

STYLE = "cinematic, mysterious, dramatic lighting, highly detailed, 16:9"


class MediaAgent(BaseAgent):
    concurrency = 3

    async def execute(self, project_id: int, state: dict) -> dict:
        media_dir = self.hub.projects.folder(project_id, "assets", "media")
        width, height = self.hub.settings.video_width, self.hub.settings.video_height
        sem = asyncio.Semaphore(self.concurrency)
        reused = 0

        async def one(scene: dict) -> dict:
            nonlocal reused
            prompt = f"{scene['visual']}, {STYLE}"
            path = scene_asset(media_dir, scene["index"], fingerprint(prompt, width, height), ".jpg")
            # Reuse images from an interrupted run, or ones the media checker did not
            # reject; anything missing or corrupt is generated again.
            if is_valid_image(path):
                reused += 1
            else:
                async with sem:
                    await self.hub.images.generate(prompt, path, width, height)
            return {**scene, "image": str(path)}

        scenes = list(await asyncio.gather(*(one(s) for s in state.get("scenes", []))))
        remove_stale(media_dir, {Path(s["image"]).name for s in scenes}, "scene_*.jpg")
        if reused:
            log.info("Project %s: reused %d/%d existing images", project_id, reused, len(scenes))
        return {"scenes": scenes}

    async def verify(self, project_id: int, output: dict) -> bool:
        scenes = output.get("scenes", [])
        if scenes and all(s.get("image") for s in scenes):
            return True
        output["feedback"] = "no images were produced"
        return False
