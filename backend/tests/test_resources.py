"""Resources (M.8): criticality survives re-ingest, technician/part CRUD, permissions.
DB tests skip without DATABASE_URL."""
from __future__ import annotations
import asyncio
import os
import uuid
import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from app.engine.resolution.models import Cluster, MergeDecision, ResolutionResult
from app.main import app
from app.services import auth
from app.services.persistence import rebuild_projection
load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
def _run(fn):
    async def go():
        conn = await asyncpg.connect(DSN)
        try:
            return await fn(conn)
        finally:
            await conn.close()
    return asyncio.run(go())
@pytest.fixture(scope="module")
def ctx():
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    ids = {}
    async def mk(conn):
        for role in ("engineer", "manager", "admin"):
            ids[role] = await conn.fetchval(
                "insert into users (email, password_hash, role) values ($1, 'x', $2) returning id",
                f"res-{role}-{uuid.uuid4().hex[:8]}@test.local", role)
    _run(mk)
    hdr = {r: {"Authorization": f"Bearer {auth.make_token(i, r)}"} for r, i in ids.items()}
    with TestClient(app) as c:
        yield c, hdr
    async def rm(conn):
        await conn.execute("delete from users where id = any($1)", list(ids.values()))
    _run(rm)
def test_permissions(ctx):
    c, h = ctx
    for method, url in [("get", "/api/resources/technicians"), ("get", "/api/resources/parts")]:
        assert getattr(c, method)(url).status_code == 401
        assert getattr(c, method)(url, headers=h["engineer"]).status_code == 403
        assert getattr(c, method)(url, headers=h["manager"]).status_code == 200
    assert c.post("/api/resources/parts", headers=h["engineer"],
                  json={"name": "x", "stock": 1}).status_code == 403
    assert c.put("/api/assets/ua-0001/criticality", headers=h["engineer"],
                 json={"level": "high"}).status_code == 403
def test_parts_crud(ctx):
    c, h = ctx
    name = f"seal-{uuid.uuid4().hex[:6]}"
    r = c.post("/api/resources/parts", headers=h["manager"], json={"name": name, "stock": 3})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert c.post("/api/resources/parts", headers=h["admin"],
                  json={"name": name, "stock": 1}).status_code == 409
    assert c.post("/api/resources/parts", headers=h["admin"],
                  json={"name": "neg", "stock": -1}).status_code == 422
    assert c.put(f"/api/resources/parts/{pid}", headers=h["manager"],
                 json={"name": name, "stock": 7}).json()["stock"] == 7
    assert c.delete(f"/api/resources/parts/{pid}", headers=h["manager"]).status_code == 200
    assert c.delete(f"/api/resources/parts/{pid}", headers=h["manager"]).status_code == 404
def test_technicians_crud(ctx):
    c, h = ctx
    name = f"tech-{uuid.uuid4().hex[:6]}"
    body = {"name": name, "skills": [" Bearing ", "bearing", "Motor"],
            "availability": [{"start": "2025-08-12T08:00", "end": "2025-08-12T16:00"}]}
    r = c.post("/api/resources/technicians", headers=h["manager"], json=body)
    assert r.status_code == 201 and r.json()["skills"] == ["bearing", "motor"]
    tid = r.json()["id"]
    bad = {**body, "name": name + "b", "availability": [{"start": "2025-08-12T16:00", "end": "2025-08-12T08:00"}]}
    assert c.post("/api/resources/technicians", headers=h["manager"], json=bad).status_code == 422
    upd = c.put(f"/api/resources/technicians/{tid}", headers=h["manager"],
                json={**body, "skills": ["pump"]})
    assert upd.json()["skills"] == ["pump"] and upd.json()["availability"] == body["availability"]
    assert tid in [t["id"] for t in c.get("/api/resources/technicians", headers=h["admin"]).json()]
    assert c.delete(f"/api/resources/technicians/{tid}", headers=h["manager"]).status_code == 200
    assert c.put(f"/api/resources/technicians/{tid}", headers=h["manager"], json=body).status_code == 404
def test_criticality_survives_reingest(ctx):
    c, h = ctx
    if _run(lambda conn: conn.fetchval("select count(*) from unified_assets")):
        pytest.skip("unified_assets is not empty; not wiping a populated database")
    serial = f"SN-{uuid.uuid4().hex[:8]}"
    def result(cluster_id):
        return ResolutionResult(clusters=[Cluster(
            cluster_id=cluster_id, members=[], identifiers={"serial_number": [serial]},
            decision=MergeDecision.AUTO_MERGED, confidence=1.0, methods=["anchor"])])
    async def ingest(conn, cluster_id):
        await rebuild_projection(conn, result(cluster_id), [], {}, {}, {cluster_id: "Pump"})
    try:
        _run(lambda conn: ingest(conn, "ua-0001"))
        def level():
            return next(a["criticality"] for a in c.get("/api/assets", headers=h["engineer"]).json()
                        if any(i["value"] == serial for i in a["identifiers"]))
        assert level() == "unknown"
        assert c.put("/api/assets/ua-0001/criticality", headers=h["manager"],
                     json={"level": "high"}).status_code == 200
        assert level() == "high"
        _run(lambda conn: ingest(conn, "ua-0007"))  # re-ingest: same asset, different row id
        assert level() == "high"
        assert c.put("/api/assets/ua-0007/criticality", headers=h["manager"],
                     json={"level": "unknown"}).status_code == 200
        assert level() == "unknown"
        assert c.put("/api/assets/ua-0007/criticality", headers=h["manager"],
                     json={"level": "bogus"}).status_code == 422
        assert c.put("/api/assets/nope/criticality", headers=h["manager"],
                     json={"level": "low"}).status_code == 404
    finally:
        async def clean(conn):
            await conn.execute("delete from unified_assets")
            await conn.execute("delete from asset_criticality where value = $1", serial.lower())
        _run(clean)
