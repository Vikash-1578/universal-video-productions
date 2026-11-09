from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.core.agent import BaseAgent
from app.core.config import Settings
from app.hub import Hub

SCRIPT = "\n\n".join(
    f"[Scene {i}]\nVisual: A dark ancient temple, shot {i}\nNarration: Yeh scene number {i} ki kahani hai, dosto."
    for i in range(1, 5)
)


class FakeLLM:
    """Answers by prompt type. ``verdicts`` lets a test script judge replies."""

    def __init__(self, verdicts: dict[str, list[bool]] | None = None):
        self.verdicts = verdicts or {}
        self.prompts: list[str] = []

    def _verdict(self, kind: str) -> bool:
        queue = self.verdicts.get(kind)
        if not queue:
            return True
        return queue.pop(0) if len(queue) > 1 else queue[0]

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        self.prompts.append(prompt)
        if prompt.startswith("Research detailed"):
            return "Fact. " * 50
        if "fact-checker" in prompt:
            ok = self._verdict("accuracy")
            return json.dumps({"verified": ok, "errors": [] if ok else ["wrong date for the temple"]})
        if "for retention" in prompt:
            return json.dumps({"viral_ok": self._verdict("virality"), "fixes": ["stronger hook"]})
        if "brand tone" in prompt:
            ok = self._verdict("quality")
            return "```json\n" + json.dumps({"passed": ok, "issues": [] if ok else ["too cheerful"]}) + "\n```"
        if "Hinglish YouTube script" in prompt:
            return SCRIPT
        if "title, description and tags" in prompt:
            return json.dumps({"title": "Mystery Temple Ka Sach", "description": "d", "tags": ["temple"]})
        return "{}"


class FakeTTS:
    def __init__(self):
        self.calls: list[str] = []

    async def synthesize(self, text: str, output_path: Path, **_) -> Path:
        self.calls.append(text)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", str(output_path)], check=True)
        return output_path


class FakeImages:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str, output_path: Path, width: int = 1280, height: int = 720) -> Path:
        self.calls += 1
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width // 4, height // 4), (40, 20, 80)).save(output_path, "JPEG")
        return output_path


class FakeRenderer:
    def __init__(self):
        self.calls = 0

    async def render(self, scenes, output_path: Path) -> Path:
        self.calls += 1
        Path(output_path).write_bytes(b"\0" * 4096)
        return output_path


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(BaseAgent, "retry_delay", 0)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(base_dir=tmp_path, data_dir=tmp_path / "data", fps=10, video_width=320, video_height=180)


@pytest.fixture
def make_hub(settings, monkeypatch):
    """Hub with fake services. The video checker is stubbed unless real_render=True."""
    def factory(llm=None, real_render=False, **kw):
        if real_render:
            if not shutil.which("ffmpeg"):
                pytest.skip("ffmpeg not installed")
            from app.rendering.engine import RenderEngine
            renderer = RenderEngine(fps=settings.fps, size=(settings.video_width, settings.video_height))
        else:
            renderer = FakeRenderer()
            import app.agents.video_checker as vc
            monkeypatch.setattr(vc, "_duration", lambda path: 4.0)
        return Hub(settings, llm=llm or FakeLLM(), tts=FakeTTS(), images=FakeImages(), renderer=renderer, **kw)
    return factory
