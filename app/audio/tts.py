from __future__ import annotations
import logging
from pathlib import Path
import edge_tts

from app.core.assets import part_path

log = logging.getLogger('app.audio.tts')


class TTS:
    def __init__(self, default_voice: str = 'hi-IN-MadhurNeural', rate: str = '+0%', pitch: str = '+0Hz'):
        self.default_voice, self.rate, self.pitch = default_voice, rate, pitch

    async def synthesize(self, text: str, output_path: Path, voice: str | None = None,
                         rate: str | None = None, pitch: str | None = None) -> Path:
        if not text.strip():
            raise ValueError('Cannot synthesize empty text')
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, voice or self.default_voice,
                                           rate=rate or self.rate, pitch=pitch or self.pitch)
        tmp = part_path(output_path)  # a crash mid-write must not leave a "finished" file
        try:
            await communicate.save(str(tmp))
            if not tmp.exists() or tmp.stat().st_size == 0:
                raise RuntimeError(f'TTS produced no audio for {output_path.name}')
            tmp.replace(output_path)
        finally:
            tmp.unlink(missing_ok=True)
        return output_path

    async def list_voices(self):
        voices = await edge_tts.VoicesManager.create()
        return voices.voices
