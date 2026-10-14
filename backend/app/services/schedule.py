"""Gather pending recommendations + resources, run the pure scheduler, store the proposal (M.11)."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any
from app.db import get_pool
from app.engine.schedule import propose
from app.workflows.retrieval import _cur

# Used when a component has no row in component_defaults.
FALLBACK = {"skill": "general", "duration_min": 60, "parts": []}


def _out(r: Any) -> dict[str, Any]:
    return {"id": r["id"], "horizon_start": r["horizon_start"].isoformat(), "horizon_end": r["horizon_end"].isoformat(),
            "assignments": json.loads(r["assignments"]), "conflicts": json.loads(r["conflicts"]),
            "created_at": r["created_at"].isoformat()}


async def propose_schedule(user_id: int, days: int) -> dict[str, Any]:
    start = datetime.now().replace(second=0, microsecond=0)
    async with get_pool().acquire() as conn:
        recs = await conn.fetch(
            "select r.id, r.priority, mr.log_id, " + _cur("component") + " from recommendations r"
            " join maintenance_records mr on mr.id = r.record_id where r.status = 'pending'"
            " and r.id = (select max(r2.id) from recommendations r2 where r2.record_id = r.record_id)")
        defaults = {d["component"]: d for d in await conn.fetch("select * from component_defaults")}
        techs = await conn.fetch("select id, name, skills, availability::text from technicians")
        stock = {p["name"]: p["stock"] for p in await conn.fetch("select name, stock from parts")}
        items = []
        for r in recs:
            d = defaults.get((r["component"] or "").strip().lower())
            d = dict(d) if d else FALLBACK
            items.append({"id": r["id"], "priority": r["priority"], "log_id": r["log_id"], "skill": d["skill"],
                          "duration_min": d["duration_min"], "parts": list(d["parts"])})
        res = propose(items, [{**dict(t), "availability": json.loads(t["availability"])} for t in techs],
                      stock, (start, start + timedelta(days=days)))
        log_of = {i["id"]: i["log_id"] for i in items}
        for x in res["assignments"] + res["conflicts"]:
            x["log_id"] = log_of[x["recommendation_id"]]
        row = await conn.fetchrow(
            "insert into schedule_proposals (horizon_start, horizon_end, assignments, conflicts, created_by)"
            " values ($1,$2,$3,$4,$5) returning *", start, start + timedelta(days=days),
            json.dumps(res["assignments"]), json.dumps(res["conflicts"]), user_id)
    return _out(row)


async def latest() -> dict[str, Any] | None:
    async with get_pool().acquire() as conn:
        r = await conn.fetchrow("select * from schedule_proposals order by id desc limit 1")
    return _out(r) if r else None
