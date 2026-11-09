"""Agent 4: Virality Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.scenes import extract_json
import logging

log = logging.getLogger("app.agents.virality")


class ViralityAgent(BaseAgent):
    max_attempts = 1

    async def execute(self, project_id: int, state: dict) -> dict:
        prompt = ("Analyze this YouTube script for retention: hook strength, pacing, curiosity gaps.\n"
                  'Reply ONLY with JSON: {"viral_ok": true|false, "fixes": ["..."]}\n\n' + state.get("script", ""))
        verdict = extract_json(await self.hub.llm.generate(prompt, temperature=0.2)) or {}
        fixes = [str(f) for f in verdict.get("fixes") or []]
        out = {"virality": {"viral_ok": verdict.get("viral_ok") is True, "fixes": fixes}}
        if not out["virality"]["viral_ok"]:
            out["feedback"] = "; ".join(fixes) if fixes else "virality reviewer gave no valid verdict"
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return output["virality"]["viral_ok"]
