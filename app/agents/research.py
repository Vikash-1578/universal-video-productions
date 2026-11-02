"""Agent 1: Research Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.research")

class ResearchAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        topic = input_data.get("topic", "Unknown")
        prompt = f"Research detailed facts for a YouTube video on: {topic}."
        report = await self.hub.llm.generate(prompt)
        return {"report": report, "source": "ai_research"}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return len(output_data.get("report", "")) > 100
