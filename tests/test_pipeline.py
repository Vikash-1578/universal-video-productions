from __future__ import annotations
from pathlib import Path

from app.core.scenes import extract_json, parse_scenes
from tests.conftest import FakeLLM, SCRIPT


def test_parse_scenes_format():
    scenes = parse_scenes(SCRIPT)
    assert len(scenes) == 4
    assert scenes[0] == {"index": 1, "visual": "A dark ancient temple, shot 1",
                         "narration": "Yeh scene number 1 ki kahani hai, dosto."}


def test_parse_scenes_strips_labels_and_markdown():
    script = "Here is your script:\n**[Scene 1: Hook]**\n**Visual:** A cave\n**Narration:** Socho zara...\nAur phir?"
    [scene] = parse_scenes(script)
    assert scene["visual"] == "A cave"
    assert scene["narration"] == "Socho zara... Aur phir?"


def test_parse_scenes_without_markers_uses_paragraphs():
    scenes = parse_scenes("Hook: Pehla paragraph.\n\nDoosra paragraph.")
    assert [s["narration"] for s in scenes] == ["Pehla paragraph.", "Doosra paragraph."]


def test_extract_json():
    assert extract_json('Sure! ```json\n{"a": {"b": "}"}}\n``` done') == {"a": {"b": "}"}}
    assert extract_json('verdict: {"verified": false} ok') == {"verified": False}
    assert extract_json("NOT VERIFIED") is None


async def test_full_pipeline_renders_real_video(make_hub):
    hub = make_hub(real_render=True)
    result = await hub.make_video("Mystery Temple")
    assert result["status"] == "success", result.get("error")
    state = result["state"]
    video = Path(state["video_path"])
    assert video.is_file() and video.stat().st_size > 1024
    assert state["video_check"]["duration"] > 4  # 4 scenes x (1s audio + tail)
    assert Path(state["thumbnail_path"]).is_file()
    assert state["seo"]["title"] == "Mystery Temple Ka Sach"
    # the topic survives to the late stages instead of falling back to "Unknown"
    assert any("Mystery Temple" in p for p in hub.llm.prompts if "title, description" in p)
    assert all(s["audio"] and s["image"] for s in state["scenes"])
    assert hub.projects.get_project(result["project_id"])["state"]["video_path"] == state["video_path"]


async def test_failed_check_regresses_with_feedback(make_hub):
    llm = FakeLLM({"accuracy": [False, True]})
    hub = make_hub(llm=llm)
    result = await hub.make_video("Temple")
    assert result["status"] == "success"
    research_prompts = [p for p in llm.prompts if p.startswith("Research detailed")]
    assert len(research_prompts) == 2
    assert "wrong date for the temple" in research_prompts[1]
    assert "RESEARCHING" not in result["state"]["feedback"]


async def test_hard_check_fails_after_max_regressions(make_hub):
    llm = FakeLLM({"accuracy": [False]})
    hub = make_hub(llm=llm)
    result = await hub.make_video("Temple")
    assert result["status"] == "failed"
    assert result["stage"] == "VERIFYING_ACCURACY"
    assert sum(p.startswith("Research detailed") for p in llm.prompts) == 3  # first run + 2 regressions


async def test_soft_check_continues_with_warning(make_hub):
    llm = FakeLLM({"quality": [False]})
    hub = make_hub(llm=llm)
    result = await hub.make_video("Temple")
    assert result["status"] == "success"
    assert any("QUALITY_CONTROL" in w for w in result["state"]["warnings"])
    rewrites = [p for p in llm.prompts if "Rewrite it to fix" in p]
    assert len(rewrites) == 2 and "too cheerful" in rewrites[0]


async def test_media_retry_keeps_good_images(make_hub):
    hub = make_hub()
    real_check = hub.media_checker_agent.execute
    calls = {"n": 0}

    async def flaky(project_id, state):
        calls["n"] += 1
        out = await real_check(project_id, state)
        if calls["n"] == 1:
            out = {"media_check": {"ok": False, "problems": ["scene 2"]}, "feedback": "scene 2: corrupt"}
        return out

    hub.media_checker_agent.execute = flaky
    result = await hub.make_video("Temple")
    assert result["status"] == "success"
    assert hub.images.calls == 4 + 1  # 4 scenes, no regeneration on retry, + thumbnail


async def test_notify_errors_do_not_break_pipeline(make_hub):
    async def broken(text):
        raise RuntimeError("telegram can't parse entities")

    result = await make_hub().make_video("Temple", notify=broken)
    assert result["status"] == "success"


async def test_manager_reports_failure(make_hub):
    hub = make_hub(llm=FakeLLM({"accuracy": [False]}))
    pid = hub.projects.create("Temple")
    out = await hub.manager_agent.execute(pid, {"topic": "Temple"})
    assert out["status"] == "failed"
    assert not await hub.manager_agent.verify(pid, out)


async def test_manager_parse_intent_rejects_garbage(make_hub):
    hub = make_hub()

    async def reply(prompt, **_):
        return '{"intent": "delete_everything"}'

    hub.llm.generate = reply
    assert (await hub.manager_agent.parse_intent("hi"))["intent"] == "chat"
