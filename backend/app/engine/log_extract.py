"""Rule-based maintenance-log extractor (M.4, M-D3). Pure: no DB, no network.

extract(text, terminology) -> {"fields": {...}, "negated": [...], "sentences": [[s, e], ...]}
Each field is None (not found) or {value, span:[start,end], confidence, needs_review,
source:'rule'}. Spans index into the untouched original text.
Confidence by match type: tag id 0.9, known-pattern id 0.7, vocabulary word 0.85,
word reached through the terminology table 0.7, date 0.9, outcome phrase 0.55-0.85.
needs_review is set below 0.75.
"""
from __future__ import annotations
import re
from typing import Any
from app.knowledge.identity import CanonicalConcept as C
from app.knowledge.patterns import ALL_PATTERNS

REVIEW_BELOW = 0.75
# Vocabulary: canonical term -> stems. A token matches a stem when it starts with it
# and has at most 4 extra letters (replac+ement, vibrat+ing); stops "fan" -> "fantastic".
COMPONENTS = {k: (k,) for k in (
    "bearing", "motor", "seal", "gearbox", "impeller", "shaft", "coupling", "valve",
    "filter", "belt", "fan", "gasket", "coil", "bolt", "hose", "piston", "rotor", "fuse")}
SYMPTOMS = {
    "vibration": ("vibrat",), "overheating": ("overheat",), "leak": ("leak",),
    "noise": ("nois",), "wear": ("wear",), "crack": ("crack",), "corrosion": ("corro",),
    "misalignment": ("misalign",), "smoke": ("smok",), "trip": ("trip", "tripp"),
    "failure": ("failure", "failed"), "blockage": ("blockage", "clog")}
ACTIONS = {
    "replace": ("replac",), "repair": ("repair",), "lubricate": ("lubricat", "lube"),
    "inspect": ("inspect",), "check": ("check",), "clean": ("clean",),
    "tighten": ("tighten",), "adjust": ("adjust",), "calibrate": ("calibrat",),
    "align": ("align",)}
EQUIPMENT_TYPES = {"pump", "compressor", "motor", "fan", "gearbox", "valve", "conveyor",
                   "turbine", "boiler", "chiller", "generator", "press", "blower"}
SYMPTOM_MODIFIERS = {"excessive", "abnormal", "unusual", "severe", "loud", "high",
                     "intermittent", "slight", "minor", "heavy"}
NEGATORS = {"no", "not", "without", "never", "cannot"}
_ID_CONCEPTS = {C.SERIAL_NUMBER, C.MAC_ADDRESS, C.UUID, C.VIN}

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")
_TAG = re.compile(r"^[A-Z]{1,3}-\d{2,5}[A-Z]?$")
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
          r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
_DATE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:,?\s+\d{{4}})?\b"
    rf"|\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
    r"|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", re.I)
_OUTCOMES = [  # (regex, confidence), best confidence wins
    (re.compile(r"\b(?:test(?:ed|ing)?|verified)\b[^.;,]{0,40}?\b"
                r"(?:successfully|ok|okay|fine|normal(?:ly)?|passed)\b", re.I), 0.85),
    (re.compile(r"\b(?:running|operating|working|runs|operates)\s+"
                r"(?:normally|fine|ok|okay|smoothly)\b", re.I), 0.85),
    (re.compile(r"\b(?:back in|returned to) service\b|\bresolved\b", re.I), 0.8),
    (re.compile(r"\btest(?:ed|ing)?\b", re.I), 0.55),
]


def sentences(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in list(re.finditer(r"(?<=[.!?])\s+|\n+", text)) + [None]:
        end = m.start() if m else len(text)
        if text[start:end].strip():
            out.append((start, end))
        if m:
            start = m.end()
    return out


def _match(tok: str, vocab: dict[str, tuple[str, ...]], table: dict[str, str]):
    """(canonical, confidence) if `tok` is a vocabulary word, else None."""
    t = tok.lower()
    for canon, stems in vocab.items():
        if any(t.startswith(s) and len(t) - len(s) <= 4 for s in stems):
            return canon, 0.85
    mapped = table.get(" ".join(re.sub(r"[^\w\s]", " ", t).split()))
    return (mapped, 0.7) if mapped in vocab else None


def _negated(toks: list[tuple[str, int, int]], start: int, text: str) -> bool:
    """A negator in the 3 tokens before `start`, with no clause break in between."""
    for w, s, e in [t for t in toks if t[2] <= start][-3:]:
        lw = w.lower()
        if (lw in NEGATORS or lw.endswith(("n't", "n’t"))) and not re.search(r"[,;:]", text[e:start]):
            return True
    return False


def _field(value: str, s: int, e: int, conf: float) -> dict[str, Any]:
    return {"value": value, "span": [s, e], "confidence": conf,
            "needs_review": conf < REVIEW_BELOW, "source": "rule"}


def _best(cands: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(cands, key=lambda c: (c["confidence"], -c["span"][0]), default=None)


def extract(text: str, terminology: dict[str, str]) -> dict[str, Any]:
    sents = sentences(text)
    cands: dict[str, list[dict[str, Any]]] = {k: [] for k in
        ("equipment", "component", "symptom", "action", "outcome", "date")}
    negated: list[dict[str, Any]] = []

    def add(field: str, f: dict[str, Any], neg: bool) -> None:
        if neg:
            negated.append({"field": field, "value": f["value"], "span": f["span"]})
        else:
            cands[field].append(f)

    for ss, se in sents:
        sent = text[ss:se]
        toks = [(m.group(), ss + m.start(), ss + m.end()) for m in _TOKEN.finditer(sent)]
        # equipment: tag like P-104, else a known identifier pattern; prefix a type word
        for i, (w, s, e) in enumerate(toks):
            conf = 0.9 if _TAG.match(w) else 0.0
            if not conf and re.search(r"\d", w) and re.search(r"[A-Za-z]", w):
                p = next((p for p in ALL_PATTERNS if p.matches(w)), None)
                conf = 0.7 if p and p.concept in _ID_CONCEPTS else 0.0
            if conf:
                if i and toks[i - 1][0].lower() in EQUIPMENT_TYPES:
                    s = toks[i - 1][1]
                add("equipment", _field(text[s:e], s, e, conf), False)
        # component (adjacent component words merge: "motor bearing"), symptom, action
        run: list[tuple[str, int, int, float]] = []
        for i, (w, s, e) in enumerate(toks + [("", -1, -1)]):
            m = _match(w, COMPONENTS, terminology) if w else None
            if m:
                run.append((m[0], s, e, m[1]))
                continue
            if run:
                add("component", _field(" ".join(r[0] for r in run), run[0][1], run[-1][2],
                                        min(r[3] for r in run)), False)
                run = []
            if not w:
                continue
            sym, act = _match(w, SYMPTOMS, terminology), _match(w, ACTIONS, terminology)
            if sym and not _TAG.match(w):
                if i and toks[i - 1][0].lower() in SYMPTOM_MODIFIERS:
                    s = toks[i - 1][1]
                    value = f"{toks[i - 1][0].lower()} {sym[0]}"
                else:
                    value = sym[0]
                add("symptom", _field(value, s, e, sym[1]), _negated(toks, s, text))
            elif act:
                add("action", _field(act[0], s, e, act[1]), _negated(toks, s, text))
        for rx, conf in _OUTCOMES:
            for m in rx.finditer(sent):
                s, e = ss + m.start(), ss + m.end()
                add("outcome", _field(text[s:e], s, e, conf), _negated(toks, s, text))
        for m in _DATE.finditer(sent):
            s, e = ss + m.start(), ss + m.end()
            add("date", _field(text[s:e], s, e, 0.9), False)
    return {"fields": {k: _best(v) for k, v in cands.items()},
            "negated": list({(n["field"], n["span"][0]): n for n in negated}.values()), "sentences": [list(s) for s in sents]}
