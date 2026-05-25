from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.kb_type import is_lightrag_kb
from app.core.neo4j_client import query_graph
from app.models.enterprise_space import EnterpriseSpace
from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument


@dataclass(frozen=True)
class Neo4jConnectionParams:
    uri: str
    username: str
    password: str | None
    database: str | None


def build_lightrag_workspace(space_id: int, kb_id: int) -> str:
    return f"space_{space_id}_kb_{kb_id}"


def sanitize_workspace_label(workspace: str) -> str:
    """Escape backticks for safe use inside Cypher backtick-quoted labels."""
    ws = (workspace or "").strip() or "base"
    return ws.replace("`", "``")


def ensure_graph_visualization_access(knowledge_base: KnowledgeBase) -> None:
    if is_lightrag_kb(knowledge_base):
        return
    raise AppError(
        status_code=400,
        code="GRAPH_VISUALIZATION_NOT_SUPPORTED",
        message="图谱可视化仅支持图知识库（kb_type=lightrag）",
    )


def resolve_neo4j_connection_params(
    knowledge_base: KnowledgeBase,
    settings: Settings | None = None,
) -> Neo4jConnectionParams:
    connection = knowledge_base.neo4j_connection
    if connection is not None and connection.is_active:
        return Neo4jConnectionParams(
            uri=connection.uri,
            username=connection.username,
            password=connection.password,
            database=connection.database,
        )

    cfg = settings or get_settings()
    if not cfg.neo4j_uri or not cfg.neo4j_username:
        raise AppError(
            status_code=503,
            code="NEO4J_NOT_CONFIGURED",
            message="Neo4j 未配置：请设置 NEO4J_URI / NEO4J_USERNAME，或为知识库配置 Neo4j 连接",
        )
    return Neo4jConnectionParams(
        uri=cfg.neo4j_uri,
        username=cfg.neo4j_username,
        password=cfg.neo4j_password,
        database=cfg.neo4j_database,
    )


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    return str(value)


def _node_props(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    return {str(k): _serialize_value(v) for k, v in raw.items()}


def _run_cypher(
    conn: Neo4jConnectionParams,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    result = query_graph(
        conn.uri,
        conn.username,
        password=conn.password,
        database=conn.database,
        cypher=cypher,
        params=params,
    )
    if not result.success:
        raise AppError(
            status_code=502,
            code="NEO4J_QUERY_FAILED",
            message=result.message,
        )
    return result.data or []


def _format_node(entity_id: str, props: dict[str, Any], degree: int) -> dict[str, Any]:
    entity_type = props.get("entity_type")
    return {
        "id": entity_id,
        "label": entity_id,
        "entity_type": str(entity_type) if entity_type is not None else None,
        "degree": int(degree or 0),
        "properties": props,
    }


def _format_edge(source: str, target: str, props: dict[str, Any]) -> dict[str, Any]:
    description = props.get("description")
    label = str(description) if description else "RELATED"
    return {
        "source": source,
        "target": target,
        "label": label,
        "properties": props,
    }


def _count_totals(workspace_label: str, conn: Neo4jConnectionParams) -> tuple[int, int]:
    node_rows = _run_cypher(
        conn,
        f"MATCH (n:`{workspace_label}`) RETURN count(n) AS node_total",
    )
    edge_rows = _run_cypher(
        conn,
        f"""
        MATCH (a:`{workspace_label}`)-[r:DIRECTED]-(b:`{workspace_label}`)
        WHERE a.entity_id IS NOT NULL AND b.entity_id IS NOT NULL
          AND a.entity_id < b.entity_id
        RETURN count(r) AS edge_total
        """,
    )
    node_total = int(node_rows[0].get("node_total", 0)) if node_rows else 0
    edge_total = int(edge_rows[0].get("edge_total", 0)) if edge_rows else 0
    return node_total, edge_total


def get_graph_stats(knowledge_base: KnowledgeBase, space: EnterpriseSpace) -> dict[str, int]:
    ensure_graph_visualization_access(knowledge_base)
    conn = resolve_neo4j_connection_params(knowledge_base)
    workspace_label = sanitize_workspace_label(
        build_lightrag_workspace(space.id, knowledge_base.id)
    )
    node_total, edge_total = _count_totals(workspace_label, conn)
    return {"node_total": node_total, "edge_total": edge_total}


def _fetch_edges_for_entity_ids(
    workspace_label: str,
    conn: Neo4jConnectionParams,
    entity_ids: list[str],
) -> list[dict[str, Any]]:
    if len(entity_ids) < 2:
        return []
    rows = _run_cypher(
        conn,
        f"""
        MATCH (a:`{workspace_label}`)-[r:DIRECTED]-(b:`{workspace_label}`)
        WHERE a.entity_id IN $entity_ids
          AND b.entity_id IN $entity_ids
          AND a.entity_id < b.entity_id
        RETURN a.entity_id AS source, b.entity_id AS target, properties(r) AS props
        """,
        {"entity_ids": entity_ids},
    )
    edges: list[dict[str, Any]] = []
    for row in rows:
        source = row.get("source")
        target = row.get("target")
        if not source or not target:
            continue
        edges.append(_format_edge(str(source), str(target), _node_props(row.get("props"))))
    return edges


def _subgraph_top_degree(
    workspace_label: str,
    conn: Neo4jConnectionParams,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _run_cypher(
        conn,
        f"""
        MATCH (n:`{workspace_label}`)
        WHERE n.entity_id IS NOT NULL
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) AS degree
        ORDER BY degree DESC, n.entity_id ASC
        LIMIT $limit
        RETURN n.entity_id AS entity_id, properties(n) AS props, degree
        """,
        {"limit": limit},
    )
    nodes: list[dict[str, Any]] = []
    entity_ids: list[str] = []
    for row in rows:
        entity_id = row.get("entity_id")
        if not entity_id:
            continue
        entity_id = str(entity_id)
        props = _node_props(row.get("props"))
        degree = int(row.get("degree") or 0)
        nodes.append(_format_node(entity_id, props, degree))
        entity_ids.append(entity_id)
    edges = _fetch_edges_for_entity_ids(workspace_label, conn, entity_ids)
    return nodes, edges


def normalize_subgraph_search_label(label: str) -> str:
    """`*` 表示全图；`*比亚迪` 等去掉前缀通配符后再做实体匹配。"""
    normalized = (label or "*").strip() or "*"
    if normalized == "*":
        return "*"
    while normalized.startswith("*") and len(normalized) > 1:
        normalized = normalized[1:].strip()
    return normalized or "*"


def _find_center_entity_id(
    workspace_label: str,
    conn: Neo4jConnectionParams,
    label: str,
) -> str | None:
    rows = _run_cypher(
        conn,
        f"""
        MATCH (n:`{workspace_label}`)
        WHERE n.entity_id IS NOT NULL
          AND (
            n.entity_id = $label
            OR toLower(n.entity_id) CONTAINS toLower($label)
            OR toLower(coalesce(n.description, '')) CONTAINS toLower($label)
            OR toLower(coalesce(n.file_path, '')) CONTAINS toLower($label)
          )
        WITH n, count {{ (n)-[]-() }} AS degree
        ORDER BY
          CASE WHEN n.entity_id = $label THEN 0 ELSE 1 END,
          CASE WHEN toLower(n.entity_id) CONTAINS toLower($label) THEN 0 ELSE 1 END,
          degree DESC,
          n.entity_id ASC
        LIMIT 1
        RETURN n.entity_id AS entity_id
        """,
        {"label": label},
    )
    if not rows:
        return None
    entity_id = rows[0].get("entity_id")
    return str(entity_id) if entity_id else None


def _subgraph_ego(
    workspace_label: str,
    conn: Neo4jConnectionParams,
    label: str,
    limit: int,
    depth: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    center_id = _find_center_entity_id(workspace_label, conn, label)
    if center_id is None:
        return [], []

    depth = max(1, min(depth, 3))
    rows = _run_cypher(
        conn,
        f"""
        MATCH (center:`{workspace_label}` {{entity_id: $center_id}})
        MATCH (n:`{workspace_label}`)
        WHERE n.entity_id IS NOT NULL
          AND (
            n = center
            OR EXISTS {{
              MATCH (center)-[*1..{depth}]-(n)
            }}
          )
        WITH n, count {{ (n)-[]-() }} AS degree
        ORDER BY
          CASE WHEN n.entity_id = $center_id THEN 0 ELSE 1 END,
          degree DESC,
          n.entity_id ASC
        LIMIT $limit
        RETURN n.entity_id AS entity_id, properties(n) AS props, degree
        """,
        {"center_id": center_id, "limit": limit},
    )
    nodes: list[dict[str, Any]] = []
    entity_ids: list[str] = []
    for row in rows:
        entity_id = row.get("entity_id")
        if not entity_id:
            continue
        entity_id = str(entity_id)
        props = _node_props(row.get("props"))
        degree = int(row.get("degree") or 0)
        nodes.append(_format_node(entity_id, props, degree))
        entity_ids.append(entity_id)
    edges = _fetch_edges_for_entity_ids(workspace_label, conn, entity_ids)
    return nodes, edges


def get_subgraph(
    knowledge_base: KnowledgeBase,
    space: EnterpriseSpace,
    *,
    label: str = "*",
    limit: int = 100,
    depth: int = 1,
) -> dict[str, Any]:
    ensure_graph_visualization_access(knowledge_base)
    conn = resolve_neo4j_connection_params(knowledge_base)
    workspace_label = sanitize_workspace_label(
        build_lightrag_workspace(space.id, knowledge_base.id)
    )
    limit = max(1, min(limit, 500))
    depth = max(1, min(depth, 3))

    node_total, edge_total = _count_totals(workspace_label, conn)
    normalized_label = normalize_subgraph_search_label(label)

    if normalized_label == "*":
        nodes, edges = _subgraph_top_degree(workspace_label, conn, limit)
    else:
        nodes, edges = _subgraph_ego(workspace_label, conn, normalized_label, limit, depth)

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_shown": len(nodes),
            "edge_shown": len(edges),
            "node_total": node_total,
            "edge_total": edge_total,
        },
    }


def _resolve_document_id(
    db: Session | None,
    knowledge_base: KnowledgeBase,
    file_path: Any,
) -> int | None:
    if db is None or not file_path:
        return None
    raw = str(file_path).split("|||")[0].strip()
    if not raw:
        return None
    base_name = os.path.basename(raw.replace("\\", "/"))
    for candidate in (raw, base_name):
        doc_id = db.execute(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.knowledge_base_id == knowledge_base.id,
                KnowledgeDocument.file_name == candidate,
            )
            .limit(1)
        ).scalar_one_or_none()
        if doc_id is not None:
            return int(doc_id)
    doc_id = db.execute(
        select(KnowledgeDocument.id)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.document_name == base_name,
        )
        .limit(1)
    ).scalar_one_or_none()
    return int(doc_id) if doc_id is not None else None


def get_node_detail(
    knowledge_base: KnowledgeBase,
    space: EnterpriseSpace,
    entity_id: str,
    db: Session | None = None,
) -> dict[str, Any]:
    ensure_graph_visualization_access(knowledge_base)
    conn = resolve_neo4j_connection_params(knowledge_base)
    workspace_label = sanitize_workspace_label(
        build_lightrag_workspace(space.id, knowledge_base.id)
    )
    rows = _run_cypher(
        conn,
        f"""
        MATCH (n:`{workspace_label}` {{entity_id: $entity_id}})
        OPTIONAL MATCH (n)-[r]-()
        RETURN properties(n) AS props, count(r) AS degree
        """,
        {"entity_id": entity_id},
    )
    if not rows:
        raise AppError(
            status_code=404,
            code="GRAPH_NODE_NOT_FOUND",
            message=f"实体不存在：{entity_id}",
        )
    props = _node_props(rows[0].get("props"))
    degree = int(rows[0].get("degree") or 0)
    created_at = props.get("created_at")
    entity_type = props.get("entity_type")
    source_id = props.get("source_id")
    file_path = props.get("file_path")
    tags: list[str] = []
    if entity_type:
        tags.append(str(entity_type))
    if source_id:
        for part in str(source_id).split("|||"):
            part = part.strip()
            if part and part not in tags:
                tags.append(part)
    return {
        "id": entity_id,
        "label": entity_id,
        "entity_type": str(entity_type) if entity_type is not None else None,
        "description": str(props["description"]) if props.get("description") is not None else None,
        "source_id": str(source_id) if source_id is not None else None,
        "file_path": str(file_path) if file_path is not None else None,
        "created_at": str(created_at) if created_at is not None else None,
        "degree": degree,
        "tags": tags,
        "properties": props,
        "document_id": _resolve_document_id(db, knowledge_base, file_path),
    }


def _build_graphml(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    graphml = ET.Element(
        "graphml",
        attrib={
            "xmlns": "http://graphml.graphdrawing.org/xmlns",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd",
        },
    )
    for key_name, attr_name, attr_type in (
        ("entity_type", "entity_type", "string"),
        ("description", "description", "string"),
        ("degree", "degree", "int"),
    ):
        ET.SubElement(
            graphml,
            "key",
            id=key_name,
            **{"for": "node", "attr.name": attr_name, "attr.type": attr_type},
        )
    ET.SubElement(
        graphml,
        "key",
        id="edge_label",
        **{"for": "edge", "attr.name": "label", "attr.type": "string"},
    )
    graph = ET.SubElement(graphml, "graph", id="G", edgedefault="undirected")
    for node in nodes:
        node_el = ET.SubElement(graph, "node", id=str(node["id"]))
        if node.get("entity_type") is not None:
            ET.SubElement(node_el, "data", key="entity_type").text = str(node["entity_type"])
        props = node.get("properties") or {}
        if props.get("description") is not None:
            ET.SubElement(node_el, "data", key="description").text = str(props["description"])
        ET.SubElement(node_el, "data", key="degree").text = str(node.get("degree", 0))
    for index, edge in enumerate(edges):
        edge_el = ET.SubElement(
            graph,
            "edge",
            id=f"e{index}",
            source=str(edge["source"]),
            target=str(edge["target"]),
        )
        if edge.get("label") is not None:
            ET.SubElement(edge_el, "data", key="edge_label").text = str(edge["label"])
    return ET.tostring(graphml, encoding="unicode")


def export_subgraph(
    knowledge_base: KnowledgeBase,
    space: EnterpriseSpace,
    *,
    label: str = "*",
    limit: int = 100,
    depth: int = 1,
    export_format: str = "json",
) -> dict[str, Any] | str:
    subgraph = get_subgraph(
        knowledge_base,
        space,
        label=label,
        limit=limit,
        depth=depth,
    )
    workspace = build_lightrag_workspace(space.id, knowledge_base.id)
    normalized_label = (label or "*").strip() or "*"
    metadata = {
        "knowledge_base_id": knowledge_base.id,
        "workspace": workspace,
        "label": normalized_label,
        "limit": limit,
        "depth": depth,
        "exported_at": datetime.now(timezone.utc),
        "format": export_format,
    }
    if export_format == "graphml":
        return _build_graphml(subgraph["nodes"], subgraph["edges"])
    return {
        "metadata": metadata,
        "nodes": subgraph["nodes"],
        "edges": subgraph["edges"],
        "stats": subgraph["stats"],
    }
