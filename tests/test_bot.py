from __future__ import annotations
import asyncio
from types import SimpleNamespace

import pytest

from app.bot.telegram_bot import StudioBot, chunks
from tests.conftest import FakeLLM

OWNER, CHAT, STRANGER = 111, 500, 999


class FakeBot:
    def __init__(self, fail_edits: bool = False):
        self.sent: list[tuple[int, str]] = []
        self.edits: list[str] = []
        self.videos: list[str] = []
        self.photos = 0
        self.fail_edits = fail_edits
        self._ids = iter(range(1, 10**6))

    async def send_message(self, chat_id, text, **_):
        assert len(text) <= 4096
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=next(self._ids))

    async def edit_message_text(self, text, chat_id=None, message_id=None, **_):
        if self.fail_edits:
            raise RuntimeError("Bad Request: message to edit not found")
        self.edits.append(text)

    async def send_video(self, chat_id, video, caption=None, **_):
        self.videos.append(caption)

    async def send_photo(self, chat_id, photo, caption=None, **_):
        self.photos += 1

    def texts(self) -> str:
        return "\n".join(t for _, t in self.sent)


def update(user=OWNER, text=""):
    return SimpleNamespace(effective_user=SimpleNamespace(id=user, username="u"),
                           effective_chat=SimpleNamespace(id=CHAT),
                           message=SimpleNamespace(text=text))


def ctx(bot, *args):
    return SimpleNamespace(bot=bot, args=list(args), error=None)


async def wait_jobs(studio: StudioBot):
    tasks = [j.task for j in list(studio.jobs.values()) if j.task]
    await asyncio.gather(*tasks, return_exceptions=True)


def test_chunks_split_on_lines():
    parts = chunks("\n".join(["x" * 100] * 100), size=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(parts).count("x") == 100 * 100


async def test_stranger_is_rejected(make_hub):
    bot, studio = FakeBot(), StudioBot(make_hub(), [OWNER])
    await studio.cmd_make(update(STRANGER), ctx(bot, "Temple"))
    assert "Access denied" in bot.texts() and str(STRANGER) in bot.texts()
    assert not studio.jobs


async def test_setup_mode_tells_user_their_id(make_hub):
    bot, studio = FakeBot(), StudioBot(make_hub(), [])
    await studio.on_text(update(STRANGER, "hello"), ctx(bot))
    assert "Setup mode" in bot.texts() and f"OWNER_ID={STRANGER}" in bot.texts()


async def test_make_without_topic_shows_usage(make_hub):
    bot, studio = FakeBot(), StudioBot(make_hub(), [OWNER])
    await studio.cmd_make(update(), ctx(bot))
    assert "Usage: /make" in bot.texts()


async def test_make_delivers_video_thumbnail_and_seo(make_hub):
    bot, studio = FakeBot(), StudioBot(make_hub(), [OWNER])
    await studio.cmd_make(update(), ctx(bot, "Mystery", "Temple"))
    await wait_jobs(studio)
    assert bot.videos == ["Mystery Temple Ka Sach"]
    assert bot.photos == 1
    assert "Tags: temple" in bot.texts()
    assert any("Agent 12 (SEO)" in e for e in bot.edits)  # progress went into one edited message
    assert len(bot.sent) == 2  # job-started message + SEO summary, not one per stage
    assert not studio.jobs


async def test_failed_pipeline_is_reported(make_hub):
    bot, studio = FakeBot(), StudioBot(make_hub(llm=FakeLLM({"accuracy": [False]})), [OWNER])
    await studio.cmd_make(update(), ctx(bot, "Temple"))
    await wait_jobs(studio)
    assert "failed at VERIFYING_ACCURACY" in bot.texts()
    assert not bot.videos


async def test_free_text_uses_manager_intent(make_hub):
    bot, hub = FakeBot(), make_hub()
    studio = StudioBot(hub, [OWNER])

    async def intent(text):
        return {"intent": "make_video", "topic": "Bermuda Triangle"}

    hub.manager_agent.parse_intent = intent
    await studio.on_text(update(text="Ek video banao Bermuda Triangle par"), ctx(bot))
    await wait_jobs(studio)
    assert "Bermuda Triangle" in bot.texts() and bot.videos


async def test_free_text_chat_reply(make_hub):
    bot, hub = FakeBot(), make_hub()

    async def intent(text):
        return {"intent": "chat", "response": "Namaste!"}

    hub.manager_agent.parse_intent = intent
    await StudioBot(hub, [OWNER]).on_text(update(text="hi"), ctx(bot))
    assert bot.sent[-1][1] == "Namaste!"


async def test_cancel_and_queue(make_hub):
    bot, hub = FakeBot(), make_hub()
    release = asyncio.Event()

    async def slow_pipeline(project_id, topic, notify=None, resume=False):
        await notify(f"working on {topic}")
        await release.wait()
        return {"status": "failed", "stage": "X", "error": "stopped", "state": {}}

    hub.orchestrator.run_pipeline = slow_pipeline
    studio = StudioBot(hub, [OWNER], max_parallel=1)
    await studio.cmd_make(update(), ctx(bot, "First"))
    await asyncio.sleep(0.05)
    await studio.cmd_make(update(), ctx(bot, "Second"))
    await asyncio.sleep(0.05)
    assert "queued" in bot.sent[-1][1]

    await studio.cmd_status(update(), ctx(bot))
    status = bot.sent[-1][1]
    assert "#1 \"First\"" in status and "running" in status
    assert "#2 \"Second\"" in status and "queued" in status

    await studio.cmd_cancel(update(), ctx(bot, "1"))
    await asyncio.sleep(0.05)
    assert "Job #1 \"First\" cancelled" in bot.texts()
    assert 2 in studio.jobs and studio.jobs[2].started  # second job got the slot
    release.set()
    await wait_jobs(studio)
    assert not studio.jobs


async def test_progress_falls_back_when_edit_fails(make_hub):
    bot, studio = FakeBot(fail_edits=True), StudioBot(make_hub(), [OWNER])
    await studio.cmd_make(update(), ctx(bot, "Temple"))
    await wait_jobs(studio)
    assert bot.videos  # pipeline still completed
    assert sum("Agent" in t for _, t in bot.sent) >= 1


async def test_cancel_rejects_bad_argument(make_hub):
    bot = FakeBot()
    await StudioBot(make_hub(), [OWNER]).cmd_cancel(update(), ctx(bot, "abc"))
    assert "Usage: /cancel" in bot.texts()
