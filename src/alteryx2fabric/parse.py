"""Parse Alteryx workflow (`.yxmd`) XML into a JSON Intermediate Representation (IR).

The IR is intentionally simple — it captures *what* the workflow does in a form
that humans and agents can read, without trying to fully execute the workflow.

IR shape:
    {
      "workflow": { "name": ..., "engine_version": ... },
      "tools": [
          {"id": "1", "plugin": "AlteryxBasePluginsGui.Input.Input",
           "annotation": "...", "config": {...raw...}},
          ...
      ],
      "connections": [
          {"from_tool": "1", "from_anchor": "Output",
           "to_tool": "2", "to_anchor": "Input"},
          ...
      ],
      "inputs": [{"tool_id": "1", "file": "..."}],
      "outputs": [{"tool_id": "99", "file": "..."}]
    }
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _xml_to_dict(elem: ET.Element) -> Any:
    """Convert an XML element into a nested dict/list/str structure."""
    children = list(elem)
    if not children and not elem.attrib:
        return (elem.text or "").strip()
    out: dict[str, Any] = {}
    if elem.attrib:
        out["@attrs"] = dict(elem.attrib)
    if elem.text and elem.text.strip():
        out["#text"] = elem.text.strip()
    for c in children:
        v = _xml_to_dict(c)
        if c.tag in out:
            existing = out[c.tag]
            if not isinstance(existing, list):
                out[c.tag] = [existing]
            out[c.tag].append(v)
        else:
            out[c.tag] = v
    return out


def parse_yxmd(path: str | Path) -> dict:
    """Parse a YXMD workflow file into the IR dict."""
    tree = ET.parse(path)
    root = tree.getroot()  # <AlteryxDocument>

    tools: list[dict] = []
    inputs: list[dict] = []
    outputs: list[dict] = []
    for node in root.findall("./Nodes/Node"):
        tool_id = node.attrib.get("ToolID", "")
        gui = node.find("./GuiSettings")
        plugin = gui.attrib.get("Plugin", "") if gui is not None else ""
        annotation_node = node.find("./Properties/Annotation/AnnotationText")
        annotation = (annotation_node.text or "").strip() if annotation_node is not None else ""
        config_node = node.find("./Properties/Configuration")
        config = _xml_to_dict(config_node) if config_node is not None else {}
        tools.append({
            "id": tool_id,
            "plugin": plugin,
            "annotation": annotation,
            "config": config,
        })
        # Common input/output plugins — surface them for quick orientation
        low = plugin.lower()
        if "input" in low:
            f = _find_file_in_config(config)
            if f:
                inputs.append({"tool_id": tool_id, "file": f})
        elif "output" in low or "render" in low:
            f = _find_file_in_config(config)
            if f:
                outputs.append({"tool_id": tool_id, "file": f})

    connections: list[dict] = []
    for c in root.findall("./Connections/Connection"):
        o = c.find("./Origin")
        d = c.find("./Destination")
        if o is None or d is None:
            continue
        connections.append({
            "from_tool": o.attrib.get("ToolID", ""),
            "from_anchor": o.attrib.get("Connection", "Output"),
            "to_tool": d.attrib.get("ToolID", ""),
            "to_anchor": d.attrib.get("Connection", "Input"),
        })

    return {
        "workflow": {
            "name": Path(path).name,
            "engine_version": root.attrib.get("yxmdVer", "unknown"),
        },
        "tools": tools,
        "connections": connections,
        "inputs": inputs,
        "outputs": outputs,
        "parameters": _params_for_ir(path),
    }


def _params_for_ir(path: str | Path) -> list[dict]:
    """Inline import to avoid a circular dependency with parameters.py."""
    from .parameters import detect_parameters
    from dataclasses import asdict
    try:
        return [asdict(p) for p in detect_parameters(path)]
    except Exception:
        return []


def _find_file_in_config(cfg: Any) -> str | None:
    """Best-effort scan for a `File` element anywhere in a tool config dict."""
    if isinstance(cfg, dict):
        if "File" in cfg:
            v = cfg["File"]
            if isinstance(v, str):
                return v
            if isinstance(v, dict):
                return v.get("#text") or (v.get("@attrs") or {}).get("FileName")
        for v in cfg.values():
            r = _find_file_in_config(v)
            if r:
                return r
    elif isinstance(cfg, list):
        for v in cfg:
            r = _find_file_in_config(v)
            if r:
                return r
    return None


def summarise(ir: dict) -> str:
    """One-page human summary of the IR — handy after parse."""
    lines = [
        f"Workflow: {ir['workflow']['name']} (engine {ir['workflow']['engine_version']})",
        f"Tools:        {len(ir['tools'])}",
        f"Connections:  {len(ir['connections'])}",
        f"Inputs:       {len(ir['inputs'])}",
        f"Outputs:      {len(ir['outputs'])}",
        "",
        "Tool plugins (count by plugin):",
    ]
    from collections import Counter
    by_plugin = Counter(t["plugin"].rsplit(".", 1)[-1] for t in ir["tools"])
    for p, n in by_plugin.most_common():
        lines.append(f"  {n:>3}  {p}")
    if ir["inputs"]:
        lines.append("\nDetected input files:")
        for i in ir["inputs"]:
            lines.append(f"  - tool {i['tool_id']}: {i['file']}")
    if ir["outputs"]:
        lines.append("\nDetected output files:")
        for o in ir["outputs"]:
            lines.append(f"  - tool {o['tool_id']}: {o['file']}")
    return "\n".join(lines)


def save_ir(ir: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(ir, indent=2), encoding="utf-8")
