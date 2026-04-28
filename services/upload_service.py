"""Upload mínimo de vídeos para operação via UI (GAT-12 final)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Final

from fastapi import UploadFile

MEDIA_DIR: Final[Path] = Path("data/media")
MAX_UPLOAD_BYTES: Final[int] = 200 * 1024 * 1024
ALLOWED_EXTENSIONS: Final[set[str]] = {".mp4", ".avi", ".mkv"}


def _sanitize_filename(filename: str) -> tuple[str, str]:
    safe_name = Path(filename).name
    stem = Path(safe_name).stem
    ext = Path(safe_name).suffix.lower()

    stem_ascii = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem_ascii = stem_ascii.replace(" ", "_").lower()
    stem_ascii = re.sub(r"[^a-z0-9_-]", "", stem_ascii)
    if not stem_ascii:
        stem_ascii = "video"

    return stem_ascii, ext


async def save_video_upload(file: UploadFile) -> str:
    stem, ext = _sanitize_filename(file.filename or "video")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Extensão inválida. Permitidas: .mp4, .avi, .mkv")

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    target = MEDIA_DIR / f"{stem}_{timestamp}_{suffix}{ext}"

    total = 0
    try:
        with target.open("wb") as fp:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError("Arquivo excede limite de 200MB")
                fp.write(chunk)
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return str(target).replace("\\", "/")
