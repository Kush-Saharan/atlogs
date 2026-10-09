"""Semantic matching of a source field NAME to a canonical concept (doc Signal 3).

Deterministic string similarity (SequenceMatcher) between the normalized field
name and each concept's display name + known aliases. Honest limitation: this
is string similarity, not contextual understanding — a future embedding-based
matcher would handle abbreviations better. Low scores fall through to voting,
which requires pattern corroboration before trusting a field as an anchor.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .identity import CanonicalConcept

# Canonical concept -> display name + alias phrases used for name similarity.
CONCEPT_VOCAB: dict[CanonicalConcept, list[str]] = {
    CanonicalConcept.SERIAL_NUMBER: ["serial number", "serial", "s/n", "sn", "serge",
                                     "u serial no", "equipment serial", "device serial"],
    CanonicalConcept.MAC_ADDRESS: ["mac address", "mac", "net mac", "mac addr"],
    CanonicalConcept.UUID: ["uuid", "guid", "machine uuid"],
    CanonicalConcept.VIN: ["vin", "vehicle identification number"],
    CanonicalConcept.IMEI: ["imei"],
    CanonicalConcept.UDI: ["udi", "udi di", "device identifier"],
    CanonicalConcept.ASSET_TAG: ["asset tag", "asset id", "tag", "u asset tag"],
    CanonicalConcept.BARCODE: ["barcode", "bar code"],
    CanonicalConcept.LOT_NUMBER: ["lot number", "lot", "batch"],
    CanonicalConcept.IP_ADDRESS: ["ip address", "ip", "ipaddr"],
    CanonicalConcept.WORK_ORDER: ["work order", "wo number", "wo", "ticket"],
    CanonicalConcept.MODEL: ["model", "model id", "type", "typbz", "model number"],
    CanonicalConcept.LOCATION: ["location", "plant", "site", "werk", "swerk"],
    CanonicalConcept.TIMESTAMP: ["timestamp", "date", "created at"],
}


def _normalize(name: str) -> str:
    # split camelCase / snake_case / separators into space-joined lowercase
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = re.sub(r"[_\-./]+", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def semantic_match(field_name: str) -> tuple[CanonicalConcept, float]:
    """Return the best-matching concept and its similarity score in [0,1]."""
    norm = _normalize(field_name)
    best_concept = CanonicalConcept.UNKNOWN
    best_score = 0.0
    for concept, phrases in CONCEPT_VOCAB.items():
        for phrase in phrases:
            score = _similarity(norm, phrase)
            if score > best_score:
                best_score, best_concept = score, concept
    return best_concept, round(best_score, 3)
