from __future__ import annotations
import asyncio
from pathlib import Path

import pytest
from PIL import Image

from app.core.scenes import parse_scenes
from app.media.images import is_valid_image
from tests.conftest import SCRIPT


def scene_state():
    return {"topic": "Temple", "feedback": {}, "warnings": [], "script": SCRIPT, "scenes": parse_scenes(SCRIPT)}


async def interrupt_at_scene(agent_call, service, method: str, scene_no: int, state, hub):
    """Run a stage and kill it when it reaches ``scene_no``, like a crash mid-stage."""
    real = getattr(service, method)
    reached = asyncio.Event()

    async def hang_on_scene(text_or_prompt, path, *a, **kw):
        if f"number {scene_no} " in text_or_prompt or f"shot {scene_no}," in text_or_prompt:
            reached.set()
            await asyncio.Event().wait()
        return await real(text_or_prompt, path, *a, **kw)

    setattr(service, method, hang_on_scene)
    task = asyncio.create_task(agent_call(1, state))
    await reached.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    setattr(service, method, real)


async def test_voice_resume_skips_finished_scenes(make_hub):
    hub = make_hub()
    hub.projects.create("Temple")
    hub.voice_agent.concurrency = 1
    state = scene_state()
    await interrupt_at_scene(hub.voice_agent.execute, hub.tts, "synthesize", 3, state, hub)
    assert len(hub.tts.calls) == 2  # scenes 1 and 2 finished before the "crash"

    hub.tts.calls.clear()
    out = await hub.voice_agent.execute(1, state)
    assert [("number 3 " in c, "number 4 " in c) for c in hub.tts.calls] == [(True, False), (False, True)]
    assert all(Path(s["audio"]).is_file() for s in out["scenes"])


async def test_images_resume_skips_finished_scenes(make_hub):
    hub = make_hub()
    hub.projects.create("Temple")
    hub.media_agent.concurrency = 1
    state = scene_state()
    await interrupt_at_scene(hub.media_agent.execute, hub.images, "generate", 3, state, hub)
    assert hub.images.calls == 2

    out = await hub.media_agent.execute(1, state)
    assert hub.images.calls == 4  # only scenes 3 and 4 were generated on resume
    assert all(is_valid_image(s["image"]) for s in out["scenes"])


async def test_changed_narration_is_regenerated_and_stale_files_removed(make_hub):
    hub = make_hub()
    hub.projects.create("Temple")
    state = scene_state()
    first = await hub.voice_agent.execute(1, state)
    state["scenes"][1] = {**state["scenes"][1], "narration": "Bilkul naya scene."}
    hub.tts.calls.clear()
    second = await hub.voice_agent.execute(1, state)
    assert hub.tts.calls == ["Bilkul naya scene."]
    assert first["scenes"][1]["audio"] != second["scenes"][1]["audio"]
    assert not Path(first["scenes"][1]["audio"]).exists()
    files = sorted(p.name for p in Path(second["scenes"][0]["audio"]).parent.glob("scene_*.mp3"))
    assert files == sorted(Path(s["audio"]).name for s in second["scenes"])


async def test_corrupt_or_truncated_image_is_regenerated(make_hub):
    hub = make_hub()
    hub.projects.create("Temple")
    state = scene_state()
    first = await hub.media_agent.execute(1, state)
    broken = Path(first["scenes"][0]["image"])
    data = broken.read_bytes()
    broken.write_bytes(data[: len(data) // 2])  # half-written JPEG
    assert not is_valid_image(broken)
    await hub.media_agent.execute(1, state)
    assert hub.images.calls == 5
    assert is_valid_image(broken)


async def test_tts_never_leaves_partial_file(tmp_path, monkeypatch):
    import app.audio.tts as tts_mod

    class DyingCommunicate:
        def __init__(self, *a, **kw): pass

        async def save(self, path):
            Path(path).write_bytes(b"partial mp3")
            raise ConnectionError("connection reset")

    monkeypatch.setattr(tts_mod.edge_tts, "Communicate", DyingCommunicate)
    out = tmp_path / "scene_1_abc.mp3"
    with pytest.raises(ConnectionError):
        await tts_mod.TTS().synthesize("Namaste", out)
    assert list(tmp_path.iterdir()) == []


def test_valid_image_check(tmp_path):
    good = tmp_path / "a.jpg"
    Image.new("RGB", (64, 64), (1, 2, 3)).save(good)
    assert is_valid_image(good)
    assert not is_valid_image(tmp_path / "missing.jpg")
