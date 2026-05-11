# Decoding YXMD — Alteryx tools → Python equivalents

The IR produced by `a2f parse` lists every tool as a record like:

```json
{ "id": "37", "plugin": "AlteryxBasePluginsGui.Formula.Formula",
  "annotation": "Compute Rollup ID", "config": { ... } }
```

The table below maps the common plugin types to a Python (pandas/PySpark)
pattern. Use it as a lookup when translating tools one by one.

| Alteryx Tool (Plugin)              | Python equivalent |
|---|---|
| `Input.Input`                      | `pd.read_excel` / `pd.read_csv` / `spark.read.format(...)` |
| `Output.Output`                    | `df.to_excel` / `df.to_csv` / `df.write.format("delta").saveAsTable` |
| `Filter.Filter`                    | `df[df[col] == val]` / `df.filter(...)` |
| `Select.Select`                    | `df = df[[cols]]` and rename / cast |
| `Formula.Formula`                  | column assignment(s) — see `formula-mapping.md` |
| `Join.Join`                        | `pd.merge(left, right, how="inner", indicator=True)` with `_merge` to recover "L only" / "R only" outputs |
| `JoinMultiple.JoinMultiple`        | chain of `pd.merge`s with the same `on=` keys |
| `Union.Union`                      | `pd.concat([...], ignore_index=True)` |
| `Append.AppendFields`              | cross join: `df1.merge(df2, how="cross")` |
| `Sort.Sort`                        | `df.sort_values(by=[...])` |
| `Unique.Unique`                    | `df.drop_duplicates(subset=[...], keep="first")` |
| `Sample.Sample`                    | `df.head(n)` / `df.tail(n)` / `df.sample` |
| `RecordID.RecordID`                | `df.insert(0, "RecordID", range(start, start+len(df)))` |
| `MultiRowFormula.MultiRowFormula`  | `df.sort_values(group+order).groupby(group).apply(<custom>)` or `shift()` |
| `MultiFieldFormula.MultiFieldFormula` | apply the same formula across many columns: `df[cols] = df[cols].apply(...)` |
| `TextToColumns.TextToColumns`      | `df[col].str.split(sep, expand=True)` |
| `FindReplace.FindReplace`          | `df[col].replace({...})` or `merge` + assign |
| `CrossTab.CrossTab`                | `pd.crosstab(...)` or `df.pivot_table(...)` |
| `Transpose.Transpose`              | `df.melt(...)` |
| `Summarize.Summarize`              | `df.groupby([...]).agg(...)` |
| `RunningTotal.RunningTotal`        | `df.groupby(g)[col].cumsum()` |
| `Cleanse` (macro)                  | Trim + collapse whitespace; **do not** uppercase unless verified. See gotcha. |
| `DateTime.DateTime`                | `pd.to_datetime(s, format=...)` — beware year-9999 sentinels |
| `BrowseV2.BrowseV2`                | inspection-only — skip |
| `ContainerTool.ContainerTool`      | grouping only — recurse into inner tools |
| `MacroOutput` / `MacroInput`       | inputs/outputs of a macro — inline the macro or expose as function |

## Working through a YXMD

1. Build a tool graph from the `connections` array in the IR (BFS / topological
   sort).
2. For each tool in execution order, generate the matching Python block.
3. Carry a Python variable through each step. Many Alteryx workflows are a
   linear or near-linear chain — a single `df` variable rebound at each step
   works fine.
4. Inline custom macros (Cleanse, Date Cleanse, etc.) rather than treating
   them as opaque tools — their internals are visible in the `.yxmc` file
   alongside the workflow.

## What to ask the user when blocked

- "What does macro `<name>` do?" — if the `.yxmc` isn't available.
- "Are these two columns equal as join keys?" — when whitespace / casing
  semantics aren't documented.
- "Should NULL be treated as 0 here?" — Alteryx behaviour varies by tool.
