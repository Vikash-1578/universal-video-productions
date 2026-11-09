"""The Hub: owns settings, services and agents, and runs the pipeline."""
from __future__ import annotations
import logging
import os

from app.core.config import Settings, load_settings
from app.core.orchestrator import Notify, Orchestrator
from app.core.pipeline import AgentState
from app.storage.projects import ProjectStore

from app.agents.research import ResearchAgent
from app.agents.accuracy import AccuracyAgent
from app.agents.scripting import ScriptingAgent
from app.agents.virality import ViralityAgent
from app.agents.quality import QualityAgent
from app.agents.voice import VoiceAgent
from app.agents.media import MediaAgent
from app.agents.media_checker import MediaCheckerAgent
from app.agents.editor import EditorAgent
from app.agents.video_checker import VideoCheckerAgent
from app.agents.thumbnail import ThumbnailAgent
from app.agents.seo import SEOAgent
from app.agents.analyser import AnalyserAgent
from app.agents.config import ConfigAgent
from app.agents.manager import ManagerAgent

log = logging.getLogger("app.hub")


class Hub:
    """Services (``llm``, ``tts``, ``images``, ``renderer``, ``projects``) can be
    passed in to replace the real ones, e.g. with fakes in tests."""

    def __init__(self, settings: Settings | None = None, *, llm=None, tts=None, images=None, renderer=None):
        self.settings = settings or load_settings()
        if self.settings.ffmpeg:
            os.environ.setdefault("IMAGEIO_FFMPEG_EXE", self.settings.ffmpeg)
        self.projects = ProjectStore(self.settings.path("projects"))

        if llm is None:
            from app.llm.client import LLMClient
            llm = LLMClient.from_settings(self.settings)
        if tts is None:
            from app.audio.tts import TTS
            tts = TTS(self.settings.voice)
        if images is None:
            from app.media.images import ImageGenerator
            images = ImageGenerator(self.settings.key("pollinations"))
        if renderer is None:
            from app.rendering.engine import RenderEngine
            renderer = RenderEngine(fps=self.settings.fps,
                                    size=(self.settings.video_width, self.settings.video_height))
        self.llm, self.tts, self.images, self.renderer = llm, tts, images, renderer

        self.research_agent = ResearchAgent(self)
        self.accuracy_agent = AccuracyAgent(self)
        self.scripting_agent = ScriptingAgent(self)
        self.virality_agent = ViralityAgent(self)
        self.quality_agent = QualityAgent(self)
        self.voice_agent = VoiceAgent(self)
        self.media_agent = MediaAgent(self)
        self.media_checker_agent = MediaCheckerAgent(self)
        self.editor_agent = EditorAgent(self)
        self.video_checker_agent = VideoCheckerAgent(self)
        self.thumbnail_agent = ThumbnailAgent(self)
        self.seo_agent = SEOAgent(self)
        self.analyser_agent = AnalyserAgent(self)
        self.config_agent = ConfigAgent(self)
        self.manager_agent = ManagerAgent(self)

        self.agents = {
            AgentState.RESEARCHING: self.research_agent,
            AgentState.VERIFYING_ACCURACY: self.accuracy_agent,
            AgentState.SCRIPTING: self.scripting_agent,
            AgentState.CHECKING_VIRALITY: self.virality_agent,
            AgentState.QUALITY_CONTROL: self.quality_agent,
            AgentState.VOICEOVER: self.voice_agent,
            AgentState.SOURCING_MEDIA: self.media_agent,
            AgentState.CHECKING_MEDIA: self.media_checker_agent,
            AgentState.EDITING: self.editor_agent,
            AgentState.VERIFYING_VIDEO: self.video_checker_agent,
            AgentState.THUMBNAIL_GEN: self.thumbnail_agent,
            AgentState.SEO_OPTIMIZATION: self.seo_agent,
            AgentState.ANALYZING: self.analyser_agent,
            AgentState.CONFIGURING: self.config_agent,
        }
        self.orchestrator = Orchestrator(self)

    async def make_video(self, topic: str, notify: Notify | None = None) -> dict:
        """Create a project for ``topic`` and run the full pipeline on it."""
        project_id = self.projects.create(topic)
        log.info("Project %d: %s", project_id, topic)
        return await self.orchestrator.run_pipeline(project_id, topic, notify)

    async def resume_video(self, project_id: int, notify: Notify | None = None) -> dict:
        """Continue an interrupted project from its last checkpoint."""
        topic = self.projects.get_project(project_id)["topic"]
        return await self.orchestrator.run_pipeline(project_id, topic, notify, resume=True)

    async def aclose(self) -> None:
        for service in (self.llm, self.images):
            close = getattr(service, "aclose", None)
            if close:
                await close()

    async def __aenter__(self) -> "Hub":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()
