---
mode: agent
description: Migrate an Alteryx .yxmd workflow to Microsoft Fabric end-to-end.
---

# Migrate an Alteryx workflow to Fabric

You are migrating `${input:yxmd_path}` to Fabric workspace
`${input:workspace_id}`.

Use the **alteryx2fabric** skill at [`../SKILL.md`](../SKILL.md). Read it
fully before starting, including all four `instructions/*.md` files.

## Plan

1. **Initialise the project** — pick a short project name and run:
   ```
   a2f init <project> --workspace-id ${input:workspace_id}
   ```
2. **Parse** the YXMD:
   ```
   a2f parse ${input:yxmd_path} --out ir.json
   ```
   Read `ir.json`. Inventory the tools, inputs, outputs.
3. **Translate** each tool into a Python block using
   [`../instructions/decoding-yxmd.md`](../instructions/decoding-yxmd.md) and
   [`../instructions/formula-mapping.md`](../instructions/formula-mapping.md).
4. **Write** three notebooks under `notebooks/`:
   - `nb_bronze.py` — read each input file → Delta `bronze_*`
   - `nb_silver.py` — business logic → Delta `silver_*`
   - `nb_gold.py`   — final outputs → Delta `gold_*` and Excel under `Files/Output/`
   Apply every rule in
   [`../instructions/known-gotchas.md`](../instructions/known-gotchas.md).
5. **Provision** the Lakehouse:
   ```
   a2f provision --lakehouse <name>
   ```
6. **Upload** input files:
   ```
   a2f upload inputs/ --to Input
   ```
7. **Deploy** notebooks + pipeline:
   ```
   a2f deploy --pipeline-name <project>_pipeline
   ```
8. **Run**:
   ```
   a2f run
   ```
9. **Download & validate**:
   ```
   a2f download Files/Output --out fabric_outputs
   a2f validate --ref reference_outputs --gen fabric_outputs
   ```

Stop and ask the user only if:
- A custom macro (`.yxmc`) is referenced but not provided.
- An Alteryx tool is configured in a way you can't map to Python with
  confidence.
- Validation fails on more than 10% of rows in any output file — surface the
  diff report and ask for guidance before patching.

Otherwise, proceed autonomously through all 9 steps and report the validation
summary at the end.
