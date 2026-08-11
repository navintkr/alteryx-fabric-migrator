"""Authentication helpers.

Uses the `az` CLI to acquire access tokens for two resources:
- Fabric / Power BI REST API
- Azure Storage (for OneLake DFS)

This avoids embedding any SDK secret-handling logic; users authenticate once
via `az login` and the toolkit reuses the existing session.
"""
from __future__ import annotations

import functools
import shutil
import subprocess
import time

FABRIC_RESOURCE = "https://analysis.windows.net/powerbi/api"
STORAGE_RESOURCE = "https://storage.azure.com"

# Small in-process cache (token, expires_at) per resource
_CACHE: dict[str, tuple[str, float]] = {}
_TTL_SECONDS = 50 * 60  # tokens are typically valid 60+ min


def _az_executable() -> str:
    executable = shutil.which("az")
    if executable is None:
        raise RuntimeError("Azure CLI (`az`) is required. Install it and run `az login` first.")
    return executable


def _check_az() -> None:
    _az_executable()


def _fetch_token(resource: str) -> str:
    _check_az()
    out = subprocess.check_output(
        [_az_executable(), "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
        shell=False,
    )
    return out.decode().strip()


def get_token(resource: str = FABRIC_RESOURCE) -> str:
    """Return a cached access token for the given resource (refresh if stale)."""
    now = time.time()
    cached = _CACHE.get(resource)
    if cached and (now < cached[1]):
        return cached[0]
    tok = _fetch_token(resource)
    _CACHE[resource] = (tok, now + _TTL_SECONDS)
    return tok


@functools.lru_cache(maxsize=4)
def get_tenant_and_user() -> tuple[str, str]:
    """Return (tenantId, userPrincipalName) of the currently signed-in `az` account."""
    _check_az()
    out = subprocess.check_output(
        [_az_executable(), "account", "show", "--query", "{t:tenantId,u:user.name}", "-o", "json"],
        shell=False,
    )
    import json
    j = json.loads(out)
    return j["t"], j["u"]


def fabric_headers(content_type: str | None = "application/json") -> dict[str, str]:
    h = {"Authorization": f"Bearer {get_token(FABRIC_RESOURCE)}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


def storage_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token(STORAGE_RESOURCE)}"}
