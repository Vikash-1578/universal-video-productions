"""Agent 3: Scripting Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.scripting")

class ScriptingAgent(BaseAgent):
    async def execute(self, project_id: int, input_data: dict) -> dict:
        report = input_data.get("report", "")
        prompt = f"Convert this research into an engaging Hinglish YouTube script with Hook and Outro:\n\n{report}"
        script = await self.hub.llm.generate(prompt)
        return {"script": script, "report": report}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return len(output_data.get("script", "")) > 500
