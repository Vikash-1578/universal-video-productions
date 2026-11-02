from __future__ import annotations
import logging
from pathlib import Path
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, ColorClip, TextClip
from moviepy.video.fx.all import resize

log = logging.getLogger('app.rendering.engine')

class RenderEngine:
    def __init__(self, base_dir: Path): self.base_dir = base_dir
    def _apply_zoom_effect(self, clip, duration): return clip.resize(lambda t: 1 + 0.1 * (t / duration))
    async def render_project(self, hub, project_id: int) -> Path:
        project = hub.projects.get_project(project_id)
        scenes = hub.storyboards.scenes(project_id)
        if not scenes: raise ValueError('Storyboard is empty')
        export_dir = hub.projects.folder(project_id, 'exports')
        export_dir.mkdir(parents=True, exist_ok=True)
        final_clips = []
        for idx, scene in enumerate(scenes):
            audio_path = export_dir / f'scene_{idx+1}.mp3'
            image_path = export_dir / f'scene_{idx+1}.jpg'
            if not audio_path.exists(): await hub.tts.synthesize(scene.get('description', ''), audio_path)
            if not image_path.exists(): await hub.free_gen.generate(scene.get('description', ''), image_path)
            audio_clip = AudioFileClip(str(audio_path))
            img_clip = ImageClip(str(image_path)).set_duration(audio_clip.duration)
            img_clip = self._apply_zoom_effect(img_clip, audio_clip.duration)
            img_clip = img_clip.set_audio(audio_clip).crossfadein(0.5).crossfadeout(0.5)
            final_clips.append(img_clip)
        video = concatenate_videoclips(final_clips, method='compose')
        output_file = export_dir / 'final_pro_video.mp4'
        video.write_videofile(str(output_file), fps=24, codec='libx264', audio_codec='aac', preset='ultrafast', threads=4)
        return output_file
