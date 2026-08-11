from __future__ import annotations

from alteryx2fabric.fabric_api import FabricClient


def test_update_definition_waits_for_async_operation(monkeypatch):
    class Response:
        def __init__(self):
            self.status_code = 202
            self.headers = {"Location": "https://operation/1"}
            self.text = ""

    client = FabricClient("workspace")
    waited = []
    monkeypatch.setattr(client, "_post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(client, "_wait_lro", lambda location: waited.append(location) or {})

    client.update_item_definition("notebooks", "notebook", {"parts": []})

    assert waited == ["https://operation/1"]