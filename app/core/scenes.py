"""Parsing helpers shared by the agents: scene splitting and JSON extraction."""
from __future__ import annotations
import json
import re

SCENE_MARKER = re.compile(r"^\s*\**\s*\[\s*Scene\s*\d+[^\]]*\]\s*\**\s*$", re.IGNORECASE | re.MULTILINE)
LABEL = re.compile(r"^\s*\**\s*(Visual|Narration|Voiceover|VO)\s*\**\s*[:：]\s*\**\s*", re.IGNORECASE)
STAGE_LABEL = re.compile(r"^\s*\**\s*(Hook|Intro|Outro|Scene\s*\d+)\s*\**\s*[:：]\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    text = re.sub(r"[*_#`]+", "", text)
    return " ".join(text.split())


def parse_scenes(script: str) -> list[dict]:
    """Split a script into scenes of {"index", "visual", "narration"}.

    The expected format (requested by ScriptingAgent) is::

        [Scene 1]
        Visual: <English image description>
        Narration: <spoken Hinglish text>

    Scripts without "[Scene N]" markers fall back to one scene per paragraph.
    Only narration is ever spoken; visual descriptions and labels are not.
    """
    script = (script or "").strip()
    if not script:
        return []
    chunks = SCENE_MARKER.split(script)
    if len(chunks) > 1:
        chunks = chunks[1:]  # drop any preamble before the first marker
    else:
        chunks = [c for c in re.split(r"\n\s*\n", script)]

    scenes: list[dict] = []
    for chunk in chunks:
        visual: list[str] = []
        narration: list[str] = []
        current = narration
        for line in chunk.splitlines():
            m = LABEL.match(line)
            if m:
                current = visual if m.group(1).lower() == "visual" else narration
                line = line[m.end():]
            else:
                line = STAGE_LABEL.sub("", line)
            if line.strip():
                current.append(line)
        spoken = _clean(" ".join(narration))
        if not spoken:
            continue
        scenes.append({
            "index": len(scenes) + 1,
            "visual": _clean(" ".join(visual)) or " ".join(spoken.split()[:20]),
            "narration": spoken,
        })
    return scenes


def extract_json(text: str) -> dict | None:
    """Return the first JSON object found in an LLM reply, or None."""
    if not text:
        return None
    text = text.replace("```json", "```")
    fenced = re.findall(r"```(.*?)```", text, re.DOTALL)
    for candidate in fenced + [text]:
        start = candidate.find("{")
        while start != -1:
            depth = 0
            in_str = esc = False
            for i in range(start, len(candidate)):
                ch = candidate[i]
                if in_str:
                    if esc: esc = False
                    elif ch == "\\": esc = True
                    elif ch == '"': in_str = False
                elif ch == '"': in_str = True
                elif ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(candidate[start:i + 1])
                        except json.JSONDecodeError:
                            break
                        if isinstance(obj, dict):
                            return obj
                        break
            start = candidate.find("{", start + 1)
    return None
