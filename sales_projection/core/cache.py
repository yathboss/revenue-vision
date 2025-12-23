from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def make_cache_key(params: dict) -> str:
    """Stable cache key from request params."""
    items = sorted((str(k), str(v)) for k, v in params.items())
    raw = "|".join([f"{k}={v}" for k, v in items])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_get(cache_dir: Path, key: str) -> Any | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_set(cache_dir: Path, key: str, value: Any) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
