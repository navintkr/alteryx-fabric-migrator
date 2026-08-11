from __future__ import annotations

import json
from pathlib import Path

from alteryx2fabric.migration import MigrationManifest


def test_manifest_resumes_completed_stage(tmp_path: Path):
    source = tmp_path / "workflow.yxmd"
    source.write_text("workflow-v1", encoding="utf-8")
    manifest = MigrationManifest(tmp_path, source)
    manifest.completed("parse", "done")

    resumed = MigrationManifest(tmp_path, source)

    assert not resumed.should_run("parse")
    assert resumed.should_run("plan")
    assert json.loads(resumed.path.read_text(encoding="utf-8"))["stages"]["parse"]["status"] == "completed"


def test_manifest_invalidates_stages_when_source_changes(tmp_path: Path):
    source = tmp_path / "workflow.yxmd"
    source.write_text("workflow-v1", encoding="utf-8")
    manifest = MigrationManifest(tmp_path, source)
    manifest.completed("parse")
    source.write_text("workflow-v2", encoding="utf-8")

    changed = MigrationManifest(tmp_path, source)

    assert changed.should_run("parse")