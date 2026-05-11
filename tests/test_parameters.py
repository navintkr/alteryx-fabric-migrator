"""Smoke tests for alteryx2fabric.parameters."""
from __future__ import annotations

from pathlib import Path

from alteryx2fabric.parameters import detect_parameters, params_to_pipeline_definition
from alteryx2fabric.parse import parse_yxmd

YXMD_WITH_PARAMS = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxGuiToolkit.Interface.TextBox.TextBox" />
      <Properties>
        <Annotation><AnnotationText>RegionCode</AnnotationText></Annotation>
        <Configuration>
          <Question>
            <Name>RegionCode</Name>
            <Description>Region code filter</Description>
            <Default>US</Default>
          </Question>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxGuiToolkit.Interface.Date.Date" />
      <Properties>
        <Annotation><AnnotationText>AsOfDate</AnnotationText></Annotation>
        <Configuration>
          <Question>
            <Name>AsOfDate</Name>
            <Default>2024-01-01</Default>
          </Question>
        </Configuration>
      </Properties>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula" />
      <Properties>
        <Annotation/>
        <Configuration>
          <Fields>
            <Field name="Filtered" expression="[Region] = '%Question.RegionCode%'" />
          </Fields>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections/>
  <Properties>
    <Constants>
      <Constant>
        <Name>BatchSize</Name>
        <Value>500</Value>
        <Description>Bronze batch size</Description>
      </Constant>
    </Constants>
  </Properties>
</AlteryxDocument>
"""


def test_detect_parameters(tmp_path: Path):
    p = tmp_path / "params.yxmd"
    p.write_text(YXMD_WITH_PARAMS, encoding="utf-8")
    params = detect_parameters(p)
    names = {x.name for x in params}
    assert "RegionCode" in names
    assert "AsOfDate" in names
    assert "BatchSize" in names

    by_name = {x.name: x for x in params}
    assert by_name["RegionCode"].source == "interface"
    assert by_name["RegionCode"].default == "US"
    assert by_name["AsOfDate"].source == "interface"
    assert by_name["BatchSize"].source == "user_constant"
    assert by_name["BatchSize"].default == "500"


def test_parse_yxmd_includes_parameters(tmp_path: Path):
    p = tmp_path / "params.yxmd"
    p.write_text(YXMD_WITH_PARAMS, encoding="utf-8")
    ir = parse_yxmd(p)
    assert "parameters" in ir
    assert len(ir["parameters"]) >= 3


def test_pipeline_definition_shape(tmp_path: Path):
    p = tmp_path / "params.yxmd"
    p.write_text(YXMD_WITH_PARAMS, encoding="utf-8")
    params = detect_parameters(p)
    defn = params_to_pipeline_definition(params)
    assert "RegionCode" in defn
    assert defn["RegionCode"]["type"] == "string"
    assert defn["RegionCode"]["defaultValue"] == "US"
