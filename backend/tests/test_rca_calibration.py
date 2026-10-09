"""RCA confidence calibration: confidence must track evidence, not eagerness.

Pure-function tests (no LLM/DB): a hypothesis can only be confident when it is
GROUNDED (cites real evidence) and, ideally, a resolving upstream cause exists;
thin/ungrounded claims are capped low.
"""

from __future__ import annotations

from app.workflows.rca import _calibrate_confidence


def _report(hyps, contradictions=None):
    return {"hypotheses": hyps, "contradictions": contradictions or []}


def test_ungrounded_hypothesis_is_capped_low_even_if_model_is_certain():
    ev = {"observed_failures": [{"citation": "INC-1", "detail": "x"}]}
    rep = _calibrate_confidence(
        _report([{"cause": "c", "explanation": "e", "evidence": [], "confidence": 0.95}]),
        ev,
    )
    assert rep["hypotheses"][0]["confidence"] <= 0.40


def test_grounded_hypothesis_without_upstream_is_moderate():
    ev = {"observed_failures": [{"citation": "INC-1", "detail": "x"}]}
    rep = _calibrate_confidence(
        _report(
            [{"cause": "c", "explanation": "e", "evidence": ["INC-1"], "confidence": 0.9}]
        ),
        ev,
    )
    # grounded (+0.25) over base 0.45 = 0.70, capped below the model's 0.9
    assert rep["hypotheses"][0]["confidence"] == 0.70


def test_grounded_with_resolving_upstream_can_be_high():
    ev = {
        "observed_failures": [{"citation": "INC-2", "detail": "packet loss"}],
        "upstream_failures": [{"citation": "UP-1", "depends_on": "ua-switch"}],
    }
    rep = _calibrate_confidence(
        _report(
            [
                {
                    "cause": "upstream switch fault",
                    "explanation": "the depended-on switch failed",
                    "evidence": ["UP-1"],
                    "confidence": 0.95,
                }
            ]
        ),
        ev,
    )
    # base .45 + grounded .25 + resolving upstream .20 = .90
    assert rep["hypotheses"][0]["confidence"] == 0.90


def test_confidence_never_reaches_absolute_certainty():
    ev = {
        "observed_failures": [
            {"citation": "INC-1"},
            {"citation": "INC-2"},
        ],
        "upstream_failures": [{"citation": "UP-1", "depends_on": "ua-x"}],
    }
    rep = _calibrate_confidence(
        _report(
            [{"cause": "c", "explanation": "upstream", "evidence": ["UP-1", "INC-1"], "confidence": 1.0}]
        ),
        ev,
    )
    assert rep["hypotheses"][0]["confidence"] <= 0.98


def test_contradictions_lower_the_ceiling():
    ev = {"observed_failures": [{"citation": "INC-1"}]}
    rep = _calibrate_confidence(
        _report(
            [{"cause": "c", "explanation": "e", "evidence": ["INC-1"], "confidence": 0.9}],
            contradictions=["conflicting reading A", "conflicting reading B"],
        ),
        ev,
    )
    # grounded 0.70 minus 2*0.08 = 0.54
    assert abs(rep["hypotheses"][0]["confidence"] - 0.54) < 1e-6
