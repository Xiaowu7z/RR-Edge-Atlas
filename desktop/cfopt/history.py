from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "RR-CF-Optimizer"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "RR-CF-Optimizer"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "rr-cf-optimizer"


def history_path() -> Path:
    return data_dir() / "history.json"


def load_history(limit: int = 50) -> list[dict[str, Any]]:
    path = history_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][:limit]


def save_history(entry: dict[str, Any], limit: int = 50) -> None:
    rows = [entry, *load_history(limit)]
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(rows[:limit], ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)

