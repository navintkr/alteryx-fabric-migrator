"""Thin wrapper over the Microsoft Fabric REST API.

Handles the common patterns: list items, find by name+type, create items
(including LRO 202 polling), update item definitions, trigger jobs.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any

import requests

from .auth import fabric_headers

BASE = "https://api.fabric.microsoft.com/v1"


class FabricClient:
    def __init__(self, workspace_id: str):
        if not workspace_id:
            raise ValueError("workspace_id is required")
        self.ws = workspace_id

    # ---------- generic ----------
    def _get(self, path: str, **kw):
        return requests.get(f"{BASE}{path}", headers=fabric_headers(), **kw)

    def _post(self, path: str, json_body: Any | None = None, **kw):
        return requests.post(f"{BASE}{path}", headers=fabric_headers(), json=json_body, **kw)

    # ---------- items ----------
    def list_items(self) -> list[dict]:
        r = self._get(f"/workspaces/{self.ws}/items")
        r.raise_for_status()
        return r.json().get("value", [])

    def find_item(self, name: str, item_type: str | None = None) -> dict | None:
        for it in self.list_items():
            if it["displayName"] == name and (item_type is None or it["type"] == item_type):
                return it
        return None

    def _wait_lro(self, location: str, timeout_s: int = 600) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            r = requests.get(location, headers=fabric_headers())
            j = r.json()
            status = j.get("status")
            if status == "Succeeded":
                res = requests.get(location + "/result", headers=fabric_headers())
                if res.ok:
                    return res.json()
                return j
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"LRO failed: {j}")
            time.sleep(3)
        raise TimeoutError("LRO timeout")

    def create_item(self, body: dict) -> dict:
        r = self._post(f"/workspaces/{self.ws}/items", json_body=body)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 202:
            loc = r.headers.get("Location")
            if not loc:
                raise RuntimeError(f"202 without Location: {r.text}")
            return self._wait_lro(loc)
        raise RuntimeError(f"create_item failed {r.status_code}: {r.text}")

    def update_item_definition(self, item_type_segment: str, item_id: str, definition: dict) -> None:
        """item_type_segment is the URL segment, e.g. 'notebooks', 'dataPipelines'."""
        url = f"/workspaces/{self.ws}/{item_type_segment}/{item_id}/updateDefinition"
        r = self._post(url, json_body={"definition": definition})
        if r.status_code not in (200, 202):
            raise RuntimeError(f"updateDefinition failed {r.status_code}: {r.text}")
        if r.status_code == 202:
            location = r.headers.get("Location")
            if not location:
                raise RuntimeError(f"updateDefinition returned 202 without Location: {r.text}")
            self._wait_lro(location)

    # ---------- lakehouse ----------
    def create_lakehouse(self, name: str) -> dict:
        existing = self.find_item(name, "Lakehouse")
        if existing:
            return existing
        return self.create_item({"displayName": name, "type": "Lakehouse"})

    # ---------- jobs / pipelines ----------
    def run_pipeline(self, pipeline_id: str, parameters: dict | None = None) -> str:
        """Trigger a Data Pipeline and return the polling URL (Location header).

        `parameters` is an optional {name: value} dict matching the pipeline's
        defined parameters; values may be str/int/bool/list.
        """
        url = f"/workspaces/{self.ws}/items/{pipeline_id}/jobs/instances?jobType=Pipeline"
        body = None
        if parameters:
            body = {"executionData": {"parameters": parameters}}
        r = self._post(url, json_body=body)
        if r.status_code not in (200, 202):
            raise RuntimeError(f"run_pipeline failed {r.status_code}: {r.text}")
        loc = r.headers.get("Location")
        if not loc:
            raise RuntimeError("run_pipeline returned no Location header")
        return loc

    def poll_job(self, status_url: str, timeout_s: int = 1800, on_tick=None) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            j = requests.get(status_url, headers=fabric_headers()).json()
            if on_tick:
                on_tick(int(time.time() - t0), j.get("status"))
            if j.get("status") in ("Completed", "Failed", "Cancelled", "Deduped"):
                return j
            time.sleep(15)
        raise TimeoutError("poll_job timeout")


# ---------- inline-definition helpers ----------
def b64_part(path: str, payload_bytes: bytes) -> dict:
    return {
        "path": path,
        "payload": base64.b64encode(payload_bytes).decode(),
        "payloadType": "InlineBase64",
    }


def encode_json_part(path: str, obj: Any) -> dict:
    return b64_part(path, json.dumps(obj, indent=1).encode("utf-8"))
