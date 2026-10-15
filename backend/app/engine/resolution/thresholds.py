"""Decision thresholds and conflict penalties (doc Section 5).

Kept in one place so they can be made per-corpus configurable later. These are
policy constants, deliberately separate from the ConfidenceEngine's aggregation
math.
"""

from __future__ import annotations

# Decision bands on a pair/cluster confidence.
AUTO_MERGE = 0.95   # >= : merge without human review
SUGGEST = 0.80      # [SUGGEST, AUTO_MERGE): suggest merge, admin confirms
REVIEW_FLOOR = 0.60  # [REVIEW_FLOOR, SUGGEST): flag for investigation; below: no match

# Embedding evidence below this contributes no mergeable edge on its own.
EMBED_MIN = 0.60

# Conflict severity: a contradicting identifier heavier than this is "high".
HIGH_CONFLICT_WEIGHT = 0.85
PENALTY_HIGH = 0.40      # high-weight identifier conflict
PENALTY_MEDIUM = 0.80    # medium-weight identifier conflict
PENALTY_NONE = 1.0
