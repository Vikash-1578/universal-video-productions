"""Base class for all AI Agents."""
from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
import logging

log = logging.getLogger("app.core.agent")


class AgentCheckFailed(RuntimeError):
    """An agent ran but its output did not pass verification.

    ``feedback`` explains what was wrong; the orchestrator passes it back to
    the stage it regresses to, so the retry can actually fix the problem.
    """

    def __init__(self, agent: str, feedback: str):
        super().__init__(f"{agent}: {feedback}")
        self.agent = agent
        self.feedback = feedback


class BaseAgent(ABC):
    """An agent reads the shared pipeline ``state`` and returns updates to it.

    ``execute`` must not mutate ``state``; it returns a dict that the
    orchestrator merges into the state. An update may carry a ``feedback``
    string explaining why ``verify`` would fail; that key is never merged.
    """

    #: Attempts per run. Judges (pass/fail reviewers) use 1: asking the same
    #: question again is not a fix, so the orchestrator regresses instead.
    max_attempts = 3
    retry_delay = 2.0

    def __init__(self, hub):
        self.hub = hub

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def execute(self, project_id: int, state: dict) -> dict: ...

    @abstractmethod
    async def verify(self, project_id: int, output: dict) -> bool: ...

    async def run(self, project_id: int, state: dict) -> dict:
        last_problem = "no attempts made"
        for attempt in range(1, self.max_attempts + 1):
            try:
                output = await self.execute(project_id, state)
            except Exception as e:  # network errors, bad replies, ...
                log.warning("%s attempt %d/%d raised: %s", self.name, attempt, self.max_attempts, e)
                last_problem = f"error: {e}"
            else:
                if await self.verify(project_id, output):
                    output.pop("feedback", None)
                    return output
                last_problem = output.get("feedback") or "output failed verification"
                log.info("%s attempt %d/%d failed check: %s", self.name, attempt, self.max_attempts, last_problem)
            if attempt < self.max_attempts:
                await asyncio.sleep(self.retry_delay * attempt)
        raise AgentCheckFailed(self.name, last_problem)
