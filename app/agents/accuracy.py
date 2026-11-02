"""Agent 2: Accuracy Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.accuracy")

class AccuracyAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        report = input_data.get("report", "")
        prompt = f"Verify this research report for accuracy. Reply 'VERIFIED' if correct, or list errors.\n\n{report}"
        verification = await self.hub.llm.generate(prompt)
        return {"report": report, "verified": "VERIFIED" in verification.upper()}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("verified", False)
