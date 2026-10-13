"""M.7: similar maintenance cases on a small labelled synthetic set.
DB tests skip without DATABASE_URL. Cases are seeded straight into the tables (no pipeline,
no network) and removed afterwards; the vector path uses fake embeddings."""
from __future__ import annotations
import asyncio
import json
import os

import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import auth
from app.workflows import retrieval

load_dotenv()
DSN = os.environ.get("DATABASE_URL", "")

# (key, equipment, component, symptom, action, outcome, date, original text, embedding axis)
CASES = [
    ("brg1", "ZT-901", "motor bearing", "excessive vibration", "bearing replacement", "resolved", "2025-08-12",
     "Pump ZT-901 had excessive vibration at the motor bearing. Bearing replaced and tested.", 0),
    ("brg2", "ZT-902", "drive bearing", "abnormal vibration", "bearing greased", "resolved", "2024-03-02",
     "Fan ZT-902 showed abnormal vibration from the drive bearing. Greased the bearing.", 0),
    ("hot1", "ZT-903", "winding", "overheating", "fins cleaned", "resolved", "2025-01-20",
     "Motor ZT-903 overheating, cooling fins blocked with dust. Cleaned the fins.", 1),
    ("leak1", "ZT-904", "pump seal", "oil leak", "seal replaced", "resolved", "2025-05-05",
     "Hydraulic unit ZT-904 oil leak at the pump seal. Seal replaced.", 2),
    ("paint1", "ZT-905", "handrail", "chipped paint", "repainted", "resolved", "2025-06-01",
     "Handrail near ZT-905 had chipped paint and was repainted.", 3),
]
DIM = 2048


def _vec(axis: int) -> str:
    return "[" + ",".join("1" if i == axis else "0" for i in range(DIM)) + "]"


class _FakeEmbed:
    """Maps a query to the axis of the case family it mentions."""
    def embed_query(self, text: str) -> list[float]:
        axis = 0 if "vibration" in text else 1 if "overheat" in text else 3
        return [1.0 if i == axis else 0.0 for i in range(DIM)]


@pytest.fixture
def seeded():
    if not DSN:
        pytest.skip("DATABASE_URL not set")

    async def run(sql, *args, fetch=False):
        conn = await asyncpg.connect(DSN)
        try:
            return await (conn.fetch(sql, *args) if fetch else conn.fetchval(sql, *args))
        finally:
            await conn.close()

    ids = {}
    for key, eq, comp, sym, act, out, day, text, axis in CASES:
        fields = {"equipment": eq, "component": comp, "symptom": sym, "action": act, "outcome": out, "date": day}
        log_id = asyncio.run(run("insert into maintenance_logs (sha256, original_text, status) values"
                                 " ('t', $1, 'reviewed') returning id", text))
        reviewed = {k: {"value": v} for k, v in fields.items()}
        asyncio.run(run("insert into maintenance_records (log_id, extracted, reviewed) values ($1, $2, $3)",
                        log_id, json.dumps({"fields": {}}), json.dumps(reviewed)))
        asyncio.run(run(
            "insert into source_records (system, record_id, raw_json, semantic_text, embedding)"
            " values ('maintenance_logs', $1, $2::jsonb, $3, $4::vector)",
            f"maintenance_logs:{log_id}", json.dumps({"log_id": log_id}),
            f"{comp} {sym} {act} {out}", _vec(axis)))
        ids[key] = log_id
    yield ids, run
    asyncio.run(run("delete from source_records where system = 'maintenance_logs' and"
                    " (raw_json->>'log_id')::bigint = any($1::bigint[])", list(ids.values())))
    asyncio.run(run("delete from maintenance_records where log_id = any($1::bigint[])", list(ids.values())))
    asyncio.run(run("delete from maintenance_logs where id = any($1::bigint[])", list(ids.values())))


def _mine(res, ids):
    mine = set(ids.values())
    return [m["log_id"] for m in res["matches"] if m["log_id"] in mine]


def _search(run, text, filters=None, k=10):
    async def go():
        conn = await asyncpg.connect(DSN)
        try:
            return await retrieval.similar_cases(conn, text, filters, k)
        finally:
            await conn.close()
    return asyncio.run(go())


def test_fts_only_relevant_ranks_above_unrelated(seeded, offline):
    ids, run = seeded
    res = _search(run, "vibration near the motor bearing on the pump")
    got = _mine(res, ids)
    assert got[0] == ids["brg1"] and ids["brg2"] in got
    assert ids["paint1"] not in got and ids["leak1"] not in got
    assert all(m["similarity"] is None and m["fts_rank"] > 0 for m in res["matches"])  # no vector offline
    top = res["matches"][0]
    assert top["link"] == f"/logs/{top['log_id']}" and top["citation"] == f"maintenance_logs:{top['log_id']}"


def test_filters(seeded, offline):
    ids, run = seeded
    q = "bearing vibration"
    assert _mine(_search(run, q, {"equipment": "zt-902"}), ids) == [ids["brg2"]]
    assert _mine(_search(run, q, {"component": "motor"}), ids) == [ids["brg1"]]
    assert _mine(_search(run, q, {"date_from": "2025-01-01"}), ids) == [ids["brg1"]]
    assert _mine(_search(run, q, {"date_to": "2024-12-31"}), ids) == [ids["brg2"]]
    assert _mine(_search(run, q, {"exclude_log_id": ids["brg1"]}), ids) == [ids["brg2"]]
    assert _search(run, q, {"equipment": "NO-SUCH-TAG"}) == {"matches": [], "reason": "no relevant match"}


def test_no_match_returns_reason(seeded, offline):
    _, run = seeded
    assert _search(run, "zzqx wibble frobnicate") == {"matches": [], "reason": "no relevant match"}
    assert _search(run, "   !!! ") == {"matches": [], "reason": "no relevant match"}


def test_vector_fused_with_fts(seeded, monkeypatch):
    ids, run = seeded
    monkeypatch.setattr(get_settings(), "embeddings_enabled", True)
    monkeypatch.setattr(retrieval, "get_embedding_client", lambda: _FakeEmbed())
    # No shared word with the cases: only the vector path can find the vibration family.
    res = _search(run, "vibration", {"component": "bearing"})
    assert set(_mine(res, ids)) == {ids["brg1"], ids["brg2"]}
    assert all(m["similarity"] == 1.0 for m in res["matches"] if m["log_id"] in ids.values())
    # Embedding service down: falls back to FTS-only instead of failing.
    monkeypatch.setattr(retrieval, "get_embedding_client", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    res = _search(run, "bearing vibration", {"component": "bearing"})
    assert set(_mine(res, ids)) == {ids["brg1"], ids["brg2"]} and res["matches"][0]["similarity"] is None


def test_routes(seeded, offline):
    ids, run = seeded
    os.environ.setdefault("AUTH_SECRET", "test-secret")
    uid = asyncio.run(run("insert into users (email, password_hash, role) values ('sim-test@test.local',"
                          " 'x', 'manager') returning id"))
    h = {"Authorization": f"Bearer {auth.make_token(uid, 'manager')}"}
    try:
        with TestClient(app) as c:
            r = c.get(f"/api/records/{ids['brg1']}/similar", headers=h, params={"equipment": "ZT-902"})
            assert r.status_code == 200 and [m["log_id"] for m in r.json()["matches"]] == [ids["brg2"]]
            r = c.get(f"/api/records/{ids['brg1']}/similar", headers=h)  # itself is excluded
            assert ids["brg1"] not in [m["log_id"] for m in r.json()["matches"]]
            assert c.get("/api/records/999999999/similar", headers=h).status_code == 404
            r = c.post("/api/similar", headers=h, json={"text": "overheating motor", "date_from": "2025-01-01"})
            assert ids["hot1"] in [m["log_id"] for m in r.json()["matches"]]
            assert c.post("/api/similar", headers=h, json={"text": ""}).status_code == 422
            assert c.post("/api/similar", json={"text": "x"}).status_code == 401
    finally:
        asyncio.run(run("delete from users where id = $1", uid))
