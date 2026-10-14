"""M.11 greedy scheduler: pure tests, plus one DB route test (skips without DATABASE_URL)."""
from __future__ import annotations
import asyncio
import copy
import json
import os
import uuid
import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app.engine.schedule import propose
from app.main import app
from app.services import auth
load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
H = ("2025-08-12T00:00", "2025-08-13T00:00")
DAY = [{"start": "2025-08-12T08:00", "end": "2025-08-12T16:00"}]


def _tech(i, skills=("mechanical",), avail=DAY):
    return {"id": i, "name": f"t{i}", "skills": list(skills), "availability": list(avail)}


def _rec(i, pri="P2", skill="mechanical", mins=120, parts=()):
    return {"id": i, "priority": pri, "skill": skill, "duration_min": mins, "parts": list(parts)}


def test_no_double_booking_and_priority_order():
    out = propose([_rec(1, "P3"), _rec(2, "P1"), _rec(3, "P2")], [_tech(1)], {}, H)
    a = sorted(out["assignments"], key=lambda x: x["start"])
    assert [x["recommendation_id"] for x in a] == [2, 3, 1]  # P1, P2, P3 back to back
    assert all(a[i]["end"] <= a[i + 1]["start"] for i in range(len(a) - 1))
    assert a[0]["start"] == "2025-08-12T08:00:00" and out["conflicts"] == []


def test_second_technician_takes_parallel_work():
    out = propose([_rec(1), _rec(2)], [_tech(1), _tech(2)], {}, H)
    assert {x["start"] for x in out["assignments"]} == {"2025-08-12T08:00:00"}
    assert {x["technician_id"] for x in out["assignments"]} == {1, 2}


def test_skill_is_enforced():
    out = propose([_rec(1, skill="electrical")], [_tech(1)], {}, H)
    assert out["assignments"] == [] and out["conflicts"][0]["reason"] == "skill"
    out = propose([_rec(1, skill="electrical")], [_tech(1), _tech(2, ("electrical",))], {}, H)
    assert out["assignments"][0]["technician_id"] == 2


def test_missing_part_is_a_part_conflict_and_stock_is_used_up():
    out = propose([_rec(1, parts=["bearing"]), _rec(2, "P3", parts=["bearing"])], [_tech(1)], {"bearing": 1}, H)
    assert [x["recommendation_id"] for x in out["assignments"]] == [1]
    assert out["conflicts"][0]["recommendation_id"] == 2 and out["conflicts"][0]["reason"] == "part"
    assert propose([_rec(1, parts=["seal"])], [_tech(1)], {}, H)["conflicts"][0]["reason"] == "part"


def test_infeasible_item_is_reported_as_availability():
    out = propose([_rec(1, mins=600)], [_tech(1)], {}, H)  # 10 h job in an 8 h window
    assert out["conflicts"][0]["reason"] == "availability"
    out = propose([_rec(1)], [_tech(1, avail=[])], {}, H)
    assert out["conflicts"][0]["reason"] == "availability"
    # window outside the horizon is unusable
    out = propose([_rec(1)], [_tech(1, avail=[{"start": "2025-09-01T08:00", "end": "2025-09-01T16:00"}])], {}, H)
    assert out["conflicts"][0]["reason"] == "availability"


def test_priority_unchanged_for_conflicts_and_inputs_not_mutated():
    recs, techs, parts = [_rec(1, "P1", skill="welding"), _rec(2, "P2")], [_tech(1)], {"x": 1}
    before = copy.deepcopy((recs, techs, parts))
    out = propose(recs, techs, parts, H)
    assert out["conflicts"][0]["priority"] == "P1"
    assert (recs, techs, parts) == before


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
def test_routes_permissions_defaults_and_proposal():
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    tag = uuid.uuid4().hex[:8]
    async def run(sql, *args):
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()
    ids = {r: asyncio.run(run("insert into users (email, password_hash, role) values ($1, 'x', $2) returning id",
                              f"sch-{r}-{tag}@test.local", r)) for r in ("engineer", "manager")}
    h = {r: {"Authorization": f"Bearer {auth.make_token(i, r)}"} for r, i in ids.items()}
    lid = asyncio.run(run("insert into maintenance_logs (sha256, original_text, status) values"
                          " ('t', 'pump-zz seal leak', 'reviewed') returning id"))
    mid = asyncio.run(run("insert into maintenance_records (log_id, extracted) values ($1, $2) returning id", lid,
                          json.dumps({"fields": {"component": {"value": f"comp{tag}"}}})))
    rid = asyncio.run(run("insert into recommendations (record_id, priority, explanation, method_version)"
                          " values ($1, 'P1', '[]', 't') returning id", mid))
    tid = asyncio.run(run("insert into technicians (name, skills, availability) values ($1, $2, $3::jsonb) returning id",
                          f"tech{tag}", [f"skill{tag}"], json.dumps([{"start": "2000-01-01T00:00", "end": "2100-01-01T00:00"}])))
    try:
        with TestClient(app) as c:
            for m, u in (("get", "/api/schedule/defaults"), ("post", "/api/schedule/propose"), ("get", "/api/schedule/proposal")):
                assert getattr(c, m)(u).status_code == 401
                assert getattr(c, m)(u, headers=h["engineer"]).status_code == 403
            body = {"skill": f"Skill{tag}", "duration_min": 30, "parts": []}
            assert c.put(f"/api/schedule/defaults/Comp{tag}", headers=h["manager"], json=body).json()["skill"] == f"skill{tag}"
            assert c.put(f"/api/schedule/defaults/comp{tag}", headers=h["manager"], json={**body, "duration_min": 0}).status_code == 422
            p = c.post("/api/schedule/propose", headers=h["manager"]).json()
            mine = [a for a in p["assignments"] if a["recommendation_id"] == rid]
            assert mine and mine[0]["technician_id"] == tid and mine[0]["log_id"] == lid
            assert c.get("/api/schedule/proposal", headers=h["manager"]).json()["id"] == p["id"]
            assert c.delete(f"/api/schedule/defaults/comp{tag}", headers=h["manager"]).status_code == 200
            assert c.delete(f"/api/schedule/defaults/comp{tag}", headers=h["manager"]).status_code == 404
    finally:
        asyncio.run(run("delete from schedule_proposals where created_by = any($1) returning 1", list(ids.values())))
        asyncio.run(run("delete from component_defaults where component = $1 returning 1", f"comp{tag}"))
        asyncio.run(run("delete from technicians where id = $1 returning 1", tid))
        asyncio.run(run("delete from recommendations where id = $1 returning 1", rid))
        asyncio.run(run("delete from maintenance_records where id = $1 returning 1", mid))
        asyncio.run(run("delete from maintenance_logs where id = $1 returning 1", lid))
        asyncio.run(run("delete from users where id = any($1) returning 1", list(ids.values())))
