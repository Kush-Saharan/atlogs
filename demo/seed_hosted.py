"""Seed the hosted Atlas instance with demo connectors.

Run:
    python demo\\seed_hosted.py

This posts each connector from demo_corpus.json to the hosted backend
(https://atlas-api-pa3s.onrender.com), then syncs them through the ingestion
pipeline.
"""

from __future__ import annotations

import json
import pathlib
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
API = "https://atlas-api-pa3s.onrender.com"


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
        print("  The Render instance may be sleeping. Wait ~60s for cold start, then retry.")
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
    print(f"=== Seeding hosted backend: {API} ===")
    if not _check_backend():
        return

    print("\n=== Seeding demo connectors ===")
    seed_connectors()
    summary()
    print("\nDone. Open https://atlas-panda-psi.vercel.app")


if __name__ == "__main__":
    main()
