# alteryx2fabric

[![Release](https://img.shields.io/github/v/release/navintkr/alteryx-fabric-migrator?display_name=tag&sort=semver)](https://github.com/navintkr/alteryx-fabric-migrator/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A toolkit for migrating Alteryx workflows (`.yxmd`) to Microsoft Fabric (Lakehouse + Notebooks + Data Pipelines), with a medallion (Bronze / Silver / Gold) architecture.

The toolkit has two complementary halves:

| Half | Purpose | Where it lives |
|---|---|---|
| **CLI (`a2f`)** | Deterministic operations: parse, provision, deploy, run, validate. Wraps Fabric REST API + OneLake DFS + `az` CLI. | `src/alteryx2fabric/` |
| **Skill** (agent pack) | Semantic knowledge: decoding YXMD tools, Alteryx → Python formula translation, architecture patterns, known gotchas. Designed for Copilot / coding agents. | `skill/` |

Use the CLI for everything that should be automated. Use the Skill (via a Copilot-aware editor) for the parts that need judgment — interpreting custom formulas, mapping macros, deciding when to use a Notebook vs. a Dataflow Gen2.

## Install

**From the latest GitHub Release (recommended):**

```powershell
pip install https://github.com/navintkr/alteryx-fabric-migrator/releases/download/v0.1.0/alteryx2fabric-0.1.0-py3-none-any.whl
```

**From source (editable, for development):**

```powershell
git clone https://github.com/navintkr/alteryx-fabric-migrator.git
cd alteryx-fabric-migrator
pipx install --editable .
```

Verify:

```powershell
a2f --help
```

## Quick start

```powershell
# 1. Install (see Install section above) and authenticate
az login --tenant <your-tenant-id>

# 2. Initialise a migration project
a2f init my-migration --workspace-id <fabric-ws-guid>
cd my-migration

# 3. Parse an Alteryx workflow into a JSON intermediate representation
a2f parse path/to/workflow.yxmd --out ir.json

# 4. Provision Fabric assets (Lakehouse + Files/Input/ folder)
a2f provision --lakehouse MyMigration_LH

# 5. Upload source files to OneLake
a2f upload ./inputs --to Input

# 6. Deploy generated Bronze/Silver/Gold notebooks + pipeline
a2f deploy

# 7. Run the pipeline end-to-end and validate against reference outputs
a2f run --pipeline PL_Migration_Run
a2f validate --ref ./reference_outputs --gen ./fabric_outputs
```

> **Tip:** Just want to scope a migration without any Azure setup? Skip straight to [Portfolio analysis](#portfolio-analysis-batch) — it runs entirely offline on a folder of `.yxmd` files.

## AI-assisted generation

The CLI can call a frontier model (Claude Opus 4-class or your choice) to draft notebook bodies from the parsed IR. Auth via GitHub Models (uses `GITHUB_TOKEN` or `gh auth token`) or Anthropic API directly (`ANTHROPIC_API_KEY`).

```powershell
# Generate Bronze / Silver / Gold notebook bodies from ir.json
a2f generate bronze --inputs ./inputs --out notebooks/nb_bronze.py
a2f generate silver --out notebooks/nb_silver.py
a2f generate gold   --out notebooks/nb_gold.py

# Override provider / model
a2f generate --provider anthropic --model claude-opus-4-20250514 silver

# Explain one Alteryx tool
a2f explain 37

# Patch a notebook from a validate diff report
a2f validate --ref ref --gen gen > diff.txt
a2f fix --notebook notebooks/nb_silver.py --diff diff.txt
```

The system prompt embeds the skill's hard rules (Delta column mapping, year-9999, NULL arithmetic, etc.) so generated code follows them by default.

## Portfolio analysis (batch)

Have a folder of dozens or hundreds of `.yxmd` files and need to scope the migration? Use `a2f analyze`:

```powershell
a2f analyze C:\path\to\workflows --out .\analysis
```

Outputs in `./analysis/`:

| File | Contents |
|---|---|
| `workflow_report.csv` | One row per workflow: tool count, plugin breakdown, inputs, outputs, complexity score, effort bucket (S/M/L/XL) |
| `workflow_dependencies.csv` | Edges `upstream → downstream` whenever an output file of one workflow is consumed as an input by another |
| `workflow_duplicates.csv` | Exact (identical structure hash) and near-duplicate (Jaccard ≥ threshold) clusters — candidates for consolidation |
| `workflow_analysis.xlsx` | All three sheets in one Excel workbook |
| `workflow_dependencies.mmd` | Mermaid diagram of the dependency graph |

Tune near-duplicate sensitivity with `--near-threshold 0.85` (default 0.9).

## Workflow parameterization

Alteryx workflows often expose runtime knobs through **user constants**, **question constants** (`%Question.X%`), or **interface tools** (TextBox, Date, DropDown, NumericUpDown, etc.). The toolkit detects these automatically and surfaces them in three places:

1. **`a2f parse`** — the IR (`ir.json`) now includes a `parameters` array.
2. **`a2f analyze`** — adds a `parameter_count` / `parameters` column to the workflow report and a dedicated `workflow_parameters.csv` (and Excel sheet) listing every parameter across the portfolio.
3. **`a2f deploy`** — automatically creates matching **Fabric Data Pipeline parameters** (with type and default) and wires each notebook activity to receive them via `@pipeline().parameters.<Name>`.

At run time, override any parameter with `--param`:

```powershell
a2f run --param RegionCode=EU --param AsOfDate=2024-12-31 --param BatchSize=1000
```

Skip parameterization for a workflow with `a2f deploy --no-parameters`.

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
