"""M.13 per-role notifications + dashboard counts (skips without DATABASE_URL)."""
from __future__ import annotations
import asyncio
import json
import os
import uuid
import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app.main import app
from app.services import auth
load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")


def run(sql, *args):
    async def go():
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()
    return asyncio.run(go())


@pytest.fixture
def env():
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    tag = uuid.uuid4().hex
    ids = {r: run("insert into users (email, password_hash, role) values ($1, 'x', $2) returning id",
                  f"ntf-{r}-{tag[:8]}@test.local", r) for r in ("engineer", "manager")}
    ins = "insert into maintenance_logs (sha256, original_text, status) values ($1, 'x', $2) returning id"
    extracted = run(ins, tag, "extracted")
    first = run(ins, tag + "d", "reviewed")
    dup = run(ins, tag + "d", "reviewed")  # same hash as `first`, later id
    rec_ids = {}
    for name, lid in (("p1", extracted), ("p3", first)):
        mid = run("insert into maintenance_records (log_id, extracted) values ($1, '{}') returning id", lid)
        pr = "P1" if name == "p1" else "P3"
        rec_ids[name] = (mid, run("insert into recommendations (record_id, priority, explanation, method_version)"
                                  " values ($1, $2, '[]', 't') returning id", mid, pr))
    # newest proposal: one pending conflict (p1) and one already-decided conflict (p3)
    run("update recommendations set status = 'approved' where id = $1", rec_ids["p3"][1])
    conflicts = [{"recommendation_id": rec_ids["p1"][1], "log_id": extracted, "reason": "skill", "priority": "P1"},
                 {"recommendation_id": rec_ids["p3"][1], "log_id": first, "reason": "part", "priority": "P3"}]
    prop = run("insert into schedule_proposals (horizon_start, horizon_end, assignments, conflicts)"
               " values (now(), now(), '[]', $1) returning id", json.dumps(conflicts))
    h = {r: {"Authorization": f"Bearer {auth.make_token(i, r)}"} for r, i in ids.items()}
    yield {"h": h, "extracted": extracted, "first": first, "dup": dup, "rec": rec_ids, "ids": ids}

    async def cleanup():
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("delete from schedule_proposals where id = $1", prop)
            mids = [m for m, _ in rec_ids.values()]
            await conn.execute("delete from recommendations where record_id = any($1)", mids)
            await conn.execute("delete from maintenance_records where id = any($1)", mids)
            await conn.execute("delete from maintenance_logs where id = any($1)", [extracted, first, dup])
            await conn.execute("delete from users where id = any($1)", list(ids.values()))
        finally:
            await conn.close()
    asyncio.run(cleanup())


def test_engineer_sees_reviews_and_duplicates_only(env):
    with TestClient(app) as c:
        items = c.get("/api/notifications", headers=env["h"]["engineer"]).json()["items"]
    pairs = {(i["kind"], i["log_id"]) for i in items}
    assert ("pending_review", env["extracted"]) in pairs
    assert ("duplicate", env["dup"]) in pairs
    assert ("duplicate", env["first"]) not in pairs  # only the later copy is warned about
    assert {i["kind"] for i in items} <= {"pending_review", "duplicate"}


def test_manager_sees_priority_unschedulable_decisions_only(env):
    with TestClient(app) as c:
        items = c.get("/api/notifications", headers=env["h"]["manager"]).json()["items"]
        pairs = {(i["kind"], i["log_id"]) for i in items}
        assert ("high_priority", env["extracted"]) in pairs      # P1 pending
        assert ("high_priority", env["first"]) not in pairs      # P3, and already approved
        assert ("unschedulable", env["extracted"]) in pairs      # pending conflict
        assert ("unschedulable", env["first"]) not in pairs      # decided conflict is not actionable
        assert not any(k == "pending_review" for k, _ in pairs)
        assert not any(k == "duplicate" for k, _ in pairs)
        # a decision shows up as a new decision notification
        rid = env["rec"]["p1"][1]
        assert c.post(f"/api/recommendations/{rid}/decision", headers=env["h"]["manager"],
                      json={"action": "approve"}).status_code == 200
        items = c.get("/api/notifications", headers=env["h"]["manager"]).json()["items"]
        assert ("decision", env["extracted"]) in {(i["kind"], i["log_id"]) for i in items}
        assert ("high_priority", env["extracted"]) not in {(i["kind"], i["log_id"]) for i in items}
    _purge_audit(env)


def _purge_audit(env):
    async def go():
        conn = await asyncpg.connect(DSN)
        try:  # the trigger blocks deletes by design; lift it only for test cleanup
            await conn.execute("alter table decision_audit disable trigger decision_audit_no_change")
            await conn.execute("delete from decision_audit where recommendation_id = any($1)",
                               [r for _, r in env["rec"].values()])
            await conn.execute("alter table decision_audit enable trigger decision_audit_no_change")
        finally:
            await conn.close()
    asyncio.run(go())


def test_overview_has_dashboard_counts_and_auth(env):
    with TestClient(app) as c:
        assert c.get("/api/notifications").status_code == 401
        o = c.get("/api/overview", headers=env["h"]["engineer"]).json()
    assert o["log_status"]["extracted"] >= 1 and o["pending_review"] == o["log_status"]["extracted"]
    assert o["high_priority"] >= 1 and o["conflicts"] >= 1
    assert isinstance(o["recent_decisions"], list)
