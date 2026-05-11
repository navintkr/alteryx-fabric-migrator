"""OneLake DFS client — upload/download/list files under a Lakehouse's `Files/` area."""
from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

import requests

from .auth import storage_headers

DFS_HOST = "https://onelake.dfs.fabric.microsoft.com"


def _encode_path(parts: list[str]) -> str:
    return "/".join(urllib.parse.quote(p, safe="") for p in parts if p)


class OneLake:
    def __init__(self, workspace: str, lakehouse_name_or_id: str):
        """`lakehouse_name_or_id` may be either the display name (preferred for DFS)
        or the GUID. Both endpoints exist on OneLake but DFS prefers names with
        the `.Lakehouse` suffix; we accept both and let callers decide.
        """
        self.workspace = workspace
        self.lakehouse = lakehouse_name_or_id

    def _base(self, *segs: str) -> str:
        if "." not in self.lakehouse:
            lh_seg = self.lakehouse + ".Lakehouse"
        else:
            lh_seg = self.lakehouse
        path = _encode_path([self.workspace, lh_seg, *segs])
        return f"{DFS_HOST}/{path}"

    def upload(self, local_path: str | os.PathLike, remote_subpath: str) -> int:
        """Upload one file to `Files/<remote_subpath>`. Returns bytes uploaded."""
        local_path = Path(local_path)
        url = self._base("Files", *remote_subpath.split("/"))
        size = local_path.stat().st_size
        h = storage_headers()

        # 1) create empty file
        r = requests.put(url + "?resource=file", headers=h)
        if not r.ok:
            raise RuntimeError(f"OneLake create failed: {r.status_code} {r.text}")
        # 2) append data
        with open(local_path, "rb") as f:
            data = f.read()
        r = requests.patch(
            url + "?action=append&position=0",
            headers={**h, "Content-Type": "application/octet-stream"},
            data=data,
        )
        if not r.ok:
            raise RuntimeError(f"OneLake append failed: {r.status_code} {r.text}")
        # 3) flush
        r = requests.patch(url + f"?action=flush&position={size}", headers=h)
        if not r.ok:
            raise RuntimeError(f"OneLake flush failed: {r.status_code} {r.text}")
        return size

    def download(self, remote_subpath: str, local_path: str | os.PathLike) -> int:
        url = self._base("Files", *remote_subpath.split("/"))
        r = requests.get(url, headers=storage_headers())
        if not r.ok:
            raise RuntimeError(f"OneLake download failed: {r.status_code} {r.text[:200]}")
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(r.content)
        return len(r.content)

    def list_dir(self, remote_subpath: str = "") -> list[dict]:
        """List paths under Files/<remote_subpath> recursively."""
        directory = "Files" + (f"/{remote_subpath}" if remote_subpath else "")
        url = self._base() + f"?recursive=true&resource=filesystem&directory={urllib.parse.quote(directory)}"
        r = requests.get(url, headers=storage_headers())
        if not r.ok:
            raise RuntimeError(f"OneLake list failed: {r.status_code} {r.text}")
        return r.json().get("paths", [])
