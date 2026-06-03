"""RAG benchmark 评测执行。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models.rag_evaluation import (
    RagBenchmark,
    RagBenchmarkItem,
    RagEvaluationResult,
    RagEvaluationRun,
)
from app.schemas.retrieval import KnowledgeSearchRequest, MultiKnowledgeSearchRequest
from app.schemas.rag_evaluation import RagBenchmarkCreate
from app.services.retrieval_service import search_knowledge_bases_multi


def create_benchmark(
    db: Session,
    *,
    space_id: int,
    user_id: int,
    payload: RagBenchmarkCreate,
) -> RagBenchmark:
    benchmark = RagBenchmark(
        enterprise_space_id=space_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        knowledge_base_ids=list(payload.knowledge_base_ids),
        created_by_user_id=user_id,
    )
    db.add(benchmark)
    db.flush()
    for idx, item in enumerate(payload.items):
        db.add(
            RagBenchmarkItem(
                benchmark_id=benchmark.id,
                question=item.question.strip(),
                expected_answer=(item.expected_answer or "").strip() or None,
                sort_order=item.sort_order if item.sort_order else idx,
            )
        )
    db.commit()
    return get_benchmark_or_error(db, space_id=space_id, benchmark_id=benchmark.id)


def get_benchmark_or_error(db: Session, *, space_id: int, benchmark_id: int) -> RagBenchmark:
    benchmark = db.execute(
        select(RagBenchmark)
        .options(selectinload(RagBenchmark.items))
        .where(
            RagBenchmark.id == benchmark_id,
            RagBenchmark.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if benchmark is None:
        raise AppError(status_code=404, code="BENCHMARK_NOT_FOUND", message="评估基准不存在")
    return benchmark


def list_benchmarks(db: Session, *, space_id: int) -> list[RagBenchmark]:
    rows = db.execute(
        select(RagBenchmark)
        .options(selectinload(RagBenchmark.items))
        .where(RagBenchmark.enterprise_space_id == space_id)
        .order_by(RagBenchmark.updated_at.desc())
    ).scalars().all()
    return list(rows)


def run_benchmark_evaluation(
    db: Session,
    *,
    space_id: int,
    benchmark_id: int,
    user_id: int,
    retrieval_config: dict | None = None,
) -> RagEvaluationRun:
    benchmark = get_benchmark_or_error(db, space_id=space_id, benchmark_id=benchmark_id)
    if not benchmark.items:
        raise AppError(status_code=400, code="BENCHMARK_EMPTY", message="评估基准没有测试问题")

    cfg = retrieval_config or {}
    run = RagEvaluationRun(
        benchmark_id=benchmark.id,
        enterprise_space_id=space_id,
        status="running",
        retrieval_config=cfg,
        started_by_user_id=user_id,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()

    hits = 0
    total = len(benchmark.items)
    try:
        for item in sorted(benchmark.items, key=lambda row: row.sort_order):
            search_payload = MultiKnowledgeSearchRequest(
                query=item.question,
                knowledge_base_ids=list(benchmark.knowledge_base_ids),
                mode=cfg.get("mode"),
                top_k=int(cfg.get("top_k") or 5),
                score_threshold=cfg.get("score_threshold"),
                vector_weight=cfg.get("vector_weight"),
                fusion_method=cfg.get("fusion_method"),
            )
            search_result = search_knowledge_bases_multi(
                db,
                space_id=space_id,
                knowledge_base_ids=list(benchmark.knowledge_base_ids),
                payload=search_payload,
            )
            results = search_result.get("results") or []
            chunk_ids = [int(row.get("chunk_id")) for row in results if row.get("chunk_id") is not None]
            top_score = float(results[0]["score"]) if results else None
            hit = bool(results) and (top_score or 0) >= float(cfg.get("hit_score_threshold") or 0.3)
            if hit:
                hits += 1
            db.add(
                RagEvaluationResult(
                    run_id=run.id,
                    benchmark_item_id=item.id,
                    question=item.question,
                    hit=hit,
                    top_score=top_score,
                    retrieved_chunk_ids=chunk_ids,
                    detail={"total": len(results)},
                )
            )
        run.status = "completed"
        run.summary = {
            "total": total,
            "hits": hits,
            "hit_rate": round(hits / total, 4) if total else 0.0,
        }
        run.finished_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = datetime.utcnow()
        db.commit()
        raise

    db.refresh(run)
    return get_evaluation_run_or_error(db, space_id=space_id, run_id=run.id)


def get_evaluation_run_or_error(db: Session, *, space_id: int, run_id: int) -> RagEvaluationRun:
    run = db.execute(
        select(RagEvaluationRun)
        .options(selectinload(RagEvaluationRun.results))
        .where(
            RagEvaluationRun.id == run_id,
            RagEvaluationRun.enterprise_space_id == space_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise AppError(status_code=404, code="EVALUATION_RUN_NOT_FOUND", message="评测运行不存在")
    return run


def list_evaluation_runs(db: Session, *, space_id: int, benchmark_id: int) -> list[RagEvaluationRun]:
    return list(
        db.execute(
            select(RagEvaluationRun)
            .where(
                RagEvaluationRun.enterprise_space_id == space_id,
                RagEvaluationRun.benchmark_id == benchmark_id,
            )
            .order_by(RagEvaluationRun.started_at.desc())
        ).scalars().all()
    )
