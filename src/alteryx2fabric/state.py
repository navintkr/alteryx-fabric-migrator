"""Per-project state — persisted under `.a2f/state.json` inside the project directory.

Keeps track of Fabric IDs across CLI invocations so commands like `run` and
`validate` don't need every ID passed on every call.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_DIR = ".a2f"
STATE_FILE = "state.json"


def state_path(project_dir: str | Path = ".") -> Path:
    return Path(project_dir) / STATE_DIR / STATE_FILE


def load(project_dir: str | Path = ".") -> dict[str, Any]:
    p = state_path(project_dir)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(state: dict[str, Any], project_dir: str | Path = ".") -> None:
    p = state_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def update(updates: dict[str, Any], project_dir: str | Path = ".") -> dict[str, Any]:
    s = load(project_dir)
    s.update(updates)
    save(s, project_dir)
    return s
