"""Agent 12: SEO Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.scenes import extract_json
import logging

log = logging.getLogger("app.agents.seo")


class SEOAgent(BaseAgent):
    async def execute(self, project_id: int, state: dict) -> dict:
        topic = state.get("topic") or "Unknown"
        prompt = (f"Generate a viral YouTube title, description and tags for a Hinglish video on: {topic}\n"
                  'Reply ONLY with JSON: {"title": "...", "description": "...", "tags": ["..."]}\n\n'
                  f"Script excerpt:\n{state.get('script', '')[:3000]}")
        data = extract_json(await self.hub.llm.generate(prompt)) or {}
        seo = {"title": str(data.get("title") or "").strip(),
               "description": str(data.get("description") or "").strip(),
               "tags": [str(t) for t in data.get("tags") or []]}
        out = {"seo": seo}
        if not seo["title"]:
            out["feedback"] = "SEO reply had no title"
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return bool(output["seo"]["title"])
