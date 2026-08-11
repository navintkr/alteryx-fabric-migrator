"""Persistent stage tracking for resumable migrations."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("parse", "plan", "generate", "preflight", "provision", "upload", "deploy", "run", "validate")


class MigrationManifest:
    def __init__(self, project_root: str | Path, source: str | Path):
        self.root = Path(project_root)
        self.path = self.root / ".a2f" / "migration.json"
        self.source = Path(source).resolve()
        fingerprint = hashlib.sha256(self.source.read_bytes()).hexdigest()
        existing = self._load()
        if existing.get("source_fingerprint") != fingerprint:
            existing = {"schema_version": 1, "stages": {}}
        self.data = existing
        self.data.update({
            "source": str(self.source),
            "source_fingerprint": fingerprint,
            "updated_at": self._now(),
        })
        self.save()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = self._now()
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def should_run(self, stage: str, restart: bool = False) -> bool:
        if stage not in STAGES:
            raise ValueError(f"Unknown migration stage: {stage}")
        return restart or self.data.get("stages", {}).get(stage, {}).get("status") != "completed"

    def mark(self, stage: str, status: str, message: str = "", details: dict | None = None) -> None:
        if stage not in STAGES:
            raise ValueError(f"Unknown migration stage: {stage}")
        self.data.setdefault("stages", {})[stage] = {
            "status": status,
            "timestamp": self._now(),
            "message": message,
            "details": details or {},
        }
        self.save()

    def completed(self, stage: str, message: str = "", details: dict | None = None) -> None:
        self.mark(stage, "completed", message, details)

    def failed(self, stage: str, error: Exception) -> None:
        self.mark(stage, "failed", str(error))

    def reset(self) -> None:
        self.data["stages"] = {}
        self.save()