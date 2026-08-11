from __future__ import annotations

from alteryx2fabric.plan import build_plan, classify_tool, format_plan


def test_classify_tool_support_levels():
    assert classify_tool("AlteryxBasePluginsGui.Formula.Formula")[0] == "native"
    assert classify_tool("AlteryxBasePluginsGui.Macro.Macro")[0] == "manual"
    assert classify_tool("Vendor.Custom.Widget")[0] == "unknown"


def test_build_plan_surfaces_risk_and_artifacts():
    ir = {
        "workflow": {"name": "sample.yxmd", "engine_version": "2024.1"},
        "tools": [
            {"id": "1", "plugin": "AlteryxBasePluginsGui.Formula.Formula", "annotation": ""},
            {"id": "2", "plugin": "Vendor.Custom.Widget", "annotation": "custom"},
        ],
        "connections": [],
        "inputs": [{"tool_id": "1", "file": "input.csv"}],
        "outputs": [{"tool_id": "2", "file": "output.csv"}],
        "parameters": [],
    }

    plan = build_plan(ir, "sample.yxmd")

    assert plan["summary"]["recommendation"] == "generate_and_review"
    assert plan["summary"]["support"] == {"native": 1, "unknown": 1}
    assert plan["artifacts"]["notebooks"][1].endswith("nb_silver.py")
    assert "Widget" in format_plan(plan)