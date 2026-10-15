"""Evidence extractors — where each piece of evidence originates.

Currently:
  - exact-anchor: two records share a value for the same identifier concept
    (weighted by that concept's physics-based identity weight).
  - embedding: semantic similarity between the records' text (similarity is
    injected — real embeddings via pgvector/NVIDIA are wired at the API layer;
    tests inject known cosines).

Extractors are the seam for adding more signals (fuzzy match, operational
cross-checks) without changing the pipeline.
"""

from __future__ import annotations

from collections.abc import Callable

from app.knowledge.identity import CanonicalConcept, weight_of

from .models import Evidence, EvidenceKind, SourceRecord

SimilarityFn = Callable[[SourceRecord, SourceRecord], float]


def _norm_values(values: list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v and v.strip()}


def pairwise_evidence(
    a: SourceRecord, b: SourceRecord, similarity: SimilarityFn | None = None
) -> list[Evidence]:
    """All supporting evidence between two records."""
    evidence: list[Evidence] = []

    # Exact-anchor: shared value on the same identifier concept.
    for concept_str, a_vals in a.identifiers.items():
        b_vals = b.identifiers.get(concept_str)
        if not b_vals:
            continue
        shared = _norm_values(a_vals) & _norm_values(b_vals)
        if not shared:
            continue
        try:
            concept = CanonicalConcept(concept_str)
        except ValueError:
            continue
        w = weight_of(concept)
        if w <= 0:
            continue
        evidence.append(
            Evidence(
                kind=EvidenceKind.EXACT_ANCHOR,
                concept=concept,
                weight=w,
                detail=f"{concept_str}={sorted(shared)[0]}",
            )
        )

    # Embedding: semantic similarity (only when texts exist and a fn is given).
    if similarity is not None and a.semantic_text and b.semantic_text:
        sim = round(float(similarity(a, b)), 4)
        if sim > 0:
            evidence.append(
                Evidence(
                    kind=EvidenceKind.EMBEDDING,
                    concept=None,
                    weight=sim,
                    detail=f"cosine={sim:.2f}",
                )
            )

    return evidence
