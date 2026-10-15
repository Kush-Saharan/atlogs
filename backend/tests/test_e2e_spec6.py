"""M.14 end-to-end walk of spec §6 (P-104 bearing vibration), offline, against a LOCAL database.
Skips without DATABASE_URL or when it does not point at localhost/127.0.0.1 (it rebuilds derived state)."""
from __future__ import annotations
import asyncio
import json
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
LOCAL = bool(DSN) and urlparse(DSN).hostname in ("localhost", "127.0.0.1")
pytestmark = pytest.mark.skipif(not LOCAL, reason="needs a local DATABASE_URL (localhost/127.0.0.1)")

PAST = "Pump P-104 had excessive vibration at the motor bearing. The bearing was replaced and the pump was tested."
NEW = ("Pump P-104 experienced excessive vibration around the motor bearing. "
       "The bearing was replaced and the pump was tested.")


def test_spec6_p104_end_to_end(offline):
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    tag = uuid.uuid4().hex[:8]

    def db(sql, *args, fetch=False):
        async def go():
            conn = await asyncpg.connect(DSN)
            try:
                return await (conn.fetch(sql, *args) if fetch else conn.fetchval(sql, *args))
            finally:
                await conn.close()
        return asyncio.run(go())

    ids = {r: db("insert into users (email, password_hash, role) values ($1, 'x', $2) returning id",
                 f"e2e-{r}-{tag}@test.local", r) for r in ("engineer", "manager")}
    h = {r: {"Authorization": f"Bearer {auth.make_token(i, r)}"} for r, i in ids.items()}
    tid = db("insert into technicians (name, skills, availability) values ($1, $2, $3::jsonb) returning id",
             f"e2e-tech-{tag}", ["general", "mechanical"],
             json.dumps([{"start": "2000-01-01T00:00", "end": "2100-01-01T00:00"}]))
    logs = []
    try:
        with TestClient(app) as c:
            # Stage 1 upload: original text preserved, status extracted
            def upload(text):
                r = c.post("/api/logs", headers=h["engineer"], data={"text": text, "force": "true"})
                assert r.status_code == 201, r.text
                logs.append(r.json()["id"])
                return r.json()["id"]

            def review(lid, fields):
                r = c.put(f"/api/records/{lid}/review", headers=h["engineer"], json={"fields": fields})
                assert r.status_code == 200, r.text

            fields = {"equipment": "P-104", "component": "motor bearing", "symptom": "excessive vibration",
                      "action": "bearing replacement", "outcome": "tested", "date": "2025-08-12"}
            past = upload(PAST)
            review(past, fields)
            lid = upload(NEW)
            log = c.get(f"/api/logs/{lid}", headers=h["engineer"]).json()
            assert log["original_text"] == NEW and log["status"] == "extracted"

            # Stage 2 extraction: values with spans from the original text
            ext = log["record"]["extracted"]["fields"]
            assert ext["equipment"]["value"].endswith("P-104") and ext["symptom"]["value"] == "excessive vibration"
            assert NEW[slice(*ext["symptom"]["span"])] == "excessive vibration"

            # Stage 3 review: correction stored beside extracted, which stays unchanged
            review(lid, fields)
            rec = c.get(f"/api/logs/{lid}", headers=h["engineer"]).json()
            assert rec["status"] == "reviewed" and rec["record"]["reviewed"]["equipment"]["value"] == "P-104"
            assert rec["record"]["extracted"]["fields"] == ext and rec["original_text"] == NEW

            # Stage 4 graph: component/symptom/action linked to the P-104 asset
            edges = {(r["source_id"], r["relation_type"], r["target_id"]) for r in db(
                "select source_id, relation_type, target_id from edges where metadata->>'citation' = $1",
                f"maintenance_logs:{lid}", fetch=True)}
            (asset_node,) = {s for s, rel, _ in edges if rel == "HAS_COMPONENT"}
            assert asset_node.startswith("asset:")
            comp = f"comp:{asset_node[6:]}:motor bearing"
            assert {(asset_node, "HAS_COMPONENT", comp), (comp, "EXHIBITED", "sym:excessive vibration")} <= edges
            # shared symptom->action edge is deduplicated, so it may carry the earlier log's citation
            assert db("select count(*) from edges where source_id = 'sym:excessive vibration' and relation_type ="
                      " 'ADDRESSED_BY' and target_id = 'act:bearing replacement'") >= 1
            # Stage 5 similar cases: the earlier P-104 case is found, this log excluded
            sim = c.get(f"/api/records/{lid}/similar", headers=h["engineer"]).json()
            found = [m["log_id"] for m in sim["matches"]]
            assert past in found and lid not in found

            # Stage 6 risk: uncalibrated, with factors; thin history is stated, not hidden
            risk = c.post(f"/api/records/{lid}/risk", headers=h["engineer"]).json()
            assert risk["method_version"].endswith("uncalibrated") and risk["factors"]
            assert risk["insufficient_evidence"] is True

            # Stage 7 priority: pending P1-P4 with an explanation
            pri = c.post(f"/api/records/{lid}/priority", headers=h["engineer"]).json()
            assert pri["priority"] in ("P1", "P2", "P3", "P4") and pri["status"] == "pending" and pri["explanation"]

            # Stage 8 schedule: manager only; our recommendation is assigned to our technician
            assert c.post("/api/schedule/propose", headers=h["engineer"]).status_code == 403
            sched = c.post("/api/schedule/propose", headers=h["manager"]).json()
            mine = [a for a in sched["assignments"] if a["recommendation_id"] == pri["id"]]
            assert mine and mine[0]["technician_id"] == tid

            # Stage 9 decision + audit: original and final kept, append-only
            assert c.post(f"/api/recommendations/{pri['id']}/decision", headers=h["engineer"],
                          json={"action": "approve"}).status_code == 403
            other = "P1" if pri["priority"] != "P1" else "P2"
            d = c.post(f"/api/recommendations/{pri['id']}/decision", headers=h["manager"],
                       json={"action": "modify", "priority": other, "comment": "critical pump"})
            assert d.status_code == 200, d.text
            hist = c.get(f"/api/records/{lid}/decisions", headers=h["engineer"]).json()
            assert len(hist) == 1 and hist[0]["original"]["priority"] == pri["priority"]
            assert hist[0]["final"]["priority"] == other and hist[0]["user_id"] == ids["manager"]
            assert hist[0]["comment"] == "critical pump" and hist[0]["created_at"]
            assert any(a["id"] == hist[0]["id"] for a in c.get("/api/audit", headers=h["manager"]).json())
            with pytest.raises(asyncpg.PostgresError, match="append-only"):
                db("update decision_audit set comment = 'x' where id = $1 returning 1", hist[0]["id"])
    finally:
        def cleanup():
            db("alter table decision_audit disable trigger decision_audit_no_change")
            try:
                db("delete from decision_audit where record_id in (select id from maintenance_records where log_id = any($1))", logs)
            finally:
                db("alter table decision_audit enable trigger decision_audit_no_change")
            db("delete from schedule_proposals where created_by = any($1) returning 1", list(ids.values()))
            db("delete from recommendations where record_id in (select id from maintenance_records where log_id = any($1)) returning 1", logs)
            db("delete from risk_assessments where log_id = any($1) returning 1", logs)
            db("delete from source_records where record_id = any($1) returning 1", [f"maintenance_logs:{i}" for i in logs])
            with TestClient(app) as c2:  # rebuild derived state without our rows
                c2.post("/api/ingest", headers=h["engineer"], json={"systems": {}})
            db("delete from technicians where id = $1 returning 1", tid)
            db("delete from maintenance_records where log_id = any($1) returning 1", logs)
            db("delete from maintenance_logs where id = any($1) returning 1", logs)
            db("delete from users where id = any($1) returning 1", list(ids.values()))
        cleanup()
