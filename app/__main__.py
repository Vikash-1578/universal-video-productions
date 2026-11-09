"""Command line entry point:  python -m app "topic of the video" """
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import sys

from app.core.config import load_settings
from app.hub import Hub


async def _print(text: str) -> None:
    print(text, flush=True)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="Make a video from a topic.")
    parser.add_argument("topic", nargs="?", help="what the video is about")
    parser.add_argument("--resume", type=int, metavar="PROJECT_ID", help="continue an interrupted project")
    args = parser.parse_args(argv)
    if bool(args.topic) == bool(args.resume):
        parser.error("give either a topic or --resume PROJECT_ID")

    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    async with Hub(settings) as hub:
        if args.resume:
            result = await hub.resume_video(args.resume, notify=_print)
        else:
            result = await hub.make_video(args.topic, notify=_print)

    state = result["state"]
    summary = {k: state.get(k) for k in ("video_path", "thumbnail_path", "seo", "warnings") if state.get(k)}
    print(json.dumps({"status": result["status"], "project_id": result["project_id"],
                      "error": result.get("error"), **summary}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
