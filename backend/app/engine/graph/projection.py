"""Project the resolved canonical model into Physical Graph edges.

The graph is derived from the resolution result — rebuildable at any time and
never a source of truth. This builds the PHYSICAL layer:
  asset -HAS_SOURCE_RECORD-> source record
  asset -HAS_SERIAL / HAS_MAC / HAS_IDENTIFIER-> identifier value node

Operational edges (failures, work orders, causes, rules) are added later during
document ingestion, on the OPERATIONAL layer.
"""

from __future__ import annotations

from app.engine.resolution.models import ResolutionResult

from .model import (
    Edge,
    GraphLayer,
    RelationType,
    asset_node,
    concept_node,
    sr_node,
)

_CONCEPT_RELATION = {
    "serial_number": RelationType.HAS_SERIAL,
    "mac_address": RelationType.HAS_MAC,
}


def project_physical_graph(result: ResolutionResult) -> list[Edge]:
    edges: list[Edge] = []
    for cluster in result.clusters:
        asset = asset_node(cluster.cluster_id)

        for record_id in cluster.members:
            edges.append(
                Edge(
                    source_id=asset,
                    relation_type=RelationType.HAS_SOURCE_RECORD,
                    target_id=sr_node(record_id),
                    layer=GraphLayer.PHYSICAL,
                    metadata={"member": record_id},
                )
            )

        for concept, values in cluster.identifiers.items():
            relation = _CONCEPT_RELATION.get(concept, RelationType.HAS_IDENTIFIER)
            for value in values:
                edges.append(
                    Edge(
                        source_id=asset,
                        relation_type=relation,
                        target_id=concept_node(concept, value),
                        layer=GraphLayer.PHYSICAL,
                        metadata={"concept": concept, "value": value},
                    )
                )
    return edges
