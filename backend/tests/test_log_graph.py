"""M.6: a reviewed log enters the pipeline once and links equipment/component/symptom/action.
DB tests skip without DATABASE_URL and run offline (embeddings disabled, no network)."""
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
from app.services import auth, logs
from app.services.pipeline import normalize_records
from app.engine.schema_discovery import discover_schema

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")

FIELDS = {"equipment": "P-104", "component": "motor bearing", "symptom": "excessive vibration",
          "action": "bearing replacement", "outcome": "resolved", "date": "2025-08-12"}


def _extracted(**vals):
    return {"fields": {k: {"value": v} for k, v in vals.items()}}


def test_projection_raw_reviewed_wins_and_falls_back():
    ex = _extracted(equipment="Pump P-104", component="bearing", symptom="noise")
    raw = logs.projection_raw(7, ex, {"equipment": {"value": "P-104"}, "symptom": {"value": None}})
    assert raw["asset_tag"] == "P-104" and raw["log_id"] == 7 and raw["record_id"] == "7"
    assert raw["component"] == "bearing"      # not reviewed: extracted value kept
    assert "symptom" not in raw               # reviewed as cleared: stays cleared
    assert raw["_event_kind"] == "failure" and raw["_ext"]["is_anomaly"] is False
    raw = logs.projection_raw(7, ex, {"action": {"value": "replaced"}})
    assert raw["_event_kind"] == "work_order" and raw["_ext"]["observation"] == "noise"


def test_equipment_is_an_asset_tag_not_a_serial_number():
    raws = [logs.projection_raw(1, _extracted(), {k: {"value": v} for k, v in FIELDS.items()})]
    (rec,) = normalize_records("maintenance_logs", raws, discover_schema(raws))
    assert rec.identifiers == {"asset_tag": ["P-104"]}


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
class TestLogGraph:
    @pytest.fixture
    def ctx(self, offline):
        os.environ.setdefault("AUTH_SECRET", "test-secret")

        async def db(sql, *args, fetch=False):
            conn = await asyncpg.connect(DSN)
            try:
                return await (conn.fetch(sql, *args) if fetch else conn.fetchval(sql, *args))
            finally:
                await conn.close()

        uid = asyncio.run(db("insert into users (email, password_hash, role) values ($1, 'x',"
                             " 'engineer') returning id", f"graph-{uuid.uuid4().hex[:8]}@test.local"))
        h = {"Authorization": f"Bearer {auth.make_token(uid, 'engineer')}"}
        for rid, tag in (("a", "P-104"), ("b", "P-105")):  # an existing registry
            asyncio.run(db(
                "insert into source_records (system, record_id, raw_json) values"
                " ('testreg', $1, $2::jsonb) on conflict do nothing", f"testreg:{rid}",
                json.dumps({"record_id": rid, "asset_tag": tag, "asset_name": f"Pump {tag}"})))
        with TestClient(app) as client:
            yield client, h, db
            asyncio.run(db("delete from source_records where system in ('testreg', 'maintenance_logs')"))
            client.post("/api/ingest", headers=h, json={"systems": {}})  # rebuild derived state
        asyncio.run(db("delete from maintenance_records where log_id in"
                       " (select id from maintenance_logs where submitted_by = $1)", uid))
        asyncio.run(db("delete from maintenance_logs where submitted_by = $1", uid))
        asyncio.run(db("delete from users where id = $1", uid))

    def _approve(self, client, h, fields):
        log = client.post("/api/logs", headers=h, data={"text": f"Pump log {uuid.uuid4()}"}).json()
        r = client.put(f"/api/records/{log['id']}/review", headers=h, json={"fields": fields})
        assert r.status_code == 200, r.text
        return log["id"]

    def _edges(self, db, log_id):
        rows = asyncio.run(db("select source_id, relation_type, target_id, metadata from edges"
                              " where metadata->>'citation' = $1", f"maintenance_logs:{log_id}",
                              fetch=True))
        return {(r["source_id"], r["relation_type"], r["target_id"]): json.loads(r["metadata"])
                for r in rows}

    def test_edges_created_and_existing_asset_reused_offline(self, ctx):
        client, h, db = ctx
        log_id = self._approve(client, h, FIELDS)
        asset = asyncio.run(db("select unified_id from asset_identifiers where concept = 'asset_tag'"
                               " and lower(value) = 'p-104'"))
        assert asyncio.run(db("select count(*) from asset_identifiers where lower(value) = 'p-104'")) == 1
        assert asyncio.run(db("select count(*) from unified_assets")) == 2  # no third asset
        # the log joined the existing registry asset
        assert asyncio.run(db(
            "select count(*) from asset_source_records a join source_records s on s.id = a.source_record_id"
            " where a.unified_id = $1 and s.record_id in ('testreg:a', $2)", asset,
            f"maintenance_logs:{log_id}")) == 2
        comp = f"comp:{asset}:motor bearing"
        edges = self._edges(db, log_id)
        assert {k for k in edges if k[1] != "HAS_WORK_ORDER"} == {
            (f"asset:{asset}", "HAS_COMPONENT", comp),
            (comp, "EXHIBITED", "sym:excessive vibration"),
            ("sym:excessive vibration", "ADDRESSED_BY", "act:bearing replacement"),
        }
        assert any(k[0] == f"asset:{asset}" and k[1] == "HAS_WORK_ORDER" for k in edges)

    def test_first_approval_only_then_corrections_read_from_reviewed(self, ctx):
        client, h, db = ctx
        log_id = self._approve(client, h, FIELDS)
        count = "select count(*) from source_records where system = 'maintenance_logs'"
        raw_sql = "select raw_json::text from source_records where record_id = $1"
        before = asyncio.run(db(raw_sql, f"maintenance_logs:{log_id}"))
        assert asyncio.run(db(count)) == 1
        # correction: no new row, raw_json untouched
        r = client.put(f"/api/records/{log_id}/review", headers=h,
                       json={"fields": {**FIELDS, "component": "seal"}})
        assert r.status_code == 200
        assert asyncio.run(db(count)) == 1
        assert asyncio.run(db(raw_sql, f"maintenance_logs:{log_id}")) == before
        # the next rebuild (here: another log's first approval) reads the correction
        self._approve(client, h, {**FIELDS, "equipment": "P-105"})
        asset = asyncio.run(db("select unified_id from asset_identifiers where lower(value) = 'p-104'"))
        edges = self._edges(db, log_id)
        assert (f"asset:{asset}", "HAS_COMPONENT", f"comp:{asset}:seal") in edges
        assert not any("motor bearing" in k[2] for k in edges)

    def test_missing_links_are_skipped(self, ctx):
        client, h, db = ctx
        log_id = self._approve(client, h, {"equipment": "P-104", "symptom": "noise"})
        asset = asyncio.run(db("select unified_id from asset_identifiers where lower(value) = 'p-104'"))
        edges = self._edges(db, log_id)
        assert (f"asset:{asset}", "EXHIBITED", "sym:noise") in edges
        assert not any(k[1] in ("HAS_COMPONENT", "ADDRESSED_BY") for k in edges)
