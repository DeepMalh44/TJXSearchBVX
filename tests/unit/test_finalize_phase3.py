from types import SimpleNamespace

import pytest

from scripts import finalize_phase3


def test_configure_entra_allows_known_stale_policy_challenge(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        finalize_phase3.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="TokenCreatedWithOutdatedPolicies",
        ),
    )

    finalize_phase3.configure_entra("tenant", "https://app.example")

    assert "Conditional Access requires reauthentication" in capsys.readouterr().err


def test_configure_entra_rejects_other_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        finalize_phase3.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Forbidden",
        ),
    )

    with pytest.raises(RuntimeError, match="Forbidden"):
        finalize_phase3.configure_entra("tenant", "https://app.example")