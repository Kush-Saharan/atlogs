"""Greedy resource-aware schedule proposal (M.11). Pure: no I/O, inputs are not mutated.

Items are handled in priority order (P1 first, then id). Each takes the earliest slot of a
free technician with the required skill and uses up part stock. An item that cannot be placed
becomes a conflict; its priority is never lowered (spec §10: risk is not scheduling feasibility).
Times are naive local datetimes, as entered on the Resources page.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

# shortcut: greedy and one part unit per listed part, not optimal; upgrade to a solver only if real schedules need it.


def _t(v: Any) -> datetime:
    return (v if isinstance(v, datetime) else datetime.fromisoformat(v)).replace(tzinfo=None)


def _slot(windows: list[tuple[datetime, datetime]], booked: list[tuple[datetime, datetime]],
          need: timedelta, hs: datetime, he: datetime) -> datetime | None:
    for ws, we in sorted(windows):
        cand, end = max(ws, hs), min(we, he)
        for bs, be in sorted(booked):
            if bs >= cand + need:
                break
            if be > cand:
                cand = be
        if cand + need <= end:
            return cand
    return None


def propose(recommendations: list[dict[str, Any]], technicians: list[dict[str, Any]],
            parts: dict[str, int], horizon: tuple[Any, Any]) -> dict[str, list[dict[str, Any]]]:
    """recommendations: {id, priority, skill, duration_min, parts[]}; technicians: {id, name, skills[],
    availability[{start,end}]}; parts: name -> stock."""
    hs, he = _t(horizon[0]), _t(horizon[1])
    stock = {k.lower(): v for k, v in parts.items()}
    booked: dict[Any, list[tuple[datetime, datetime]]] = {t["id"]: [] for t in technicians}
    wins = {t["id"]: [(_t(w["start"]), _t(w["end"])) for w in t["availability"]] for t in technicians}
    assignments: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for r in sorted(recommendations, key=lambda r: (r["priority"], r["id"])):
        need = timedelta(minutes=r["duration_min"])
        skilled = [t for t in technicians if r["skill"].lower() in {s.lower() for s in t["skills"]}]
        short = [p for p in r["parts"] if stock.get(p.lower(), 0) < 1]
        best: tuple[datetime, Any, str] | None = None
        for t in skilled:
            s = _slot(wins[t["id"]], booked[t["id"]], need, hs, he)
            if s and (best is None or (s, t["id"]) < (best[0], best[1])):
                best = (s, t["id"], t["name"])
        reason = ("skill" if not skilled else "part" if short else "availability" if best is None else None)
        if reason:
            detail = {"skill": f"no technician has skill '{r['skill']}'",
                      "part": f"out of stock: {', '.join(short)}",
                      "availability": "no free window in the horizon long enough"}[reason]
            conflicts.append({"recommendation_id": r["id"], "priority": r["priority"], "reason": reason, "detail": detail})
            continue
        start, tid, name = best  # type: ignore[misc]
        booked[tid].append((start, start + need))
        for p in r["parts"]:
            stock[p.lower()] -= 1
        assignments.append({"recommendation_id": r["id"], "priority": r["priority"], "technician_id": tid,
                            "technician": name, "start": start.isoformat(), "end": (start + need).isoformat(),
                            "parts": list(r["parts"])})
    return {"assignments": assignments, "conflicts": conflicts}
