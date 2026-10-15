"""M.12 decisions + append-only audit (skips without DATABASE_URL)."""
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
    tag = uuid.uuid4().hex[:8]
    ids = {r: run("insert into users (email, password_hash, role) values ($1, 'x', $2) returning id",
                  f"dec-{r}-{tag}@test.local", r) for r in ("engineer", "manager")}
    lid = run("insert into maintenance_logs (sha256, original_text, status) values ('t', 'pump seal leak', 'reviewed') returning id")
    mid = run("insert into maintenance_records (log_id, extracted) values ($1, '{}') returning id", lid)
    recs = []
    def new_rec():
        recs.append(run("insert into recommendations (record_id, priority, explanation, method_version)"
                        " values ($1, 'P2', '[]', 't') returning id", mid))
        return recs[-1]
    h = {r: {"Authorization": f"Bearer {auth.make_token(i, r)}"} for r, i in ids.items()}
    yield {"ids": ids, "h": h, "lid": lid, "new": new_rec}
    async def cleanup():
        conn = await asyncpg.connect(DSN)
        try:  # the trigger blocks deletes by design; lift it only for test cleanup
            await conn.execute("alter table decision_audit disable trigger decision_audit_no_change")
            await conn.execute("delete from decision_audit where record_id = $1", mid)
            await conn.execute("alter table decision_audit enable trigger decision_audit_no_change")
            await conn.execute("delete from recommendations where record_id = $1", mid)
            await conn.execute("delete from maintenance_records where id = $1", mid)
            await conn.execute("delete from maintenance_logs where id = $1", lid)
            await conn.execute("delete from users where id = any($1)", list(ids.values()))
        finally:
            await conn.close()
    asyncio.run(cleanup())
def test_modify_keeps_original_and_final_and_engineer_denied(env):
    rid = env["new"]()
    url = f"/api/recommendations/{rid}/decision"
    with TestClient(app) as c:
        assert c.post(url, json={"action": "approve"}).status_code == 401
        assert c.post(url, headers=env["h"]["engineer"], json={"action": "approve"}).status_code == 403
        assert run("select status from recommendations where id = $1", rid) == "pending"
        assert c.post(url, headers=env["h"]["manager"], json={"action": "modify", "priority": "P1"}).status_code == 422  # no comment
        assert c.post(url, headers=env["h"]["manager"], json={"action": "modify", "priority": "P2", "comment": "x"}).status_code == 422
        r = c.post(url, headers=env["h"]["manager"], json={"action": "modify", "priority": "P1", "comment": "pump is critical"})
        assert r.status_code == 200
        assert c.post(url, headers=env["h"]["manager"], json={"action": "approve"}).status_code == 409  # decided once
        hist = c.get(f"/api/records/{env['lid']}/decisions", headers=env["h"]["engineer"]).json()
        assert len(hist) == 1 and hist[0]["original"] == {"priority": "P2", "status": "pending"}
        assert hist[0]["final"] == {"priority": "P1", "status": "modified"} and hist[0]["comment"] == "pump is critical"
        assert hist[0]["user_id"] == env["ids"]["manager"] and hist[0]["created_at"]
        assert c.get("/api/audit", headers=env["h"]["engineer"]).status_code == 403
        assert any(a["id"] == hist[0]["id"] for a in c.get("/api/audit", headers=env["h"]["manager"]).json())
    assert run("select status from recommendations where id = $1", rid) == "modified"
    assert run("select priority from recommendations where id = $1", rid) == "P2"  # original untouched
def test_audit_is_append_only(env):
    rid = env["new"]()
    with TestClient(app) as c:
        aid = c.post(f"/api/recommendations/{rid}/decision", headers=env["h"]["manager"], json={"action": "approve"}).json()["id"]
    for sql in ("update decision_audit set comment = 'x' where id = $1 returning 1",
                "delete from decision_audit where id = $1 returning 1"):
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            run(sql, aid)
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        run("truncate decision_audit")
def test_failed_decision_leaves_no_partial_rows(env):
    from app.db import close_pool, init_pool
    from app.services import decision
    rid = env["new"]()
    async def go():
        await init_pool()
        try:  # unknown user: status update runs first, the audit insert then fails the FK
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await decision.decide(rid, 2_000_000_000, "approve", None, None)
        finally:
            await close_pool()
    asyncio.run(go())
    assert run("select status from recommendations where id = $1", rid) == "pending"
    assert run("select count(*) from decision_audit where recommendation_id = $1", rid) == 0
