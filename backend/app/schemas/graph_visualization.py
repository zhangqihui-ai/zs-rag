from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphStats(BaseModel):
    node_total: int = 0
    edge_total: int = 0


class GraphSubgraphStats(BaseModel):
    node_shown: int = 0
    edge_shown: int = 0
    node_total: int = 0
    edge_total: int = 0


class GraphNodeItem(BaseModel):
    id: str
    label: str
    entity_type: str | None = None
    degree: int = 0
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeItem(BaseModel):
    source: str
    target: str
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSubgraphResponse(BaseModel):
    nodes: list[GraphNodeItem]
    edges: list[GraphEdgeItem]
    stats: GraphSubgraphStats


class GraphNodeDetailResponse(BaseModel):
    id: str
    label: str
    entity_type: str | None = None
    degree: int = 0
    description: str | None = None
    file_path: str | None = None
    source_id: str | None = None
    created_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    document_id: int | None = None
