"""Log intake (M.2): validation, duplicates, status lifecycle. DB tests skip without DATABASE_URL."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth, logs

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "maintenance_logs.json").read_text())


def test_fixture_set():
    assert len(FIXTURES) >= 30 and len({f["id"] for f in FIXTURES}) == len(FIXTURES)
    cats = {f["category"] for f in FIXTURES}
    assert {"spec_example", "motor_overheating", "abbreviations", "negation",
            "missing_fields", "unrelated"} <= cats
    assert any("P-104" in f["text"] and "12 August" in f["text"] for f in FIXTURES)


def test_decode_utf8_then_latin1():
    assert logs.decode("naïve ✓".encode()) == "naïve ✓"
    assert logs.decode("café".encode("latin-1")) == "café"


@pytest.mark.parametrize("name,data,code", [
    ("log.pdf", b"x", 415),
    ("log.exe", b"x", 415),
    ("log.txt", b"   \n ", 400),
    ("log.txt", b"", 400),
    ("log.txt", b"a" * (logs.MAX_BYTES + 1), 413),
])
def test_validate_rejects(name, data, code):
    with pytest.raises(HTTPException) as e:
        logs.validate(name, data)
    assert e.value.status_code == code


def test_validate_accepts_allowed_types():
    for name in ("a.txt", "a.LOG", "a.csv", None):
        assert logs.validate(name, b"pump ok") == "pump ok"


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
class TestLogsApi:
    @pytest.fixture(autouse=True)
    def no_llm(self, monkeypatch):
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)  # tests never call the network
    @pytest.fixture(scope="class")
    def ctx(self):
        os.environ.setdefault("AUTH_SECRET", "test-secret")
        email = f"logs-{uuid.uuid4().hex[:8]}@test.local"

        async def db(sql, *args):
            conn = await asyncpg.connect(DSN)
            try:
                return await conn.fetchval(sql, *args)
            finally:
                await conn.close()

        uid = asyncio.run(db(
            "insert into users (email, password_hash, role) values ($1, 'x', 'engineer') returning id",
            email))
        headers = {"Authorization": f"Bearer {auth.make_token(uid, 'engineer')}"}
        with TestClient(app) as client:
            yield client, headers, db, uid
        asyncio.run(db("delete from maintenance_records where log_id in"
                       " (select id from maintenance_logs where submitted_by = $1)", uid))
        asyncio.run(db("delete from maintenance_logs where submitted_by = $1", uid))
        asyncio.run(db("delete from users where id = $1", uid))

    def test_http_rejections(self, ctx):
        client, h, *_ = ctx
        assert client.post("/api/logs", headers=h).status_code == 400
        assert client.post("/api/logs", headers=h, data={"text": "  "}).status_code == 400
        r = client.post("/api/logs", headers=h, files={"file": ("a.pdf", b"x")})
        assert r.status_code == 415 and "Unsupported" in r.json()["detail"]
        big = client.post("/api/logs", headers=h,
                          files={"file": ("a.txt", b"a" * (logs.MAX_BYTES + 10))})
        assert big.status_code == 413

    def test_duplicate_warns_and_force_overrides(self, ctx):
        client, h, *_ = ctx
        text = f"Pump P-104 vibration {uuid.uuid4()}"
        first = client.post("/api/logs", headers=h, data={"text": text})
        assert first.status_code == 201 and first.json()["status"] == "extracted"
        dup = client.post("/api/logs", headers=h, files={"file": ("x.log", text.encode())})
        assert dup.status_code == 409
        assert dup.json()["detail"]["existing_id"] == first.json()["id"]
        forced = client.post("/api/logs", headers=h, data={"text": text, "force": "true"})
        assert forced.status_code == 201 and forced.json()["id"] != first.json()["id"]

    def test_latin1_upload_and_list_detail(self, ctx):
        client, h, *_ = ctx
        body = f"Moteur surchauffé {uuid.uuid4()}".encode("latin-1")
        r = client.post("/api/logs", headers=h, files={"file": ("m.txt", body)})
        assert r.status_code == 201
        detail = client.get(f"/api/logs/{r.json()['id']}", headers=h).json()
        assert detail["original_text"].startswith("Moteur surchauffé")
        assert r.json()["id"] in [x["id"] for x in client.get("/api/logs", headers=h).json()]
        assert client.get("/api/logs/999999999", headers=h).status_code == 404

    def test_extraction_failure_keeps_original_with_error(self, ctx, monkeypatch):
        client, h, *_ = ctx

        async def boom(_conn, _text):
            raise RuntimeError("extractor exploded")

        monkeypatch.setattr(logs, "extract", boom)
        text = f"Seal leaking {uuid.uuid4()}"
        r = client.post("/api/logs", headers=h, data={"text": text})
        assert r.status_code == 201
        assert r.json()["status"] == "error" and r.json()["error"] == "extractor exploded"
        assert client.get(f"/api/logs/{r.json()['id']}", headers=h).json()["original_text"] == text

    def test_successful_extraction_sets_extracted(self, ctx, monkeypatch):
        client, h, *_ = ctx
        async def fake(_conn, _text):
            return {"ok": True}
        monkeypatch.setattr(logs, "extract", fake)
        r = client.post("/api/logs", headers=h, data={"text": f"Fan ok {uuid.uuid4()}"})
        assert r.json()["status"] == "extracted"


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
class TestReview:
    @pytest.fixture(autouse=True)
    def no_llm(self, offline):  # first review enters the pipeline: keep it off the network
        pass

    def test_review_persists_beside_extracted_and_denies_manager(self):
        os.environ.setdefault("AUTH_SECRET", "test-secret")
        async def db(sql, *args):
            conn = await asyncpg.connect(DSN)
            try:
                return await conn.fetchval(sql, *args)
            finally:
                await conn.close()
        uid = asyncio.run(db("insert into users (email, password_hash, role) values ($1, 'x',"
                             " 'engineer') returning id", f"rev-{uuid.uuid4().hex[:8]}@test.local"))
        eng = {"Authorization": f"Bearer {auth.make_token(uid, 'engineer')}"}
        mgr = {"Authorization": f"Bearer {auth.make_token(uid, 'manager')}"}
        text = f"Pump P-104 had excessive vibration, bearing replaced {uuid.uuid4()}"
        try:
            with TestClient(app) as c:
                try:
                    log = c.post("/api/logs", headers=eng, data={"text": text}).json()
                    before = c.get(f"/api/logs/{log['id']}", headers=eng).json()
                    url = f"/api/records/{log['id']}/review"
                    body = {"fields": {"equipment": "P-105", "outcome": "  "}}
                    assert c.put(url, json=body).status_code == 401
                    assert c.put(url, headers=mgr, json=body).status_code == 403
                    assert c.put(url, headers=eng, json={"fields": {"bogus": "x"}}).status_code == 422
                    assert c.put("/api/records/999999999/review", headers=eng, json=body).status_code == 404
                    r = c.put(url, headers=eng, json=body)
                    assert r.status_code == 200 and r.json()["status"] == "reviewed"
                    after = c.get(f"/api/logs/{log['id']}", headers=eng).json()
                    rec = after["record"]
                    assert rec["reviewed"] == {"equipment": {"value": "P-105"}, "outcome": {"value": None}}
                    assert rec["reviewed_by"] == uid and rec["reviewed_at"]
                    assert rec["extracted"] == before["record"]["extracted"]  # unchanged
                    assert rec["extracted"]["fields"]["equipment"]["value"] == "Pump P-104"
                    assert after["original_text"] == text == before["original_text"]
                finally:  # drop the projected record and rebuild: leave no graph state behind
                    asyncio.run(db("delete from source_records where system = 'maintenance_logs' and"
                                   " (raw_json->>'log_id')::int in"
                                   " (select id from maintenance_logs where submitted_by = $1)", uid))
                    c.post("/api/ingest", headers=eng, json={"systems": {}})
        finally:
            asyncio.run(db("delete from source_records where system = 'maintenance_logs' and"
                           " (raw_json->>'log_id')::int in"
                           " (select id from maintenance_logs where submitted_by = $1)", uid))
            asyncio.run(db("delete from maintenance_records where log_id in"
                           " (select id from maintenance_logs where submitted_by = $1)", uid))
            asyncio.run(db("delete from maintenance_logs where submitted_by = $1", uid))
            asyncio.run(db("delete from users where id = $1", uid))
