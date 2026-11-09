from __future__ import annotations
import asyncio

from app.bot.telegram_bot import MAX_RESUMES, StudioBot
from tests.conftest import FakeLLM
from tests.test_bot import CHAT, OWNER, FakeBot, ctx, update, wait_jobs


def block_editing(hub) -> asyncio.Event:
    """Make the editor hang, like a long render when the process dies."""
    started = asyncio.Event()

    async def hang(project_id, state):
        started.set()
        await asyncio.Event().wait()

    hub.editor_agent.execute = hang
    return started


def research_calls(llm) -> int:
    return sum(p.startswith("Research detailed") for p in llm.prompts)


async def test_pipeline_resumes_from_checkpoint(make_hub):
    first = make_hub()
    started = block_editing(first)
    pid = first.projects.create("Temple")
    task = asyncio.create_task(first.orchestrator.run_pipeline(pid, "Temple"))
    await started.wait()
    task.cancel()  # process "dies" mid-render
    await asyncio.gather(task, return_exceptions=True)

    saved = first.projects.get_project(pid)
    assert saved["status"] == "running"
    assert saved["pipeline"]["stage"] == "EDITING"
    assert all(s.get("audio") and s.get("image") for s in saved["state"]["scenes"])

    second = make_hub()  # fresh process, same data dir
    result = await second.resume_video(pid)
    assert result["status"] == "success"
    assert research_calls(second.llm) == 0  # earlier stages were not redone
    assert second.images.calls == 1  # only the thumbnail; scene images were kept
    assert second.projects.get_project(pid)["status"] == "success"


async def test_resume_keeps_regression_counts(make_hub):
    first = make_hub(llm=FakeLLM({"accuracy": [False]}))
    pid = first.projects.create("Temple")
    first.projects.save_state(pid, {"topic": "Temple", "feedback": {}, "warnings": [], "report": "x" * 200},
                              {"stage": "VERIFYING_ACCURACY", "regressions": {"VERIFYING_ACCURACY": 2}})
    result = await first.resume_video(pid)
    assert result["status"] == "failed"  # no regressions left, so it fails instead of looping
    assert research_calls(first.llm) == 0


async def test_bot_resumes_interrupted_job_after_restart(make_hub):
    hub1, bot1 = make_hub(), FakeBot()
    started = block_editing(hub1)
    studio1 = StudioBot(hub1, [OWNER])
    job = await studio1.cmd_make(update(), ctx(bot1, "Temple")) or next(iter(studio1.jobs.values()))
    await started.wait()
    await studio1.shutdown()  # bot stops
    assert "cancelled" not in bot1.texts()
    project = hub1.projects.get_project(job.id)
    assert project["status"] == "running" and not project["meta"]["delivered"]

    hub2, bot2 = make_hub(), FakeBot()
    studio2 = StudioBot(hub2, [OWNER])
    resumed = await studio2.resume_unfinished(bot2)
    assert [j.id for j in resumed] == [job.id]
    assert f"Resuming job #{job.id} \"Temple\" at EDITING" in bot2.texts()
    await wait_jobs(studio2)
    assert bot2.videos == ["Mystery Temple Ka Sach"]
    assert research_calls(hub2.llm) == 0
    assert hub2.projects.get_project(job.id)["meta"]["delivered"] is True
    assert await StudioBot(make_hub(), [OWNER]).resume_unfinished(FakeBot()) == []  # nothing left


async def test_queued_jobs_resume_in_order(make_hub):
    hub1, bot1 = make_hub(), FakeBot()
    started = block_editing(hub1)
    studio1 = StudioBot(hub1, [OWNER], max_parallel=1)
    await studio1.cmd_make(update(), ctx(bot1, "First"))
    await studio1.cmd_make(update(), ctx(bot1, "Second"))
    await started.wait()
    await studio1.shutdown()
    statuses = [p["status"] for p in hub1.projects.list_projects()]
    assert statuses == ["running", "queued"]

    bot2 = FakeBot()
    studio2 = StudioBot(make_hub(), [OWNER], max_parallel=1)
    await studio2.resume_unfinished(bot2)
    assert "job #2 \"Second\" from the queue" in bot2.texts()
    await wait_jobs(studio2)
    assert len(bot2.videos) == 2


async def test_finished_but_undelivered_is_sent_without_rerunning(make_hub):
    hub = make_hub()
    pid = hub.projects.create("Temple", meta={"source": "telegram", "chat_id": CHAT, "user_id": OWNER,
                                              "delivered": False})
    hub.projects.update(pid, status="failed", pipeline={"stage": "EDITING"},
                        state={"error": "EDITING: ffmpeg exploded"})
    bot = FakeBot()
    studio = StudioBot(hub, [OWNER])
    await studio.resume_unfinished(bot)
    await wait_jobs(studio)
    assert "failed at EDITING:\nffmpeg exploded" in bot.texts()
    assert hub.llm.prompts == []


async def test_gives_up_after_repeated_crashes(make_hub):
    hub = make_hub()
    pid = hub.projects.create("Temple", meta={"source": "telegram", "chat_id": CHAT, "user_id": OWNER,
                                              "delivered": False, "resumes": MAX_RESUMES})
    hub.projects.set_status(pid, "running")
    bot = FakeBot()
    assert await StudioBot(hub, [OWNER]).resume_unfinished(bot) == []
    assert "giving up" in bot.texts()
    assert hub.projects.get_project(pid)["status"] == "failed"


async def test_skips_cancelled_disallowed_and_cli_projects(make_hub):
    hub = make_hub()
    tg = {"source": "telegram", "chat_id": CHAT, "delivered": False}
    cancelled = hub.projects.create("A", meta={**tg, "user_id": OWNER})
    hub.projects.set_status(cancelled, "cancelled")
    stranger = hub.projects.create("B", meta={**tg, "user_id": 999})
    hub.projects.create("C")  # made from the command line
    bot = FakeBot()
    assert await StudioBot(hub, [OWNER]).resume_unfinished(bot) == []
    assert bot.sent == []
    assert hub.projects.get_project(stranger)["status"] == "cancelled"


async def test_user_cancel_is_not_resumed(make_hub):
    hub, bot = make_hub(), FakeBot()
    started = block_editing(hub)
    studio = StudioBot(hub, [OWNER])
    await studio.cmd_make(update(), ctx(bot, "Temple"))
    await started.wait()
    await studio.cmd_cancel(update(), ctx(bot))
    await wait_jobs(studio)
    assert hub.projects.get_project(1)["status"] == "cancelled"
    assert await StudioBot(make_hub(), [OWNER]).resume_unfinished(FakeBot()) == []
