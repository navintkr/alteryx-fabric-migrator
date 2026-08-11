from __future__ import annotations

from pathlib import Path

import pytest

from alteryx2fabric.deploy import deploy_generated_notebooks


class FakeClient:
    ws = "workspace-id"

    def __init__(self) -> None:
        self.items: list[dict] = []

    def find_item(self, name: str, item_type: str):
        return None

    def create_item(self, payload: dict):
        self.items.append(payload)
        return {"id": f"id-{len(self.items)}"}


def test_deploy_generated_notebooks_uses_local_bodies(tmp_path: Path):
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    for name in ("nb_bronze.py", "nb_silver.py", "nb_gold.py"):
        (notebooks / name).write_text(f"print('{name}')", encoding="utf-8")

    client = FakeClient()
    ids = deploy_generated_notebooks(client, str(notebooks), "lakehouse-id", "Lakehouse")

    assert set(ids) == {"Nb_Bronze_Ingest", "Nb_Silver_Transform", "Nb_Gold_Outputs"}
    assert len(client.items) == 3
    payload = client.items[0]["definition"]["parts"][0]["payload"]
    import base64
    import json
    notebook = json.loads(base64.b64decode(payload))
    assert len(notebook["cells"]) == 3
    assert any("def write_delta" in "".join(cell["source"]) for cell in notebook["cells"])


def test_deploy_generated_notebooks_rejects_missing_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="a2f generate all"):
        deploy_generated_notebooks(FakeClient(), str(tmp_path), "lakehouse-id", "Lakehouse")


def test_deploy_generated_notebooks_rejects_placeholder(tmp_path: Path):
    for name in ("nb_bronze.py", "nb_silver.py", "nb_gold.py"):
        (tmp_path / name).write_text("print('ok')", encoding="utf-8")
    (tmp_path / "nb_silver.py").write_text("src = spark.table('bronze_example')", encoding="utf-8")

    with pytest.raises(ValueError, match="Placeholder content"):
        deploy_generated_notebooks(FakeClient(), str(tmp_path), "lakehouse-id", "Lakehouse")