from __future__ import annotations

import json
from pathlib import Path

from alteryx2fabric.preflight import exit_code, run_checks


def test_offline_checks_are_structured(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("alteryx2fabric.preflight.shutil.which", lambda command: "C:/az.cmd")
    (tmp_path / ".a2f").mkdir()
    (tmp_path / ".a2f" / "state.json").write_text(
        json.dumps({"workspace_id": "ws"}), encoding="utf-8"
    )
    (tmp_path / "ir.json").write_text(json.dumps({
        "workflow": {}, "tools": [], "connections": [], "inputs": [], "outputs": []
    }), encoding="utf-8")
    (tmp_path / "notebooks").mkdir()
    for layer in ("bronze", "silver", "gold"):
        (tmp_path / "notebooks" / f"nb_{layer}.py").write_text("print('ok')", encoding="utf-8")

    checks = run_checks(tmp_path, online=False)

    assert {check.status for check in checks} <= {"pass", "warn"}
    assert next(check for check in checks if check.name == "reference_outputs").status == "warn"
    assert exit_code(checks) == 0


def test_offline_checks_fail_for_missing_artifacts(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("alteryx2fabric.preflight.shutil.which", lambda command: None)

    checks = run_checks(tmp_path, online=False)

    assert exit_code(checks) == 2
    assert any(check.name == "notebook_silver" and check.status == "fail" for check in checks)