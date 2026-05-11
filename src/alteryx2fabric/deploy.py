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


def _nb_activity(name: str, depends_on: list[str], nb_id: str, ws: str,
                 nb_params: dict | None = None) -> dict:
    type_props: dict = {"notebookId": nb_id, "workspaceId": ws}
    if nb_params:
        # Each param: {"value": "@pipeline().parameters.<Name>", "type": "<type>"}
        type_props["parameters"] = nb_params
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
        "typeProperties": type_props,
    }


def _build_pipeline_parameters(params: list[dict] | None) -> dict:
    """Convert detected Parameter dicts to the pipeline `parameters` block."""
    if not params:
        return {}
    from .parameters import Parameter
    out: dict = {}
    for p in params:
        if not isinstance(p, dict) or "name" not in p:
            continue
        obj = Parameter(**{k: v for k, v in p.items() if k in Parameter.__annotations__})
        out[obj.name] = obj.as_pipeline_param()
    return out


def _build_nb_param_pass_through(params: list[dict] | None) -> dict:
    """For each pipeline parameter, build a notebook activity parameter that
    references it via `@pipeline().parameters.<name>`."""
    if not params:
        return {}
    from .parameters import Parameter
    out: dict = {}
    for p in params:
        if not isinstance(p, dict) or "name" not in p:
            continue
        obj = Parameter(**{k: v for k, v in p.items() if k in Parameter.__annotations__})
        pi_type = obj.as_pipeline_param()["type"]
        out[obj.name] = {
            "value": f"@pipeline().parameters.{obj.name}",
            "type": pi_type,
        }
    return out


def deploy_pipeline(
    client: FabricClient,
    name: str,
    chain: list[tuple[str, str]],
    parameters: list[dict] | None = None,
) -> str:
    """Deploy a Data Pipeline that runs a linear chain of notebooks.

    `chain` is a list of (activity_name, notebook_id) in execution order.
    `parameters` is an optional list of Parameter-shaped dicts; they become
    pipeline-level parameters that are passed through to each notebook
    activity (so notebooks can reference them via `mssparkutils.runtime.context`
    or notebook `%%configure` parameter cells).

    Returns the pipeline item id.
    """
    nb_params = _build_nb_param_pass_through(parameters)
    activities = []
    prev: list[str] = []
    for activity_name, nb_id in chain:
        activities.append(_nb_activity(activity_name, prev, nb_id, client.ws, nb_params))
        prev = [activity_name]
    pipeline = {
        "properties": {
            "activities": activities,
            "parameters": _build_pipeline_parameters(parameters),
        }
    }
    definition = {"parts": [encode_json_part("pipeline-content.json", pipeline)]}

    existing = client.find_item(name, "DataPipeline")
    if existing:
        client.update_item_definition("dataPipelines", existing["id"], definition)
        return existing["id"]
    res = client.create_item({"displayName": name, "type": "DataPipeline", "definition": definition})
    return res["id"]
