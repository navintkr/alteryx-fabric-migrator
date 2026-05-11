# Architecture

## Components

```
┌───────────────────────────────────────────────────────────────────┐
│                  alteryx2fabric repo                              │
│                                                                   │
│  ┌──────────────────────┐         ┌──────────────────────────┐    │
│  │  CLI (a2f)           │         │  Skill (skill/)          │    │
│  │  src/alteryx2fabric  │ ◄──────►│  SKILL.md + prompts +    │    │
│  │  pip-installable     │         │  instructions/*.md       │    │
│  └────────┬─────────────┘         └──────────────────────────┘    │
│           │                                                       │
│           ▼                                                       │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  Fabric REST API + OneLake DFS API                       │     │
│  │  Auth via `az account get-access-token`                  │     │
│  └────┬──────────────────────────────────────────────┬──────┘     │
│       ▼                                              ▼            │
└───────┼──────────────────────────────────────────────┼────────────┘
        │                                              │
        ▼                                              ▼
┌────────────────┐                          ┌────────────────────┐
│  Fabric        │                          │  OneLake           │
│  workspace     │                          │  Files/Tables      │
│  ├ Lakehouse   │                          │                    │
│  ├ Notebooks   │                          │                    │
│  └ Pipeline    │                          │                    │
└────────────────┘                          └────────────────────┘
```

## CLI module map

| Module           | Responsibility |
|---|---|
| `auth.py`        | `az` token cache (Fabric + Storage resources) |
| `fabric_api.py`  | `FabricClient` — items, LRO polling, notebook/pipeline update |
| `onelake.py`     | DFS upload/download with chunked PUT+PATCH semantics |
| `parse.py`       | `.yxmd` XML → IR (`workflow`, `tools`, `connections`, `inputs`, `outputs`) |
| `state.py`       | per-project `.a2f/state.json` keyed by workspace_id + project name |
| `notebooks.py`   | Build Synapse-PySpark .ipynb with trident metadata + helper cells |
| `deploy.py`      | Idempotent create-or-update of notebooks + pipeline |
| `run.py`         | Trigger pipeline, poll job, surface progress |
| `validate.py`    | Diff reference vs. generated output folders |
| `cli.py`         | Click commands: init / doctor / parse / provision / upload / deploy / run / download / validate |

## Default deployment shape

`a2f deploy` creates a linear pipeline of three notebooks:

```
NbBronze ──Succeeded──► NbSilver ──Succeeded──► NbGold
```

Each notebook embeds the Lakehouse as its `default_lakehouse` via trident
metadata so file paths are relative (`Files/...`, `Tables/...`).

## State file

`.a2f/state.json`:

```json
{
  "projects": {
    "<cwd-absolute-path>": {
      "name": "my-migration",
      "workspace_id": "...",
      "lakehouse_id": "...",
      "lakehouse_name": "my_migration_lh",
      "notebooks": {"NbBronze": "...", "NbSilver": "...", "NbGold": "..."},
      "pipeline_id": "...",
      "pipeline_name": "my_migration_pipeline"
    }
  }
}
```

The CLI reads/writes only the entry matching the current working directory,
so multiple migrations can coexist on one workstation.

## Why not...?

- **...use Fabric's Item Definition import-export tooling?** The toolkit
  uses `updateDefinition` under the hood — same protocol, but with templated
  notebook bodies and idempotent create-or-update logic.
- **...generate Dataflow Gen2 for Bronze?** Roadmap. Notebook Bronze is more
  flexible for header-offset Excel inputs and mixed encodings.
- **...drive Fabric via Spark Job Definitions?** Notebooks have richer
  observability and a click-to-debug story. SJD remains an option for
  customer environments that forbid notebooks.
