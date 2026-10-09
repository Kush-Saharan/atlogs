"""Industry detection from sample data (doc Section 4).

Scans field names + values + manufacturer names against per-industry signatures.
Field-name matches are weighted 2x, manufacturer matches 3x (a manufacturer name
is a strong industry signal). The highest-scoring industry is selected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class IndustrySignature:
    keywords: set[str]
    field_names: set[str]
    manufacturers: set[str]


# Shipped-as-code signatures. Extend to add industries.
INDUSTRY_SIGNATURES: dict[str, IndustrySignature] = {
    "manufacturing": IndustrySignature(
        keywords={"pump", "motor", "valve", "compressor", "line", "bearing"},
        field_names={"werk", "swerk", "equnr", "typbz", "herst"},
        manufacturers={"grundfos", "siemens", "abb", "trane"},
    ),
    "healthcare": IndustrySignature(
        keywords={"patient", "device", "implant", "udi"},
        field_names={"udi", "mrn", "lot_number"},
        manufacturers={"medtronic", "boston scientific", "ge"},
    ),
    "telecom": IndustrySignature(
        keywords={"tower", "antenna", "imei", "cell_id"},
        field_names={"imsi", "iccid", "enodeb_id"},
        manufacturers={"ericsson", "nokia", "huawei"},
    ),
}

KEYWORD_WEIGHT = 1
FIELD_NAME_WEIGHT = 2
MANUFACTURER_WEIGHT = 3


@dataclass
class IndustryDetection:
    industry: str
    confidence: float
    scores: dict[str, int] = field(default_factory=dict)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def detect_industry(records: list[dict[str, object]]) -> IndustryDetection:
    """Score sample records against each industry signature."""
    field_names: set[str] = set()
    value_tokens: set[str] = set()
    value_blob_parts: list[str] = []
    for rec in records:
        for k, v in rec.items():
            field_names.add(str(k).lower())
            if v is not None:
                s = str(v)
                value_tokens |= _tokens(s)
                value_blob_parts.append(s.lower())
    value_blob = " ".join(value_blob_parts)

    scores: dict[str, int] = {}
    for industry, sig in INDUSTRY_SIGNATURES.items():
        score = 0
        score += KEYWORD_WEIGHT * len(sig.keywords & value_tokens)
        score += FIELD_NAME_WEIGHT * len(sig.field_names & field_names)
        # Manufacturer names can be multi-word; substring match on the value blob.
        score += MANUFACTURER_WEIGHT * sum(
            1 for m in sig.manufacturers if m in value_blob
        )
        scores[industry] = score

    if not any(scores.values()):
        return IndustryDetection("unknown", 0.0, scores)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_industry, best = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    # Confidence 1.0 when the runner-up scored nothing (clean signal).
    confidence = 1.0 if runner_up == 0 else round(min(1.0, (best - runner_up) / best + 0.5), 3)
    return IndustryDetection(best_industry, confidence, scores)
