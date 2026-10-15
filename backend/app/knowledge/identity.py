"""Canonical identity concepts and their physics-based weights.

Weights are DOMAIN CONSTANTS derived from physical-world reliability, not
learned from data (see the architecture doc, Section 5). They express how much
a matching value of that type should be trusted as evidence that two records
are the same physical asset.

These are defaults; a deployment may override them per corpus/config. They are
consumed by the resolution ConfidenceEngine and by schema-discovery voting.
"""

from __future__ import annotations

from enum import Enum


class CanonicalConcept(str, Enum):
    """The standard identity/attribute concepts a source field can map to."""

    # Strong physical identifiers (anchor-eligible).
    SERIAL_NUMBER = "serial_number"
    MAC_ADDRESS = "mac_address"
    VIN = "vin"
    UUID = "uuid"
    IMEI = "imei"
    UDI = "udi"
    # Weak / reassignable identifiers.
    ASSET_TAG = "asset_tag"
    BARCODE = "barcode"
    LOT_NUMBER = "lot_number"
    # Non-identifying or transactional.
    IP_ADDRESS = "ip_address"
    WORK_ORDER = "work_order"
    TIMESTAMP = "timestamp"
    SYSTEM_INTERNAL_ID = "system_internal_id"
    MODEL = "model"
    LOCATION = "location"
    # Generic fallbacks.
    ALPHANUMERIC_ID = "alphanumeric_id"
    NUMERIC_ID = "numeric_id"
    UNKNOWN = "unknown"


# Physics-based identity weights (0..1). Higher = more reliable identity signal.
IDENTITY_WEIGHTS: dict[CanonicalConcept, float] = {
    CanonicalConcept.SERIAL_NUMBER: 0.95,  # etched into metal; survives fire
    CanonicalConcept.VIN: 0.95,            # stamped chassis identifier
    CanonicalConcept.MAC_ADDRESS: 0.90,    # burned into NIC EEPROM (IEEE-unique)
    CanonicalConcept.IMEI: 0.90,           # burned-in cellular identifier
    CanonicalConcept.UDI: 0.90,            # regulated device identifier (FDA)
    CanonicalConcept.UUID: 0.85,           # cryptographically unique, software
    CanonicalConcept.ASSET_TAG: 0.60,      # company sticker; can peel/reassign
    CanonicalConcept.BARCODE: 0.55,        # like asset tag, scannable
    CanonicalConcept.LOT_NUMBER: 0.30,     # batch, not unit-unique
    CanonicalConcept.MODEL: 0.30,          # descriptive, not unique
    CanonicalConcept.IP_ADDRESS: 0.15,     # DHCP lease; changes; NAT-shared
    CanonicalConcept.LOCATION: 0.10,       # descriptive
    CanonicalConcept.WORK_ORDER: 0.10,     # DB auto-increment; not on asset
    CanonicalConcept.NUMERIC_ID: 0.20,     # ambiguous plain number
    CanonicalConcept.ALPHANUMERIC_ID: 0.50,  # unknown structured code
    CanonicalConcept.SYSTEM_INTERNAL_ID: 0.05,  # sequential row id
    CanonicalConcept.TIMESTAMP: 0.05,      # temporal metadata
    CanonicalConcept.UNKNOWN: 0.0,
}

# A field is anchor-eligible (by weight) only at/above this threshold.
ANCHOR_WEIGHT_THRESHOLD = 0.85


def weight_of(concept: CanonicalConcept) -> float:
    return IDENTITY_WEIGHTS.get(concept, 0.0)


def is_anchor_eligible(concept: CanonicalConcept) -> bool:
    return weight_of(concept) >= ANCHOR_WEIGHT_THRESHOLD
