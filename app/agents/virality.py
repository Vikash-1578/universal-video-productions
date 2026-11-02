"""Agent 4: Virality Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.virality")

class ViralityAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        script = input_data.get("script", "")
        prompt = f"Analyze this script for virality. Reply 'VIRAL_OK' if it's high-retention, else suggest fixes.\n\n{script}"
        analysis = await self.hub.llm.generate(prompt)
        return {"script": script, "is_viral": "VIRAL_OK" in analysis.upper()}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("is_viral", False)
