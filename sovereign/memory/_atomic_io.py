"""Atomic JSON write helper — write to temp file then os.replace to avoid partial writes."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _save_json(
    path: Path,
    data: object,
    *,
    indent: int = 2,
    default: object = str,
    ensure_ascii: bool = True,
    **kwargs: object,
) -> None:
    """Atomically serialise *data* as JSON and write to *path*.

    Uses a sibling temp file + ``os.replace`` so concurrent readers never see
    a partial write.  Creates parent directories if they don't exist.
    """
    text = json.dumps(data, indent=indent, default=default, ensure_ascii=ensure_ascii, **kwargs)
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dir_), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
