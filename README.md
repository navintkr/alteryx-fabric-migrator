# alteryx2fabric

A toolkit for migrating Alteryx workflows (`.yxmd`) to Microsoft Fabric (Lakehouse + Notebooks + Data Pipelines), with a medallion (Bronze / Silver / Gold) architecture.

The toolkit has two complementary halves:

| Half | Purpose | Where it lives |
|---|---|---|
| **CLI (`a2f`)** | Deterministic operations: parse, provision, deploy, run, validate. Wraps Fabric REST API + OneLake DFS + `az` CLI. | `src/alteryx2fabric/` |
| **Skill** (agent pack) | Semantic knowledge: decoding YXMD tools, Alteryx → Python formula translation, architecture patterns, known gotchas. Designed for Copilot / coding agents. | `skill/` |

Use the CLI for everything that should be automated. Use the Skill (via a Copilot-aware editor) for the parts that need judgment — interpreting custom formulas, mapping macros, deciding when to use a Notebook vs. a Dataflow Gen2.

## Quick start

```powershell
# 1. Install (editable)
pipx install --editable .

# 2. Authenticate (Fabric uses Power BI auth resource)
az login --tenant <your-tenant-id>

# 3. Initialise a migration project
a2f init my-migration --workspace-id <fabric-ws-guid>
cd my-migration

# 4. Parse an Alteryx workflow into a JSON intermediate representation
a2f parse path/to/workflow.yxmd --out ir.json

# 5. Provision Fabric assets (Lakehouse + Files/Input/ folder)
a2f provision --lakehouse MyMigration_LH

# 6. Upload source files to OneLake
a2f upload ./inputs --to Input

# 7. Deploy generated Bronze/Silver/Gold notebooks + pipeline
a2f deploy

# 8. Run the pipeline end-to-end and validate against reference outputs
a2f run --pipeline PL_Migration_Run
a2f validate --ref ./reference_outputs --gen ./fabric_outputs
```

## What the toolkit does NOT do

- It does not **autonomously** translate every Alteryx formula. The semantic gap (Alteryx expression language, macros, spatial tools, R/Python tools) is what the **Skill** is for — point Copilot at your YXMD with this skill loaded.
- It does not provision capacities or workspaces. Use `az` / Fabric portal for those.
- It does not generate Dataflow Gen2 mashup PQ. Bronze ingestion currently uses notebooks; DFG2 emission is on the roadmap.

## Architecture

```
        ┌────────────┐    ┌──────────────────┐    ┌─────────────────┐
.yxmd → │ a2f parse  │ →  │  IR JSON         │ →  │ a2f deploy      │ → Fabric
        └────────────┘    │  (tools, formulas│    │ (Notebooks +     │
                          │   joins, schema) │    │  Data Pipeline)  │
                          └──────────────────┘    └─────────────────┘
                                   ↓
                          ┌──────────────────┐
                          │  Skill (agent)   │   ← Copilot reads IR + skill,
                          │   guides         │     writes notebook content
                          └──────────────────┘
```

## Known gotchas baked in

These come from real engagements and are encoded in both the CLI defaults and the skill instructions:

- **Delta column mapping** (`name` mode, reader v2 / writer v5) — required for Alteryx-style column names with spaces or special characters.
- **`timestampNtz` Delta feature** — avoid by serialising datetimes as strings before writing.
- **Year-9999 sentinel dates** — pandas `datetime64[ns]` overflows; use Python `datetime` objects or `datetime64[us]`.
- **NULL arithmetic** — Alteryx propagates NULLs through sums. Use `skipna=False` in pandas.
- **Join key normalisation** — Alteryx treats NaN / "" / "  " as equal in joins. Strip + fill before merging.

See [`skill/instructions/known-gotchas.md`](skill/instructions/known-gotchas.md) for the full catalogue.

## Repo layout

```
alteryx2fabric/
├── src/alteryx2fabric/        # CLI package
├── skill/                     # Agent skill (SKILL.md + instructions)
├── examples/sales-rollup-demo/ # Synthetic example workflow
├── docs/                      # Quickstart + architecture notes
├── tests/                     # Unit tests
└── pyproject.toml
```

## License

MIT. See [`LICENSE`](LICENSE).
