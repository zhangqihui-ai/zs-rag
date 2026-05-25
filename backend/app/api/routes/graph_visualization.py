from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.core.kb_type import ensure_lightrag_kb
from app.db.session import get_db
from app.models.enterprise_space import EnterpriseSpace
from app.schemas.graph_visualization import (
    GraphNodeDetailResponse,
    GraphStats,
    GraphSubgraphResponse,
)
from app.services.graph_visualization_service import (
    export_subgraph,
    get_graph_stats,
    get_node_detail,
    get_subgraph,
)
from app.services.knowledge_base_service import get_knowledge_base_or_error

router = APIRouter(prefix="/knowledge-bases", tags=["graph-visualization"])


def _load_lightrag_kb(db: Session, space: EnterpriseSpace, kb_id: int):
    kb = get_knowledge_base_or_error(db, space_id=space.id, kb_id=kb_id)
    ensure_lightrag_kb(kb)
    return kb


@router.get("/{kb_id}/graph/stats", response_model=GraphStats)
def graph_stats(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> GraphStats:
    kb = _load_lightrag_kb(db, current_space, kb_id)
    data = get_graph_stats(kb, current_space)
    return GraphStats(**data)


@router.get("/{kb_id}/graph/subgraph", response_model=GraphSubgraphResponse)
def graph_subgraph(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    label: str = Query("*", description="实体名或 * 表示按度数取 Top N"),
    limit: int = Query(100, ge=1, le=500),
    depth: int = Query(1, ge=1, le=2),
) -> GraphSubgraphResponse:
    kb = _load_lightrag_kb(db, current_space, kb_id)
    data = get_subgraph(kb, current_space, label=label, limit=limit, depth=depth)
    return GraphSubgraphResponse(**data)


@router.get("/{kb_id}/graph/nodes/{entity_id}", response_model=GraphNodeDetailResponse)
def graph_node_detail(
    kb_id: int,
    entity_id: str,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> GraphNodeDetailResponse:
    kb = _load_lightrag_kb(db, current_space, kb_id)
    data = get_node_detail(kb, current_space, entity_id, db=db)
    return GraphNodeDetailResponse(**data)


@router.get("/{kb_id}/graph/export")
def graph_export(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    label: str = Query("*"),
    limit: int = Query(100, ge=1, le=500),
    depth: int = Query(1, ge=1, le=2),
    format: str = Query("json", alias="format", description="json 或 graphml"),
):
    kb = _load_lightrag_kb(db, current_space, kb_id)
    export_format = "graphml" if format.lower() == "graphml" else "json"
    payload = export_subgraph(
        kb,
        current_space,
        label=label,
        limit=limit,
        depth=depth,
        export_format=export_format,
    )
    if export_format == "graphml":
        return PlainTextResponse(
            content=str(payload),
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="graph-kb-{kb_id}.graphml"',
            },
        )
    return JSONResponse(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="graph-kb-{kb_id}.json"',
        },
    )
