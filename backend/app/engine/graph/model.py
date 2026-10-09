"""Graph node/edge model and node-id conventions.

Nodes are referenced by string ids with a type prefix so a single `edges` table
can hold the whole graph. Only the allowed entity kinds get nodes (assets,
components, sensors, work orders, incidents/failures, causes, rules, etc.) —
never dates or raw numbers (those are edge metadata).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GraphLayer(str, Enum):
    PHYSICAL = "physical"        # equipment structure; changes rarely
    OPERATIONAL = "operational"  # incidents/work orders/documents; changes constantly


class RelationType(str, Enum):
    # physical (from the canonical model projection)
    HAS_SOURCE_RECORD = "HAS_SOURCE_RECORD"
    HAS_SERIAL = "HAS_SERIAL"
    HAS_MAC = "HAS_MAC"
    HAS_IDENTIFIER = "HAS_IDENTIFIER"
    HAS_SENSOR = "HAS_SENSOR"
    LOCATED_IN = "LOCATED_IN"
    SUBJECT_TO = "SUBJECT_TO"
    DEPENDS_ON = "DEPENDS_ON"   # asset -> upstream asset it relies on (for multi-hop RCA)
    # operational (from document ingestion / events)
    HAS_WORK_ORDER = "HAS_WORK_ORDER"
    HAS_FAILURE = "HAS_FAILURE"
    MAY_BE_CAUSED_BY = "MAY_BE_CAUSED_BY"
    VIOLATES = "VIOLATES"


class Edge(BaseModel):
    source_id: str
    relation_type: RelationType
    target_id: str
    layer: GraphLayer
    metadata: dict[str, Any] = Field(default_factory=dict)


def _norm(value: str) -> str:
    return value.strip().lower()


# --- node id helpers (stable, prefixed) ------------------------------------
def asset_node(unified_id: str) -> str:
    return f"asset:{unified_id}"


def sr_node(record_id: str) -> str:
    return f"sr:{record_id}"


def concept_node(concept: str, value: str) -> str:
    return f"{concept}:{_norm(value)}"


def failure_node(name: str) -> str:
    return f"fm:{name}"


def cause_node(name: str) -> str:
    return f"cf:{name}"


def rule_node(rule_id: str) -> str:
    return f"rule:{rule_id}"


def work_order_node(wo_id: str) -> str:
    return f"wo:{wo_id}"


def sensor_node(sensor_id: str) -> str:
    return f"sensor:{sensor_id}"
