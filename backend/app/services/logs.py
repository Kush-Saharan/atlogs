"""Maintenance-log intake (spec M1): validate, decode, hash, store the original first.

Extraction (M.4) plugs in through `extract`; until then it returns None and a log
stays `received`. A failing extractor marks the log `error` — the original text is
already saved and is never touched afterwards.
"""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import HTTPException

from app.db import get_pool

MAX_BYTES = 1_000_000  # 1 MB
ALLOWED_EXT = (".txt", ".log", ".csv")


def extract(text: str) -> Any | None:
    """Placeholder for the M.4 extractor. None = nothing extracted yet."""
    return None


def decode(data: bytes) -> str:
    """UTF-8 first, Latin-1 as fallback (it accepts every byte)."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def validate(filename: str | None, data: bytes) -> str:
    """Return the decoded text, or raise a clear 4xx."""
    if filename and not filename.lower().endswith(ALLOWED_EXT):
        raise HTTPException(
            415, f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXT)}"
        )
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Log is larger than the 1 MB limit")
    text = decode(data)
    if not text.strip():
        raise HTTPException(400, "Log is empty")
    return text


async def submit(
    text: str, filename: str | None, user_id: int, force: bool
) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode()).hexdigest()
    async with get_pool().acquire() as conn:
        if not force:
            dup = await conn.fetchval(
                "select id from maintenance_logs where sha256 = $1 order by id limit 1",
                digest,
            )
            if dup is not None:
                raise HTTPException(
                    409,
                    detail={
                        "message": "This log was already submitted. Submit anyway to add it again.",
                        "existing_id": dup,
                    },
                )
        log_id = await conn.fetchval(  # original text saved before any processing
            "insert into maintenance_logs (sha256, filename, original_text, submitted_by)"
            " values ($1, $2, $3, $4) returning id",
            digest, filename, text, user_id,
        )
        try:
            status = "received" if extract(text) is None else "extracted"
            await conn.execute(
                "update maintenance_logs set status = $2 where id = $1", log_id, status
            )
        except Exception as exc:  # noqa: BLE001 - any extractor failure becomes status=error
            await conn.execute(
                "update maintenance_logs set status = 'error', error = $2 where id = $1",
                log_id, str(exc) or type(exc).__name__,
            )
        row = await conn.fetchrow(_SELECT + " where id = $1", log_id)
    return dict(row)


_SELECT = (
    "select id, filename, status, error, sha256, submitted_by, created_at,"
    " left(original_text, 160) as preview from maintenance_logs"
)


async def list_logs() -> list[dict[str, Any]]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(_SELECT + " order by id desc limit 200")
    return [dict(r) for r in rows]


async def get_log(log_id: int) -> dict[str, Any]:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "select id, filename, status, error, sha256, submitted_by, created_at,"
            " original_text from maintenance_logs where id = $1",
            log_id,
        )
    if row is None:
        raise HTTPException(404, "Log not found")
    return dict(row)
