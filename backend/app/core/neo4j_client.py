from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


@dataclass
class Neo4jResult:
    success: bool
    message: str
    response_time_ms: float
    data: Any | None = None


def _build_driver(uri: str, username: str, password: str | None = None):
    if not NEO4J_AVAILABLE or GraphDatabase is None:
        raise RuntimeError("neo4j 库未安装")
    return GraphDatabase.driver(uri, auth=(username, password or ""))


def test_neo4j_connection(uri: str, username: str, password: str | None = None, database: str | None = None) -> Neo4jResult:
    start_time = time.time()
    try:
        driver = _build_driver(uri, username, password)
        with driver.session(database=database) as session:
            result = session.run("MATCH (n) RETURN count(n) AS count LIMIT 1")
            record = result.single()
            count = record["count"] if record else 0
        driver.close()
        return Neo4jResult(
            success=True,
            message="Neo4j 连接成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data={"sample_count": count},
        )
    except Exception as exc:
        return Neo4jResult(
            success=False,
            message=f"Neo4j 连接失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def create_graph_node(
    uri: str,
    username: str,
    password: str | None = None,
    database: str | None = None,
    label: str = "Entity",
    properties: dict[str, Any] | None = None,
) -> Neo4jResult:
    start_time = time.time()
    try:
        driver = _build_driver(uri, username, password)
        with driver.session(database=database) as session:
            if properties:
                props_str = ", ".join([f"{key}: ${key}" for key in properties.keys()])
                query = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
            else:
                query = f"CREATE (n:{label}) RETURN n"
            result = session.run(query, **(properties or {}))
            record = result.single()
        driver.close()
        return Neo4jResult(
            success=True,
            message="节点创建成功",
            response_time_ms=(time.time() - start_time) * 1000,
            data=dict(record["n"]) if record else None,
        )
    except Exception as exc:
        return Neo4jResult(
            success=False,
            message=f"创建节点失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )


def query_graph(
    uri: str,
    username: str,
    password: str | None = None,
    database: str | None = None,
    cypher: str = "MATCH (n) RETURN n LIMIT 10",
    params: dict[str, Any] | None = None,
) -> Neo4jResult:
    start_time = time.time()
    try:
        driver = _build_driver(uri, username, password)
        with driver.session(database=database) as session:
            result = session.run(cypher, **(params or {}))
            records = []
            for record in result:
                row: dict[str, Any] = {}
                for key in record.keys():
                    value = record[key]
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
    except Exception as exc:
        return Neo4jResult(
            success=False,
            message=f"图查询失败：{exc}",
            response_time_ms=(time.time() - start_time) * 1000,
        )
