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

## Run

```bash
python -m app "The mystery of the Kailasa temple"
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
