"""Layer 3 — Entity Resolution.

Evidence-based, three-phase resolution (doc Section 5):
  anchor matching -> embedding matching -> conflict audit.

Design (agreed): Evidence, Confidence, and Authority are separate concerns.
The ConfidenceEngine is a pluggable interface; the default is weighted voting.
"""

from .engine import resolve
from .models import (
    Cluster,
    Evidence,
    EvidenceKind,
    ExplainableScore,
    MergeDecision,
    ResolutionResult,
    ReviewItem,
    SourceRecord,
)

__all__ = [
    "resolve",
    "Cluster",
    "Evidence",
    "EvidenceKind",
    "ExplainableScore",
    "MergeDecision",
    "ResolutionResult",
    "ReviewItem",
    "SourceRecord",
]
