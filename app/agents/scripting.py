"""Agent 3: Scripting Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.scenes import parse_scenes
import logging

log = logging.getLogger("app.agents.scripting")

MIN_SCENES = 3

FORMAT = """Write it as 6-12 scenes, using EXACTLY this format for every scene:

[Scene 1]
Visual: <one English sentence describing the image to show>
Narration: <the Hinglish words the narrator speaks>

Scene 1 is the Hook and the last scene is the Outro. Narration must contain only spoken words:
no stage directions, labels or emojis."""


class ScriptingAgent(BaseAgent):
    async def execute(self, project_id: int, state: dict) -> dict:
        prompt = (f"Convert this research into an engaging Hinglish YouTube script about "
                  f"'{state.get('topic', '')}'.\n{FORMAT}\n\nResearch:\n{state.get('report', '')}")
        fix = state.get("feedback", {}).get("SCRIPTING")
        if fix and state.get("script"):
            prompt += (f"\n\nA reviewer rejected the previous script:\n{state['script']}\n\n"
                       f"Rewrite it to fix these problems:\n{fix}")
        script = await self.hub.llm.generate(prompt)
        scenes = parse_scenes(script)
        out = {"script": script, "scenes": scenes}
        if len(scenes) < MIN_SCENES:
            out["feedback"] = f"script had {len(scenes)} scenes, need at least {MIN_SCENES} in the [Scene N] format"
        return out

    async def verify(self, project_id: int, output: dict) -> bool:
        return len(output.get("scenes", [])) >= MIN_SCENES
