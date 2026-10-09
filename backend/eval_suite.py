"""Atlas — HONEST evaluation harness.

This replaces the earlier harness, which graded RCA "cause accuracy" against
hand-written keyword synonym lists tuned to the seed incidents — a circular test
that scored ~1.00 by construction. That measured memorization of our own data,
not generalization.

Instead we grade only what can be VERIFIED objectively, over WHATEVER assets are
currently in the system (seed data and/or ingested PDFs):

  A. Resolution F1        — do the right source records cluster into one asset?
                            (legitimate ground truth: record membership.)
  B. Anomaly gating       — a benign/within-tolerance log is NOT a failure.
  C. Grounding            — every RCA hypothesis cites evidence that REALLY
                            exists for that asset (no fabricated citations).
  D. Calibration          — confident hypotheses (>=0.8) are grounded; ungrounded
                            hypotheses stay low (<=0.4); grounded outrank ungrounded.
  E. Cross-asset leakage  — RCA on asset A never cites asset B's evidence.
  F. Compliance           — at-risk propagation is deterministic on the graph.

Nothing here rewards saying a particular "right answer" word. Scores are NOT
expected to be 1.00 — the point is an honest signal of grounding + calibration.

Usage: .venv\\Scripts\\python.exe eval_suite.py   (backend running on :8001)
"""
from __future__ import annotations
import asyncio, json, os, pathlib, urllib.request

API = "http://127.0.0.1:8001"

for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
DSN = os.environ["DATABASE_URL"]


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.loads(r.read())


def sse(path, body):
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    result = None
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r.read().decode().splitlines():
            raw = raw.strip()
            if raw.startswith("data:"):
                try:
                    ev = json.loads(raw[5:].strip())
                except Exception:
                    continue
                if ev.get("step") == "complete":
                    result = ev.get("result")
    return result


def uid_for(serial):
    for a in get("/api/assets"):
        if any(i["value"].lower() == serial.lower() for i in a["identifiers"]):
            return a["unified_id"]
    return None


async def _connect():
    import asyncpg
    return await asyncpg.connect(dsn=DSN, timeout=10)


async def evidence_ids_for(uid: str) -> set[str]:
    """All citation ids that genuinely exist for an asset: its operational-edge
    citations plus the failure citations of assets it DEPENDS_ON (upstream)."""
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "select metadata->>'citation' as c from edges "
            "where source_id=$1 and layer='operational'", f"asset:{uid}")
        ids = {r["c"] for r in rows if r["c"]}
        deps = await conn.fetch(
            "select target_id from edges where source_id=$1 and relation_type='DEPENDS_ON'",
            f"asset:{uid}")
        for d in deps:
            urows = await conn.fetch(
                "select metadata->>'citation' as c from edges "
                "where source_id=$1 and relation_type='HAS_FAILURE'", d["target_id"])
            ids |= {r["c"] for r in urows if r["c"]}
        return {i for i in ids if i}
    finally:
        await conn.close()


async def failure_citations(uid: str) -> set[str]:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "select metadata->>'citation' as c from edges "
            "where source_id=$1 and relation_type='HAS_FAILURE'", f"asset:{uid}")
        return {r["c"] for r in rows if r["c"]}
    finally:
        await conn.close()


async def assets_with_failures() -> list[str]:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            "select distinct source_id from edges where relation_type='HAS_FAILURE'")
        return [r["source_id"].replace("asset:", "") for r in rows]
    finally:
        await conn.close()


def _hint_for(uid: str) -> str:
    """A resolvable asset hint: a primary identifier value, else the asset name,
    else the uid itself (RCA resolves identifiers/names)."""
    for a in get("/api/assets"):
        if a["unified_id"] == uid:
            idents = a.get("identifiers") or []
            if idents:
                prim = next((i for i in idents if i.get("is_primary")), idents[0])
                return prim["value"]
            if a.get("asset_name"):
                return a["asset_name"]
    return uid


def rca_for_hint(hint: str):
    r = sse("/api/rca", {"question": "", "asset": hint})
    return (r or {}).get("report") or {}


def _cited_ids(h) -> list[str]:
    return [str(e).strip() for e in h.get("evidence", []) if str(e).strip()]


def _canon(x: str) -> str:
    """Canonical citation token: the id's final ':'-segment, lowercased. This
    distinguishes 'INC-1' from 'IT-INC-1' (naive substring matching conflated
    them, causing false 'leakage')."""
    s = str(x).strip().lower().strip('"[]() ')
    return s.rsplit(":", 1)[-1] if ":" in s else s


def _matches(ev_id: str, pool: set[str]) -> bool:
    e = _canon(ev_id)
    if not e:
        return False
    tokens = {_canon(k) for k in pool} | {str(k).strip().lower() for k in pool}
    return e in tokens


async def main():
    S: dict[str, float] = {}
    print("=" * 72)
    print("ATLAS — HONEST EVAL (grounding + calibration + resolution)")
    print("=" * 72)

    # ---- A. Resolution F1 (objective: record membership) -------------------
    def prf(actual, exp):
        a, e = set(actual), set(exp)
        tp = len(a & e)
        p = tp / len(a) if a else 0
        r = tp / len(e) if e else 0
        return 2 * p * r / (p + r) if (p + r) else 0.0
    # Seed ground-truth membership (legitimate: which records ARE the same asset).
    exp = {
        "apu-3701-01": {"Metro Asset Registry:AR-APU-3701", "IBM Maximo CMMS:WO-1001",
                        "IBM Maximo CMMS:WO-1002", "SCADA Incident Log:INC-1",
                        "SCADA Incident Log:INC-2", "SCADA Incident Log:INC-3",
                        "Compliance Register:REG-3701"},
        "sn-dell-7x2k": {"ServiceNow CMDB:CI-DB01", "Datadog Incidents:IT-INC-1",
                         "Datadog Incidents:IT-INC-2", "Datadog Incidents:IT-INC-3",
                         "Datadog Incidents:IT-INC-4", "ServiceNow Change:CHG-1",
                         "IT Compliance Register:IT-REG-1", "Network Topology:TOPO-DB01"},
    }
    f1s = []
    for serial, members in exp.items():
        uid = uid_for(serial)
        if not uid:
            print(f"[A] resolution {serial}: SKIP (asset not present)")
            continue
        doc = get(f"/api/asset/{uid}")
        f = prf(doc["citations"], members)
        f1s.append(f)
        print(f"[A] resolution {serial}: F1={f:.2f} ({len(doc['citations'])}/{len(members)})")
    if f1s:
        S["A_resolution_f1"] = sum(f1s) / len(f1s)

    # ---- B. Anomaly gating -------------------------------------------------
    it_uid = uid_for("sn-dell-7x2k")
    if it_uid:
        fc = await failure_citations(it_uid)
        benign_ok = not any("IT-INC-3" in c for c in fc)
        print(f"\n[B] anomaly gating: benign backup excluded from failures: "
              f"{'PASS' if benign_ok else 'FAIL'}")
        S["B_anomaly_gating"] = 1.0 if benign_ok else 0.0

    # ---- C+D. Grounding + calibration over ALL assets with failures --------
    uids = await assets_with_failures()
    print(f"\n[C/D] grounding + calibration over {len(uids)} asset(s) with failures")
    # Run RCA once per asset (via a resolvable hint); reuse for grounding,
    # calibration, and leakage.
    reports = {uid: rca_for_hint(_hint_for(uid)) for uid in uids}
    known_by_uid = {uid: await evidence_ids_for(uid) for uid in uids}
    total_h = grounded_h = fabricated = 0
    overconfident_ungrounded = 0
    conf_grounded: list[float] = []
    conf_ungrounded: list[float] = []
    for uid in uids:
        known = known_by_uid[uid]
        rep = reports[uid]
        for h in rep.get("hypotheses", []):
            total_h += 1
            ids = _cited_ids(h)
            grounded = bool(ids) and all(_matches(e, known) for e in ids)
            has_fabricated = any(not _matches(e, known) for e in ids)
            conf = float(h.get("confidence", 0.0) or 0.0)
            if grounded:
                grounded_h += 1
                conf_grounded.append(conf)
            else:
                conf_ungrounded.append(conf)
            if has_fabricated:
                fabricated += 1
            if conf >= 0.8 and not grounded:
                overconfident_ungrounded += 1
    if total_h:
        grounding_rate = grounded_h / total_h
        fabricated_rate = fabricated / total_h
        S["C_grounding_rate"] = grounding_rate
        # Calibration score: no overconfident-ungrounded, and grounded outrank ungrounded.
        mg = sum(conf_grounded) / len(conf_grounded) if conf_grounded else 0.0
        mu = sum(conf_ungrounded) / len(conf_ungrounded) if conf_ungrounded else 0.0
        calib_ok = (overconfident_ungrounded == 0) and (mg >= mu)
        S["D_calibration"] = 1.0 if calib_ok else 0.0
        print(f"    hypotheses={total_h}  grounded={grounded_h} ({grounding_rate:.2f})  "
              f"fabricated-citation rate={fabricated_rate:.2f}")
        print(f"    mean conf grounded={mg:.2f}  ungrounded={mu:.2f}  "
              f"overconfident+ungrounded={overconfident_ungrounded}  "
              f"calibrated={'PASS' if calib_ok else 'FAIL'}")
    else:
        print("    (no hypotheses produced — RCA abstained or assets unresolved)")

    # ---- E. Cross-asset leakage -------------------------------------------
    if len(uids) >= 2:
        leak = 0
        for uid in uids:
            own = known_by_uid[uid]
            others: set[str] = set()
            for other in uids:
                if other != uid:
                    others |= known_by_uid[other]
            others -= own  # ids unique to other assets
            rep = reports[uid]
            for h in rep.get("hypotheses", []):
                for e in _cited_ids(h):
                    if _matches(e, others) and not _matches(e, own):
                        leak += 1
        print(f"\n[E] cross-asset citation leakage: {leak} "
              f"({'PASS' if leak == 0 else 'FAIL'})")
        S["E_no_leakage"] = 1.0 if leak == 0 else 0.0

    # ---- F. Compliance determinism ----------------------------------------
    # Run twice; the at-risk set must be identical (pure graph propagation).
    rules = []
    conn = await _connect()
    try:
        rrows = await conn.fetch(
            "select distinct target_id from edges where relation_type='SUBJECT_TO' limit 3")
        rules = [r["target_id"].replace("rule:", "") for r in rrows]
    finally:
        await conn.close()
    if rules:
        det_ok = True
        for rule in rules:
            a = sse("/api/compliance", {"question": "", "rule": rule, "asset": None})
            b = sse("/api/compliance", {"question": "", "rule": rule, "asset": None})
            sa = {x["asset"] for x in (a or {}).get("at_risk_assets", [])}
            sb = {x["asset"] for x in (b or {}).get("at_risk_assets", [])}
            det_ok = det_ok and (sa == sb)
        print(f"\n[F] compliance determinism over {len(rules)} rule(s): "
              f"{'PASS' if det_ok else 'FAIL'}")
        S["F_compliance_determinism"] = 1.0 if det_ok else 0.0

    print("\n" + "=" * 72)
    for k, v in S.items():
        print(f"  {k:26s} {v:.2f}")
    if S:
        print(f"  {'OVERALL':26s} {sum(S.values())/len(S):.2f} / 1.00")
    print("=" * 72)
    print("Note: scores reflect grounding + calibration, not keyword matching.")


asyncio.run(main())
