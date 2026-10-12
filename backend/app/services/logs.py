"""Maintenance-log intake (spec M1): validate, decode, hash, store the original first.

Extraction (M.4) runs through `extract`. A failing extractor marks the log `error` —
the original text is already saved and is never touched afterwards.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from fastapi import HTTPException

from app.db import get_pool
from app.engine import log_extract

MAX_BYTES = 1_000_000  # 1 MB
ALLOWED_EXT = (".txt", ".log", ".csv")


_LLM_FIELDS = ("equipment", "component", "symptom", "action", "outcome", "date")


async def fill_with_llm(text: str, result: dict[str, Any], api_key: str) -> dict[str, Any]:
    """M-D3: ask the LLM only for fields the rules left empty. Skipped without a key.
    A value is kept only if it appears verbatim in the log (gives a real span)."""
    empty = [f for f in _LLM_FIELDS if result["fields"].get(f) is None]
    if not api_key or not empty:
        return result
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.services.llm import get_extract_model, resilient  # shares the NVIDIA rate limiter
    from app.workflows.extract_ops import _extract_json, _text_of
    try:
        out = await resilient(get_extract_model()).ainvoke([
            SystemMessage(content="detailed thinking off\nExtract maintenance facts. Copy "
                          "values verbatim from the log. Use null if absent or negated."),
            HumanMessage(content=f"Log:\n{text}\n\nReturn ONLY a JSON object with keys "
                         f"{json.dumps(empty)}.")])
        data = _extract_json(_text_of(out)) or {}
    except Exception:  # noqa: BLE001 - the LLM is optional; rule results stand
        return result
    for f in empty:
        v = data.get(f)
        i = text.lower().find(v.strip().lower()) if isinstance(v, str) and v.strip() else -1
        if i >= 0:
            result["fields"][f] = {"value": v.strip(), "span": [i, i + len(v.strip())],
                                   "confidence": 0.5, "needs_review": True, "source": "llm"}
    return result


async def extract(conn: Any, text: str) -> dict[str, Any]:
    rows = await conn.fetch("select term, canonical from terminology")
    result = log_extract.extract(text, {r["term"]: r["canonical"] for r in rows})
    return await fill_with_llm(text, result, os.environ.get("NVIDIA_API_KEY", ""))


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
            result = await extract(conn, text)
            await conn.execute(
                "insert into maintenance_records (log_id, extracted) values ($1, $2)",
                log_id, json.dumps(result),
            )
            await conn.execute(
                "update maintenance_logs set status = 'extracted' where id = $1", log_id
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
        rec = await conn.fetchrow(
            "select extracted, reviewed, reviewed_by, reviewed_at from maintenance_records"
            " where log_id = $1", log_id)
    if row is None:
        raise HTTPException(404, "Log not found")
    out = dict(row)
    out["record"] = None if rec is None else {
        **rec, "extracted": json.loads(rec["extracted"]),
        "reviewed": json.loads(rec["reviewed"]) if rec["reviewed"] else None}
    return out


async def review(log_id: int, fields: dict[str, str | None], user_id: int) -> dict[str, Any]:
    """Save reviewed values beside `extracted` (never over it); the log text is untouched."""
    bad = set(fields) - set(_LLM_FIELDS)
    if bad:
        raise HTTPException(422, f"Unknown field(s): {', '.join(sorted(bad))}")
    clean = {}
    for k, v in fields.items():
        v = (v or "").strip()
        if len(v) > 500:
            raise HTTPException(422, f"{k} is longer than 500 characters")
        clean[k] = {"value": v or None}
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            ok = await conn.fetchval(
                "update maintenance_records set reviewed = $2, reviewed_by = $3,"
                " reviewed_at = now() where log_id = $1 returning id",
                log_id, json.dumps(clean), user_id)
            if ok is None:
                raise HTTPException(404, "No extracted record for this log")
            await conn.execute(
                "update maintenance_logs set status = 'reviewed' where id = $1", log_id)
    return await get_log(log_id)
