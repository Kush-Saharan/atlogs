"""Layer 2 schema-discovery tests, built from the architecture doc's own
examples (Section 3 Signal tables, Section 4 industry detection, Examples 5-6).

Assertions are on classification *decisions* (role / anchor), not exact
confidence floats, per the testing-scope steering.
"""

from __future__ import annotations

import pytest

from app.engine.schema_discovery import FieldRole, discover_schema
from app.knowledge.identity import CanonicalConcept

MODELS = [
    "CR10-10", "HVAC-XV20i", "CR15-5", "CR32-2", "TP50", "NB40",
    "MAGNA3", "SP17", "CM10", "CRE20", "UPS25", "SEV80",
]
PLANTS = ["PLANT_1", "PLANT_2", "PLANT_3", "PLANT_4"]


def sample_records(n: int = 100) -> list[dict[str, object]]:
    """A manufacturing (SAP + ServiceNow-shaped) sample, per the doc's tables."""
    recs: list[dict[str, object]] = []
    for i in range(n):
        recs.append(
            {
                "serge": f"SN-{4521987 + i}",          # serial -> ANCHOR
                "equnr": str(100000421 + i),           # sequential -> internal id
                "typbz": MODELS[i % len(MODELS)],      # model -> descriptive
                "swerk": PLANTS[i % len(PLANTS)],      # plant -> location
                "herst": "Grundfos",                   # manufacturer (industry signal)
                "u_serial_no": f"SN-{4521987 + i}",    # serial -> ANCHOR
                "u_asset_tag": f"AT-{7000 + i}-A",      # asset tag -> probable
                "wo_number": f"WO-2024-{i + 1:03d}",   # work order -> transactional
                "factory_code": f"GF-{4521987 + i}-X",  # proprietary -> probable
            }
        )
    return recs


@pytest.fixture(scope="module")
def result():
    return discover_schema(sample_records())


def _field(result, name):
    return next(f for f in result.fields if f.field_name == name)


# --- Section 4: industry detection ----------------------------------------

def test_industry_detected_as_manufacturing(result):
    assert result.industry == "manufacturing"
    assert result.industry_confidence >= 0.5


# --- Section 3: Signal tables ---------------------------------------------

def test_serge_is_serial_anchor(result):
    f = _field(result, "serge")
    assert f.role == FieldRole.ANCHOR
    assert f.detected_concept == CanonicalConcept.SERIAL_NUMBER
    assert f.is_anchor is True


def test_equnr_is_internal_id_not_anchor(result):
    """The equnr trap: 100% unique but sequential -> not a physical identifier."""
    f = _field(result, "equnr")
    assert f.detected_concept == CanonicalConcept.SYSTEM_INTERNAL_ID
    assert f.role == FieldRole.INTERNAL_ID
    assert f.is_anchor is False


def test_typbz_is_descriptive_model(result):
    f = _field(result, "typbz")
    assert f.role == FieldRole.DESCRIPTIVE
    assert f.is_anchor is False


def test_swerk_is_descriptive_location(result):
    f = _field(result, "swerk")
    assert f.role == FieldRole.DESCRIPTIVE
    assert f.is_anchor is False


# --- Section 3 / Example 5: the work-order lookalike ----------------------

def test_wo_number_is_transactional_not_anchor(result):
    f = _field(result, "wo_number")
    assert f.detected_concept == CanonicalConcept.WORK_ORDER
    assert f.role == FieldRole.TRANSACTIONAL
    assert f.is_anchor is False


# --- Example 6: proprietary serial format ---------------------------------

def test_factory_code_is_probable_needs_human(result):
    f = _field(result, "factory_code")
    assert f.role == FieldRole.PROBABLE_ANCHOR
    assert f.needs_human is True
    assert f.is_anchor is False


# --- ServiceNow fields (doc admin table) ----------------------------------

def test_u_serial_no_is_anchor(result):
    f = _field(result, "u_serial_no")
    assert f.role == FieldRole.ANCHOR
    assert f.detected_concept == CanonicalConcept.SERIAL_NUMBER


def test_u_asset_tag_is_probable_weak_identifier(result):
    """Asset tag is a weak identifier (0.60) -> surfaced for human confirmation."""
    f = _field(result, "u_asset_tag")
    assert f.role == FieldRole.PROBABLE_ANCHOR
    assert f.needs_human is True


# --- overall shape ---------------------------------------------------------

def test_anchors_are_the_serials(result):
    anchor_fields = {f.field_name for f in result.anchors}
    assert anchor_fields == {"serge", "u_serial_no"}
