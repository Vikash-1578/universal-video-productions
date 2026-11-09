"""Agent 0: Manager Agent."""
from __future__ import annotations
from app.core.agent import BaseAgent
from app.core.pipeline import AgentState
import logging
import json

log = logging.getLogger("app.agents.manager")

class ManagerAgent(BaseAgent):
    async def parse_intent(self, text: str) -> dict:
        prompt = (f"You are the Manager of 'Universal World' AI Studio. User said: '{text}'.\n"
                  f'Respond ONLY in JSON: {{ "intent": "make_video", "topic": "topic" }} OR '
                  f'{{ "intent": "status" }} OR {{ "intent": "chat", "response": "reply" }}')
        response = await self.hub.llm.generate(prompt)
        try:
            cleaned = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except: return {"intent": "chat", "response": "Ji, main samajh gaya. Kya banana hai?"}

    async def execute(self, project_id: int, input_data: dict) -> dict:
        try:
            result = await self.hub.orchestrator.run_pipeline(project_id, {"topic": input_data.get("topic", "")})
            return {"status": "completed", "result": result}
        except Exception as e: return {"status": "failed", "error": str(e)}

    async def verify(self, project_id: int, output_data: dict) -> bool:
        return output_data.get("status") == "completed"
