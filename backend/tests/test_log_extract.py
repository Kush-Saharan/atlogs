"""Rule-based log extractor (M.4). Pure, no DB, no network."""
import asyncio
import pytest
from app.engine.log_extract import extract
from app.knowledge.terminology import key
from app.services import logs

TERMS = {key(k): v for k, v in {"brg": "bearing", "vib": "vibration", "mtr": "motor",
                                "repl": "replace", "pmp": "pump", "temp": "overheating"}.items()}
SPEC = ("On 12 August, pump P-104 experienced excessive vibration near its motor bearing. "
        "The technician replaced the bearing and tested the equipment successfully.")


def f(text, name):
    r = extract(text, TERMS)
    v = r["fields"][name]
    return v and v["value"]


def test_spec_example():
    r = extract(SPEC, TERMS)["fields"]
    assert r["date"]["value"] == "12 August"
    assert r["equipment"]["value"] == "pump P-104" and r["equipment"]["confidence"] == 0.9
    assert r["component"]["value"] == "motor bearing"
    assert r["symptom"]["value"] == "excessive vibration"
    assert r["action"]["value"] == "replace"
    assert r["outcome"]["value"] == "tested the equipment successfully"
    for v in r.values():
        assert v["source"] == "rule" and v["needs_review"] == (v["confidence"] < 0.75)
    assert SPEC[slice(*r["equipment"]["span"])] == "pump P-104"


def test_negated_action_is_not_an_action():
    r = extract("The bearing was not replaced.", TERMS)
    assert r["fields"]["action"] is None
    assert [n["field"] for n in r["negated"]] == ["action"]
    assert f("They couldn't replace the seal", "action") is None
    assert f("Seal never repaired", "action") is None


def test_negated_symptom():
    assert f("Inspected pump P-9. No leak found.", "symptom") is None
    assert f("Checked without any vibration", "symptom") is None
    assert f("No leak, but severe noise", "symptom") == "severe noise"  # comma ends scope


def test_negated_outcome():
    assert f("Pump was not tested successfully", "outcome") is None


def test_missing_fields():
    r = extract("Routine walk-round done", TERMS)["fields"]
    assert r["equipment"] is None and r["symptom"] is None and r["date"] is None
    assert extract("", TERMS)["fields"]["action"] is None


def test_abbreviations_normalised():
    r = extract("12/08/2024 pmp A-12 brg vib, repl brg", TERMS)["fields"]
    assert (r["component"]["value"], r["symptom"]["value"], r["action"]["value"]) == (
        "bearing", "vibration", "replace")
    assert r["symptom"]["confidence"] == 0.7 and r["symptom"]["needs_review"]
    assert r["date"]["value"] == "12/08/2024"
    assert f("Motor hot", "symptom") is None  # no 'hot' mapping in this table


def test_bare_test_needs_review():
    r = extract("Pump P-1 was tested.", TERMS)["fields"]["outcome"]
    assert r["needs_review"] and r["confidence"] == 0.55


def test_llm_skipped_without_key(monkeypatch):
    def boom():
        raise AssertionError("LLM must not be built without a key")
    monkeypatch.setattr("app.services.llm.get_extract_model", boom)
    res = extract("Routine walk-round done", TERMS)
    out = asyncio.run(logs.fill_with_llm("Routine walk-round done", res, ""))
    assert all(v is None for v in out["fields"].values())
