from __future__ import annotations
import asyncio
import logging
from pathlib import Path

from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips, vfx

log = logging.getLogger('app.rendering.engine')


class RenderEngine:
    """Turns scenes (image + narration audio) into one MP4 with moviepy 2.x."""

    def __init__(self, fps: int = 30, size: tuple[int, int] = (1280, 720), zoom: float = 0.08,
                 fade: float = 0.4, tail: float = 0.3, preset: str = 'veryfast', threads: int = 4):
        self.fps, self.size, self.zoom, self.fade, self.tail = fps, size, zoom, fade, tail
        self.preset, self.threads = preset, threads

    async def render(self, scenes: list[dict], output_path: Path) -> Path:
        """Render scenes that each have "image" and "audio" paths. Runs off the event loop."""
        missing = [s.get('index') for s in scenes if not s.get('image') or not s.get('audio')]
        if not scenes:
            raise ValueError('No scenes to render')
        if missing:
            raise ValueError(f'Scenes missing image or audio: {missing}')
        return await asyncio.to_thread(self._render_sync, scenes, Path(output_path))

    def _scene_clip(self, scene: dict, opened: list):
        width, height = self.size
        audio = AudioFileClip(str(scene['audio']))
        opened.append(audio)
        duration = audio.duration + self.tail
        image = ImageClip(str(scene['image'])).with_duration(duration)
        cover = max(width / image.w, height / image.h)  # fill the frame, crop the overflow
        zoom = self.zoom
        moving = image.resized(lambda t: cover * (1 + zoom * t / duration)).with_position('center')
        return (CompositeVideoClip([moving], size=self.size)
                .with_duration(duration)
                .with_audio(audio)
                .with_effects([vfx.FadeIn(self.fade), vfx.FadeOut(self.fade)]))

    def _render_sync(self, scenes: list[dict], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        opened: list = []
        try:
            clips = [self._scene_clip(s, opened) for s in scenes]
            opened.extend(clips)
            video = concatenate_videoclips(clips, method='chain')
            opened.append(video)
            tmp = output_path.with_name(output_path.stem + '.part.mp4')
            video.write_videofile(str(tmp), fps=self.fps, codec='libx264', audio_codec='aac',
                                  preset=self.preset, threads=self.threads, logger=None)
            tmp.replace(output_path)
            log.info('Rendered %s (%.1fs, %d scenes)', output_path, video.duration, len(scenes))
            return output_path
        finally:
            for clip in reversed(opened):
                try:
                    clip.close()
                except Exception:
                    pass
