"""ConfidenceEngine — pluggable scoring of evidence into an explainable score.

The aggregation algorithm is an implementation detail behind this interface
(weighted voting today; Bayesian / logistic / learned later) — swappable without
touching the resolution pipeline. Authority is intentionally NOT a factor here;
it only arbitrates conflicts in the engine, not the strength of agreeing evidence.
"""

from __future__ import annotations

from typing import Protocol

from .models import Evidence, EvidenceKind, ExplainableScore
from .thresholds import EMBED_MIN


class ConfidenceEngine(Protocol):
    def score(
        self, evidence: list[Evidence], conflict_penalty: float = 1.0
    ) -> ExplainableScore: ...


class WeightedConfidenceEngine:
    """Doc Section 5: confidence = base x redundancy_bonus x conflict_penalty.

    - base: the highest-weight single piece of match evidence.
    - redundancy: independent matching signals (distinct anchor concepts, plus
      embedding as one signal) -> 1 field 1.0, 2 fields 1.05, 3+ fields 1.08;
      +0.03 when an exact anchor AND an embedding both agree.
    - conflict_penalty: supplied by the caller based on cluster contradictions.
    """

    def score(
        self, evidence: list[Evidence], conflict_penalty: float = 1.0
    ) -> ExplainableScore:
        if not evidence:
            return ExplainableScore(
                score=0.0, base=0.0, redundancy_bonus=1.0,
                conflict_penalty=conflict_penalty, rationale="no evidence",
            )

        base = max(e.weight for e in evidence)
        anchor_concepts = {
            e.concept for e in evidence if e.kind == EvidenceKind.EXACT_ANCHOR and e.concept
        }
        has_embedding = any(
            e.kind == EvidenceKind.EMBEDDING and e.weight >= EMBED_MIN for e in evidence
        )
        signals = len(anchor_concepts) + (1 if has_embedding else 0)

        bonus = 1.08 if signals >= 3 else 1.05 if signals == 2 else 1.0
        if anchor_concepts and has_embedding:
            bonus += 0.03

        score = min(1.0, base * bonus * conflict_penalty)
        rationale = (
            f"base={base:.2f} x bonus={bonus:.2f} x penalty={conflict_penalty:.2f} "
            f"({len(anchor_concepts)} anchor concept(s)"
            + (", +embedding" if has_embedding else "")
            + ")"
        )
        return ExplainableScore(
            score=round(score, 4),
            base=base,
            redundancy_bonus=round(bonus, 3),
            conflict_penalty=conflict_penalty,
            evidence=list(evidence),
            rationale=rationale,
        )
