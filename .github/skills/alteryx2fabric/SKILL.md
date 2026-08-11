---
name: alteryx2fabric
description: "Migrate Alteryx YXMD workflows to Microsoft Fabric Lakehouse, PySpark notebooks, Delta tables, and Data Pipelines. Use when: Alteryx migration, YXMD conversion, Alteryx formula translation, workflow assessment, notebook generation, parity validation, or Fabric deployment."
---

# Alteryx to Fabric

Read the canonical [migration skill](../../../skill/SKILL.md) and all files under [skill instructions](../../../skill/instructions/) before authoring code.

## Required Workflow

1. Run `a2f plan <workflow.yxmd>` and review `.a2f/migration-plan.md`.
2. Stop for explicit approval when the recommendation is `review_required`.
3. Use `a2f migrate <workflow.yxmd>` for local parse, generation, and preflight.
4. Inspect all generated notebook bodies; never deploy placeholders.
5. Use `a2f doctor --json-output` before Fabric writes.
6. Deploy only with `a2f migrate <workflow.yxmd> --to-fabric --yes` or the equivalent explicit commands.
7. Run parity validation against Alteryx reference outputs.
8. When a Fabric notebook fails, use the installed `spark-operations-cli` skill to diagnose the failed run before editing code.

## Boundaries

- Keep `a2f` deterministic for parsing, planning, packaging, deployment, and validation.
- Use Copilot as the optional authoring and orchestration layer, not as a Python subprocess dependency.
- Use `spark-authoring-cli` guidance for current Fabric notebook conventions.
- Use `e2e-medallion-architecture` for architecture review when a migration spans multiple workflows or data domains.
- Do not use Microsoft Foundry tools for this workflow.
