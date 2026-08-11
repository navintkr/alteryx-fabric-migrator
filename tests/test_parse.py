"""Smoke test for alteryx2fabric.parse."""
from __future__ import annotations

from pathlib import Path

from alteryx2fabric.parse import parse_yxmd, summarise

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
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="Output" />
      <Destination ToolID="2" Connection="Input" />
    </Connection>
    <Connection>
      <Origin ToolID="2" Connection="Output" />
      <Destination ToolID="3" Connection="Input" />
    </Connection>
  </Connections>
  <Properties>
    <MetaInfo><Name>tiny</Name></MetaInfo>
  </Properties>
</AlteryxDocument>
"""


def test_parse_yxmd_basic(tmp_path: Path):
    p = tmp_path / "tiny.yxmd"
    p.write_text(TINY_YXMD, encoding="utf-8")

    ir = parse_yxmd(str(p))

    assert ir["workflow"]["name"] == "tiny.yxmd"
    tool_ids = {t["id"] for t in ir["tools"]}
    assert tool_ids == {"1", "2", "3"}
    assert len(ir["connections"]) == 2
    # 1 input tool, 1 output tool
    assert len(ir["inputs"]) >= 1
    assert len(ir["outputs"]) >= 1


def test_summarise_runs(tmp_path: Path):
    p = tmp_path / "tiny.yxmd"
    p.write_text(TINY_YXMD, encoding="utf-8")
    ir = parse_yxmd(str(p))
    txt = summarise(ir)
    assert "Formula" in txt or "tools" in txt.lower()
