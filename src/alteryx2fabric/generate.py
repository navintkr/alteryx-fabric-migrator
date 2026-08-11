"""AI-assisted notebook generation, explanation, and patching."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .ai import LLMClient

# System prompt — embeds the skill's hard rules so the model behaves even when
# the skill folder isn't shipped alongside the CLI.
SYSTEM_PROMPT = """You are an expert Microsoft Fabric data engineer migrating an Alteryx workflow (.yxmd) to a Fabric Lakehouse using PySpark and pandas in a Synapse PySpark notebook.

Architecture: Bronze (raw -> Delta) -> Silver (business logic) -> Gold (final outputs). Single Lakehouse, table prefixes by layer.

Hard rules — every notebook MUST follow these:
1. Delta column mapping mode = "name", minReaderVersion = 2, minWriterVersion = 5 on every write. Alteryx column names contain spaces.
2. Avoid Spark TimestampNTZ feature: serialise datetime columns to ISO strings before passing pandas -> Spark.
3. Year-9999 sentinel dates (e.g. "31-Dec-9999") overflow datetime64[ns]. Use Python datetime (object dtype) or datetime64[us].
4. Alteryx sums propagate NULL: use s.sum(skipna=False) when emulating Summarize / running totals.
5. Normalise join keys before merge: s.astype("string").fillna("").str.strip(). Alteryx treats NaN/"" / whitespace as equal.
6. Cleanse macro: strip + collapse whitespace only. Do NOT uppercase unless config says so.
7. Crosstab values: replace spaces with underscores in pivot column names.
8. Use a parquet-stage write pattern: pandas -> /lakehouse/default/Files/stage/<layer>/<table>, then spark.read.parquet(...).write Delta saveAsTable.

Output format: respond with ONLY the Python code for the notebook body, no markdown fences, no commentary. The code will be inserted directly into a Fabric notebook cell.

Use these helpers (assume they are defined in an earlier cell):
- write_delta(pdf, table_name, stage_subdir): handles the parquet-stage Delta write with column mapping.
- _fmt_dt(v): formats a datetime/Timestamp to ISO string, handles year-9999 and NaT.

Available variables in scope: spark, notebookutils.
"""


def _read_file_headers(path: Path, max_rows: int = 5) -> list[str]:
    """Best-effort header sniff for csv/xlsx so the model knows column names."""
    suf = path.suffix.lower()
    try:
        if suf == ".csv":
            import pandas as pd
            return list(pd.read_csv(path, nrows=max_rows).columns)
        if suf in (".xlsx", ".xls"):
            import pandas as pd
            return list(pd.read_excel(path, nrows=max_rows).columns)
    except (ImportError, OSError, ValueError):
        return []
    return []


def _input_summary(inputs_dir: Path) -> str:
    if not inputs_dir.exists():
        return "(no inputs directory)"
    lines = []
    for p in sorted(inputs_dir.iterdir()):
        if p.is_dir() or p.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        cols = _read_file_headers(p)
        lines.append(f"- {p.name}  (columns: {cols})")
    return "\n".join(lines) or "(no usable input files)"


def _strip_code_fence(text: str) -> str:
    """If the model wrapped the answer in ```python ... ``` blocks, strip them."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)\n```", text, flags=re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def generate_bronze(ir: dict, inputs_dir: Path, llm: LLMClient) -> str:
    user = (
        "Generate the Bronze notebook body.\n\n"
        "Alteryx workflow IR (truncated):\n"
        f"{json.dumps({'inputs': ir.get('inputs', []), 'workflow': ir.get('workflow', {})}, indent=2)}\n\n"
        f"Input files in inputs/:\n{_input_summary(inputs_dir)}\n\n"
        "For each input file, read with pandas (read_csv or read_excel), then "
        "call write_delta(pdf, 'bronze_<short_name>', 'bronze'). Use snake_case "
        "for the table suffix."
    )
    return _strip_code_fence(llm.chat(SYSTEM_PROMPT, user))


def generate_silver(ir: dict, llm: LLMClient) -> str:
    # Trim oversize tool configs to keep token budget reasonable
    tools_lite = [
        {"id": t["id"], "plugin": t["plugin"].rsplit(".", 1)[-1],
         "annotation": t.get("annotation", ""),
         "config_keys": list(t.get("config", {}).keys()) if isinstance(t.get("config"), dict) else []}
        for t in ir.get("tools", [])
    ]
    user = (
        "Generate the Silver notebook body — translate the Alteryx workflow's "
        "business logic into pandas/PySpark.\n\n"
        "Read bronze tables with: pdf = spark.read.table('bronze_<name>').toPandas().\n"
        "Apply the same sequence of transformations as the Alteryx tools.\n"
        "Write each meaningful intermediate to silver_<name> via write_delta(pdf, name, 'silver').\n\n"
        "Tools (in workflow order):\n"
        f"{json.dumps(tools_lite, indent=2)}\n\n"
        "Connections:\n"
        f"{json.dumps(ir.get('connections', []), indent=2)}\n\n"
        "Full tool configs:\n"
        f"{json.dumps(ir.get('tools', []), indent=2)[:20000]}\n"
    )
    return _strip_code_fence(llm.chat(SYSTEM_PROMPT, user, max_tokens=8192))


def generate_gold(ir: dict, llm: LLMClient) -> str:
    user = (
        "Generate the Gold notebook body. Read the latest silver tables and "
        "produce the final outputs that the Alteryx workflow's Output tools "
        "produced.\n\n"
        "For each output:\n"
        "  1. Read silver via spark.read.table('silver_<name>').toPandas().\n"
        "  2. Apply any final shaping (column selection, ordering, renames).\n"
        "  3. Write the gold Delta via write_delta(pdf, 'gold_<name>', 'gold').\n"
        "  4. Also write the file form (xlsx or csv) under "
        "/lakehouse/default/Files/Output/<original_filename> using pandas.\n\n"
        "Alteryx output tools:\n"
        f"{json.dumps(ir.get('outputs', []), indent=2)}\n"
    )
    return _strip_code_fence(llm.chat(SYSTEM_PROMPT, user))


def explain_tool(ir: dict, tool_id: str, llm: LLMClient) -> str:
    tool = next((t for t in ir.get("tools", []) if t["id"] == tool_id), None)
    if not tool:
        return f"Tool {tool_id} not found in IR."
    sys = (
        "You explain Alteryx workflow tools to a data engineer who knows Python "
        "but not Alteryx. Be concise (<= 200 words). Cover: what the tool does, "
        "the key configuration values, and the equivalent pandas/PySpark idiom."
    )
    user = f"Explain this tool:\n\n{json.dumps(tool, indent=2)}"
    return llm.chat(sys, user, max_tokens=1024)


def fix_from_diff(notebook_path: Path, diff_report: str, llm: LLMClient) -> str:
    code = notebook_path.read_text(encoding="utf-8")
    sys = (
        SYSTEM_PROMPT
        + "\nYou are patching an existing notebook to fix a validation failure. "
        "Return the complete updated notebook body as plain Python — no markdown."
    )
    user = (
        "Current notebook body:\n\n"
        f"{code}\n\n"
        "Validation diff report (reference vs. generated):\n\n"
        f"{diff_report}\n\n"
        "Patch the notebook to make the validation diff zero. Keep the same "
        "structure; only change cells that are wrong."
    )
    return _strip_code_fence(llm.chat(sys, user, max_tokens=8192))
