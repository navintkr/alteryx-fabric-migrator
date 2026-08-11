"""Structured preflight checks for local migration projects and Fabric access."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from . import state as project_state
from .notebooks import validate_notebook_body


@dataclass
class Check:
    name: str
    status: str
    message: str
    details: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _local_checks(root: Path) -> list[Check]:
    checks: list[Check] = []
    az_path = shutil.which("az")
    checks.append(Check("azure_cli", "pass" if az_path else "fail", az_path or "Azure CLI was not found."))

    state = project_state.load(root)
    workspace_id = state.get("workspace_id")
    checks.append(Check(
        "workspace_config",
        "pass" if workspace_id else "fail",
        f"Workspace configured: {workspace_id}" if workspace_id else "workspace_id is missing from .a2f/state.json.",
    ))

    ir_path = root / "ir.json"
    if not ir_path.is_file():
        checks.append(Check("ir", "fail", "ir.json is missing; run `a2f parse`."))
    else:
        try:
            ir = json.loads(ir_path.read_text(encoding="utf-8"))
            required = {"workflow", "tools", "connections", "inputs", "outputs"}
            missing = sorted(required - set(ir))
            checks.append(Check(
                "ir", "fail" if missing else "pass",
                f"IR is missing keys: {', '.join(missing)}" if missing else f"IR contains {len(ir['tools'])} tools.",
            ))
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            checks.append(Check("ir", "fail", f"ir.json is invalid: {exc}"))

    notebook_dir = root / "notebooks"
    for layer in ("bronze", "silver", "gold"):
        path = notebook_dir / f"nb_{layer}.py"
        if not path.is_file():
            checks.append(Check(f"notebook_{layer}", "fail", f"Missing {path.relative_to(root)}."))
            continue
        issues = validate_notebook_body(path.read_text(encoding="utf-8"))
        checks.append(Check(
            f"notebook_{layer}", "fail" if issues else "pass",
            "; ".join(issues) if issues else f"{path.relative_to(root)} is valid.",
        ))

    refs = root / "reference_outputs"
    ref_count = sum(1 for path in refs.rglob("*") if path.is_file()) if refs.is_dir() else 0
    checks.append(Check(
        "reference_outputs", "pass" if ref_count else "warn",
        f"Found {ref_count} reference output file(s)." if ref_count else "No reference outputs found; parity cannot be verified.",
    ))
    return checks


def run_checks(
    root: str | Path = ".",
    *,
    online: bool = True,
    client_factory: Callable | None = None,
) -> list[Check]:
    project_root = Path(root)
    checks = _local_checks(project_root)
    if not online:
        return checks

    from .auth import get_tenant_and_user
    try:
        tenant, user = get_tenant_and_user()
        checks.append(Check("azure_auth", "pass", f"Signed in as {user}.", {"tenant": tenant, "user": user}))
    except Exception as exc:  # noqa: BLE001 - preflight converts provider failures into diagnostics
        checks.append(Check("azure_auth", "fail", str(exc)))
        return checks

    state = project_state.load(project_root)
    workspace_id = state.get("workspace_id")
    if not workspace_id:
        return checks
    if client_factory is None:
        from .fabric_api import FabricClient
        client_factory = FabricClient
    try:
        client = client_factory(workspace_id)
        items = client.list_items()
        checks.append(Check("workspace_access", "pass", f"Workspace contains {len(items)} item(s)."))
        lakehouse_name = state.get("lakehouse_name")
        if lakehouse_name:
            lakehouse = next(
                (item for item in items if item.get("type") == "Lakehouse" and item.get("displayName") == lakehouse_name),
                None,
            )
            checks.append(Check(
                "lakehouse", "pass" if lakehouse else "warn",
                f"Lakehouse found: {lakehouse_name}." if lakehouse else f"Lakehouse not yet provisioned: {lakehouse_name}.",
            ))
    except Exception as exc:  # noqa: BLE001 - Fabric clients expose multiple transport exception types
        checks.append(Check("workspace_access", "fail", str(exc)))
    return checks


def exit_code(checks: list[Check]) -> int:
    return 2 if any(check.status == "fail" for check in checks) else 0