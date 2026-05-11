"""Build and deploy Notebooks + Data Pipeline to a Fabric workspace."""
from __future__ import annotations

from typing import Iterable

from .fabric_api import FabricClient, encode_json_part
from .notebooks import build_ipynb, bronze_cells, silver_cells, gold_cells


def deploy_notebook(
    client: FabricClient,
    name: str,
    cells: Iterable[tuple[str, str]],
    lakehouse_id: str,
    lakehouse_name: str,
) -> str:
    """Create-or-update a notebook from the given cells. Returns its id."""
    ipynb = build_ipynb(cells, client.ws, lakehouse_id, lakehouse_name)
    definition = {
        "format": "ipynb",
        "parts": [encode_json_part("notebook-content.ipynb", ipynb)],
    }
    existing = client.find_item(name, "Notebook")
    if existing:
        client.update_item_definition("notebooks", existing["id"], definition)
        return existing["id"]
    res = client.create_item({"displayName": name, "type": "Notebook", "definition": definition})
    return res["id"]


def deploy_default_notebooks(
    client: FabricClient,
    inputs: list[dict],
    lakehouse_id: str,
    lakehouse_name: str,
    prefix: str = "Nb",
) -> dict[str, str]:
    """Deploy Bronze / Silver / Gold scaffold notebooks. Returns name->id map."""
    ids: dict[str, str] = {}
    ids[f"{prefix}_Bronze_Ingest"] = deploy_notebook(
        client, f"{prefix}_Bronze_Ingest", bronze_cells(inputs), lakehouse_id, lakehouse_name
    )
    ids[f"{prefix}_Silver_Transform"] = deploy_notebook(
        client, f"{prefix}_Silver_Transform", silver_cells(), lakehouse_id, lakehouse_name
    )
    ids[f"{prefix}_Gold_Outputs"] = deploy_notebook(
        client, f"{prefix}_Gold_Outputs", gold_cells(), lakehouse_id, lakehouse_name
    )
    return ids


def _nb_activity(name: str, depends_on: list[str], nb_id: str, ws: str) -> dict:
    return {
        "name": name,
        "type": "TridentNotebook",
        "dependsOn": [{"activity": d, "dependencyConditions": ["Succeeded"]} for d in depends_on],
        "policy": {
            "timeout": "0.12:00:00",
            "retry": 0,
            "retryIntervalInSeconds": 30,
            "secureOutput": False,
            "secureInput": False,
        },
        "typeProperties": {"notebookId": nb_id, "workspaceId": ws},
    }


def deploy_pipeline(
    client: FabricClient,
    name: str,
    chain: list[tuple[str, str]],
) -> str:
    """Deploy a Data Pipeline that runs a linear chain of notebooks.

    `chain` is a list of (activity_name, notebook_id) in execution order.
    Returns the pipeline item id.
    """
    activities = []
    prev: list[str] = []
    for activity_name, nb_id in chain:
        activities.append(_nb_activity(activity_name, prev, nb_id, client.ws))
        prev = [activity_name]
    pipeline = {"properties": {"activities": activities}}
    definition = {"parts": [encode_json_part("pipeline-content.json", pipeline)]}

    existing = client.find_item(name, "DataPipeline")
    if existing:
        client.update_item_definition("dataPipelines", existing["id"], definition)
        return existing["id"]
    res = client.create_item({"displayName": name, "type": "DataPipeline", "definition": definition})
    return res["id"]
