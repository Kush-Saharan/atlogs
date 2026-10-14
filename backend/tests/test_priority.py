"""M.10 priority policy: pure per-factor tests, plus one DB route test (skips without DATABASE_URL)."""
from __future__ import annotations
import asyncio
import json
import os
import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app.engine.priority import recommend_priority
from app.main import app
from app.services import auth
load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
BASE = {"risk_category": "low", "text": "bearing noise", "criticality": "low", "recurrence_90d": 0}
def _p(**kw):
    return recommend_priority(**{**BASE, **kw})
def test_baseline_is_p4_with_four_explained_factors():
    r = _p()
    assert r["priority"] == "P4" and r["points"] == 0
    assert [e["factor"] for e in r["explanation"]] == ["risk", "urgency", "criticality", "recurrence"]
def test_risk_category_raises_priority():
    assert [_p(risk_category=c)["priority"] for c in ("low", "medium", "high")] == ["P4", "P3", "P3"]
    assert _p(risk_category="high", criticality="high")["priority"] == "P2"
def test_criticality_raises_priority():
    assert _p(criticality="medium")["points"] == 1 and _p(criticality="high")["points"] == 2
    assert _p(criticality="unknown")["points"] == 0
def test_recurrence_raises_priority():
    assert [_p(recurrence_90d=n)["points"] for n in (0, 1, 2, 9)] == [0, 1, 2, 2]
def test_urgency_words_raise_priority_once():
    for t in ("URGENT repair", "stop immediately", "plant shutdown required"):
        assert _p(text=t)["points"] == 3, t
    assert _p(text="urgent, urgent, immediately")["points"] == 3
def test_negated_urgency_does_not_raise_priority():
    for t in ("Not urgent, schedule later", "no shutdown needed", "this is not urgent"):
        r = _p(text=t)
        assert r["points"] == 0 and r["priority"] == "P4", t
        assert "negated urgency ignored" in r["explanation"][1]["reason"]
    # a negator across a clause break does not carry over
    assert _p(text="not sure, urgent")["points"] == 3
def test_factors_combine_to_p1():
    r = _p(risk_category="high", text="urgent", criticality="high", recurrence_90d=3)
    assert r["points"] == 11 and r["priority"] == "P1"
    assert sum(e["points"] for e in r["explanation"]) == r["points"]
@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
def test_route_stores_pending_recommendation_with_explanation():
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    async def run(sql, *args):
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()
    uid = asyncio.run(run("insert into users (email, password_hash, role) values ($1, 'x', 'engineer') returning id",
                          f"prio-{os.urandom(4).hex()}@test.local"))
    lid = asyncio.run(run("insert into maintenance_logs (sha256, original_text, status) values"
                          " ('t', 'RK-1 bearing vibration, urgent', 'reviewed') returning id"))
    asyncio.run(run("insert into maintenance_records (log_id, extracted) values ($1, $2) returning id", lid,
                    json.dumps({"fields": {"equipment": {"value": "RK-1"}, "component": {"value": "bearing"},
                                           "date": {"value": "2025-08-20"}}})))
    hdr = {"Authorization": f"Bearer {auth.make_token(uid, 'engineer')}"}
    try:
        with TestClient(app) as c:
            assert c.post(f"/api/records/{lid}/priority").status_code == 401
            assert c.post("/api/records/999999999/priority", headers=hdr).status_code == 404
            assert c.get(f"/api/records/{lid}/priority", headers=hdr).json() is None
            r = c.post(f"/api/records/{lid}/priority", headers=hdr).json()
            assert r["status"] == "pending" and r["priority"] in ("P3", "P4") and r["risk_id"]
            assert {e["factor"]: e["points"] for e in r["explanation"]}["urgency"] == 3
            assert c.get(f"/api/records/{lid}/priority", headers=hdr).json()["id"] == r["id"]
    finally:
        asyncio.run(run("delete from recommendations where record_id in (select id from maintenance_records"
                        " where log_id = $1) returning 1", lid))
        asyncio.run(run("delete from risk_assessments where log_id = $1 returning 1", lid))
        asyncio.run(run("delete from maintenance_records where log_id = $1 returning 1", lid))
        asyncio.run(run("delete from maintenance_logs where id = $1 returning 1", lid))
        asyncio.run(run("delete from users where id = $1 returning 1", uid))
