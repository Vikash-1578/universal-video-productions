"""Agent 12: SEO Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.seo")

class SEOAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        topic = input_data.get("topic", "Unknown")
        prompt = f"Generate viral YouTube title, description and tags for: {topic}"
        seo = await self.hub.llm.generate(prompt)
        return {"seo": seo}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return len(output_data.get("seo", "")) > 50
