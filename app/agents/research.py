"""Agent 1: Research Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
import logging

log = logging.getLogger("app.agents.research")


class ResearchAgent(BaseAgent):
    async def execute(self, project_id: int, state: dict) -> dict:
        topic = state.get("topic") or "Unknown"
        prompt = (f"Research detailed, accurate facts for a YouTube video on: {topic}.\n"
                  "Give a structured report: key facts, dates, names, numbers and surprising details. "
                  "Only include claims you are confident are true.")
        fix = state.get("feedback", {}).get("RESEARCHING")
        if fix:
            prompt += f"\n\nA fact-checker rejected the previous report. Fix these problems:\n{fix}"
        report = await self.hub.llm.generate(prompt)
        return {"report": report, "source": "ai_research"}

    async def verify(self, project_id: int, output: dict) -> bool:
        if len(output.get("report", "")) > 100:
            return True
        output["feedback"] = "research report was empty or too short"
        return False
