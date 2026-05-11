---
name: alteryx2fabric
description: |
  Use this skill when migrating an Alteryx workflow (`.yxmd`) to Microsoft
  Fabric. Triggers: "migrate alteryx", "alteryx to fabric", "convert yxmd",
  "rebuild alteryx workflow in fabric", "alteryx in lakehouse", "decode yxmd",
  "translate alteryx formula", any task that involves a `.yxmd` file or talks
  about moving an Alteryx workflow onto a Lakehouse / Notebook / Data Pipeline
  architecture.
applyTo: "**/*.yxmd"
---

# alteryx2fabric — Skill

This skill teaches a coding agent how to migrate an Alteryx workflow to
Microsoft Fabric using the [`alteryx2fabric`](../README.md) toolkit.

## When to use

Use this skill when the user wants to:
- Rebuild an Alteryx `.yxmd` workflow inside a Fabric workspace.
- Understand or translate Alteryx-specific logic (formulas, macros, Multi-Row,
  Crosstab, etc.) into PySpark/pandas.
- Validate that a Fabric implementation matches the Alteryx outputs.

## Default architecture

Always target a **medallion** layout in a single Lakehouse:

```
  Bronze (raw)  →  Silver (business logic)  →  Gold (final outputs)
```

Each layer is its own notebook; orchestration is a Fabric **Data Pipeline**
that chains them with `Succeeded` dependencies. The `a2f deploy` command
creates this structure automatically.

**Do not** put all logic into one notebook unless the user explicitly asks.

### Choosing notebook vs. Dataflow Gen2 for Bronze
- **Notebook** — when source files have irregular structure (Excel with offset
  header row, mixed sheets, multi-encoded CSVs).
- **Dataflow Gen2** — when sources are tabular and clean (single-header CSV,
  database table, parquet).

The toolkit currently generates Notebook-based Bronze. DFG2 emission is on the
roadmap.

## Workflow

1. **`a2f parse workflow.yxmd --out ir.json`** — generates a JSON IR. Read it
   to inventory the tools the workflow uses.
2. **Read** [`instructions/decoding-yxmd.md`](instructions/decoding-yxmd.md) to
   map Alteryx tool plugins to Python equivalents.
3. **Read** [`instructions/formula-mapping.md`](instructions/formula-mapping.md)
   for the Alteryx expression language → pandas/Python cheatsheet.
4. **Read** [`instructions/known-gotchas.md`](instructions/known-gotchas.md)
   before you write any Spark/Delta code. These bite every engagement.
5. **Generate** the three notebooks. Bronze can be templated from the IR;
   Silver/Gold need bespoke logic per workflow.
6. **`a2f deploy`** to push notebooks + pipeline.
7. **`a2f run`** to execute end-to-end.
8. **`a2f validate --ref reference_outputs --gen fabric_outputs`** — zero
   diff = success.

## Hard rules

- **Always use Delta column mapping mode `name`** with reader v2 / writer v5.
  Alteryx column names with spaces (`Plant Region`, `S4 PriceReasonCode`) will
  break Delta otherwise.
- **Never let pandas auto-cast dates to `datetime64[ns]`** when the data may
  contain year > 2262 sentinels (e.g. `31-Dec-9999`). Use Python `datetime`
  objects or `datetime64[us]`.
- **Always set `skipna=False`** when summing numeric columns that mirror
  Alteryx tools that don't have an explicit "ignore null" option. Alteryx
  propagates NULL through arithmetic.
- **Normalise join keys** before merging: `s.fillna("").str.strip()` —
  Alteryx treats NaN, empty string, and whitespace-only as equal.
- **Verify outputs by validation**, never by inspection of a few rows.

## Reference

- Toolkit CLI commands: see [`../README.md`](../README.md).
- Detailed gotchas:        [`instructions/known-gotchas.md`](instructions/known-gotchas.md)
- Tool → Python mapping:   [`instructions/decoding-yxmd.md`](instructions/decoding-yxmd.md)
- Expression mapping:      [`instructions/formula-mapping.md`](instructions/formula-mapping.md)
- Architecture patterns:   [`instructions/architecture-patterns.md`](instructions/architecture-patterns.md)
