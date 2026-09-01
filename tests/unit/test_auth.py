from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import auth
from app.api.auth import TokenValidator


def test_validator_accepts_client_id_and_identifier_uri_audiences(monkeypatch):
    settings = SimpleNamespace(
        azure_tenant_id="tenant-id",
        issuer="https://login.microsoftonline.com/tenant-id/v2.0",
        token_audiences=["client-id", "api://client-id"],
    )
    validator = object.__new__(TokenValidator)
    validator.settings = settings
    validator.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="signing-key")
    )
    captured: dict[str, object] = {}

    def decode(*_args, **kwargs):
        captured.update(kwargs)
        return {"tid": "tenant-id"}

    monkeypatch.setattr(auth.jwt, "decode", decode)

    validator.validate("token")

    assert captured["audience"] == ["client-id", "api://client-id"]


def test_search_service_rejects_other_managed_identity(monkeypatch):
    settings = SimpleNamespace(azure_search_principal_id="search-object-id")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    monkeypatch.setattr(TokenValidator, "validate", lambda _self, _token: {"oid": "other-id"})
    monkeypatch.setattr(TokenValidator, "__init__", lambda _self, _settings: None)

    with pytest.raises(HTTPException) as exc_info:
        auth.require_search_service(credentials, settings)

    assert exc_info.value.status_code == 403