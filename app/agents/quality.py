"""Agent 5: Quality Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.quality")

class QualityAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        script = input_data.get("script", "")
        prompt = f"Review this script for Verinomia brand tone (Mysterious, Curious). Reply 'QUALITY_PASSED' if perfect.\n\n{script}"
        review = await self.hub.llm.generate(prompt)
        return {"script": script, "passed": "QUALITY_PASSED" in review.upper()}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("passed", False)
