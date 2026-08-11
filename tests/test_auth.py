from __future__ import annotations

from alteryx2fabric import auth


def test_fetch_token_uses_resolved_az_executable(monkeypatch):
    calls = []
    monkeypatch.setattr(auth.shutil, "which", lambda _: r"C:\AzureCLI\az.cmd")
    monkeypatch.setattr(
        auth.subprocess,
        "check_output",
        lambda command, **kwargs: calls.append(command) or b"token\n",
    )

    assert auth._fetch_token(auth.FABRIC_RESOURCE) == "token"
    assert calls[0][0] == r"C:\AzureCLI\az.cmd"


def test_account_lookup_uses_resolved_az_executable(monkeypatch):
    calls = []
    monkeypatch.setattr(auth.shutil, "which", lambda _: r"C:\AzureCLI\az.cmd")
    monkeypatch.setattr(
        auth.subprocess,
        "check_output",
        lambda command, **kwargs: calls.append(command) or b'{"t":"tenant","u":"user"}',
    )
    auth.get_tenant_and_user.cache_clear()

    assert auth.get_tenant_and_user() == ("tenant", "user")
    assert calls[0][0] == r"C:\AzureCLI\az.cmd"
