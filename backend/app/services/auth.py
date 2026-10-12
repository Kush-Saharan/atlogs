"""Password hashing and signed role tokens (M-D2), stdlib only.

Token = base64url(JSON {uid, role, exp}) + "." + base64url(HMAC-SHA256 with AUTH_SECRET).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Header, HTTPException

ROLES = ("engineer", "manager", "admin")
TOKEN_TTL_SECONDS = 8 * 3600
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def get_secret() -> bytes:
    """AUTH_SECRET as bytes; raises a clear error when unset (called at startup)."""
    secret = os.environ.get("AUTH_SECRET", "")
    if not secret:
        raise RuntimeError(
            "AUTH_SECRET is not set. Add a long random value to backend/.env "
            '(e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
        )
    return secret.encode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(dk_hex)
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return hmac.compare_digest(dk, expected)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(get_secret(), body.encode(), hashlib.sha256).digest())


def make_token(uid: int, role: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    body = _b64(json.dumps({"uid": uid, "role": role, "exp": int(time.time()) + ttl}).encode())
    return f"{body}.{_sign(body)}"


def verify_token(token: str) -> dict | None:
    """Payload dict, or None if malformed, forged or expired."""
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(_unb64(body))
        if payload["role"] not in ROLES or payload["exp"] <= time.time():
            return None
        return payload
    except (ValueError, KeyError, TypeError):
        return None


def require_role(*roles: str):
    """FastAPI dependency: 401 without a valid bearer token, 403 if role not allowed.
    No roles given means any signed-in user."""

    def dep(authorization: str | None = Header(default=None)) -> dict:
        scheme, _, token = (authorization or "").partition(" ")
        payload = verify_token(token) if scheme.lower() == "bearer" else None
        if payload is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if roles and payload["role"] not in roles:
            raise HTTPException(status_code=403, detail="Role not permitted")
        return payload

    return dep
