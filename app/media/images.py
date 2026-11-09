"""Image generation via Pollinations (free, no key required)."""
from __future__ import annotations
import asyncio
import io
import logging
import random
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image

from app.core.assets import part_path

log = logging.getLogger("app.media.images")


class ImageError(RuntimeError):
    pass


def is_valid_image(path: str | Path) -> bool:
    """True if ``path`` is a complete, decodable image (catches truncated files too)."""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:  # verify() misses truncated data; decoding does not
            im.load()
        return True
    except Exception:
        return False


class ImageGenerator:
    BASE_URL = "https://image.pollinations.ai/prompt/"

    def __init__(self, api_key: str = "", timeout: float = 180.0, attempts: int = 3):
        self.attempts = attempts
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True)

    async def generate(self, prompt: str, output_path: Path, width: int = 1280, height: int = 720) -> Path:
        """Generate an image for ``prompt`` and save it as JPEG at ``output_path``."""
        url = self.BASE_URL + quote(" ".join(prompt.split())[:500], safe="")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        last = ""
        for attempt in range(1, self.attempts + 1):
            params = {"width": width, "height": height, "nologo": "true", "seed": random.randint(1, 10**9)}
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
                if not resp.headers.get("content-type", "").startswith("image/"):
                    raise ImageError(f"not an image ({resp.headers.get('content-type')})")
                tmp = part_path(output_path)  # never leave a half-written file under the final name
                with Image.open(io.BytesIO(resp.content)) as im:
                    im.convert("RGB").save(tmp, "JPEG", quality=92)
                tmp.replace(output_path)
                return output_path
            except (httpx.HTTPError, ImageError, OSError) as e:
                last = str(e) or type(e).__name__
                log.warning("Image attempt %d/%d failed: %s", attempt, self.attempts, last)
                if attempt < self.attempts:
                    await asyncio.sleep(3 * attempt)
        raise ImageError(f"Image generation failed for '{prompt[:60]}': {last}")

    async def aclose(self) -> None:
        await self._client.aclose()
