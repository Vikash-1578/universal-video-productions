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

    async def run_pipeline(self, project_id: int, topic: str, notify: Notify | None = None,
                           resume: bool = False) -> dict:
        """Run every stage for one project, sharing a single ``state`` dict.

        Each agent sees the whole state (topic, report, script, scenes, ...)
        and returns updates that are merged into it. When a check fails, its
        feedback is stored under ``state["feedback"][<target stage>]`` and the
        pipeline goes back to that stage, at most MAX_REGRESSIONS times per
        check.

        Before every stage the state and the stage about to run are saved to
        the project. With ``resume=True`` the run continues from that
        checkpoint, re-running the stage that was interrupted.
        """
        state: dict = {"topic": topic, "feedback": {}, "warnings": []}
        regressions: dict[AgentState, int] = {}
        current: AgentState | None = AGENT_SEQUENCE[0]

        if resume:
            project = self.hub.projects.get_project(project_id)
            if project.get("status") in ("success", "failed"):
                return self.result_from_project(project)
            saved = project.get("pipeline") or {}
            state = {**state, **(project.get("state") or {})}
            regressions = {AgentState[k]: v for k, v in (saved.get("regressions") or {}).items()
                           if k in AgentState.__members__}
            current = self._restore_stage(saved.get("stage"))
            where = current.name if current else "the end"
            await self._notify(notify, f"♻️ Resuming at {where}")

        self.hub.projects.set_status(project_id, "running")
        while current is not None:
            self._checkpoint(project_id, state, current, regressions)
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
                    current = target
                    continue
                if current in SOFT_CHECKS:
                    state["warnings"].append(f"{current.name}: {feedback}")
                    await self._notify(notify, f"⚠️ {current.name} still not satisfied, continuing anyway: {feedback}")
                    current = get_next_state(current)
                    continue
                state["error"] = f"{current.name}: {feedback}"
                self.hub.projects.update(project_id, status="failed", state=state,
                                         pipeline=self._pipeline(current, regressions))
                await self._notify(notify, f"❌ Critical Failure at {current.name}: {feedback}")
                return {"status": "failed", "project_id": project_id, "stage": current.name,
                        "error": feedback, "state": state}

            state.update(updates)
            state["feedback"].pop(current.name, None)  # this stage's fix request is handled
            current = get_next_state(current)

        self.hub.projects.update(project_id, status="success", state=state,
                                 pipeline={"stage": AgentState.COMPLETED.name,
                                           "regressions": {k.name: v for k, v in regressions.items()}})
        await self._notify(notify, "🎉 Mission Accomplished! Video is ready.")
        return {"status": "success", "project_id": project_id, "state": state}

    @staticmethod
    def _pipeline(stage: AgentState, regressions: dict[AgentState, int]) -> dict:
        return {"stage": stage.name, "regressions": {k.name: v for k, v in regressions.items()}}

    def _checkpoint(self, project_id: int, state: dict, stage: AgentState, regressions: dict) -> None:
        self.hub.projects.save_state(project_id, state, self._pipeline(stage, regressions))

    @staticmethod
    def _restore_stage(name: str | None) -> AgentState | None:
        """The stage to continue from; stages no longer in the sequence skip ahead."""
        if not name:
            return AGENT_SEQUENCE[0]
        stage = AgentState.__members__.get(name)
        if stage is None:
            return AGENT_SEQUENCE[0]
        if stage in AGENT_SEQUENCE:
            return stage
        if stage is AgentState.COMPLETED:
            return None
        later = [s for s in AGENT_SEQUENCE if s.value > stage.value]
        return later[0] if later else None

    @staticmethod
    def result_from_project(project: dict) -> dict:
        """Rebuild run_pipeline's return value for a project that already finished."""
        state = project.get("state") or {}
        result = {"status": project.get("status"), "project_id": project.get("id"), "state": state}
        if project.get("status") == "failed":
            stage = (project.get("pipeline") or {}).get("stage", "?")
            error = state.get("error", "unknown error")
            result.update(stage=stage, error=error.split(": ", 1)[-1] if error.startswith(stage) else error)
        return result
