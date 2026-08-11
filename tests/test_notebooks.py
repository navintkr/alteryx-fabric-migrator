from __future__ import annotations

import json
from pathlib import Path

from alteryx2fabric.notebooks import package_notebook, validate_notebook_body


def test_validate_notebook_body_detects_syntax_and_placeholders():
    assert validate_notebook_body("print('valid')") == []
    assert any("syntax error" in issue.lower() for issue in validate_notebook_body("if:"))
    assert any("placeholder" in issue.lower() for issue in validate_notebook_body("spark.table('silver_example')"))


def test_package_notebook_writes_complete_fabric_ipynb(tmp_path: Path):
    source = tmp_path / "body.py"
    source.write_text("print('ready')", encoding="utf-8")
    target = package_notebook(source, tmp_path / "body.ipynb", "Ready", "ws", "lh", "Lakehouse")

    notebook = json.loads(target.read_text(encoding="utf-8"))
    assert notebook["metadata"]["trident"]["lakehouse"]["default_lakehouse"] == "lh"
    assert len(notebook["cells"]) == 3
    assert "def write_delta" in "".join(notebook["cells"][1]["source"])