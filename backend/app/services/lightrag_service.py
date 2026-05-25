from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.kb_type import build_lightrag_workspace, sanitize_workspace_label
from app.core.neo4j_runtime import Neo4jConnParams, resolve_neo4j_params, run_neo4j_read
from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument


def _node_entity_type(node_props: dict[str, Any], workspace_label: str) -> str | None:
    raw = node_props.get("entity_type")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    labels = node_props.get("labels")
    if isinstance(labels, list):
        for label in labels:
            if label and label != workspace_label:
                return str(label)
    return None


def _serialize_node(node: dict[str, Any], workspace_label: str, degree: int = 0) -> dict[str, Any]:
    entity_id = str(node.get("entity_id") or node.get("id") or "")
    return {
        "id": entity_id,
        "label": entity_id,
        "entity_type": _node_entity_type(node, workspace_label),
        "degree": degree,
        "properties": node,
    }


def _serialize_edge(
    rel: dict[str, Any] | None,
    source: str,
    target: str,
) -> dict[str, Any]:
    props = dict(rel or {})
    keywords = props.get("keywords")
    label = str(keywords) if keywords else props.get("description")
    if label is not None:
        label = str(label)[:120]
    return {
        "source": source,
        "target": target,
        "label": label,
        "properties": props,
    }


def get_graph_stats(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
) -> dict[str, int]:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    label = sanitize_workspace_label(workspace)
    params = resolve_neo4j_params(db, knowledge_base)
    node_rows = run_neo4j_read(
        params,
        f"MATCH (n:`{label}`) RETURN count(n) AS total",
    )
    edge_rows = run_neo4j_read(
        params,
        f"""
        MATCH (a:`{label}`)-[r:DIRECTED]-(b:`{label}`)
        RETURN count(r) AS total
        """,
    )
    return {
        "node_total": int(node_rows[0]["total"]) if node_rows else 0,
        "edge_total": int(edge_rows[0]["total"]) if edge_rows else 0,
    }


def _resolve_entity_id(
    params: Neo4jConnParams,
    workspace_label: str,
    label_query: str,
) -> str | None:
    exact = run_neo4j_read(
        params,
        f"""
        MATCH (n:`{workspace_label}` {{entity_id: $entity_id}})
        RETURN n.entity_id AS entity_id
        LIMIT 1
        """,
        {"entity_id": label_query},
    )
    if exact:
        return str(exact[0]["entity_id"])
    fuzzy = run_neo4j_read(
        params,
        f"""
        MATCH (n:`{workspace_label}`)
        WHERE n.entity_id CONTAINS $q
           OR toLower(n.entity_id) CONTAINS toLower($q)
        RETURN n.entity_id AS entity_id
        ORDER BY size(n.entity_id)
        LIMIT 1
        """,
        {"q": label_query},
    )
    if fuzzy:
        return str(fuzzy[0]["entity_id"])
    return None


def _append_edges_from_rows(
    edge_rows: list[Any],
    nodes_map: dict[str, dict[str, Any]],
    edges_list: list[dict[str, Any]],
    seen_edges: set[tuple[str, str]],
) -> None:
    for row in edge_rows:
        if not row:
            continue
        data = dict(row) if hasattr(row, "items") else row
        if not isinstance(data, dict):
            continue
        src = str(data.get("source") or "")
        tgt = str(data.get("target") or "")
        if not src or not tgt or src == tgt:
            continue
        key = tuple(sorted((src, tgt)))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        if src not in nodes_map or tgt not in nodes_map:
            continue
        rel_props = data.get("properties")
        props = dict(rel_props) if hasattr(rel_props, "items") else (rel_props or {})
        edges_list.append(_serialize_edge(props if isinstance(props, dict) else {}, src, tgt))


def _node_degrees_batch(
    params: Neo4jConnParams,
    workspace_label: str,
    entity_ids: list[str],
) -> dict[str, int]:
    if not entity_ids:
        return {}
    rows = run_neo4j_read(
        params,
        f"""
        UNWIND $node_ids AS id
        MATCH (n:`{workspace_label}` {{entity_id: id}})
        RETURN n.entity_id AS entity_id, count {{ (n)--() }} AS degree
        """,
        {"node_ids": entity_ids},
    )
    return {str(r["entity_id"]): int(r["degree"]) for r in rows}


def get_subgraph(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    label: str = "*",
    limit: int = 100,
    depth: int = 1,
) -> dict[str, Any]:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    workspace_label = sanitize_workspace_label(workspace)
    params = resolve_neo4j_params(db, knowledge_base)
    totals = get_graph_stats(db, knowledge_base=knowledge_base)
    limit = max(1, min(limit, 500))
    depth = max(1, min(depth, 2))

    label_query = (label or "*").strip() or "*"
    nodes_map: dict[str, dict[str, Any]] = {}
    edges_list: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    if label_query == "*":
        rows = run_neo4j_read(
            params,
            f"""
            MATCH (n:`{workspace_label}`)
            OPTIONAL MATCH (n)-[r:DIRECTED]-()
            WITH n, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            WITH collect(n) AS kept
            UNWIND kept AS a
            UNWIND kept AS b
            OPTIONAL MATCH (a)-[rel:DIRECTED]-(b)
            WHERE id(a) < id(b)
            RETURN kept AS nodes,
                   collect(DISTINCT {{
                     source: a.entity_id,
                     target: b.entity_id,
                     properties: properties(rel)
                   }}) AS edge_rows
            """,
            {"limit": limit},
        )
        if rows:
            kept_nodes = rows[0].get("nodes") or []
            edge_rows = rows[0].get("edge_rows") or []
            entity_ids = [
                str(dict(n).get("entity_id"))
                for n in kept_nodes
                if dict(n).get("entity_id")
            ]
            degree_map = _node_degrees_batch(params, workspace_label, entity_ids)
            for raw in kept_nodes:
                props = dict(raw)
                eid = str(props.get("entity_id") or "")
                if not eid:
                    continue
                nodes_map[eid] = _serialize_node(props, workspace_label, degree_map.get(eid, 0))
            _append_edges_from_rows(edge_rows, nodes_map, edges_list, seen_edges)
    else:
        entity_id = _resolve_entity_id(params, workspace_label, label_query)
        if entity_id:
            hop = depth
            rows = run_neo4j_read(
                params,
                f"""
                MATCH (start:`{workspace_label}` {{entity_id: $entity_id}})
                OPTIONAL MATCH p = (start)-[:DIRECTED*0..{hop}]-(other:`{workspace_label}`)
                WITH start, collect(DISTINCT other) AS others
                WITH [start] + others AS all_nodes
                UNWIND all_nodes AS a
                UNWIND all_nodes AS b
                OPTIONAL MATCH (a)-[rel:DIRECTED]-(b)
                WHERE id(a) <= id(b)
                RETURN all_nodes AS nodes,
                       collect(DISTINCT {{
                         source: a.entity_id,
                         target: b.entity_id,
                         properties: properties(rel)
                       }}) AS edge_rows
                LIMIT 1
                """,
                {"entity_id": entity_id},
            )
            if rows:
                all_nodes = rows[0].get("nodes") or []
                edge_rows = rows[0].get("edge_rows") or []
                entity_ids = [
                    str(dict(n).get("entity_id"))
                    for n in all_nodes
                    if dict(n).get("entity_id")
                ][:limit]
                degree_map = _node_degrees_batch(params, workspace_label, entity_ids)
                for raw in all_nodes[:limit]:
                    props = dict(raw)
                    eid = str(props.get("entity_id") or "")
                    if not eid:
                        continue
                    nodes_map[eid] = _serialize_node(props, workspace_label, degree_map.get(eid, 0))
                _append_edges_from_rows(edge_rows, nodes_map, edges_list, seen_edges)

    nodes = list(nodes_map.values())[:limit]
    return {
        "nodes": nodes,
        "edges": edges_list,
        "stats": {
            "node_shown": len(nodes),
            "edge_shown": len(edges_list),
            "node_total": totals["node_total"],
            "edge_total": totals["edge_total"],
        },
    }


def get_node_detail(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    entity_id: str,
) -> dict[str, Any]:
    workspace = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    workspace_label = sanitize_workspace_label(workspace)
    params = resolve_neo4j_params(db, knowledge_base)
    rows = run_neo4j_read(
        params,
        f"MATCH (n:`{workspace_label}` {{entity_id: $entity_id}}) RETURN n AS node LIMIT 1",
        {"entity_id": entity_id},
    )
    if not rows:
        raise AppError(status_code=404, code="GRAPH_NODE_NOT_FOUND", message="图谱节点不存在")
    node = dict(rows[0]["node"])
    eid = str(node.get("entity_id") or entity_id)
    degree_rows = run_neo4j_read(
        params,
        f"""
        MATCH (n:`{workspace_label}` {{entity_id: $entity_id}})
        OPTIONAL MATCH (n)-[r]-()
        RETURN count(r) AS degree
        """,
        {"entity_id": eid},
    )
    degree = int(degree_rows[0]["degree"]) if degree_rows else 0
    entity_type = _node_entity_type(node, workspace_label)
    tags: list[str] = []
    if entity_type:
        tags.append(entity_type)
    source_id = node.get("source_id")
    if source_id:
        for part in str(source_id).split("|||"):
            part = part.strip()
            if part and part not in tags:
                tags.append(part)
    file_path = node.get("file_path")
    document_id = _resolve_document_id(db, knowledge_base, file_path)
    return {
        "id": eid,
        "label": eid,
        "entity_type": entity_type,
        "degree": degree,
        "description": str(node.get("description")) if node.get("description") is not None else None,
        "file_path": str(file_path) if file_path is not None else None,
        "source_id": str(source_id) if source_id is not None else None,
        "created_at": str(node.get("created_at")) if node.get("created_at") is not None else None,
        "tags": tags,
        "properties": node,
        "document_id": document_id,
    }


def _resolve_document_id(
    db: Session,
    knowledge_base: KnowledgeBase,
    file_path: Any,
) -> int | None:
    if not file_path:
        return None
    raw = str(file_path).split("|||")[0].strip()
    if not raw:
        return None
    base_name = os.path.basename(raw.replace("\\", "/"))
    for name in (raw, base_name):
        doc = db.execute(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.knowledge_base_id == knowledge_base.id,
                KnowledgeDocument.file_name == name,
            )
            .limit(1)
        ).scalar_one_or_none()
        if doc is not None:
            return int(doc)
    doc = db.execute(
        select(KnowledgeDocument.id)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeDocument.document_name == base_name,
        )
        .limit(1)
    ).scalar_one_or_none()
    return int(doc) if doc is not None else None


def export_subgraph(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    label: str = "*",
    limit: int = 100,
    depth: int = 1,
) -> dict[str, Any]:
    payload = get_subgraph(
        db,
        knowledge_base=knowledge_base,
        label=label,
        limit=limit,
        depth=depth,
    )
    payload["workspace"] = build_lightrag_workspace(knowledge_base.enterprise_space_id, knowledge_base.id)
    payload["label_query"] = label
    return payload
