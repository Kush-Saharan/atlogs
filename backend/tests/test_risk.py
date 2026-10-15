"""M.9 risk baseline: pure arithmetic tests, plus one DB route test (skips without DATABASE_URL)."""
from __future__ import annotations
import asyncio
import json
import os
import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app.engine.risk import METHOD_VERSION, assess_risk
from app.main import app
from app.services import auth

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
FULL = {"history_count": 5, "recurrence_90d": 3, "recent_incidents_90d": 5,
        "criticality": "high", "similar_adverse_rate": 1.0}


def _contrib(r):
    return {f["name"]: f["contribution"] for f in r["factors"]}


def test_max_inputs_score_100_high():
    r = assess_risk(FULL)
    assert r["score"] == 100 and r["category"] == "high" and not r["insufficient_evidence"]
    assert r["method_version"] == METHOD_VERSION == "risk-v0-uncalibrated"


def test_each_factor_arithmetic():
    base = {"history_count": 5, "recurrence_90d": 0, "recent_incidents_90d": 0,
            "criticality": "low", "similar_adverse_rate": 0.0}
    assert assess_risk(base)["score"] == 0
    assert _contrib(assess_risk({**base, "recurrence_90d": 1}))["recurrence"] == 10   # 30 * 1/3
    assert _contrib(assess_risk({**base, "recurrence_90d": 9}))["recurrence"] == 30   # capped at 3
    assert _contrib(assess_risk({**base, "recent_incidents_90d": 2}))["recent_incidents"] == 8  # 20 * 2/5
    assert _contrib(assess_risk({**base, "criticality": "medium"}))["criticality"] == 12.5
    assert _contrib(assess_risk({**base, "similar_adverse_rate": 0.4}))["similar_adverse_rate"] == 10


def test_score_is_sum_of_factors_and_category_cutoffs():
    r = assess_risk({**FULL, "recurrence_90d": 1, "recent_incidents_90d": 2,
                     "criticality": "medium", "similar_adverse_rate": 0.4})
    assert r["score"] == sum(f["contribution"] for f in r["factors"]) == 10 + 8 + 12.5 + 10
    assert r["category"] == "medium"  # 40.5
    assert assess_risk({**FULL, "recurrence_90d": 0, "recent_incidents_90d": 0,
                        "criticality": "low", "similar_adverse_rate": 0.3})["category"] == "low"


def test_factors_report_inputs_and_weights():
    f = {x["name"]: x for x in assess_risk(FULL)["factors"]}
    assert set(f) == {"recurrence", "recent_incidents", "criticality", "similar_adverse_rate"}
    assert f["recurrence"]["input"] == 3 and f["recurrence"]["weight"] == 30
    assert f["criticality"]["input"] == "high" and f["criticality"]["normalised"] == 1.0


def test_missing_data_sets_insufficient_evidence():
    assert assess_risk({**FULL, "history_count": 2})["insufficient_evidence"]
    assert assess_risk({**FULL, "history_count": 3})["insufficient_evidence"] is False
    r = assess_risk({**FULL, "criticality": "unknown"})
    assert r["insufficient_evidence"] and "criticality unknown" in r["insufficient_reasons"][0]
    r = assess_risk({"history_count": 0})  # nothing known at all: no crash, zero score
    assert r["insufficient_evidence"] and r["score"] == 0 and len(r["insufficient_reasons"]) == 2


def test_missing_similar_rate_contributes_zero():
    r = assess_risk({**FULL, "similar_adverse_rate": None})
    f = {x["name"]: x for x in r["factors"]}["similar_adverse_rate"]
    assert f["normalised"] is None and f["contribution"] == 0 and r["score"] == 75


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
def test_route_stores_assessment_with_inputs():
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    async def run(sql, *args):
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()
    uid = asyncio.run(run("insert into users (email, password_hash, role) values ($1, 'x', 'engineer') returning id",
                          f"risk-{os.urandom(4).hex()}@test.local"))
    logs = []
    # three older motor-bearing logs on RK-1 (two inside 90 days) + the current one
    for day, comp in (("2025-08-01", "bearing"), ("2025-07-10", "bearing"), ("2025-01-01", "bearing"),
                      ("2025-08-20", "bearing")):
        lid = asyncio.run(run("insert into maintenance_logs (sha256, original_text, status) values"
                              " ('t', 'RK-1 bearing vibration', 'reviewed') returning id"))
        asyncio.run(run("insert into maintenance_records (log_id, extracted) values ($1, $2) returning id", lid,
                        json.dumps({"fields": {"equipment": {"value": "RK-1"}, "component": {"value": comp},
                                               "date": {"value": day}}})))
        logs.append(lid)
    hdr = {"Authorization": f"Bearer {auth.make_token(uid, 'engineer')}"}
    try:
        with TestClient(app) as c:
            assert c.post(f"/api/records/{logs[-1]}/risk").status_code == 401
            assert c.post("/api/records/999999999/risk", headers=hdr).status_code == 404
            r = c.post(f"/api/records/{logs[-1]}/risk", headers=hdr).json()
            assert r["features"]["history_count"] == 3 and r["features"]["recurrence_90d"] == 2
            assert r["features"]["criticality"] == "unknown" and r["insufficient_evidence"]
            assert set(r["input_refs"]["recurrence_log_ids"]) == set(logs[:2])
            assert c.get(f"/api/records/{logs[-1]}/risk", headers=hdr).json()["id"] == r["id"]
            assert c.get(f"/api/records/{logs[0]}/risk", headers=hdr).json() is None
    finally:
        asyncio.run(run("delete from risk_assessments where log_id = any($1) returning 1", logs))
        asyncio.run(run("delete from maintenance_records where log_id = any($1) returning 1", logs))
        asyncio.run(run("delete from maintenance_logs where id = any($1) returning 1", logs))
        asyncio.run(run("delete from users where id = $1 returning 1", uid))
