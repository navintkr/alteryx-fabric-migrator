# Quickstart

This walks through a full migration of a `.yxmd` workflow to Microsoft Fabric
using the `alteryx2fabric` toolkit.

## 0. Prereqs

- Python 3.10+
- Azure CLI (`az login` against the tenant that owns the Fabric workspace)
- A Fabric workspace ID (GUID) where you have **Member** or higher

## 1. Install

```powershell
pip install -e d:\path\to\alteryx2fabric
a2f --version
```

## 2. Initialise a project

```powershell
mkdir D:\my-migration
cd D:\my-migration
a2f init my-migration --workspace-id 00000000-0000-0000-0000-000000000000
```

This creates:

```
my-migration/
├── .a2f/state.json
├── inputs/
├── reference_outputs/
├── fabric_outputs/
├── notebooks/
└── README.md
```

Run local checks first, then verify Azure and Fabric access:

```powershell
a2f doctor --offline
a2f doctor --json-output
```

## 3. Plan the workflow

```powershell
a2f plan C:\path\to\workflow.yxmd
```

Review `.a2f/migration-plan.md`, especially manual or unknown tool mappings.

## 4. Drop input files in

```powershell
copy C:\path\to\source-data\*.xlsx .\inputs\
```

## 5. Generate local artifacts

```powershell
a2f migrate C:\path\to\workflow.yxmd --inputs inputs
```

This parses, plans, generates, validates, and records resumable stage state in
`.a2f/migration.json`. GitHub Models is the default provider; Copilot can invoke
the workflow through the repository agent but is not a runtime dependency.

## 6. Review and package

```powershell
a2f doctor --offline
```

Inspect `notebooks/nb_bronze.py`, `nb_silver.py`, and `nb_gold.py`. Deployment
rejects missing, invalid, empty, or placeholder bodies.

## 7. Deploy and run

```powershell
a2f migrate C:\path\to\workflow.yxmd --inputs inputs --to-fabric --yes --run-pipeline `
	--reference reference_outputs --outputs fabric_outputs
```

Fabric writes require explicit `--yes`. Rerun the same command to resume after
a failure, or add `--restart` to regenerate all stages.

## 8. Optional standalone packaging

```powershell
a2f package-notebooks
```

This emits complete `.ipynb` files with helper cells and Lakehouse metadata.

## 9. Validate

```powershell
a2f download Files/Output --out fabric_outputs
a2f validate --ref reference_outputs --gen fabric_outputs --atol 1e-3
```

Exit code 0 means every reference file matched. Non-zero prints a per-file
diff report.
