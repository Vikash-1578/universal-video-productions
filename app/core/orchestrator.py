"""The Master Orchestrator with State Regression and Live Progress Reporting."""
from __future__ import annotations
from typing import Awaitable, Callable
import logging

from app.core.agent import AgentCheckFailed
from app.core.pipeline import AgentState, AGENT_SEQUENCE, get_next_state

log = logging.getLogger("app.core.orchestrator")

Notify = Callable[[str], Awaitable[None]]

#: When a checking stage fails, go back to the stage that produced its input.
REGRESSION_MAP = {
    AgentState.VERIFYING_ACCURACY: AgentState.RESEARCHING,
    AgentState.CHECKING_VIRALITY: AgentState.SCRIPTING,
    AgentState.QUALITY_CONTROL: AgentState.SCRIPTING,
    AgentState.CHECKING_MEDIA: AgentState.SOURCING_MEDIA,
    AgentState.VERIFYING_VIDEO: AgentState.EDITING,
}

#: Subjective reviews: once regressions run out, continue with a warning
#: instead of failing the whole video.
SOFT_CHECKS = {AgentState.CHECKING_VIRALITY, AgentState.QUALITY_CONTROL}

MAX_REGRESSIONS = 2

AGENT_DESCRIPTIONS = {
    AgentState.RESEARCHING: "🔍 Agent 1 (Research): Gathering deep facts...",
    AgentState.VERIFYING_ACCURACY: "🧪 Agent 2 (Accuracy): Cross-verifying claims...",
    AgentState.SCRIPTING: "✍️ Agent 3 (Scripting): Crafting the Hinglish story...",
    AgentState.CHECKING_VIRALITY: "📈 Agent 4 (Virality): Optimizing for retention...",
    AgentState.QUALITY_CONTROL: "🧐 Agent 5 (Quality): Checking brand tone...",
    AgentState.VOICEOVER: "🎙️ Agent 6 (Voice): Synthesizing human-like audio...",
    AgentState.SOURCING_MEDIA: "🖼️ Agent 7 (Media): Sourcing visuals...",
    AgentState.CHECKING_MEDIA: "👁️ Agent 8 (Media Checker): Verifying visuals...",
    AgentState.EDITING: "🎬 Agent 9 (Editor): Professional assembly...",
    AgentState.VERIFYING_VIDEO: "✅ Agent 10 (Video Checker): Final scan...",
    AgentState.THUMBNAIL_GEN: "🎨 Agent 11 (Thumbnail): Designing high-CTR art...",
    AgentState.SEO_OPTIMIZATION: "🚀 Agent 12 (SEO): Optimizing titles/tags...",
    AgentState.ANALYZING: "📊 Agent 13 (Analyser): Studying performance...",
    AgentState.CONFIGURING: "⚙️ Agent 14 (Config): Tuning system...",
}


class Orchestrator:
    def __init__(self, hub):
        self.hub = hub

    async def _notify(self, notify: Notify | None, text: str) -> None:
        log.info(text.replace("\n", " | "))
        if notify is None:
            return
        try:
            await notify(text)
        except Exception as e:  # a failed progress message must never kill the pipeline
            log.warning("Progress notification failed: %s", e)

    async def run_pipeline(self, project_id: int, topic: str, notify: Notify | None = None) -> dict:
        """Run every stage for one project, sharing a single ``state`` dict.

        Each agent sees the whole state (topic, report, script, scenes, ...)
        and returns updates that are merged into it. When a check fails, its
        feedback is stored under ``state["feedback"][<target stage>]`` and the
        pipeline goes back to that stage, at most MAX_REGRESSIONS times per
        check.
        """
        state: dict = {"topic": topic, "feedback": {}, "warnings": []}
        regressions: dict[AgentState, int] = {}
        current: AgentState | None = AGENT_SEQUENCE[0]

        while current is not None:
            await self._notify(notify, AGENT_DESCRIPTIONS.get(current, f"Processing {current.name}..."))
            agent = self.hub.agents.get(current)
            if agent is None:
                current = get_next_state(current)
                continue
            try:
                updates = await agent.run(project_id, state)
            except Exception as e:
                feedback = e.feedback if isinstance(e, AgentCheckFailed) else str(e)
                target = REGRESSION_MAP.get(current)
                used = regressions.get(current, 0)
                if target is not None and used < MAX_REGRESSIONS:
                    regressions[current] = used + 1
                    state["feedback"][target.name] = feedback
                    await self._notify(notify, f"⚠️ Quality Alert! Sending back to {target.name} "
                                               f"(retry {used + 1}/{MAX_REGRESSIONS}): {feedback}")
                    self.hub.projects.save_state(project_id, state)
                    current = target
                    continue
                if current in SOFT_CHECKS:
                    state["warnings"].append(f"{current.name}: {feedback}")
                    await self._notify(notify, f"⚠️ {current.name} still not satisfied, continuing anyway: {feedback}")
                    current = get_next_state(current)
                    continue
                state["error"] = f"{current.name}: {feedback}"
                self.hub.projects.save_state(project_id, state)
                await self._notify(notify, f"❌ Critical Failure at {current.name}: {feedback}")
                return {"status": "failed", "project_id": project_id, "stage": current.name,
                        "error": feedback, "state": state}

            state.update(updates)
            state["feedback"].pop(current.name, None)  # this stage's fix request is handled
            self.hub.projects.save_state(project_id, state)
            current = get_next_state(current)

        await self._notify(notify, "🎉 Mission Accomplished! Video is ready.")
        return {"status": "success", "project_id": project_id, "state": state}
