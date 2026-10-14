"""Priority policy (M.10): risk + stated urgency + criticality + recurrence -> P1..P4. Pure, no I/O.

The policy is documented in docs/rules.md §4.1; points and cut-offs here are its versioned form.
"""
from __future__ import annotations
import re
from typing import Any
from app.engine.log_extract import _TOKEN, _negated

METHOD_VERSION = "priority-v0"
# shortcut: guessed points/cut-offs, re-fit with the manager's decisions (M.12) once enough exist.
RISK_POINTS = {"low": 0, "medium": 2, "high": 4}
URGENCY_POINTS = 3
CRITICALITY_POINTS = {"medium": 1, "high": 2}
RECURRENCE_POINTS = ((2, 2), (1, 1))  # (min recurrences in 90 days, points)
LEVELS = ((8, "P1"), (5, "P2"), (2, "P3"), (0, "P4"))
# shortcut: keyword list, no synonyms or typo handling; extend from reviewed logs.
_URGENT = re.compile(r"^(urgent(ly)?|immediate(ly)?|shut-?down)$", re.I)


def urgency_terms(text: str) -> tuple[list[str], list[str]]:
    """(stated, negated) urgency words; a word after a negator ('not urgent') is negated."""
    toks = [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(text)]
    stated, negated = [], []
    for w, s, _ in toks:
        if _URGENT.match(w):
            (negated if _negated(toks, s, text) else stated).append(w.lower())
    return stated, negated


def recommend_priority(*, risk_category: str, text: str, criticality: str, recurrence_90d: int) -> dict[str, Any]:
    """Returns {priority, points, explanation:[{factor, input, points, reason}], method_version}."""
    stated, negated = urgency_terms(text)
    rec = next((p for n, p in RECURRENCE_POINTS if recurrence_90d >= n), 0)
    rows = [
        ("risk", risk_category, RISK_POINTS.get(risk_category, 0), f"risk category {risk_category} (uncalibrated)"),
        ("urgency", stated or None, URGENCY_POINTS if stated else 0,
         f"log states {', '.join(sorted(set(stated)))}" if stated
         else f"negated urgency ignored: {', '.join(sorted(set(negated)))}" if negated
         else "no urgency words"),
        ("criticality", criticality, CRITICALITY_POINTS.get(criticality, 0), f"equipment criticality {criticality}"),
        ("recurrence", recurrence_90d, rec, f"{recurrence_90d} recurrence(s) on the same component in 90 days"),
    ]
    points = sum(r[2] for r in rows)
    return {"priority": next(p for cut, p in LEVELS if points >= cut), "points": points,
            "explanation": [{"factor": f, "input": i, "points": p, "reason": r} for f, i, p, r in rows],
            "method_version": METHOD_VERSION}
