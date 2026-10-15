"""Turn a log's latest risk assessment into a stored, pending priority recommendation (M.10)."""
from __future__ import annotations
import json
from typing import Any
from fastapi import HTTPException
from app.db import get_pool
from app.engine.priority import recommend_priority
from app.services import risk as risk_service


def _out(r: Any) -> dict[str, Any]:
    return {"id": r["id"], "record_id": r["record_id"], "risk_id": r["risk_id"], "priority": r["priority"],
            "status": r["status"], "method_version": r["method_version"],
            "explanation": json.loads(r["explanation"]), "created_at": r["created_at"].isoformat()}


async def recommend_log(log_id: int, user_id: int) -> dict[str, Any]:
    risk = await risk_service.latest(log_id) or await risk_service.assess_log(log_id, user_id)
    async with get_pool().acquire() as conn:
        rec = await conn.fetchrow(
            "select mr.id, ml.original_text from maintenance_records mr join maintenance_logs ml"
            " on ml.id = mr.log_id where mr.log_id = $1", log_id)
        if rec is None:
            raise HTTPException(404, "No extracted record for this log")
        res = recommend_priority(
            risk_category=risk["category"], text=rec["original_text"],
            criticality=risk["features"]["criticality"], recurrence_90d=risk["features"]["recurrence_90d"])
        row = await conn.fetchrow(
            "insert into recommendations (record_id, risk_id, priority, explanation, method_version, created_by)"
            " values ($1,$2,$3,$4,$5,$6) returning *",
            rec["id"], risk["id"], res["priority"], json.dumps(res["explanation"]), res["method_version"], user_id)
    return _out(row)


async def latest(log_id: int) -> dict[str, Any] | None:
    async with get_pool().acquire() as conn:
        r = await conn.fetchrow(
            "select r.* from recommendations r join maintenance_records mr on mr.id = r.record_id"
            " where mr.log_id = $1 order by r.created_at desc, r.id desc limit 1", log_id)
    return _out(r) if r else None
