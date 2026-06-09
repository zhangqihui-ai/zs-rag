from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, CurrentUser, RequireMembership
from app.core.platform_audit_helper import audit_action
from app.db.session import get_db
from app.schemas.rag_evaluation import (
    RagAgenticComparisonRequest,
    RagAgenticComparisonResponse,
    RagBenchmarkCreate,
    RagBenchmarkResponse,
    RagEvaluationRunRequest,
    RagEvaluationRunResponse,
)
from app.services import rag_evaluation_service

router = APIRouter(prefix="/rag-evaluation", tags=["rag-evaluation"])


@router.get("/benchmarks", response_model=list[RagBenchmarkResponse])
def list_benchmarks(
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> list[RagBenchmarkResponse]:
    return rag_evaluation_service.list_benchmarks(db, space_id=current_space.id)


@router.post("/benchmarks", response_model=RagBenchmarkResponse, status_code=status.HTTP_201_CREATED)
def create_benchmark(
    payload: RagBenchmarkCreate,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> RagBenchmarkResponse:
    benchmark = rag_evaluation_service.create_benchmark(
        db,
        space_id=current_space.id,
        user_id=current_user.id,
        payload=payload,
    )
    audit_action(
        db,
        request,
        action="rag.benchmark.create",
        resource_type="rag_benchmark",
        resource_id=benchmark.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"name": benchmark.name},
    )
    db.commit()
    return benchmark


@router.get("/benchmarks/{benchmark_id}", response_model=RagBenchmarkResponse)
def get_benchmark(
    benchmark_id: int,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> RagBenchmarkResponse:
    return rag_evaluation_service.get_benchmark_or_error(
        db, space_id=current_space.id, benchmark_id=benchmark_id
    )


@router.post("/benchmarks/{benchmark_id}/runs", response_model=RagEvaluationRunResponse)
def run_benchmark(
    benchmark_id: int,
    payload: RagEvaluationRunRequest,
    request: Request,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> RagEvaluationRunResponse:
    run = rag_evaluation_service.run_benchmark_evaluation(
        db,
        space_id=current_space.id,
        benchmark_id=benchmark_id,
        user_id=current_user.id,
        retrieval_config=payload.retrieval_config,
    )
    audit_action(
        db,
        request,
        action="rag.evaluation.run",
        resource_type="rag_evaluation_run",
        resource_id=run.id,
        enterprise_space_id=current_space.id,
        user_id=current_user.id,
        detail={"benchmark_id": benchmark_id, "summary": run.summary},
    )
    db.commit()
    return run


@router.get("/benchmarks/{benchmark_id}/runs", response_model=list[RagEvaluationRunResponse])
def list_runs(
    benchmark_id: int,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> list[RagEvaluationRunResponse]:
    return rag_evaluation_service.list_evaluation_runs(
        db, space_id=current_space.id, benchmark_id=benchmark_id
    )


@router.post("/benchmarks/{benchmark_id}/agentic-comparison", response_model=RagAgenticComparisonResponse)
def compare_agentic_rag(
    benchmark_id: int,
    payload: RagAgenticComparisonRequest,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> RagAgenticComparisonResponse:
    return rag_evaluation_service.compare_agentic_rag_with_baseline(
        db,
        space_id=current_space.id,
        benchmark_id=benchmark_id,
        retrieval_config=payload.retrieval_config,
        agentic_config=payload.agentic_config,
    )


@router.get("/runs/{run_id}", response_model=RagEvaluationRunResponse)
def get_run(
    run_id: int,
    current_space: CurrentSpace,
    _: RequireMembership,
    db: Session = Depends(get_db),
) -> RagEvaluationRunResponse:
    return rag_evaluation_service.get_evaluation_run_or_error(
        db, space_id=current_space.id, run_id=run_id
    )
