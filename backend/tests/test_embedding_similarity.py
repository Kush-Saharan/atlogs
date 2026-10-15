"""Deterministic tests for the embedding-backed similarity helper (no network).

The live NVIDIA embedding call is exercised via manual/integration checks; here
we only verify the cosine math and the SimilarityFn wiring with fixed vectors.
"""

from __future__ import annotations

from app.engine.resolution.models import SourceRecord
from app.services.embeddings import build_similarity, cosine


def test_cosine_bounds():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0  # zero vector -> 0, no div error


def test_similarity_fn_uses_vectors():
    a = SourceRecord(record_id="A", system="X")
    b = SourceRecord(record_id="B", system="Y")
    c = SourceRecord(record_id="C", system="Z")
    vectors = {"A": [1.0, 0.0, 0.0], "B": [0.9, 0.1, 0.0], "C": [0.0, 0.0, 1.0]}
    sim = build_similarity(vectors)

    assert sim(a, b) > 0.9      # near-parallel -> high similarity
    assert sim(a, c) < 0.1      # orthogonal -> low
    # a record with no vector -> 0 (missing embedding never fabricates a match)
    missing = SourceRecord(record_id="Z", system="Q")
    assert sim(a, missing) == 0.0
