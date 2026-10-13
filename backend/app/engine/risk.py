"""Risk baseline (M.9, M-D5): a transparent weighted formula, labelled UNCALIBRATED.

Pure: no I/O. Weights and cut-offs below are the versioned method (`METHOD_VERSION`);
they are unevaluated guesses until compared with labelled outcomes (spec §5).
"""
from __future__ import annotations
from typing import Any

METHOD_VERSION = "risk-v0-uncalibrated"
MIN_HISTORY = 3  # fewer records on the equipment -> insufficient_evidence
# shortcut: guessed weights/caps/cut-offs, re-fit once labelled outcomes exist.
WEIGHTS = {"recurrence": 30, "recent_incidents": 20, "criticality": 25, "similar_adverse_rate": 25}
CAPS = {"recurrence": 3, "recent_incidents": 5}  # counts at/above the cap score 1.0
CRITICALITY = {"low": 0.0, "medium": 0.5, "high": 1.0}
CATEGORIES = ((67, "high"), (34, "medium"), (0, "low"))


def assess_risk(features: dict[str, Any]) -> dict[str, Any]:
    """features: history_count, recurrence_90d, recent_incidents_90d (counts),
    criticality ('low'|'medium'|'high'|'unknown'), similar_adverse_rate (0..1 or None)."""
    crit = features.get("criticality") or "unknown"
    rate = features.get("similar_adverse_rate")
    history = int(features.get("history_count") or 0)
    # normalised value 0..1 per factor; None = no data, contributes 0
    norm = {
        "recurrence": min(int(features.get("recurrence_90d") or 0), CAPS["recurrence"]) / CAPS["recurrence"],
        "recent_incidents": min(int(features.get("recent_incidents_90d") or 0), CAPS["recent_incidents"])
        / CAPS["recent_incidents"],
        "criticality": CRITICALITY.get(crit),
        "similar_adverse_rate": None if rate is None else min(max(float(rate), 0.0), 1.0),
    }
    factors = [
        {"name": n, "input": features.get({"recurrence": "recurrence_90d", "recent_incidents": "recent_incidents_90d"}
                                          .get(n, n)),
         "normalised": v, "weight": WEIGHTS[n], "contribution": round(WEIGHTS[n] * (v or 0.0), 2)}
        for n, v in norm.items()
    ]
    score = round(sum(f["contribution"] for f in factors), 2)
    category = next(c for cut, c in CATEGORIES if score >= cut)
    reasons = []
    if history < MIN_HISTORY:
        reasons.append(f"only {history} history record(s), need {MIN_HISTORY}")
    if crit not in CRITICALITY:
        reasons.append("equipment criticality unknown")
    return {"score": score, "category": category, "factors": factors,
            "insufficient_evidence": bool(reasons), "insufficient_reasons": reasons,
            "method_version": METHOD_VERSION}
