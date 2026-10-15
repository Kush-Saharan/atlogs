"""Regex pattern library, shipped as code (derived from ISO/IEEE/FDA/3GPP).

Each pattern validates the *structure* of a value and maps to a canonical
concept (whose identity weight lives in identity.py). Patterns are grouped so an
industry loads only the relevant set, but all are defined once here.

Precedence matters: more specific/reliable patterns are tried before generic
fallbacks (alphanumeric_id / numeric_id), so e.g. a serial isn't mislabeled as
a generic alphanumeric id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .identity import CanonicalConcept


@dataclass(frozen=True)
class Pattern:
    concept: CanonicalConcept
    regex: re.Pattern[str]

    def matches(self, value: str) -> bool:
        return bool(self.regex.match(value.strip()))


# --- individual patterns (order = precedence, most specific first) ----------
_MAC = Pattern(
    CanonicalConcept.MAC_ADDRESS,
    re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$"),
)
_UUID = Pattern(
    CanonicalConcept.UUID,
    re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
)
_VIN = Pattern(CanonicalConcept.VIN, re.compile(r"^[A-HJ-NPR-Z0-9]{17}$"))
_IMEI = Pattern(CanonicalConcept.IMEI, re.compile(r"^\d{15}$"))
_UDI = Pattern(
    CanonicalConcept.UDI, re.compile(r"^01[-\s]?\d{14}[-\s]?\d{2}[-\s]?\d{4,6}$")
)
_WORK_ORDER = Pattern(
    CanonicalConcept.WORK_ORDER,
    re.compile(r"^(WO|PM|TK)[-]?\d{2,4}(?:-\d{1,6})?$", re.IGNORECASE),
)
_IP = Pattern(
    CanonicalConcept.IP_ADDRESS,
    re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$"),
)
# Serial: conservative on purpose. Either a recognized serial prefix (SN/SER,
# optional hyphen, then alphanumerics) OR a long (>=10) unbroken mixed
# alphanumeric token (e.g. Apple-style "C02ZW1Y2MD6T"). Proprietary hyphenated
# codes like "GF-4521987-X" deliberately do NOT match — they fall to
# alphanumeric_id and get proposed to a human (doc Example 6), which is the
# intended "learn a custom pattern" behavior.
_SERIAL = Pattern(
    CanonicalConcept.SERIAL_NUMBER,
    re.compile(
        r"^(?:(?:SN|SER)[-]?[A-Za-z0-9]{2,}"
        r"|(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{10,30})$",
        re.IGNORECASE,
    ),
)
_BARCODE = Pattern(CanonicalConcept.BARCODE, re.compile(r"^\d{8,13}$"))
# Generic fallbacks.
_ALNUM = Pattern(
    CanonicalConcept.ALPHANUMERIC_ID, re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{2,}$")
)
_NUMERIC = Pattern(CanonicalConcept.NUMERIC_ID, re.compile(r"^\d+$"))

# Ordered list used for matching (specific -> generic).
ALL_PATTERNS: list[Pattern] = [
    _MAC, _UUID, _VIN, _IMEI, _UDI, _WORK_ORDER, _IP, _SERIAL, _BARCODE,
    _NUMERIC, _ALNUM,
]

# Which concepts each industry's pattern library includes (doc Section 4).
INDUSTRY_PATTERN_SETS: dict[str, list[CanonicalConcept]] = {
    "manufacturing": [
        CanonicalConcept.SERIAL_NUMBER, CanonicalConcept.MAC_ADDRESS,
        CanonicalConcept.VIN, CanonicalConcept.UUID, CanonicalConcept.WORK_ORDER,
        CanonicalConcept.BARCODE, CanonicalConcept.IP_ADDRESS,
    ],
    "healthcare": [
        CanonicalConcept.UDI, CanonicalConcept.SERIAL_NUMBER,
        CanonicalConcept.UUID, CanonicalConcept.WORK_ORDER,
    ],
    "telecom": [
        CanonicalConcept.IMEI, CanonicalConcept.MAC_ADDRESS,
        CanonicalConcept.UUID, CanonicalConcept.SERIAL_NUMBER,
    ],
    "unknown": [
        CanonicalConcept.UUID, CanonicalConcept.MAC_ADDRESS,
        CanonicalConcept.IP_ADDRESS,
    ],
}


def patterns_for_industry(industry: str) -> list[Pattern]:
    """Return the ordered pattern list for an industry (falls back to generics).

    Generic fallbacks (numeric/alphanumeric) are always appended last so any
    industry can still classify unrecognized structured codes.
    """
    concepts = set(INDUSTRY_PATTERN_SETS.get(industry, INDUSTRY_PATTERN_SETS["unknown"]))
    specific = [p for p in ALL_PATTERNS if p.concept in concepts]
    generics = [_NUMERIC, _ALNUM]
    return specific + generics


def looks_sequential(values: list[str]) -> bool:
    """True if the numeric values form a (mostly) consecutive run.

    Sequential integers are row IDs (system_internal_id), not physical
    identifiers — the doc's equnr trap.
    """
    nums: list[int] = []
    for v in values:
        v = v.strip()
        if not v.isdigit():
            return False
        nums.append(int(v))
    if len(nums) < 3:
        return False
    nums.sort()
    consecutive = sum(1 for a, b in zip(nums, nums[1:]) if b - a == 1)
    return consecutive / (len(nums) - 1) >= 0.8
