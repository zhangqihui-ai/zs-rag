"""
Neo4j 客户端集成 - 用于图数据库操作
"""

import time
from dataclasses import dataclass
from typing import Any

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


@dataclass
class Neo4jResult:
    """Neo4j 操作结果"""
    success: bool
    message: str
    response_time_ms: float
    data: Any | None = None


def test_neo4j_connection(uri: str, username: str, password: str | None = None, database: str | None = None) -> Neo4jResult:
    """测试 Neo4j 连接"""
    start_time = time.time()
    
    if not NEO4J_AVAILABLE:
        return Neo4jResult(
            success=False,
            message="neo4j 库未安装",
            response_time_ms=0,
        )
    
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password or ""), database=database)
        
        # 测试连接
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
            record = result.single()
            count = record["count"] if record else 0
        
        driver.close()
        
        return Neo4jResult(
            success=True,
            message="Neo4j 连接成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data={"sample_count": count},
        )
    except Exception as e:
        return Neo4jResult(
            success=False,
            message=f"Neo4j 连接失败：{str(e)}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def create_graph_node(
    uri: str,
    username: str,
    password: str | None = None,
    database: str | None = None,
    label: str = "Entity",
    properties: dict | None = None,
) -> Neo4jResult:
    """创建图节点"""
    start_time = time.time()
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password or ""), database=database)
        
        with driver.session() as session:
            # 构建 Cypher 查询
            if properties:
                props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                query = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
            else:
                query = f"CREATE (n:{label}) RETURN n"
            
            result = session.run(query, **(properties or {}))
            record = result.single()
        
        driver.close()
        
        return Neo4jResult(
            success=True,
            message=f"节点创建成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data=dict(record["n"]) if record else None,
        )
    except Exception as e:
        return Neo4jResult(
            success=False,
            message=f"创建节点失败：{str(e)}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def query_graph(
    uri: str,
    username: str,
    password: str | None = None,
    database: str | None = None,
    cypher: str = "MATCH (n) RETURN n LIMIT 10",
) -> Neo4jResult:
    """执行图查询"""
    start_time = time.time()
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password or ""), database=database)
        
        with driver.session() as session:
            result = session.run(cypher)
            records = []
            for record in result:
                row = {}
                for key in record.keys():
                    value = record[key]
                    # 转换 Neo4j 节点/关系为字典
                    if hasattr(value, "items"):
                        row[key] = dict(value)
                    else:
                        row[key] = value
                records.append(row)
        
        driver.close()
        
        return Neo4jResult(
            success=True,
            message=f"查询成功，返回 {len(records)} 条记录",
            response_time_ms=(time.time() - start_time) * 1000,
            data=records,
        )
    except Exception as e:
        return Neo4jResult(
            success=False,
            message=f"图查询失败：{str(e)}",
            response_time_ms=(time.time() - start_time) * 1000,
        )
