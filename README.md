# universal-video-productions

Multi-agent pipeline that turns a topic into a narrated Hinglish YouTube video:
research → fact-check → script → virality/brand review → voiceover (Edge TTS) →
images (Pollinations) → media check → render (moviepy) → video check → thumbnail → SEO.

## Setup

```bash
pip install -r requirements.txt        # needs ffmpeg on PATH (or FFMPEG_PATH)
```

Put at least one LLM key in `.env` (or `keys.txt`, one `provider: key` per line):

```
GEMINI_API_KEY=...        # or GROQ_API_KEY / OPEN_ROUTER_API_KEY / OPENAI_API_KEY
```

Keys are tried in order (`gemini, groq, openrouter, openai`); a failing key falls through to the next.

## Run the Telegram bot

1. Create a bot with @BotFather and add the token to `.env`: `BOT_TOKEN=123456:ABC...`
2. Start it: `python -m app.bot`
3. Message your bot. In setup mode (no users allowed yet) it replies with your user ID.
   Add `OWNER_ID=<that id>` to `.env` and restart. More users: `TELEGRAM_ALLOWED_USER_IDS=1,2,3`.

Commands: `/make <topic>`, `/status`, `/cancel [job]`, `/whoami`, `/help`. Plain messages
("Ek video banao Bermuda Triangle par") go through the Manager agent.

Each job shows one live progress message, then sends the video (if under Telegram's 50 MB bot
limit; otherwise the file path), the thumbnail, and the SEO title/description/tags. Videos run
one at a time by default (`[hub] max_heavy_workers` in config.toml); extra jobs queue.
Only people in the allowed list can use the bot, since every video spends your API quota.

**Restarts are safe.** The pipeline saves a checkpoint (state + next stage) to `project.json`
before every stage. When the bot starts it resumes every unfinished video from the stage that was
interrupted, keeping the stages already done (and, within the voiceover and image
stages, every scene that was already finished), and sends any finished result that was never
delivered. A video interrupted 3 times is given up. `/cancel`led videos are not resumed.
Job numbers are project IDs, so they stay the same across restarts.

## Run from the command line

```bash
python -m app "The mystery of the Kailasa temple"
python -m app --resume 7      # continue interrupted project 7
```

Output goes to `data/projects/<id>/`: `exports/final_video.mp4`, `exports/thumbnail.jpg`,
and `project.json` (the full pipeline state, saved after every stage).

From code: `async with Hub() as hub: await hub.make_video(topic, notify=send_progress)`.

## How the pipeline works

- All agents share one `state` dict (`topic`, `report`, `script`, `scenes`, `video_path`, ...);
  each returns updates that are merged in.
- When a check fails, its feedback goes back to the stage that made the input
  (e.g. fact-check errors go to research), at most 2 times per check. Then the run
  fails, except the subjective virality/quality reviews, which continue with a warning.
- The script must use `[Scene N]` / `Visual:` / `Narration:` blocks; only narration is spoken.

## Optional config (`config/config.toml`)

```toml
[render]
fps = 30
width = 1280
height = 720
voice = "hi-IN-MadhurNeural"

[llm]
order = ["groq", "gemini"]
[llm.models]
groq = "llama-3.3-70b-versatile"
```

## Tests

```bash
pip install -r requirements-dev.txt && pytest
```
