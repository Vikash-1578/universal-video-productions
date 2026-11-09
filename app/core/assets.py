"""Helpers for per-scene asset files that can be safely reused across runs."""
from __future__ import annotations
import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger("app.core.assets")


def fingerprint(*parts) -> str:
    """Short stable hash of everything that determines an asset's content."""
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def scene_asset(folder: Path, index: int, key: str, suffix: str) -> Path:
    """e.g. scene_3_1a2b3c4d5e6f.mp3: a changed narration/prompt gets a new name,
    so a file from an older script is never mistaken for the current one."""
    return Path(folder) / f"scene_{index}_{key}{suffix}"


def part_path(path: Path) -> Path:
    """Temporary name to write to before renaming into place."""
    path = Path(path)
    return path.with_name(path.stem + ".part" + path.suffix)


def remove_stale(folder: Path, keep: set[str], pattern: str) -> int:
    """Delete scene files in ``folder`` matching ``pattern`` that are not in ``keep``."""
    removed = 0
    for f in Path(folder).glob(pattern):
        if f.name not in keep:
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                log.warning("Could not remove stale asset %s: %s", f, e)
    return removed
