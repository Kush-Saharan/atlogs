"""Layer 4 — Knowledge Graph (in Postgres, NOT a graph database).

The graph is a PROJECTION of the resolved canonical model, stored in the
`edges` table and traversed with recursive CTEs. See the Tech Stack decision
log for why this replaces Neo4j.
"""

from .model import Edge, GraphLayer, RelationType, asset_node, concept_node, sr_node
from .projection import project_physical_graph
from .store import GraphStore

__all__ = [
    "Edge",
    "GraphLayer",
    "RelationType",
    "asset_node",
    "concept_node",
    "sr_node",
    "project_physical_graph",
    "GraphStore",
]
