"""Auth tests — pure, no database."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import auth


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret")


def test_right_password_verifies_wrong_rejected():
    h = auth.hash_password("correct horse")
    assert auth.verify_password("correct horse", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "garbage")


def test_salt_is_random():
    assert auth.hash_password("same") != auth.hash_password("same")


def test_token_roundtrip():
    p = auth.verify_token(auth.make_token(7, "manager"))
    assert p and p["uid"] == 7 and p["role"] == "manager"


def test_forged_signature_rejected(monkeypatch):
    token = auth.make_token(7, "engineer")
    body, sig = token.split(".")
    assert auth.verify_token(f"{body}.{sig[:-2]}AA") is None
    # Token signed with another secret is rejected.
    monkeypatch.setenv("AUTH_SECRET", "other")
    assert auth.verify_token(token) is None


def test_expired_token_rejected():
    assert auth.verify_token(auth.make_token(1, "admin", ttl=-1)) is None


def test_role_denied_is_403_and_missing_token_401():
    dep = auth.require_role("manager", "admin")
    ok = dep(f"Bearer {auth.make_token(1, 'manager')}")
    assert ok["role"] == "manager"
    with pytest.raises(HTTPException) as e:
        dep(f"Bearer {auth.make_token(2, 'engineer')}")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        dep(None)
    assert e.value.status_code == 401


def test_missing_secret_fails_clearly(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET")
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        auth.get_secret()
