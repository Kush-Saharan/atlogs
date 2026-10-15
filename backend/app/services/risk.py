"""Gather risk inputs for a log (M.9), score them with the pure `engine.risk`, store the result."""
from __future__ import annotations
import json
import re
from datetime import date, timedelta
from typing import Any
from fastapi import HTTPException
from app.db import get_pool
from app.engine.risk import assess_risk
from app.workflows.retrieval import _cur, similar_cases

WINDOW_DAYS = 90
# shortcut: the extractor only finds positive outcomes, so "adverse" is a keyword guess; revisit with real outcome labels.
_ADVERSE = re.compile(r"\b(fail\w*|recurr\w*|repeat\w*|unresolved|not resolved|still)\b", re.I)
_FIELDS = ("equipment", "component", "date")


def _day(value: str | None, fallback: date) -> date:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return fallback


async def assess_log(log_id: int, user_id: int) -> dict[str, Any]:
    async with get_pool().acquire() as conn:
        cur = await conn.fetchrow(
            "select ml.original_text, ml.created_at::date as created, "
            + ", ".join(_cur(f) for f in _FIELDS)
            + " from maintenance_records mr join maintenance_logs ml on ml.id = mr.log_id"
            " where mr.log_id = $1", log_id)
        if cur is None:
            raise HTTPException(404, "No extracted record for this log")
        ref = _day(cur["date"], cur["created"])
        equipment = (cur["equipment"] or "").strip()
        history: list[Any] = []
        crit = None
        if equipment:
            history = await conn.fetch(
                "select * from (select mr.log_id, ml.created_at::date as created, "
                + ", ".join(_cur(f) for f in _FIELDS)
                + " from maintenance_records mr join maintenance_logs ml on ml.id = mr.log_id"
                " where mr.log_id <> $1) h where lower(trim(h.equipment)) = lower($2)",
                log_id, equipment)
            crit = await conn.fetchval(
                "select c.level from asset_criticality c join asset_identifiers i "
                "on i.concept = c.concept and lower(i.value) = c.value where lower(i.value) = lower($1) limit 1",
                equipment)
        start = ref - timedelta(days=WINDOW_DAYS)
        recent = [h for h in history if start <= _day(h["date"], h["created"]) <= ref]
        comp = (cur["component"] or "").strip().lower()
        recurrence = [h["log_id"] for h in recent if comp and (h["component"] or "").strip().lower() == comp]
        sim = (await similar_cases(conn, cur["original_text"], {"exclude_log_id": log_id}, 5))["matches"]
        with_outcome = [m for m in sim if m["outcome"]]
        adverse = [m["log_id"] for m in with_outcome if _ADVERSE.search(m["outcome"])]
        features = {
            "history_count": len(history), "recurrence_90d": len(recurrence),
            "recent_incidents_90d": len(recent), "criticality": crit or "unknown",
            "similar_adverse_rate": len(adverse) / len(with_outcome) if with_outcome else None,
        }
        result = assess_risk(features)
        refs = {
            "equipment": equipment or None, "reference_date": ref.isoformat(), "window_days": WINDOW_DAYS,
            "recurrence_log_ids": recurrence, "recent_log_ids": [h["log_id"] for h in recent],
            "history_log_ids": [h["log_id"] for h in history],
            "similar_log_ids": [m["log_id"] for m in sim], "adverse_similar_log_ids": adverse,
            "criticality_source": "asset_criticality" if crit else None,
        }
        row = await conn.fetchrow(
            "insert into risk_assessments (log_id, score, category, insufficient_evidence, method_version,"
            " factors, features, input_refs, created_by) values ($1,$2,$3,$4,$5,$6,$7,$8,$9)"
            " returning id, created_at",
            log_id, result["score"], result["category"], result["insufficient_evidence"],
            result["method_version"], json.dumps(result["factors"]), json.dumps(features),
            json.dumps(refs), user_id)
    return {**result, "id": row["id"], "created_at": row["created_at"].isoformat(),
            "features": features, "input_refs": refs}


async def latest(log_id: int) -> dict[str, Any] | None:
    async with get_pool().acquire() as conn:
        r = await conn.fetchrow(
            "select * from risk_assessments where log_id = $1 order by created_at desc, id desc limit 1", log_id)
    if r is None:
        return None
    out = {k: r[k] for k in ("id", "score", "category", "insufficient_evidence", "method_version")}
    out.update(score=float(r["score"]), created_at=r["created_at"].isoformat(),
               **{k: json.loads(r[k]) for k in ("factors", "features", "input_refs")})
    return out
