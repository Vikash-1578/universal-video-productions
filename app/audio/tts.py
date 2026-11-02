from __future__ import annotations
import logging
from pathlib import Path
import edge_tts

log = logging.getLogger('app.audio.tts')

class TTS:
    def __init__(self, default_voice: str = 'hi-IN-MadhurNeural'): self.default_voice = default_voice
    async def synthesize(self, text: str, output_path: Path, voice: str = None, rate: str = '+0%', pitch: str = '+0Hz') -> Path:
        voice = voice or self.default_voice
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return output_path
    async def list_voices(self):
        voices = await edge_tts.VoicesManager.create()
        return voices.voices
