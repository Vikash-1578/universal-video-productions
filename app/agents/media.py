"""Agent 7: Media Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import httpx
import logging
from pathlib import Path
import re

log = logging.getLogger("app.agents.media")

class MediaAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        script = input_data.get("script", "")
        export_dir = self.hub.projects.folder(project_id, "assets", "media")
        export_dir.mkdir(parents=True, exist_ok=True)
        scenes = re.split(r"\[Scene \d+.*?\]", script)
        scenes = [s.strip() for s in scenes if s.strip()]
        media_map = {}
        async with httpx.AsyncClient() as client:
            for idx, text in enumerate(scenes):
                prompt = " ".join(text.split()[:5])
                url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
                resp = await client.get(url, follow_redirects=True)
                path = export_dir / f"scene_{idx+1}.jpg"
                path.write_bytes(resp.content)
                media_map[idx+1] = str(path)
        return {"media_map": media_map, "script": script}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return len(output_data.get("media_map", {})) > 0
