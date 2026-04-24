from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

try:
    from pymilvus import MilvusClient

    MILVUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    MilvusClient = None  # type: ignore
    MILVUS_AVAILABLE = False


@dataclass
class MilvusResult:
    success: bool
    message: str
    response_time_ms: float
    data: Any | None = None


def _build_uri(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _build_client(host: str, port: int, username: str | None = None, password: str | None = None) -> MilvusClient:
    if not MILVUS_AVAILABLE or MilvusClient is None:
        raise RuntimeError("pymilvus 库未安装")
    return MilvusClient(uri=_build_uri(host, port), user=username, password=password or "", timeout=30)


def test_milvus_connection(host: str, port: int, username: str | None = None, password: str | None = None) -> MilvusResult:
    start_time = time.time()
    try:
        client = _build_client(host, port, username, password)
        collections = client.list_collections()
        return MilvusResult(
            success=True,
            message="Milvus 连接成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data={"collections_count": len(collections)},
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"Milvus 连接失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def create_collection_if_not_exists(
    host: str,
    port: int,
    collection_name: str,
    dimension: int = 1536,
    metric_type: str = "COSINE",
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    start_time = time.time()
    try:
        client = _build_client(host, port, username, password)
        if client.has_collection(collection_name):
            return MilvusResult(
                success=True,
                message="Collection 已存在",
                response_time_ms=(time.time() - start_time) * 1000,
            )

        client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            primary_field_name="chunk_uid",
            id_type="string",
            max_length=64,
            vector_field_name="vector",
            metric_type=metric_type,
            auto_id=False,
            enable_dynamic_field=True,
        )
        return MilvusResult(
            success=True,
            message=f"Collection '{collection_name}' 创建成功",
            response_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"创建 Collection 失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def drop_collection_if_exists(
    host: str,
    port: int,
    collection_name: str,
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    start_time = time.time()
    try:
        client = _build_client(host, port, username, password)
        if not client.has_collection(collection_name):
            return MilvusResult(
                success=True,
                message="Collection 不存在，无需删除",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        client.drop_collection(collection_name)
        return MilvusResult(
            success=True,
            message=f"Collection '{collection_name}' 删除成功",
            response_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"删除 Collection 失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def insert_vectors(
    host: str,
    port: int,
    collection_name: str,
    vectors: list[list[float]],
    metadata: list[dict[str, Any]] | None = None,
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    start_time = time.time()
    try:
        client = _build_client(host, port, username, password)
        data: list[dict[str, Any]] = []
        for index, vector in enumerate(vectors):
            payload = dict(metadata[index] if metadata and index < len(metadata) else {})
            payload["vector"] = vector
            data.append(payload)
        result = client.insert(collection_name=collection_name, data=data)
        return MilvusResult(
            success=True,
            message=f"成功插入 {len(vectors)} 条向量",
            response_time_ms=(time.time() - start_time) * 1000,
            data=result,
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"插入向量失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def delete_vectors(
    host: str,
    port: int,
    collection_name: str,
    chunk_uids: list[str],
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    start_time = time.time()
    try:
        if not chunk_uids:
            return MilvusResult(success=True, message="无需删除向量", response_time_ms=0, data={"deleted": 0})
        client = _build_client(host, port, username, password)
        escaped = [uid.replace('"', '\\"') for uid in chunk_uids]
        if len(escaped) == 1:
            filter_expr = f'chunk_uid == "{escaped[0]}"'
        else:
            joined = ", ".join(f'"{uid}"' for uid in escaped)
            filter_expr = f"chunk_uid in [{joined}]"
        result = client.delete(collection_name=collection_name, filter=filter_expr)
        return MilvusResult(
            success=True,
            message=f"成功删除 {len(chunk_uids)} 条向量",
            response_time_ms=(time.time() - start_time) * 1000,
            data=result,
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"删除向量失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def search_vectors(
    host: str,
    port: int,
    collection_name: str,
    query_vector: list[float],
    top_k: int = 5,
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    start_time = time.time()
    try:
        client = _build_client(host, port, username, password)
        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["chunk_uid", "document_id", "chunk_index", "page_no", "heading_path"],
        )
        raw_hits = results[0] if isinstance(results, list) and results else []
        hits: list[dict[str, Any]] = []
        for hit in raw_hits:
            if not isinstance(hit, dict):
                continue
            entity = hit.get("entity") if isinstance(hit.get("entity"), dict) else {}
            chunk_uid = hit.get("id") or hit.get("chunk_uid") or entity.get("chunk_uid")
            if not chunk_uid:
                continue
            payload = dict(entity)
            payload.setdefault("chunk_uid", chunk_uid)
            payload["score"] = float(hit.get("distance") or hit.get("score") or 0)
            hits.append(payload)
        return MilvusResult(
            success=True,
            message=f"检索到 {len(hits)} 条结果",
            response_time_ms=(time.time() - start_time) * 1000,
            data=hits,
        )
    except Exception as exc:
        return MilvusResult(
            success=False,
            message=f"向量检索失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )
