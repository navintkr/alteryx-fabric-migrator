"""Smoke tests for alteryx2fabric.analyze."""
from __future__ import annotations

from pathlib import Path

from alteryx2fabric.analyze import (
    analyze_one,
    analyze_dir,
    detect_dependencies,
    detect_duplicates,
    _collect_irs,
)

# Two workflows. A writes shared.csv. B reads shared.csv. C is structurally
# identical to A (exact dup).
WF_A = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Nodes>
    <Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput"/>
      <Properties><Annotation/><Configuration><File>raw\\sales.csv</File></Configuration></Properties></Node>
    <Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"/>
      <Properties><Annotation/><Configuration><Fields><Field name="x" expression="1"/></Fields></Configuration></Properties></Node>
    <Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"/>
      <Properties><Annotation/><Configuration><File>out\\shared.csv</File></Configuration></Properties></Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
</AlteryxDocument>
"""

WF_B = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Nodes>
    <Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput"/>
      <Properties><Annotation/><Configuration><File>in\\shared.csv</File></Configuration></Properties></Node>
    <Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter"/>
      <Properties><Annotation/><Configuration/></Properties></Node>
    <Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"/>
      <Properties><Annotation/><Configuration><File>out\\final.csv</File></Configuration></Properties></Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
    <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
  </Connections>
</AlteryxDocument>
"""

# Same plugin multiset and edge anchors as A → exact dup
WF_C = WF_A


def _write(tmp: Path, name: str, body: str) -> Path:
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return p


def test_analyze_one_basic(tmp_path: Path):
    p = _write(tmp_path, "a.yxmd", WF_A)
    r = analyze_one(p)
    assert r.tool_count == 3
    assert r.connection_count == 2
    assert r.input_count == 1
    assert r.output_count == 1
    assert "Formula:1" in r.top_plugins
    assert r.effort in {"S", "M", "L", "XL"}
    assert r.structure_hash


def test_dependency_detection(tmp_path: Path):
    _write(tmp_path, "a.yxmd", WF_A)
    _write(tmp_path, "b.yxmd", WF_B)
    irs = _collect_irs(tmp_path)
    edges = detect_dependencies(irs)
    assert len(edges) == 1
    assert edges[0].shared_file == "shared.csv"
    assert edges[0].upstream.endswith("a.yxmd")
    assert edges[0].downstream.endswith("b.yxmd")


def test_duplicate_detection(tmp_path: Path):
    _write(tmp_path, "a.yxmd", WF_A)
    _write(tmp_path, "c.yxmd", WF_C)
    _write(tmp_path, "b.yxmd", WF_B)
    irs = _collect_irs(tmp_path)
    clusters = detect_duplicates(irs)
    exacts = [c for c in clusters if c.kind == "exact"]
    assert len(exacts) == 1
    assert len(exacts[0].members) == 2


def test_analyze_dir_writes_outputs(tmp_path: Path):
    _write(tmp_path, "a.yxmd", WF_A)
    _write(tmp_path, "b.yxmd", WF_B)
    out = tmp_path / "report"
    result = analyze_dir(tmp_path, out)
    assert result["file_count"] == 2
    assert (out / "workflow_report.csv").exists()
    assert (out / "workflow_dependencies.csv").exists()
    assert (out / "workflow_duplicates.csv").exists()
