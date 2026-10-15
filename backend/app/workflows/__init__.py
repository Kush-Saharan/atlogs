"""Read-path AI workflows over the canonical model + knowledge graph.

These are grounded, controlled LangGraph workflows (not a free-roaming agent):
  - chat:       intent router dispatching to ask / rca / compliance / lookup
  - rca:        root-cause analysis over the operational graph
  - compliance: compliance posture + at-risk propagation

They read the canonical assets, identifiers, source records (+ embeddings), and
the `edges` graph produced by the ingestion write-path. Nothing is stated as
fact without a source; unknown references are flagged, never fabricated.
"""
