"""
Milvus 客户端集成 - 用于向量数据库操作
"""

import time
from dataclasses import dataclass
from typing import Any

try:
    from pymilvus import MilvusClient, DataType
    MILVUS_AVAILABLE = True
except ImportError:
    MilvusClient = None  # type: ignore
    DataType = None  # type: ignore
    MILVUS_AVAILABLE = False


@dataclass
class MilvusResult:
    """Milvus 操作结果"""
    success: bool
    message: str
    response_time_ms: float
    data: Any | None = None


def test_milvus_connection(host: str, port: int, username: str | None = None, password: str | None = None) -> MilvusResult:
    """测试 Milvus 连接"""
    start_time = time.time()
    
    if not MILVUS_AVAILABLE:
        return MilvusResult(
            success=False,
            message="pymilvus 库未安装",
            response_time_ms=0,
        )
    
    try:
        uri = f"http://{host}:{port}"
        client = MilvusClient(uri=uri, user=username, password=password or "", timeout=5)
        
        # 尝试列出 collections
        collections = client.list_collections()
        
        return MilvusResult(
            success=True,
            message="Milvus 连接成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data={"collections_count": len(collections)},
        )
    except Exception as e:
        return MilvusResult(
            success=False,
            message=f"Milvus 连接失败：{str(e)}",
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
    """创建 collection（如果不存在）"""
    start_time = time.time()
    try:
        uri = f"http://{host}:{port}"
        client = MilvusClient(uri=uri, user=username, password=password or "", timeout=10)
        
        if client.has_collection(collection_name):
            return MilvusResult(
                success=True,
                message="Collection 已存在",
                response_time_ms=(time.time() - start_time) * 1000,
            )
        
        # 创建 collection
        client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            metric_type=metric_type,
            auto_id=True,
        )
        
        # 创建索引
        client.create_index(
            collection_name=collection_name,
            field_name="vector",
            index_params={"index_type": "FLAT", "metric_type": metric_type},
        )
        
        return MilvusResult(
            success=True,
            message=f"Collection '{collection_name}' 创建成功",
            response_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        return MilvusResult(
            success=False,
            message=f"创建 Collection 失败：{str(e)}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def insert_vectors(
    host: str,
    port: int,
    collection_name: str,
    vectors: list[list[float]],
    metadata: list[dict] | None = None,
    username: str | None = None,
    password: str | None = None,
) -> MilvusResult:
    """插入向量"""
    start_time = time.time()
    try:
        uri = f"http://{host}:{port}"
        client = MilvusClient(uri=uri, user=username, password=password or "", timeout=30)
        
        # 准备数据
        data = []
        for i, vector in enumerate(vectors):
            item = {"vector": vector}
            if metadata and i < len(metadata):
                item.update(metadata[i])
            data.append(item)
        
        # 插入
        result = client.insert(collection_name=collection_name, data=data)
        
        return MilvusResult(
            success=True,
            message=f"成功插入 {len(vectors)} 条向量",
            response_time_ms=(time.time() - start_time) * 1000,
            data=result,
        )
    except Exception as e:
        return MilvusResult(
            success=False,
            message=f"插入向量失败：{str(e)}",
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
    """向量检索"""
    start_time = time.time()
    try:
        uri = f"http://{host}:{port}"
        client = MilvusClient(uri=uri, user=username, password=password or "", timeout=30)
        
        # 搜索
        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["*"],
        )
        
        return MilvusResult(
            success=True,
            message=f"检索到 {len(results[0])} 条结果",
            response_time_ms=(time.time() - start_time) * 1000,
            data=results,
        )
    except Exception as e:
        return MilvusResult(
            success=False,
            message=f"向量检索失败：{str(e)}",
            response_time_ms=(time.time() - start_time) * 1000,
        )
