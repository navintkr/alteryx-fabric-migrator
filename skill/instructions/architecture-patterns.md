# Architecture patterns

## Medallion in a single Lakehouse

```
Lakehouse <project>
├── Files/
│   ├── Input/         ← user-uploaded raw files (xlsx, csv)
│   ├── Output/        ← Excel/CSV outputs the customer reads
│   └── stage/         ← parquet staging area
└── Tables/
    ├── bronze_*       ← raw, schema-on-write, 1:1 with input files
    ├── silver_*       ← cleansed, joined, business logic applied
    └── gold_*         ← final outputs (one per Alteryx Output tool)
```

Why a single Lakehouse instead of separate Bronze/Silver/Gold lakehouses?
- Cheaper governance (one item, one set of permissions).
- One `default_lakehouse` in every notebook means no cross-lakehouse path
  juggling.
- The medallion layering happens at the **table prefix** level, which is
  enough for most Alteryx workflows (≤ 100 tools, ≤ 20 inputs).

Use multiple Lakehouses only when:
- Bronze data must follow a different retention/RBAC policy than Gold.
- The workflow ingests > 1 TB of raw data per run.

## Parquet-stage write pattern

```python
def write_delta(pdf, table_name, stage_subdir):
    stage = f"Files/stage/{stage_subdir}/{table_name}"
    pdf.to_parquet(f"/lakehouse/default/{stage}", index=False)
    sdf = spark.read.parquet(f"Files/stage/{stage_subdir}/{table_name}")
    (sdf.write.mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.columnMapping.mode", "name")
        .option("delta.minReaderVersion", "2")
        .option("delta.minWriterVersion", "5")
        .format("delta").saveAsTable(table_name))
```

Why parquet stage?
- Avoids `spark.createDataFrame(pdf)` schema inference glitches on mixed-NULL
  columns.
- Keeps datetime serialisation under your control (write strings, parse later).
- Cleanly recovers `timestampNtz` Delta feature errors.

## Pipeline shape

A linear chain is the default:

```
NbBronze  →  NbSilver  →  NbGold
```

With dependency `Succeeded` on each link. Use `a2f deploy` to emit this
structure automatically.

Branch only when:
- Two independent Silver flows feed one Gold (use `dependsOn: [NbSilverA, NbSilverB]`).
- Bronze ingestion can run in parallel for very large inputs.

## Validation

The toolkit assumes you have **reference outputs** from running the Alteryx
workflow locally. `a2f validate` byte/value-diffs Excel/CSV/Parquet files
between `reference_outputs/` and `fabric_outputs/`.

- Use `--atol 1e-3` (default) for monetary columns.
- Tighten to `--atol 0` for ID/integer columns.
- Validation is **not optional**. Treat it as the migration's acceptance test.

## When *not* to use this toolkit

- Pure data-prep workflows that are mostly Excel-side gymnastics with no real
  joins/aggregations → Power Query / Dataflow Gen2 directly.
- Real-time streaming workflows → Fabric Eventstream + KQL.
- Workflows that depend heavily on Alteryx Macros that can't be reasonably
  rewritten in Python — recommend Alteryx Designer Cloud instead.
