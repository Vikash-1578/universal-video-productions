"""Telegram front-end for the studio.

Commands: /start /help /make <topic> /status /cancel [job] /whoami
Any other text goes through the Manager agent (make a video, status, or chat).

Only user IDs in ``settings.allowed_user_ids`` may use it. With no IDs
configured the bot runs in setup mode and only tells people their user ID.
Jobs are Telegram projects (job number = project ID). Each project records
its chat, so when the bot starts it resumes every unfinished one from its
last checkpoint and delivers results that were never sent.

All messages are plain text (no Markdown) so user or error text can never
break message parsing.
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("app.bot")

TELEGRAM_LIMIT = 4000          # Telegram allows 4096 chars; keep a margin
BOT_UPLOAD_LIMIT = 50 * 1024**2  # Bot API upload limit for send_video
PROGRESS_LINES = 14
MAX_RESUMES = 3  # a project that keeps dying (e.g. out of memory) is given up after this
UPLOAD_TIMEOUT = 600

HELP = (
    "🎬 Universal World AI Studio\n\n"
    "/make <topic> — make a video, e.g. /make The mystery of Kailasa temple\n"
    "/status — show running and queued videos\n"
    "/cancel [job] — cancel your videos (or one job number)\n"
    "/whoami — show your Telegram user ID\n\n"
    "You can also just write what you want, e.g. \"Ek video banao Bermuda Triangle par\"."
)


def chunks(text: str, size: int = TELEGRAM_LIMIT) -> list[str]:
    """Split text into Telegram-sized pieces, preferring line breaks."""
    text = text or "(empty)"
    out = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        cut = cut if cut > size // 2 else size
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    out.append(text)
    return out


@dataclass
class Job:
    id: int  # the project ID
    chat_id: int
    user_id: int
    topic: str
    resume: bool = False
    cancel_requested: bool = False
    stage: str = "queued"
    created: float = field(default_factory=time.monotonic)
    started: float | None = None
    progress_message_id: int | None = None
    lines: list[str] = field(default_factory=list)
    task: asyncio.Task | None = None

    def describe(self) -> str:
        clock = time.monotonic() - (self.started or self.created)
        when = f"{int(clock // 60)}m{int(clock % 60):02d}s"
        state = f"running {when}" if self.started else f"queued {when}"
        return f"#{self.id} \"{self.topic}\": {self.stage} ({state})"


class StudioBot:
    def __init__(self, hub, allowed_user_ids: list[int] | set[int] | None = None, max_parallel: int | None = None):
        self.hub = hub
        ids = hub.settings.allowed_user_ids if allowed_user_ids is None else allowed_user_ids
        self.allowed = {int(i) for i in ids}
        self.jobs: dict[int, Job] = {}
        self._slots = asyncio.Semaphore(max_parallel or hub.settings.max_heavy_workers or 1)

    # ---------------------------------------------------------------- access
    @property
    def setup_mode(self) -> bool:
        return not self.allowed

    async def _guard(self, update, context) -> bool:
        """True if the sender may use the bot; otherwise tell them why not."""
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None:
            return False
        if user.id in self.allowed:
            return True
        if self.setup_mode:
            text = (f"🔧 Setup mode: no users are allowed yet.\nYour Telegram user ID is {user.id}.\n"
                    f"Add OWNER_ID={user.id} to .env (or TELEGRAM_ALLOWED_USER_IDS) and restart the bot.")
        else:
            text = f"⛔ Access denied. Your user ID is {user.id}."
        log.info("Rejected user %s (%s)", user.id, getattr(user, "username", ""))
        await self._send(context.bot, chat.id, text)
        return False

    # -------------------------------------------------------------- handlers
    async def cmd_start(self, update, context) -> None:
        if await self._guard(update, context):
            await self._send(context.bot, update.effective_chat.id, HELP)

    async def cmd_whoami(self, update, context) -> None:
        user = update.effective_user
        allowed = "allowed" if user.id in self.allowed else "not allowed"
        await self._send(context.bot, update.effective_chat.id, f"Your Telegram user ID is {user.id} ({allowed}).")

    async def cmd_make(self, update, context) -> None:
        if not await self._guard(update, context):
            return
        topic = " ".join(context.args or []).strip()
        if not topic:
            await self._send(context.bot, update.effective_chat.id, "Usage: /make <topic>")
            return
        await self.start_job(context.bot, update.effective_chat.id, update.effective_user.id, topic)

    async def cmd_status(self, update, context) -> None:
        if await self._guard(update, context):
            await self._send(context.bot, update.effective_chat.id, self.status_text())

    async def cmd_cancel(self, update, context) -> None:
        if not await self._guard(update, context):
            return
        chat_id = update.effective_chat.id
        arg = (context.args or [""])[0].lstrip("#")
        if arg and not arg.isdigit():
            await self._send(context.bot, chat_id, "Usage: /cancel [job number]")
            return
        targets = [j for j in self.jobs.values()
                   if j.chat_id == chat_id and (not arg or j.id == int(arg))]
        if not targets:
            await self._send(context.bot, chat_id, "Nothing to cancel.")
            return
        for job in targets:
            if job.task and not job.task.done():
                job.cancel_requested = True
                job.task.cancel()
        names = ", ".join(f"#{j.id}" for j in targets)
        await self._send(context.bot, chat_id, f"🛑 Cancelling {names}. "
                                               "A render already in progress finishes in the background but is not sent.")

    async def on_text(self, update, context) -> None:
        if not await self._guard(update, context):
            return
        chat_id = update.effective_chat.id
        text = (update.message.text or "").strip()
        if not text:
            return
        intent = await self.hub.manager_agent.parse_intent(text)
        kind = intent.get("intent")
        if kind == "make_video":
            await self.start_job(context.bot, chat_id, update.effective_user.id, str(intent["topic"]).strip())
        elif kind == "status":
            await self._send(context.bot, chat_id, self.status_text())
        else:
            await self._send(context.bot, chat_id, str(intent.get("response") or "🙂"))

    async def on_error(self, update, context) -> None:
        log.error("Telegram handler error", exc_info=context.error)
        chat = getattr(update, "effective_chat", None)
        if chat is not None:
            await self._send(context.bot, chat.id, f"⚠️ Something went wrong: {context.error}")

    # ------------------------------------------------------------------ jobs
    def status_text(self) -> str:
        active = [j for j in self.jobs.values() if j.task and not j.task.done()]
        if not active:
            return "😴 No videos in progress. Send /make <topic> to start one."
        return "📋 In progress:\n" + "\n".join(j.describe() for j in sorted(active, key=lambda j: j.id))

    def _busy(self) -> bool:
        return self._slots.locked() or any(j.started and j.task and not j.task.done() for j in self.jobs.values())

    async def start_job(self, bot, chat_id: int, user_id: int, topic: str) -> Job:
        topic = topic[:300]
        queued = " (queued, another video is rendering)" if self._busy() else ""
        pid = self.hub.projects.create(topic, meta={"source": "telegram", "chat_id": chat_id,
                                                    "user_id": user_id, "delivered": False})
        job = Job(id=pid, chat_id=chat_id, user_id=user_id, topic=topic)
        msg = await self._send(bot, chat_id, f"🎬 Job #{job.id}: \"{job.topic}\"{queued}\nUse /status to check progress.")
        job.progress_message_id = getattr(msg, "message_id", None)
        self._launch(bot, job)
        return job

    def _launch(self, bot, job: Job) -> None:
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._run_job(bot, job), name=f"job-{job.id}")

    async def resume_unfinished(self, bot) -> list[Job]:
        """Restart every Telegram project that was queued, running, or finished but never delivered."""
        resumed = []
        for project in self.hub.projects.list_projects():
            meta = project.get("meta") or {}
            status = project.get("status")
            if meta.get("source") != "telegram" or meta.get("delivered") or project["id"] in self.jobs:
                continue
            if status not in ("queued", "running", "success", "failed"):
                continue
            pid, chat_id, user_id = project["id"], meta.get("chat_id"), meta.get("user_id")
            if chat_id is None or user_id not in self.allowed:
                self.hub.projects.update(pid, status="cancelled" if status in ("queued", "running") else status,
                                         meta={"delivered": True, "skipped": "user no longer allowed"})
                continue
            attempts = int(meta.get("resumes", 0)) + 1
            if status in ("queued", "running") and attempts > MAX_RESUMES:
                self.hub.projects.update(pid, status="failed", meta={"delivered": True})
                await self._send(bot, chat_id, f"❌ Job #{pid} \"{project['topic']}\" was interrupted "
                                               f"{MAX_RESUMES} times, giving up. Use /make to try again.")
                continue
            self.hub.projects.update(pid, meta={"resumes": attempts})
            job = Job(id=pid, chat_id=chat_id, user_id=user_id, topic=project["topic"], resume=True)
            if status in ("queued", "running"):
                stage = (project.get("pipeline") or {}).get("stage") or "the start"
                where = "from the queue" if status == "queued" else f"at {stage}"
                msg = await self._send(bot, chat_id, f"♻️ Bot restarted. Resuming job #{pid} \"{job.topic}\" {where}.")
                job.progress_message_id = getattr(msg, "message_id", None)
            self._launch(bot, job)
            resumed.append(job)
        if resumed:
            log.info("Resumed %d unfinished job(s): %s", len(resumed), ", ".join(f"#{j.id}" for j in resumed))
        return resumed

    async def _run_job(self, bot, job: Job) -> None:
        notify = lambda text: self._progress(bot, job, text)  # noqa: E731
        try:
            async with self._slots:
                job.started = time.monotonic()
                job.stage = "starting"
                result = await self.hub.orchestrator.run_pipeline(job.id, job.topic, notify=notify,
                                                                  resume=job.resume)
            await self._deliver(bot, job, result)
            self.hub.projects.update(job.id, meta={"delivered": True})
        except asyncio.CancelledError:
            if job.cancel_requested:  # /cancel; otherwise the bot is shutting down and resumes later
                job.stage = "cancelled"
                self.hub.projects.update(job.id, status="cancelled", meta={"delivered": True})
                await self._send(bot, job.chat_id, f"🛑 Job #{job.id} \"{job.topic}\" cancelled.")
            raise
        except Exception as e:
            job.stage = "crashed"
            log.exception("Job %s crashed", job.id)
            self.hub.projects.update(job.id, status="failed", meta={"delivered": True})
            await self._send(bot, job.chat_id, f"❌ Job #{job.id} crashed: {e}")
        finally:
            self.jobs.pop(job.id, None)

    async def _progress(self, bot, job: Job, text: str) -> None:
        """Keep one live progress message per job instead of flooding the chat."""
        first_line = text.splitlines()[0] if text else ""
        job.stage = first_line[:80]
        job.lines.append(text)
        body = f"🎬 Job #{job.id}: \"{job.topic}\"\n\n" + "\n".join(job.lines[-PROGRESS_LINES:])
        body = body[-TELEGRAM_LIMIT:]
        if job.progress_message_id is not None:
            try:
                await bot.edit_message_text(body, chat_id=job.chat_id, message_id=job.progress_message_id)
                return
            except Exception as e:
                if "not modified" in str(e).lower():
                    return
                log.info("Could not edit progress message (%s); sending a new one", e)
        msg = await self._send(bot, job.chat_id, body)
        job.progress_message_id = getattr(msg, "message_id", None)

    async def _deliver(self, bot, job: Job, result: dict) -> None:
        state = result.get("state", {})
        if result.get("status") != "success":
            job.stage = "failed"
            await self._send(bot, job.chat_id, f"❌ Job #{job.id} failed at {result.get('stage', '?')}:\n"
                                               f"{result.get('error', 'unknown error')}")
            return
        job.stage = "delivering"
        seo = state.get("seo") or {}
        title = seo.get("title") or job.topic
        video = Path(state.get("video_path") or "")
        if video.is_file() and video.stat().st_size <= BOT_UPLOAD_LIMIT:
            try:
                with video.open("rb") as f:
                    await bot.send_video(job.chat_id, video=f, caption=title[:1000], supports_streaming=True,
                                         read_timeout=UPLOAD_TIMEOUT, write_timeout=UPLOAD_TIMEOUT)
            except Exception as e:
                log.warning("Video upload failed: %s", e)
                await self._send(bot, job.chat_id, f"⚠️ Upload failed ({e}). The video is saved at:\n{video}")
        else:
            size = f"{video.stat().st_size / 1024**2:.0f} MB" if video.is_file() else "missing"
            await self._send(bot, job.chat_id, f"📁 Video is too large for Telegram ({size}). Saved at:\n{video}")

        thumb = Path(state.get("thumbnail_path") or "")
        if thumb.is_file():
            try:
                with thumb.open("rb") as f:
                    await bot.send_photo(job.chat_id, photo=f, caption="🎨 Thumbnail")
            except Exception as e:
                log.warning("Thumbnail upload failed: %s", e)

        lines = [f"🚀 {title}"]
        if seo.get("description"):
            lines += ["", seo["description"]]
        if seo.get("tags"):
            lines += ["", "Tags: " + ", ".join(seo["tags"])]
        if state.get("warnings"):
            lines += ["", "⚠️ Warnings:"] + [f"- {w}" for w in state["warnings"]]
        lines += ["", f"📂 Project {job.id}: {self.hub.projects.folder(job.id)}"]
        await self._send(bot, job.chat_id, "\n".join(lines))

    # --------------------------------------------------------------- helpers
    async def _send(self, bot, chat_id: int, text: str):
        last = None
        for part in chunks(text):
            try:
                last = await bot.send_message(chat_id, part)
            except Exception as e:
                log.warning("send_message to %s failed: %s", chat_id, e)
        return last

    async def shutdown(self) -> None:
        tasks = [j.task for j in self.jobs.values() if j.task and not j.task.done()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------ telegram
    def build_application(self, token: str):
        from telegram.ext import Application, CommandHandler, MessageHandler, filters

        async def post_init(app) -> None:
            await self.resume_unfinished(app.bot)

        async def post_shutdown(app) -> None:
            await self.shutdown()
            await self.hub.aclose()

        app = (Application.builder().token(token)
               .concurrent_updates(True)
               .post_init(post_init)
               .post_shutdown(post_shutdown)
               .build())
        app.add_handler(CommandHandler(["start", "help"], self.cmd_start))
        app.add_handler(CommandHandler("whoami", self.cmd_whoami))
        app.add_handler(CommandHandler("make", self.cmd_make))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("cancel", self.cmd_cancel))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))
        app.add_error_handler(self.on_error)
        return app
