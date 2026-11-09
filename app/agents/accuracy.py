"""Agent 2: Accuracy Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.scenes import extract_json
import logging

log = logging.getLogger("app.agents.accuracy")


class AccuracyAgent(BaseAgent):
    max_attempts = 1  # a rejected report goes back to research, not to the same judge

    async def execute(self, project_id: int, state: dict) -> dict:
        report = state.get("report", "")
        prompt = ("You are a strict fact-checker. Check this research report for factual errors.\n"
                  'Reply ONLY with JSON: {"verified": true|false, "errors": ["..."]}\n'
                  "Set verified to false only for real factual errors, not style.\n\n" + report)
        verdict = extract_json(await self.hub.llm.generate(prompt, temperature=0.1)) or {}
        errors = [str(e) for e in verdict.get("errors") or []]
        out = {"accuracy": {"verified": verdict.get("verified") is True, "errors": errors}}
        if not out["accuracy"]["verified"]:
            out["feedback"] = "; ".join(errors) if errors else "fact-checker gave no valid verdict"
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return output["accuracy"]["verified"]
