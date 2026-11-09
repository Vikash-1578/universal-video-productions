"""Agent 5: Quality Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.scenes import extract_json
import logging

log = logging.getLogger("app.agents.quality")


class QualityAgent(BaseAgent):
    max_attempts = 1

    async def execute(self, project_id: int, state: dict) -> dict:
        prompt = ("Review this script for the Verinomia brand tone (Mysterious, Curious).\n"
                  'Reply ONLY with JSON: {"passed": true|false, "issues": ["..."]}\n\n' + state.get("script", ""))
        verdict = extract_json(await self.hub.llm.generate(prompt, temperature=0.2)) or {}
        issues = [str(i) for i in verdict.get("issues") or []]
        out = {"quality": {"passed": verdict.get("passed") is True, "issues": issues}}
        if not out["quality"]["passed"]:
            out["feedback"] = "; ".join(issues) if issues else "quality reviewer gave no valid verdict"
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return output["quality"]["passed"]
