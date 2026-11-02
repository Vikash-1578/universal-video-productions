"""Base class for all AI Agents."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import logging

log = logging.getLogger("app.core.agent")

class BaseAgent(ABC):
    def __init__(self, hub): self.hub = hub
    @abstractmethod
    async def execute(self, project_id: int, input_data: dict) -> dict: pass
    @abstractmethod
    async def verify(self, project_id: int, output_data: dict) -> bool: pass
    async def run(self, project_id: int, input_data: dict):
        attempts = 0
        while attempts < 3:
            attempts += 1
            output = await self.execute(project_id, input_data)
            if await self.verify(project_id, output): return output
        raise RuntimeError(f"Agent {self.__class__.__name__} failed after 3 attempts.")
