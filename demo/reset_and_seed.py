"""Atlas demo — reset ALL data and seed a fresh demo corpus.

What it does:
  1. Wipes every application table (assets, records, edges, connectors,
     documents, extractions, workflow history, review queue…), so you start the
     demo from a clean slate.
  2. Creates the five demo connectors from demo_corpus.json and syncs each one
     through the real ingestion pipeline (resolution -> graph -> operational
     extraction -> OKF bundles), streaming per-step status.
  3. Optionally ingests one or more PDFs (a file or a folder) as a background
     job and waits for it, so the graph also contains document-derived assets.

Run (backend must be up on :8001). Easiest — the wrapper works from any folder:

    demo\\reset.bat                 (connectors only; recommended before a demo)
    demo\\reset.bat --reset-only    (wipe only, seed nothing)
    demo\\reset.bat --pdf "C:\\path\\to\\pdfs"   (also ingest a file or folder)

Or invoke directly from the REPO ROOT (note: not from backend\\):

    backend\\.venv\\Scripts\\python.exe demo\\reset_and_seed.py

Notes:
  * DATABASE_URL is read from backend/.env. API is http://127.0.0.1:8001.
  * Big PDFs (40+ pages) use the low-memory text path automatically.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
API = "http://127.0.0.1:8001"

# Tables cleared, in FK-safe order.
_TABLES = [
    "asset_source_records",
    "asset_identifiers",
    "edges",
    "unified_assets",
    "source_records",
    "review_queue",
    "okf_documents",
    "operational_extractions",
    "doc_extractions",
    "document_parses",
    "workflow_runs",
    "manual_decisions",
    "discovered_fields",
    "connectors",
    "source_systems",
]


def _load_env() -> str:
    env = BACKEND / ".env"
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.environ["DATABASE_URL"]


async def clear_all(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn=dsn, timeout=15)
    try:
        for t in _TABLES:
            try:
                await conn.execute(f"delete from {t}")
                print(f"  cleared {t}")
            except Exception as exc:  # noqa: BLE001 - table may not exist
                print(f"  skip {t}: {exc}")
    finally:
        await conn.close()


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read())


def _post_sse(path: str, body: dict, prefix: str = "    ") -> None:
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r.read().decode().splitlines():
            raw = raw.strip()
            if raw.startswith("data:"):
                try:
                    ev = json.loads(raw[5:].strip())
                except Exception:
                    continue
                msg = ev.get("message") or ""
                if ev.get("step") not in ("heartbeat",) and msg:
                    print(f"{prefix}{msg}")


def _check_backend() -> bool:
    try:
        _get("/api/health")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"! Backend not reachable at {API} ({exc}).")
        print("  Start it:  cd backend ; .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001")
        return False


def seed_connectors() -> None:
    corpus = json.loads((HERE / "demo_corpus.json").read_text())
    for c in corpus["connectors"]:
        print(f"\n> Connector: {c['name']}  ({len(c['records'])} records)")
        created = _post(
            "/api/connectors",
            {"name": c["name"], "description": c["description"],
             "kind": "manual", "payload": c["records"]},
        )
        cid = created.get("id")
        if cid is None:
            print(f"  ! could not create connector: {created}")
            continue
        _post_sse(f"/api/connectors/{cid}/sync", {})


def seed_pdf(path: str) -> None:
    print(f"\n> Ingesting PDF(s) from: {path}")
    started = _post("/api/documents/ingest-path", {"path": path})
    if started.get("error"):
        print(f"  ! {started['error']}")
        return
    job_id = started.get("job_id")
    print(f"  job {job_id} started ({started.get('label')}). Tailing…")
    # Tail the background job to completion.
    try:
        with urllib.request.urlopen(
            API + f"/api/documents/jobs/{job_id}/stream", timeout=3600
        ) as r:
            for raw in r.read().decode().splitlines():
                raw = raw.strip()
                if raw.startswith("data:"):
                    try:
                        ev = json.loads(raw[5:].strip())
                    except Exception:
                        continue
                    if ev.get("step") == "_end":
                        break
                    msg = ev.get("message") or ""
                    if ev.get("step") != "heartbeat" and msg:
                        print(f"    {msg}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ! stream error (job keeps running server-side): {exc}")


def summary() -> None:
    try:
        o = _get("/api/overview")
        print("\n=== Seeded ===")
        print(f"  unified assets : {o.get('unified_assets')}")
        print(f"  source records : {o.get('source_records')}")
        print(f"  edges          : {o.get('edges_total')} "
              f"(operational: {o.get('edges_operational')})")
        print(f"  review open    : {o.get('review_open')}")
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-only", action="store_true", help="wipe data, seed nothing")
    ap.add_argument("--pdf", default=None, help="a PDF file OR folder to also ingest")
    ap.add_argument("--no-connectors", action="store_true", help="skip connector seeding")
    args = ap.parse_args()

    dsn = _load_env()
    print("=== Clearing ALL data ===")
    asyncio.run(clear_all(dsn))

    if args.reset_only:
        print("\nReset complete (no seed).")
        return

    if not _check_backend():
        sys.exit(1)

    if not args.no_connectors:
        print("\n=== Seeding demo connectors ===")
        seed_connectors()

    if args.pdf:
        seed_pdf(args.pdf)

    summary()
    print("\nDone. Open the app and follow demo/DEMO_SCRIPT.md.")


if __name__ == "__main__":
    main()
