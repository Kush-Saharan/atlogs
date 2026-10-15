"""Pure graph-projection tests (no database)."""

from __future__ import annotations

from app.engine.graph import project_physical_graph
from app.engine.graph.model import (
    GraphLayer,
    RelationType,
    asset_node,
    concept_node,
    sr_node,
)
from app.engine.resolution import SourceRecord, resolve


def test_projection_from_resolved_cluster():
    a = SourceRecord(record_id="A", system="SAP",
                     identifiers={"serial_number": ["SN-1"], "mac_address": ["00:11:22:33:44:55"]})
    b = SourceRecord(record_id="B", system="ServiceNow",
                     identifiers={"serial_number": ["SN-1"], "asset_tag": ["AT-9"]})
    res = resolve([a, b])
    cluster = res.cluster_of("A")

    edges = project_physical_graph(res)
    asset = asset_node(cluster.cluster_id)

    # every edge is physical and rooted at the unified asset
    assert edges and all(e.layer == GraphLayer.PHYSICAL for e in edges)
    assert all(e.source_id == asset for e in edges)

    rels = {(e.relation_type, e.target_id) for e in edges}
    assert (RelationType.HAS_SOURCE_RECORD, sr_node("A")) in rels
    assert (RelationType.HAS_SOURCE_RECORD, sr_node("B")) in rels
    assert (RelationType.HAS_SERIAL, concept_node("serial_number", "SN-1")) in rels
    assert (RelationType.HAS_MAC, concept_node("mac_address", "00:11:22:33:44:55")) in rels
    # asset_tag has no dedicated relation -> generic HAS_IDENTIFIER
    assert (RelationType.HAS_IDENTIFIER, concept_node("asset_tag", "AT-9")) in rels
