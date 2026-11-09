"""Agent 7: Media Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.media.images import is_valid_image
import asyncio
import logging

log = logging.getLogger("app.agents.media")

STYLE = "cinematic, mysterious, dramatic lighting, highly detailed, 16:9"


class MediaAgent(BaseAgent):
    concurrency = 3

    async def execute(self, project_id: int, state: dict) -> dict:
        media_dir = self.hub.projects.folder(project_id, "assets", "media")
        # On a retry sent back by the media checker, keep the images that were fine.
        retry = bool(state.get("feedback", {}).get("SOURCING_MEDIA"))
        width, height = self.hub.settings.video_width, self.hub.settings.video_height
        sem = asyncio.Semaphore(self.concurrency)

        async def one(scene: dict) -> dict:
            path = media_dir / f"scene_{scene['index']}.jpg"
            if not (retry and is_valid_image(path)):
                async with sem:
                    await self.hub.images.generate(f"{scene['visual']}, {STYLE}", path, width, height)
            return {**scene, "image": str(path)}

        return {"scenes": list(await asyncio.gather(*(one(s) for s in state.get("scenes", []))))}

    async def verify(self, project_id: int, output: dict) -> bool:
        scenes = output.get("scenes", [])
        if scenes and all(s.get("image") for s in scenes):
            return True
        output["feedback"] = "no images were produced"
        return False
