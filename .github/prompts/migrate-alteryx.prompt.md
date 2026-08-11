---
name: Migrate Alteryx Workflow
description: "Plan and migrate one Alteryx YXMD workflow to Microsoft Fabric with notebook review and output parity validation."
agent: Alteryx2Fabric
argument-hint: "YXMD path, workspace ID, inputs folder, and reference outputs folder"
---

Migrate the supplied Alteryx workflow using `.github/skills/alteryx2fabric/SKILL.md`.

Start with deterministic planning and summarize the support classification and risks. Generate and validate local notebook artifacts before requesting approval for Fabric writes. After approval, provision or reuse the Lakehouse, upload inputs, deploy the authored notebooks and pipeline, execute it, download outputs, and report exact parity results. Resume from `.a2f/migration.json` when prior stages are complete.
