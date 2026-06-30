"""平台用量埋点写入与时间序列聚合。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.platform_usage import PlatformUsageEvent

logger = logging.getLogger(__name__)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = ZoneInfo("UTC")

UsageRange = Literal["24h", "7d", "30d"]
UsageMetric = Literal["model_calls", "tokens", "chat_api"]


def record_usage_event(
    db: Session | None = None,
    *,
    enterprise_space_id: int,
    event_type: str,
    model_type: str | None = None,
    model_id: int | None = None,
    source: str | None = None,
    knowledge_base_id: int | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    result_count: int = 0,
    user_id: int | None = None,
    commit: bool = False,
) -> None:
    """写入用量事件；失败不阻断主流程。

    使用独立 DB 会话提交，避免污染聊天/检索主事务，也避免流式接口关闭 session 时丢数据。
    ``db`` / ``commit`` 参数保留兼容，写入始终走独立会话。
    """
    _ = db, commit
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        row = PlatformUsageEvent(
            enterprise_space_id=enterprise_space_id,
            event_type=event_type,
            model_type=model_type,
            model_id=model_id,
            source=source,
            knowledge_base_id=knowledge_base_id,
            tokens_in=max(0, int(tokens_in or 0)),
            tokens_out=max(0, int(tokens_out or 0)),
            result_count=max(0, int(result_count or 0)),
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
    except Exception:
        logger.exception("record_usage_event failed (event_type=%s space=%s)", event_type, enterprise_space_id)
        try:
            session.rollback()
        except Exception:
            logger.exception("record_usage_event rollback failed")
    finally:
        session.close()


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _coerce_shanghai(ts: datetime) -> datetime:
    """Naive datetimes are treated as UTC (DB / utcnow storage)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC_TZ)
    return ts.astimezone(SHANGHAI_TZ)


def _to_utc_naive(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(UTC_TZ).replace(tzinfo=None)


def get_range_start(now: datetime, range_key: UsageRange) -> datetime:
    buckets = _build_time_buckets(_coerce_shanghai(now), range_key)
    return _to_utc_naive(buckets[0][0]) if buckets else _to_utc_naive(_coerce_shanghai(now))


def get_usage_timeseries(
    db: Session,
    *,
    space_id: int,
    range_key: UsageRange,
    metric: UsageMetric,
) -> dict[str, Any]:
    now = _now_shanghai()
    buckets = _build_time_buckets(now, range_key)
    if not buckets:
        return {"range": range_key, "metric": metric, "series": [], "total": 0}

    start = _to_utc_naive(buckets[0][0])
    rows = db.execute(
        select(
            PlatformUsageEvent.event_type,
            PlatformUsageEvent.model_type,
            PlatformUsageEvent.tokens_in,
            PlatformUsageEvent.tokens_out,
            PlatformUsageEvent.created_at,
        ).where(
            PlatformUsageEvent.enterprise_space_id == space_id,
            PlatformUsageEvent.created_at >= start,
        )
    ).all()

    return {
        "range": range_key,
        "metric": metric,
        "series": _aggregate_rows(rows, buckets, range_key, metric),
        "total": _metric_total(rows, metric),
    }


def _build_time_buckets(now: datetime, range_key: UsageRange) -> list[tuple[datetime, str]]:
    sh_now = _coerce_shanghai(now)
    buckets: list[tuple[datetime, str]] = []
    if range_key == "24h":
        anchor = sh_now.replace(minute=0, second=0, microsecond=0)
        for i in range(23, -1, -1):
            start = anchor - timedelta(hours=i)
            label = start.strftime("%H:00")
            buckets.append((start, label))
        return buckets

    if range_key == "7d":
        anchor = sh_now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(6, -1, -1):
            start = anchor - timedelta(days=i)
            label = start.strftime("%m-%d")
            buckets.append((start, label))
        return buckets

    anchor = sh_now.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(29, -1, -1):
        start = anchor - timedelta(days=i)
        label = start.strftime("%m-%d")
        buckets.append((start, label))
    return buckets


def _bucket_index(ts: datetime, buckets: list[tuple[datetime, str]], range_key: UsageRange) -> int | None:
    key = _coerce_shanghai(ts)
    if range_key == "24h":
        key = key.replace(minute=0, second=0, microsecond=0)
        for idx, (start, _) in enumerate(buckets):
            end = start + timedelta(hours=1)
            if start <= key < end:
                return idx
        return None

    key = key.replace(hour=0, minute=0, second=0, microsecond=0)
    for idx, (start, _) in enumerate(buckets):
        end = start + timedelta(days=1)
        if start <= key < end:
            return idx
    return None


def _aggregate_rows(
    rows: list[Any],
    buckets: list[tuple[datetime, str]],
    range_key: UsageRange,
    metric: UsageMetric,
) -> list[dict[str, Any]]:
    if metric == "model_calls":
        llm_counts = [0] * len(buckets)
        embed_counts = [0] * len(buckets)
        for row in rows:
            if row.event_type not in ("llm_call", "embedding_call"):
                continue
            idx = _bucket_index(row.created_at, buckets, range_key)
            if idx is None:
                continue
            if row.event_type == "llm_call":
                llm_counts[idx] += 1
            else:
                embed_counts[idx] += 1
        return [
            {
                "key": "llm",
                "label": "LLM",
                "points": [{"t": buckets[i][1], "v": llm_counts[i]} for i in range(len(buckets))],
            },
            {
                "key": "embedding",
                "label": "Embedding",
                "points": [{"t": buckets[i][1], "v": embed_counts[i]} for i in range(len(buckets))],
            },
        ]

    if metric == "tokens":
        llm_counts = [0] * len(buckets)
        embed_counts = [0] * len(buckets)
        for row in rows:
            if row.event_type not in ("llm_call", "embedding_call"):
                continue
            idx = _bucket_index(row.created_at, buckets, range_key)
            if idx is None:
                continue
            token_amt = int(row.tokens_in or 0) + int(row.tokens_out or 0)
            if row.event_type == "llm_call":
                llm_counts[idx] += token_amt
            else:
                embed_counts[idx] += token_amt
        return [
            {
                "key": "llm",
                "label": "LLM",
                "points": [{"t": buckets[i][1], "v": llm_counts[i]} for i in range(len(buckets))],
            },
            {
                "key": "embedding",
                "label": "Embedding",
                "points": [{"t": buckets[i][1], "v": embed_counts[i]} for i in range(len(buckets))],
            },
        ]

    api_counts = [0] * len(buckets)
    for row in rows:
        if row.event_type != "chat_api":
            continue
        idx = _bucket_index(row.created_at, buckets, range_key)
        if idx is None:
            continue
        api_counts[idx] += 1
    return [
        {
            "key": "chat_api",
            "label": "对话 API",
            "points": [{"t": buckets[i][1], "v": api_counts[i]} for i in range(len(buckets))],
        },
    ]


def _metric_total(rows: list[Any], metric: UsageMetric) -> int:
    if metric == "model_calls":
        return sum(1 for r in rows if r.event_type in ("llm_call", "embedding_call"))
    if metric == "tokens":
        return sum(
            int(r.tokens_in or 0) + int(r.tokens_out or 0)
            for r in rows
            if r.event_type in ("llm_call", "embedding_call")
        )
    return sum(1 for r in rows if r.event_type == "chat_api")
