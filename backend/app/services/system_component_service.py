from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.milvus_client import test_milvus_connection
from app.core.neo4j_client import test_neo4j_connection
from app.db.session import engine
from app.schemas.system_components import (
    ComponentCredential,
    ComponentStatus,
    ServiceComponentItem,
    ServiceComponentsStatusResponse,
)

ProbeFn = Callable[[Settings], tuple[ComponentStatus, str | None, float | None]]


@dataclass(frozen=True)
class ComponentDefinition:
    id: str
    name: str
    service_type: str
    host: str
    port: int
    is_enabled: Callable[[Settings], bool]
    exposed_port_getter: Callable[[Settings], int | None]
    visit_port_getter: Callable[[Settings], int | None] | None = None
    visit_path: str | None = None
    visit_label: str | None = None


def _positive_port(value: int | None) -> int | None:
    if value is None or value <= 0:
        return None
    return value


def _resolved_frontend_container_port(settings: Settings) -> int:
    """容器内监听端口：compose 显式配置优先；开发环境默认 5173（Vite）。"""
    port = settings.frontend_container_port
    if port > 0 and not (settings.app_env.lower() == "development" and port == 80):
        return port
    if settings.app_env.lower() == "development":
        return 5173
    return 80 if port <= 0 else port


def _frontend_probe_ports(settings: Settings) -> list[int]:
    primary = _resolved_frontend_container_port(settings)
    ports = [primary]
    for alt in (5173, 80):
        if alt not in ports:
            ports.append(alt)
    return ports


def _parse_url_host_port(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    return host, port


def _probe_postgres(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    start = time.time()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.alive, "PostgreSQL 连接正常", elapsed
    except SQLAlchemyError as exc:
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.dead, f"PostgreSQL 连接失败：{exc}", elapsed


def _probe_milvus(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    result = test_milvus_connection(
        settings.milvus_host,
        settings.milvus_port,
        settings.milvus_username,
        settings.milvus_password,
    )
    status = ComponentStatus.alive if result.success else ComponentStatus.dead
    return status, result.message, result.response_time_ms


def _probe_minio(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    url = "http://minio:9000/minio/health/live"
    start = time.time()
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.alive, "MinIO 健康检查通过", elapsed
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.dead, f"MinIO 健康检查失败：{exc}", elapsed


def _probe_opensearch(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    base_url = (settings.opensearch_url or "").rstrip("/")
    start = time.time()
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base_url}/_cluster/health")
            response.raise_for_status()
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.alive, "OpenSearch 集群健康", elapsed
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.dead, f"OpenSearch 连接失败：{exc}", elapsed


def _probe_neo4j(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    result = test_neo4j_connection(
        settings.neo4j_uri or "",
        settings.neo4j_username or "neo4j",
        settings.neo4j_password,
        settings.neo4j_database,
    )
    status = ComponentStatus.alive if result.success else ComponentStatus.dead
    return status, result.message, result.response_time_ms


def _probe_etcd(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    start = time.time()
    try:
        with socket.create_connection(("etcd", 2379), timeout=3.0):
            pass
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.alive, "etcd 端口可达", elapsed
    except OSError as exc:
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.unknown, f"etcd 状态未知：{exc}", elapsed


def _probe_backend(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    return ComponentStatus.alive, "后端服务运行中", 0.0


def _probe_frontend(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    start = time.time()
    last_detail: str | None = None
    for port in _frontend_probe_ports(settings):
        url = f"http://frontend:{port}/"
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code < 500:
                    elapsed = (time.time() - start) * 1000
                    hint = f"（容器端口 {port}）" if port != _resolved_frontend_container_port(settings) else ""
                    return ComponentStatus.alive, f"前端页面可访问{hint}", elapsed
                last_detail = f"{url} HTTP {response.status_code}"
        except Exception as exc:
            last_detail = f"{url} {exc}"
    elapsed = (time.time() - start) * 1000
    return ComponentStatus.dead, f"前端连接失败：{last_detail or '无可用端口'}", elapsed


def _probe_mineru(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    base_url = settings.mineru_base_url.rstrip("/")
    start = time.time()
    for path in ("/health", "/docs"):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}{path}")
                if response.status_code < 500:
                    elapsed = (time.time() - start) * 1000
                    return ComponentStatus.alive, f"MinerU 响应正常 ({path})", elapsed
        except Exception:
            continue
    elapsed = (time.time() - start) * 1000
    return ComponentStatus.dead, "MinerU 无响应", elapsed


def _probe_odl_hybrid(settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    url = settings.odl_hybrid_url.rstrip("/") + "/health"
    start = time.time()
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.alive, "ODL Hybrid 健康检查通过", elapsed
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return ComponentStatus.dead, f"ODL Hybrid 连接失败：{exc}", elapsed


def _mineru_host_port(settings: Settings) -> tuple[str, int]:
    return _parse_url_host_port(settings.mineru_base_url, 8000)


def _odl_host_port(settings: Settings) -> tuple[str, int]:
    return _parse_url_host_port(settings.odl_hybrid_url, 5002)


def _milvus_visit_port(settings: Settings) -> int | None:
    explicit = _positive_port(settings.milvus_web_exposed_port)
    if explicit is not None:
        return explicit
    if _positive_port(settings.milvus_exposed_port) is not None:
        return 9091
    return None


def _parse_postgres_credentials(settings: Settings) -> list[ComponentCredential]:
    normalized = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    parsed = urlparse(normalized)
    credentials: list[ComponentCredential] = []
    if parsed.username:
        credentials.append(ComponentCredential(label="用户名", value=unquote(parsed.username)))
    if parsed.password:
        credentials.append(ComponentCredential(label="密码", value=unquote(parsed.password)))
    database = (parsed.path or "").lstrip("/")
    if database:
        credentials.append(ComponentCredential(label="数据库", value=unquote(database)))
    return credentials


def _build_credentials(component_id: str, settings: Settings) -> list[ComponentCredential]:
    if component_id == "backend":
        return [
            ComponentCredential(label="说明", value="Swagger /docs 无需登录"),
            ComponentCredential(label="平台管理员", value=f"{settings.admin_username} / {settings.admin_password}"),
        ]
    if component_id == "frontend":
        return [
            ComponentCredential(label="说明", value="浏览器主入口；生产环境由 nginx 同源反代 /api 至后端"),
        ]
    if component_id == "postgres":
        return _parse_postgres_credentials(settings)
    if component_id == "milvus":
        credentials: list[ComponentCredential] = []
        if settings.milvus_username:
            credentials.append(ComponentCredential(label="用户名", value=settings.milvus_username))
        if settings.milvus_password:
            credentials.append(ComponentCredential(label="密码", value=settings.milvus_password))
        if settings.milvus_db_name:
            credentials.append(ComponentCredential(label="数据库", value=settings.milvus_db_name))
        if not credentials:
            credentials.append(ComponentCredential(label="认证", value="默认无需账号密码"))
        return credentials
    if component_id == "minio":
        return [
            ComponentCredential(label="用户名", value=settings.minio_root_user),
            ComponentCredential(label="密码", value=settings.minio_root_password),
        ]
    if component_id == "opensearch":
        return [ComponentCredential(label="认证", value="未启用安全插件，无需账号密码")]
    if component_id == "neo4j":
        if not settings.neo4j_uri:
            return []
        credentials = [
            ComponentCredential(label="用户名", value=settings.neo4j_username or "neo4j"),
        ]
        if settings.neo4j_password:
            credentials.append(ComponentCredential(label="密码", value=settings.neo4j_password))
        if settings.neo4j_database:
            credentials.append(ComponentCredential(label="数据库", value=settings.neo4j_database))
        return credentials
    if component_id in {"etcd", "mineru", "odl_hybrid"}:
        return [ComponentCredential(label="认证", value="默认无需账号密码")]
    return []


COMPONENT_DEFINITIONS: list[ComponentDefinition] = [
    ComponentDefinition(
        id="backend",
        name="zs-rag API",
        service_type="app_server",
        host="0.0.0.0",
        port=8000,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda s: _positive_port(s.backend_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.backend_exposed_port),
        visit_path="/docs",
        visit_label="API 文档",
    ),
    ComponentDefinition(
        id="frontend",
        name="ZS-RAG 前端",
        service_type="web_ui",
        host="frontend",
        port=80,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda s: _positive_port(s.frontend_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.frontend_exposed_port),
        visit_path="/",
        visit_label="访问",
    ),
    ComponentDefinition(
        id="postgres",
        name="PostgreSQL",
        service_type="meta_data",
        host="postgres",
        port=5432,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda s: _positive_port(s.postgres_exposed_port),
    ),
    ComponentDefinition(
        id="milvus",
        name="Milvus",
        service_type="retrieval",
        host="milvus",
        port=19530,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda s: _positive_port(s.milvus_exposed_port),
        visit_port_getter=_milvus_visit_port,
        visit_path="/webui",
        visit_label="WebUI",
    ),
    ComponentDefinition(
        id="minio",
        name="MinIO",
        service_type="file_store",
        host="minio",
        port=9000,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda s: _positive_port(s.minio_console_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.minio_console_exposed_port),
        visit_path="/",
        visit_label="访问",
    ),
    ComponentDefinition(
        id="opensearch",
        name="OpenSearch",
        service_type="retrieval",
        host="opensearch",
        port=9200,
        is_enabled=lambda s: bool(s.opensearch_url),
        exposed_port_getter=lambda s: _positive_port(s.opensearch_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.opensearch_exposed_port),
        visit_path="/",
        visit_label="访问",
    ),
    ComponentDefinition(
        id="neo4j",
        name="Neo4j",
        service_type="graph",
        host="neo4j",
        port=7687,
        is_enabled=lambda s: bool(s.neo4j_uri),
        exposed_port_getter=lambda s: _positive_port(s.neo4j_http_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.neo4j_http_exposed_port),
        visit_path="/",
        visit_label="访问",
    ),
    ComponentDefinition(
        id="etcd",
        name="etcd",
        service_type="coordination",
        host="etcd",
        port=2379,
        is_enabled=lambda _s: True,
        exposed_port_getter=lambda _s: None,
    ),
    ComponentDefinition(
        id="mineru",
        name="MinerU",
        service_type="parser",
        host="mineru",
        port=8000,
        is_enabled=lambda s: s.mineru_enabled,
        exposed_port_getter=lambda s: _positive_port(s.mineru_exposed_port),
        visit_port_getter=lambda s: _positive_port(s.mineru_exposed_port),
        visit_path="/docs",
        visit_label="访问",
    ),
    ComponentDefinition(
        id="odl_hybrid",
        name="ODL Hybrid",
        service_type="parser",
        host="opendataloader-hybrid",
        port=5002,
        is_enabled=lambda s: s.odl_hybrid,
        exposed_port_getter=lambda s: _positive_port(s.odl_hybrid_exposed_port),
    ),
]

PROBE_FUNCTIONS: dict[str, ProbeFn] = {
    "backend": _probe_backend,
    "frontend": _probe_frontend,
    "postgres": _probe_postgres,
    "milvus": _probe_milvus,
    "minio": _probe_minio,
    "opensearch": _probe_opensearch,
    "neo4j": _probe_neo4j,
    "etcd": _probe_etcd,
    "mineru": _probe_mineru,
    "odl_hybrid": _probe_odl_hybrid,
}


def _resolve_definition_host_port(defn: ComponentDefinition, settings: Settings) -> tuple[str, int]:
    if defn.id == "mineru":
        return _mineru_host_port(settings)
    if defn.id == "odl_hybrid":
        return _odl_host_port(settings)
    if defn.id == "backend":
        return defn.host, settings.app_port
    if defn.id == "frontend":
        return defn.host, _resolved_frontend_container_port(settings)
    if defn.id == "milvus":
        return settings.milvus_host, settings.milvus_port
    return defn.host, defn.port


def _compose_item(
    defn: ComponentDefinition,
    settings: Settings,
    host: str,
    port: int,
    status: ComponentStatus,
    message: str | None,
    *,
    response_time_ms: float | None = None,
) -> ServiceComponentItem:
    exposed_port = defn.exposed_port_getter(settings)
    exposed = exposed_port is not None
    visit_port = defn.visit_port_getter(settings) if defn.visit_port_getter else None
    credentials = _build_credentials(defn.id, settings)
    return ServiceComponentItem(
        id=defn.id,
        name=defn.name,
        service_type=defn.service_type,
        host=host,
        port=port,
        status=status,
        message=message,
        response_time_ms=response_time_ms,
        exposed=exposed,
        external_port=exposed_port if exposed else None,
        visit_port=visit_port if exposed else None,
        visit_path=defn.visit_path if exposed and visit_port else None,
        visit_label=defn.visit_label if exposed and visit_port else None,
        credentials=credentials,
    )


def _build_item(defn: ComponentDefinition, settings: Settings) -> ServiceComponentItem:
    host, port = _resolve_definition_host_port(defn, settings)

    if not defn.is_enabled(settings):
        return _compose_item(
            defn,
            settings,
            host,
            port,
            ComponentStatus.disabled,
            "未启用",
        )

    status, message, response_time_ms = PROBE_FUNCTIONS[defn.id](settings)
    return _compose_item(
        defn,
        settings,
        host,
        port,
        status,
        message,
        response_time_ms=response_time_ms,
    )


def collect_status(settings: Settings | None = None) -> ServiceComponentsStatusResponse:
    settings = settings or get_settings()
    items: list[ServiceComponentItem] = []
    futures_map: dict = {}

    with ThreadPoolExecutor(max_workers=len(COMPONENT_DEFINITIONS)) as executor:
        for defn in COMPONENT_DEFINITIONS:
            futures_map[executor.submit(_build_item, defn, settings)] = defn

        for future, defn in futures_map.items():
            try:
                items.append(future.result(timeout=8))
            except Exception as exc:
                host, port = _resolve_definition_host_port(defn, settings)
                items.append(
                    _compose_item(
                        defn,
                        settings,
                        host,
                        port,
                        ComponentStatus.dead,
                        f"探测超时或失败：{exc}",
                    )
                )

    order = {defn.id: index for index, defn in enumerate(COMPONENT_DEFINITIONS)}
    items.sort(key=lambda item: order.get(item.id, 999))

    return ServiceComponentsStatusResponse(
        checked_at=datetime.now(timezone.utc),
        items=items,
    )
