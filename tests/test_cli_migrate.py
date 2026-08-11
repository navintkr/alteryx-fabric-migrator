from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from alteryx2fabric import state as _state
from alteryx2fabric.cli import main

# DbFileInput -> Formula -> DbFileOutput: all natively supported, so the plan
# does not require manual review and the command reaches the generate stage.
TINY_YXMD = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput" />
      <Properties>
        <Annotation><AnnotationText>Read sales</AnnotationText></Annotation>
        <Configuration><File>inputs\\sales.csv</File></Configuration>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula" />
      <Properties>
        <Annotation><AnnotationText>Compute revenue</AnnotationText></Annotation>
        <Configuration><Fields><Field name="Revenue" expression="[Qty] * [Price]" /></Fields></Configuration>
      </Properties>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput" />
      <Properties>
        <Annotation><AnnotationText>Write</AnnotationText></Annotation>
        <Configuration><File>outputs\\rollup.csv</File></Configuration>
      </Properties>
    </Node>
  </Nodes>
</AlteryxDocument>
"""

VALID_BODY = "result = 1 + 1\n"


@pytest.fixture
def _no_network_generate(monkeypatch):
    monkeypatch.setattr("alteryx2fabric.generate.generate_bronze", lambda *a, **k: VALID_BODY)
    monkeypatch.setattr("alteryx2fabric.generate.generate_silver", lambda *a, **k: VALID_BODY)
    monkeypatch.setattr("alteryx2fabric.generate.generate_gold", lambda *a, **k: VALID_BODY)


def test_migrate_bootstraps_state_and_folders(_no_network_generate):
    runner = CliRunner()
    with runner.isolated_filesystem() as cwd:
        Path("workflow.yxmd").write_text(TINY_YXMD, encoding="utf-8")
        result = runner.invoke(
            main,
            ["migrate", "workflow.yxmd", "--workspace-id", "ws-guid-123", "--yes"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        st = _state.load(cwd)
        assert st["workspace_id"] == "ws-guid-123"
        assert st["project_name"] == "workflow"
        assert st["lakehouse_name"] == "workflow_LH"
        for sub in ("inputs", "reference_outputs", "fabric_outputs", "notebooks", ".a2f"):
            assert Path(cwd, sub).is_dir()
        assert Path(cwd, "ir.json").is_file()
        assert Path(cwd, ".a2f", "migration-plan.md").is_file()
        assert "Local migration artifacts are ready" in result.output


def test_migrate_ship_requires_workspace():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("workflow.yxmd").write_text(TINY_YXMD, encoding="utf-8")
        result = runner.invoke(main, ["migrate", "workflow.yxmd", "--ship"])
        assert result.exit_code != 0
        assert "requires a Fabric workspace" in result.output
