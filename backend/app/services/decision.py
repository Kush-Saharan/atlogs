"""Manager decisions on a pending recommendation (M.12). The system recommends; this records the human's call."""
from __future__ import annotations
import json
from typing import Any
from fastapi import HTTPException
from app.db import get_pool
_STATUS = {"approve": "approved", "modify": "modified", "reject": "rejected"}
def _out(r: Any) -> dict[str, Any]:
    return {"id": r["id"], "recommendation_id": r["recommendation_id"], "record_id": r["record_id"],
            "action": r["action"], "original": json.loads(r["original"]), "final": json.loads(r["final"]),
            "user_id": r["user_id"], "user": r.get("user"), "log_id": r.get("log_id"), "comment": r["comment"],
            "created_at": r["created_at"].isoformat()}
async def decide(rec_id: int, user_id: int, action: str, priority: str | None, comment: str | None) -> dict[str, Any]:
    """Status update and audit insert in ONE transaction: both happen or neither does."""
    status = _STATUS[action]
    comment = (comment or "").strip() or None
    if action != "approve" and comment is None:
        raise HTTPException(422, "A comment is required to modify or reject")
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            rec = await conn.fetchrow("select * from recommendations where id = $1 for update", rec_id)
            if rec is None:
                raise HTTPException(404, "Recommendation not found")
            if rec["status"] != "pending":
                raise HTTPException(409, f"Already {rec['status']}")
            final_priority = rec["priority"]
            if action == "modify":
                if priority is None or priority == rec["priority"]:
                    raise HTTPException(422, "Modify needs a different priority")
                final_priority = priority
            await conn.execute("update recommendations set status = $2 where id = $1", rec_id, status)
            row = await conn.fetchrow(
                "insert into decision_audit (recommendation_id, record_id, action, original, final, user_id, comment)"
                " values ($1,$2,$3,$4,$5,$6,$7) returning *", rec_id, rec["record_id"], status,
                json.dumps({"priority": rec["priority"], "status": "pending"}),
                json.dumps({"priority": final_priority, "status": status}), user_id, comment)
    return _out(row)
_SELECT = ('select a.*, mr.log_id, u.email as "user" from decision_audit a'
           " join users u on u.id = a.user_id join maintenance_records mr on mr.id = a.record_id")
async def history(log_id: int) -> list[dict[str, Any]]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            _SELECT + " where mr.log_id = $1"
            " order by a.created_at desc, a.id desc", log_id)
    return [_out(dict(r)) for r in rows]
async def audit_log(limit: int = 200) -> list[dict[str, Any]]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            _SELECT + " order by a.created_at desc, a.id desc limit $1", limit)
    return [_out(dict(r)) for r in rows]
