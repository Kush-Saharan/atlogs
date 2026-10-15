"""In-app notifications (M-D7): derived per role from existing tables, no table of their own."""
from __future__ import annotations
import json
from typing import Any
from app.db import get_pool

LIMIT = 50
# shortcut: no read-state, so "new decisions" means the last 7 days; add a per-user last-seen if that is too noisy.
DECISION_DAYS = 7
_LATEST_PENDING = ("r.status = 'pending' and r.id = (select max(r2.id) from recommendations r2"
                   " where r2.record_id = r.record_id)")


def _item(kind: str, message: str, log_id: int | None, at: Any) -> dict[str, Any]:
    return {"kind": kind, "message": message, "link": f"/logs/{log_id}" if log_id else "/schedule",
            "log_id": log_id, "at": at.isoformat() if at else None}


async def log_status_counts(conn) -> dict[str, int]:
    counts = {"received": 0, "extracted": 0, "reviewed": 0, "error": 0}
    for r in await conn.fetch("select status, count(*) n from maintenance_logs group by status"):
        counts[r["status"]] = r["n"]
    return counts


async def high_priority(conn) -> list[Any]:
    return await conn.fetch(
        "select r.id, r.priority, r.created_at, mr.log_id from recommendations r"
        " join maintenance_records mr on mr.id = r.record_id"
        f" where r.priority in ('P1','P2') and {_LATEST_PENDING} order by r.priority, r.id limit {LIMIT}")


async def unschedulable(conn) -> list[dict[str, Any]]:
    """Conflicts in the latest proposal that are still pending (a decided one is no longer actionable)."""
    row = await conn.fetchrow("select conflicts, created_at from schedule_proposals order by id desc limit 1")
    if row is None:
        return []
    conflicts = json.loads(row["conflicts"])
    if not conflicts:
        return []
    pending = {r["id"] for r in await conn.fetch(
        "select id from recommendations where id = any($1) and status = 'pending'",
        [c["recommendation_id"] for c in conflicts])}
    return [{**c, "at": row["created_at"]} for c in conflicts if c["recommendation_id"] in pending]


async def recent_decisions(conn, limit: int = 10, days: int | None = None) -> list[Any]:
    return await conn.fetch(
        "select a.action, a.final, a.created_at, mr.log_id, u.email from decision_audit a"
        " join maintenance_records mr on mr.id = a.record_id join users u on u.id = a.user_id"
        " where $2::int is null or a.created_at > now() - make_interval(days => $2)"
        " order by a.created_at desc, a.id desc limit $1", limit, days)


async def for_role(role: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    async with get_pool().acquire() as conn:
        if role == "engineer":
            for r in await conn.fetch(
                    "select id, filename, created_at from maintenance_logs where status = 'extracted'"
                    f" order by id desc limit {LIMIT}"):
                items.append(_item("pending_review", f"Log #{r['id']} awaits your review", r["id"], r["created_at"]))
            for r in await conn.fetch(
                    "select id, created_at from maintenance_logs l where exists"
                    " (select 1 from maintenance_logs o where o.sha256 = l.sha256 and o.id < l.id)"
                    f" order by id desc limit {LIMIT}"):
                items.append(_item("duplicate", f"Log #{r['id']} duplicates an earlier log", r["id"], r["created_at"]))
        else:  # manager and admin
            for r in await high_priority(conn):
                items.append(_item("high_priority", f"{r['priority']} recommendation pending on log #{r['log_id']}",
                                   r["log_id"], r["created_at"]))
            for c in await unschedulable(conn):
                items.append(_item("unschedulable", f"Log #{c['log_id']} cannot be scheduled ({c['reason']})",
                                   c["log_id"], c["at"]))
            for d in await recent_decisions(conn, LIMIT, DECISION_DAYS):
                items.append(_item("decision", f"{d['email']} {d['action']} log #{d['log_id']}", d["log_id"], d["created_at"]))
    return items
