"""Deterministic migration planning for parsed Alteryx workflows."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

NATIVE_TOOLS = {
    "DbFileInput", "DbFileOutput", "InputData", "OutputData", "Formula",
    "Filter", "Select", "Sort", "Sample", "Unique", "Join", "JoinMultiple",
    "Union", "Summarize", "CrossTab", "Transpose", "RecordID", "TextToColumns",
}
PARTIAL_TOOLS = {
    "MultiRowFormula", "MultiFieldFormula", "FuzzyMatch", "Download", "DynamicInput",
    "DynamicOutput", "Render", "Email", "RunCommand", "Python", "R",
}


def short_plugin(plugin: str) -> str:
    return plugin.rsplit(".", 1)[-1] if plugin else "Unknown"


def classify_tool(plugin: str) -> tuple[str, float, str]:
    """Return support level, confidence, and recommended handling."""
    name = short_plugin(plugin)
    low = name.lower()
    if "macro" in low:
        return "manual", 0.25, "Provide and inline the referenced macro before generation."
    if "spatial" in low or "predictive" in low:
        return "manual", 0.20, "Redesign with an equivalent Fabric or Python library."
    if name in NATIVE_TOOLS:
        return "native", 0.95, "Translate deterministically to pandas or PySpark."
    if name in PARTIAL_TOOLS:
        return "partial", 0.60, "Generate a candidate and require engineering review."
    return "unknown", 0.40, "Inspect configuration and approve a mapping before deployment."


def build_plan(ir: dict, source: str | None = None) -> dict:
    tools = []
    risks: list[dict] = []
    confidence_values: list[float] = []
    support_counts: Counter[str] = Counter()

    for tool in ir.get("tools", []):
        support, confidence, action = classify_tool(tool.get("plugin", ""))
        support_counts[support] += 1
        confidence_values.append(confidence)
        item = {
            "id": tool.get("id", ""),
            "name": short_plugin(tool.get("plugin", "")),
            "annotation": tool.get("annotation", ""),
            "support": support,
            "confidence": confidence,
            "action": action,
        }
        tools.append(item)
        if support != "native":
            risks.append({
                "severity": "high" if support == "manual" else "medium",
                "code": f"tool_{support}",
                "tool_id": item["id"],
                "message": f"{item['name']} requires {support} migration handling.",
            })

    if not ir.get("outputs"):
        risks.append({"severity": "high", "code": "no_outputs", "message": "No output artifact was detected."})
    if not ir.get("inputs"):
        risks.append({"severity": "medium", "code": "no_inputs", "message": "No file input was detected."})

    confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0
    if any(r["severity"] == "high" for r in risks):
        recommendation = "review_required"
    elif risks:
        recommendation = "generate_and_review"
    else:
        recommendation = "ready_to_generate"

    workflow = ir.get("workflow", {})
    return {
        "schema_version": 1,
        "workflow": {
            "name": workflow.get("name", Path(source).name if source else "unknown"),
            "source": source,
            "engine_version": workflow.get("engine_version", "unknown"),
        },
        "summary": {
            "tool_count": len(tools),
            "connection_count": len(ir.get("connections", [])),
            "input_count": len(ir.get("inputs", [])),
            "output_count": len(ir.get("outputs", [])),
            "parameter_count": len(ir.get("parameters", [])),
            "support": dict(sorted(support_counts.items())),
            "confidence": confidence,
            "recommendation": recommendation,
        },
        "tools": tools,
        "inputs": ir.get("inputs", []),
        "outputs": ir.get("outputs", []),
        "parameters": ir.get("parameters", []),
        "risks": risks,
        "artifacts": {
            "ir": "ir.json",
            "plan": ".a2f/migration-plan.json",
            "notebooks": [
                "notebooks/nb_bronze.py",
                "notebooks/nb_silver.py",
                "notebooks/nb_gold.py",
            ],
            "fabric_items": ["Lakehouse", "Bronze notebook", "Silver notebook", "Gold notebook", "Data Pipeline"],
        },
        "architecture": {
            "pattern": "medallion",
            "bronze": "Raw source files to bronze_* Delta tables",
            "silver": "Alteryx transformations to conformed silver_* Delta tables",
            "gold": "Final gold_* Delta tables and file-compatible outputs",
        },
    }


def format_plan(plan: dict) -> str:
    summary = plan["summary"]
    lines = [
        f"# Migration plan: {plan['workflow']['name']}",
        "",
        f"- Recommendation: **{summary['recommendation']}**",
        f"- Confidence: **{summary['confidence']:.0%}**",
        f"- Tools: {summary['tool_count']} ({', '.join(f'{k}: {v}' for k, v in summary['support'].items())})",
        f"- Inputs / outputs / parameters: {summary['input_count']} / {summary['output_count']} / {summary['parameter_count']}",
        "",
        "## Tool mappings",
        "",
        "| ID | Tool | Support | Confidence | Action |",
        "|---|---|---|---:|---|",
    ]
    for tool in plan["tools"]:
        lines.append(
            f"| {tool['id']} | {tool['name']} | {tool['support']} | "
            f"{tool['confidence']:.0%} | {tool['action']} |"
        )
    lines.extend(["", "## Risks", ""])
    if plan["risks"]:
        lines.extend(f"- **{risk['severity']}** `{risk['code']}`: {risk['message']}" for risk in plan["risks"])
    else:
        lines.append("- No deterministic migration blockers detected.")
    return "\n".join(lines) + "\n"


def save_plan(plan: dict, json_path: str | Path, markdown_path: str | Path | None = None) -> None:
    json_target = Path(json_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    if markdown_path:
        markdown_target = Path(markdown_path)
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        markdown_target.write_text(format_plan(plan), encoding="utf-8")