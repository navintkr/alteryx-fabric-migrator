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

Sanity-check that az auth works against Fabric:

```powershell
a2f doctor
```

## 3. Parse the workflow

```powershell
a2f parse C:\path\to\workflow.yxmd --out ir.json
```

Read `ir.json` to inventory the tools. The summary printed to stdout is a
quick tool-count snapshot.

## 4. Drop input files in

```powershell
copy C:\path\to\source-data\*.xlsx .\inputs\
```

## 5. Provision the Lakehouse

```powershell
a2f provision --lakehouse my_migration_lh
```

## 6. Upload inputs to OneLake

```powershell
a2f upload inputs --to Input
```

## 7. Write the notebooks

Edit `notebooks/nb_bronze.py`, `notebooks/nb_silver.py`, `notebooks/nb_gold.py`
with the Python translation of your YXMD. Use the agent prompt at
[`../skill/prompts/migrate-workflow.prompt.md`](../skill/prompts/migrate-workflow.prompt.md)
to have Copilot do most of this.

## 8. Deploy

```powershell
a2f deploy --pipeline-name my_migration_pipeline
```

## 9. Run

```powershell
a2f run
```

## 10. Validate

```powershell
a2f download Files/Output --out fabric_outputs
a2f validate --ref reference_outputs --gen fabric_outputs --atol 1e-3
```

Exit code 0 means every reference file matched. Non-zero prints a per-file
diff report.
