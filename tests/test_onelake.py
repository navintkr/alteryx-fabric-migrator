from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from alteryx2fabric import cli
from alteryx2fabric.onelake import OneLake


def test_base_preserves_lakehouse_guid():
    lakehouse_id = "fe1c2cf5-bf3e-46e5-9bbb-a3cd1d890987"
    client = OneLake("ac57aef0-c96c-40ba-a741-cc9422a169d0", lakehouse_id)

    assert client._base("Files", "Input").endswith(f"/{lakehouse_id}/Files/Input")


def test_list_dir_addresses_workspace_filesystem(monkeypatch):
    lakehouse_id = "fe1c2cf5-bf3e-46e5-9bbb-a3cd1d890987"
    workspace_id = "ac57aef0-c96c-40ba-a741-cc9422a169d0"
    requested_urls = []

    class Response:
        ok = True

        def json(self):
            return {"paths": []}

    monkeypatch.setattr("alteryx2fabric.onelake.storage_headers", dict)
    monkeypatch.setattr(
        "alteryx2fabric.onelake.requests.get",
        lambda url, headers: requested_urls.append(url) or Response(),
    )

    OneLake(workspace_id, lakehouse_id).list_dir("Output")

    assert requested_urls[0].startswith(f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}?")
    assert f"directory={lakehouse_id}/Files/Output" in requested_urls[0]


def test_upload_prefers_lakehouse_id(monkeypatch, tmp_path: Path):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "sales.csv").write_text("id\n1\n", encoding="utf-8")
    state = {
        "workspace_id": "workspace-id",
        "lakehouse_id": "lakehouse-id",
        "lakehouse_name": "lakehouse-name",
    }
    created_with = []

    class FakeOneLake:
        def __init__(self, workspace, lakehouse):
            created_with.append((workspace, lakehouse))

        def upload(self, local_path, remote_subpath):
            return Path(local_path).stat().st_size

    monkeypatch.setattr(cli._state, "load", lambda _: state)
    monkeypatch.setattr(cli, "OneLake", FakeOneLake)

    result = CliRunner().invoke(cli.main, ["upload", str(input_dir), "--to", "Input"])

    assert result.exit_code == 0
    assert created_with == [("workspace-id", "lakehouse-id")]
    assert "1 files uploaded" in result.output


def test_download_normalizes_files_prefix(monkeypatch, tmp_path: Path):
    listed = []

    class FakeOneLake:
        def __init__(self, workspace, lakehouse):
            pass

        def list_dir(self, remote_subpath):
            listed.append(remote_subpath)
            return []

        def download(self, remote_subpath, local_path):
            Path(local_path).write_text("data", encoding="utf-8")
            return 4

    monkeypatch.setattr(cli._state, "load", lambda _: {
        "workspace_id": "workspace-id", "lakehouse_id": "lakehouse-id"
    })
    monkeypatch.setattr(cli, "OneLake", FakeOneLake)

    result = CliRunner().invoke(
        cli.main, ["download", "Files/Output/result.csv", "--out", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert listed == ["Output/result.csv"]
    assert (tmp_path / "result.csv").is_file()
