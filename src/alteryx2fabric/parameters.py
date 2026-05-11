"""Detect parameters in an Alteryx workflow.

Alteryx exposes parameters through several mechanisms; this module extracts
them so they can be surfaced in the analyze report and re-created as Fabric
pipeline parameters.

Sources we look for:
  1. User constants  — <Constants><Constant>...</Constant></Constants>
                       (defined under workflow Properties).
  2. Engine constants used in tool configs — %Engine.WorkflowDirectory%, etc.
  3. Question constants referenced in expressions — %Question.VarName%.
  4. Interface tools (analytic-app style) — TextBox, Date, DropDown,
     FileBrowse, NumericUpDown, ListBox, etc.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Tokens like %Question.StartDate% or %Engine.WorkflowDirectory%
_TOKEN_RE = re.compile(r"%(Question|Engine|User)\.([A-Za-z0-9_]+)%")

# Interface-tool plugin substrings (analytic-app inputs)
_INTERFACE_PLUGINS = (
    "interface.textbox",
    "interface.date",
    "interface.dropdown",
    "interface.filebrowse",
    "interface.folderbrowse",
    "interface.numericupdown",
    "interface.listbox",
    "interface.radiobutton",
    "interface.checkbox",
    "interface.action",
)

# Default-value mapping per interface plugin
_DEFAULT_TYPE = {
    "interface.textbox": "string",
    "interface.date": "string",      # ISO date string
    "interface.dropdown": "string",
    "interface.filebrowse": "string",
    "interface.folderbrowse": "string",
    "interface.numericupdown": "int",
    "interface.listbox": "array",
    "interface.radiobutton": "string",
    "interface.checkbox": "bool",
    "interface.action": "string",
}


@dataclass
class Parameter:
    name: str
    source: str           # "user_constant" | "question" | "engine" | "interface"
    type: str = "string"  # string | int | bool | array
    default: str = ""
    description: str = ""
    interface_plugin: str = ""

    def as_pipeline_param(self) -> dict:
        """Shape for a Fabric pipeline parameter definition."""
        pi_type = {"string": "string", "int": "int", "bool": "bool", "array": "array"}.get(self.type, "string")
        default: object = self.default
        if pi_type == "int":
            try: default = int(self.default) if self.default else 0
            except Exception: default = 0
        elif pi_type == "bool":
            default = str(self.default).strip().lower() in {"1", "true", "yes"}
        elif pi_type == "array":
            default = [s for s in (self.default or "").split(",") if s]
        return {"type": pi_type, "defaultValue": default}


def _walk_text(elem: ET.Element):
    """Yield every text/attribute string in an XML subtree."""
    for e in elem.iter():
        if e.text and e.text.strip():
            yield e.text
        for v in e.attrib.values():
            if isinstance(v, str) and v:
                yield v


def _extract_user_constants(root: ET.Element) -> list[Parameter]:
    out: list[Parameter] = []
    for c in root.findall(".//Properties/Constants/Constant"):
        name_el = c.find("./Name")
        if name_el is None:
            name_el = c.find("./Namespace")
        val_el = c.find("./Value")
        desc_el = c.find("./Description")
        if name_el is not None and (name_el.text or "").strip():
            out.append(Parameter(
                name=name_el.text.strip(),
                source="user_constant",
                default=(val_el.text or "").strip() if val_el is not None else "",
                description=(desc_el.text or "").strip() if desc_el is not None else "",
            ))
    return out


def _extract_token_refs(root: ET.Element) -> list[Parameter]:
    seen: dict[tuple[str, str], Parameter] = {}
    for s in _walk_text(root):
        for kind, name in _TOKEN_RE.findall(s):
            key = (kind, name)
            if key in seen:
                continue
            source = {"Question": "question", "Engine": "engine", "User": "user_constant"}[kind]
            seen[key] = Parameter(name=name, source=source)
    return list(seen.values())


def _interface_tool_param(node: ET.Element, plugin: str) -> Parameter | None:
    """Pull a single interface tool's parameter."""
    plugin_low = plugin.lower()
    short = next((s for s in _INTERFACE_PLUGINS if s in plugin_low), None)
    if not short:
        return None
    cfg = node.find("./Properties/Configuration")
    if cfg is None:
        return None

    def _first(*paths):
        for pth in paths:
            el = cfg.find(pth)
            if el is not None:
                return el
        return None

    # Common shapes: <Question><Name>...</Name></Question> or <Name>...</Name>
    name_el = _first("./Question/Name", "./Name", ".//Annotation/Name")
    desc_el = _first("./Question/Description", "./Description")
    default_el = _first("./Question/Default", "./Default", "./Value")
    if name_el is None or not (name_el.text or "").strip():
        # Fall back to the tool's annotation
        ann = node.find("./Properties/Annotation/AnnotationText")
        if ann is None or not (ann.text or "").strip():
            return None
        nm = ann.text.strip()
    else:
        nm = name_el.text.strip()
    return Parameter(
        name=nm,
        source="interface",
        type=_DEFAULT_TYPE.get(short, "string"),
        default=(default_el.text or "").strip() if default_el is not None and default_el.text else "",
        description=(desc_el.text or "").strip() if desc_el is not None and desc_el.text else "",
        interface_plugin=plugin,
    )


def _extract_interface_tools(root: ET.Element) -> list[Parameter]:
    out: list[Parameter] = []
    for node in root.findall("./Nodes/Node"):
        gui = node.find("./GuiSettings")
        if gui is None:
            continue
        plugin = gui.attrib.get("Plugin", "")
        p = _interface_tool_param(node, plugin)
        if p:
            out.append(p)
    return out


def _dedupe(params: list[Parameter]) -> list[Parameter]:
    """Merge duplicates by name, prefer the most informative source."""
    rank = {"interface": 4, "user_constant": 3, "question": 2, "engine": 1}
    by_name: dict[str, Parameter] = {}
    for p in params:
        existing = by_name.get(p.name)
        if not existing or rank.get(p.source, 0) > rank.get(existing.source, 0):
            by_name[p.name] = p
        elif not existing.default and p.default:
            existing.default = p.default
    return sorted(by_name.values(), key=lambda x: (x.source, x.name))


def detect_parameters(path: str | Path) -> list[Parameter]:
    """Parse `.yxmd` and return its parameter list (deduplicated)."""
    root = ET.parse(path).getroot()
    found: list[Parameter] = []
    found += _extract_user_constants(root)
    found += _extract_interface_tools(root)
    found += _extract_token_refs(root)
    # Drop pure engine constants we cannot map (they are runtime, not config)
    found = [p for p in found if not (p.source == "engine" and p.name in {"WorkflowDirectory", "WorkflowFileName", "WorkflowVersion"})]
    return _dedupe(found)


def params_to_pipeline_definition(params: list[Parameter]) -> dict:
    """Build the `parameters` block for a Fabric DataPipeline definition."""
    return {p.name: p.as_pipeline_param() for p in params}


def params_to_rows(params: list[Parameter], workflow: str) -> list[dict]:
    """Flatten for CSV/Excel reporting."""
    return [{"workflow": workflow, **asdict(p)} for p in params]
