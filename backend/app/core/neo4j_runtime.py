from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.neo4j_client import NEO4J_AVAILABLE, _build_driver
from app.models.knowledge_base import KnowledgeBase, Neo4jConnection


@dataclass
class Neo4jConnParams:
    uri: str
    username: str
    password: str | None
    database: str | None


def resolve_neo4j_params(db: Session, knowledge_base: KnowledgeBase) -> Neo4jConnParams:
    settings = get_settings()
    if settings.neo4j_uri:
        return Neo4jConnParams(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username or "neo4j",
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
    connection = (
        db.execute(
            select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == knowledge_base.id)
        )
        .scalar_one_or_none()
    )
    if connection is None:
        raise AppError(
            status_code=503,
            code="NEO4J_NOT_CONFIGURED",
            message="未配置 Neo4j 连接（平台环境变量或知识库 neo4j_connection）",
        )
    return Neo4jConnParams(
        uri=connection.uri,
        username=connection.username,
        password=connection.password,
        database=connection.database,
    )


def ensure_driver_available() -> None:
    if not NEO4J_AVAILABLE:
        raise AppError(status_code=503, code="NEO4J_UNAVAILABLE", message="neo4j 驱动未安装")


def run_neo4j_read(
    params: Neo4jConnParams,
    cypher: str,
    query_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    ensure_driver_available()
    driver = _build_driver(params.uri, params.username, params.password)
    records: list[dict[str, Any]] = []
    try:
        with driver.session(database=params.database) as session:
            result = session.run(cypher, **(query_params or {}))
            for record in result:
                row: dict[str, Any] = {}
                for key in record.keys():
                    value = record[key]
                    if hasattr(value, "items"):
                        row[key] = dict(value)
                    elif isinstance(value, list):
                        row[key] = [
                            dict(item) if hasattr(item, "items") else item for item in value
                        ]
                    else:
                        row[key] = value
                records.append(row)
    finally:
        driver.close()
    return records
