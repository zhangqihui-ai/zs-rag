"""服务组件状态 API 与探测逻辑测试。"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.enterprise_space_context import get_current_user
from app.main import app
from app.models.enterprise_space import User
from app.schemas.system_components import ComponentStatus, ServiceComponentItem, ServiceComponentsStatusResponse
from app.services import system_component_service as svc


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _mock_user() -> User:
    return User(
        id=1,
        username="admin",
        email="admin@test.com",
        password_hash="x",
        is_active=True,
        is_admin=True,
    )


def _alive_probe(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    return ComponentStatus.alive, "ok", 1.0


def _dead_probe(_settings: Settings) -> tuple[ComponentStatus, str | None, float | None]:
    return ComponentStatus.dead, "failed", 2.0


def test_components_status_requires_auth(client: TestClient):
    resp = client.get("/system/components/status")
    assert resp.status_code == 401


def test_components_status_requires_system_admin(client: TestClient):
    def _member_user() -> User:
        return User(
            id=2,
            username="member1",
            email="member1@test.com",
            password_hash="x",
            is_active=True,
            is_admin=False,
        )

    app.dependency_overrides[get_current_user] = _member_user
    try:
        resp = client.get(
            "/system/components/status",
            headers={"Authorization": "Bearer test-token", "X-Enterprise-Space": "default"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_components_status_returns_items(client: TestClient):
    mock_items = [
        ServiceComponentItem(
            id="backend",
            name="zs-rag API",
            service_type="app_server",
            host="0.0.0.0",
            port=8000,
            status=ComponentStatus.alive,
            message="后端服务运行中",
            response_time_ms=0.0,
            exposed=True,
            visit_port=8000,
            visit_path="/docs",
            visit_label="API 文档",
        )
    ]

    app.dependency_overrides[get_current_user] = _mock_user
    try:
        with patch("app.api.routes.system.collect_status", return_value=ServiceComponentsStatusResponse(items=mock_items)):
            resp = client.get("/system/components/status")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "backend"
    assert data["items"][0]["exposed"] is True
    assert data["items"][0]["visit_port"] == 8000


def test_frontend_component_when_exposed():
    settings = Settings(
        frontend_exposed_port=8090,
        frontend_container_port=80,
        app_env="production",
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    frontend = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "frontend")
    item = svc._build_item(frontend, settings)
    assert item.name == "ZS-RAG 前端"
    assert item.exposed is True
    assert item.external_port == 8090
    assert item.visit_port == 8090
    assert item.port == 80


def test_frontend_dev_container_port_defaults_to_5173():
    settings = Settings(
        app_env="development",
        frontend_container_port=80,
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    frontend = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "frontend")
    host, port = svc._resolve_definition_host_port(frontend, settings)
    assert host == "frontend"
    assert port == 5173


def test_exposed_port_when_configured():
    settings = Settings(
        backend_exposed_port=8000,
        postgres_exposed_port=5432,
        minio_console_exposed_port=9001,
        milvus_exposed_port=19530,
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    backend = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "backend")
    postgres = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "postgres")
    minio = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "minio")

    backend_item = svc._build_item(backend, settings)
    postgres_item = svc._build_item(postgres, settings)
    minio_item = svc._build_item(minio, settings)

    assert backend_item.exposed is True
    assert backend_item.visit_port == 8000
    assert postgres_item.exposed is True
    assert postgres_item.external_port == 5432
    assert postgres_item.visit_port is None
    assert minio_item.exposed is True
    assert minio_item.visit_port == 9001

    milvus = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "milvus")
    milvus_item = svc._build_item(milvus, settings)
    assert milvus_item.external_port == 19530
    assert milvus_item.visit_port == 9091


def test_not_exposed_when_port_unset():
    settings = Settings(
        backend_exposed_port=None,
        postgres_exposed_port=None,
        milvus_exposed_port=None,
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    backend = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "backend")
    item = svc._build_item(backend, settings)

    assert item.exposed is False
    assert item.visit_port is None


def test_disabled_components():
    settings = Settings(
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
        celery_enabled=False,
    )
    mineru = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "mineru")
    odl = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "odl_hybrid")
    neo4j = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "neo4j")
    opensearch = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "opensearch")
    celery = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "celery_worker")

    assert svc._build_item(mineru, settings).status == ComponentStatus.disabled
    assert svc._build_item(odl, settings).status == ComponentStatus.disabled
    assert svc._build_item(neo4j, settings).status == ComponentStatus.disabled
    assert svc._build_item(opensearch, settings).status == ComponentStatus.disabled
    assert svc._build_item(celery, settings).status == ComponentStatus.disabled


def test_redis_component_host_port_and_exposed():
    settings = Settings(
        redis_url="redis://cache:6380/2",
        redis_exposed_port=6379,
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    redis_defn = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "redis")
    item = svc._build_item(redis_defn, settings)

    host, port = svc._resolve_definition_host_port(redis_defn, settings)
    assert host == "cache"
    assert port == 6380
    assert item.exposed is True
    assert item.external_port == 6379


def test_redis_credentials():
    settings = Settings(
        redis_url="redis://:secret@redis:6379/1",
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    redis_defn = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "redis")
    item = svc._build_item(redis_defn, settings)
    labels = {cred.label: cred.value for cred in item.credentials}
    assert labels["连接地址"] == "redis://:secret@redis:6379/1"
    assert labels["主机"] == "redis"
    assert labels["端口"] == "6379"
    assert labels["密码"] == "secret"
    assert labels["DB 索引"] == "1"


def test_redis_credentials_default_no_auth():
    settings = Settings(
        redis_url="redis://redis:6379/0",
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    redis_defn = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "redis")
    item = svc._build_item(redis_defn, settings)
    labels = {cred.label: cred.value for cred in item.credentials}
    assert labels["DB 索引"] == "0"
    assert labels["认证"] == "默认无需账号密码"


def test_celery_worker_credentials_and_probe_mock():
    settings = Settings(
        celery_enabled=True,
        redis_url="redis://redis:6379/0",
        mineru_enabled=False,
        odl_hybrid=False,
        neo4j_uri=None,
        opensearch_url=None,
    )
    celery_defn = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "celery_worker")

    original_probe = svc.PROBE_FUNCTIONS["celery_worker"]
    svc.PROBE_FUNCTIONS["celery_worker"] = _alive_probe
    try:
        item = svc._build_item(celery_defn, settings)
    finally:
        svc.PROBE_FUNCTIONS["celery_worker"] = original_probe

    assert item.status == ComponentStatus.alive
    labels = {cred.label: cred.value for cred in item.credentials}
    assert labels["Broker"] == "redis://redis:6379/0"
    assert "Worker" in labels["说明"]


def test_component_credentials():
    settings = Settings(
        database_url="postgresql+psycopg://pguser:pgpass@postgres:5432/zs_rag",
        minio_root_user="minioadmin",
        minio_root_password="miniosecret",
        neo4j_uri="bolt://neo4j:7687",
        neo4j_username="neo4j",
        neo4j_password="graphpass",
        admin_username="admin",
        admin_password="adminpass",
        mineru_enabled=False,
        odl_hybrid=False,
        opensearch_url="http://opensearch:9200",
    )

    postgres = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "postgres")
    minio = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "minio")
    neo4j = next(defn for defn in svc.COMPONENT_DEFINITIONS if defn.id == "neo4j")

    postgres_item = svc._build_item(postgres, settings)
    minio_item = svc._build_item(minio, settings)
    neo4j_item = svc._build_item(neo4j, settings)

    postgres_labels = {item.label: item.value for item in postgres_item.credentials}
    assert postgres_labels["用户名"] == "pguser"
    assert postgres_labels["密码"] == "pgpass"
    assert postgres_labels["数据库"] == "zs_rag"

    minio_labels = {item.label: item.value for item in minio_item.credentials}
    assert minio_labels["用户名"] == "minioadmin"
    assert minio_labels["密码"] == "miniosecret"

    neo4j_labels = {item.label: item.value for item in neo4j_item.credentials}
    assert neo4j_labels["用户名"] == "neo4j"
    assert neo4j_labels["密码"] == "graphpass"


def test_probe_alive_and_dead_with_mocks():
    settings = Settings(
        mineru_enabled=True,
        odl_hybrid=True,
        neo4j_uri="bolt://neo4j:7687",
        neo4j_username="neo4j",
        opensearch_url="http://opensearch:9200",
    )

    original_probes = dict(svc.PROBE_FUNCTIONS)
    svc.PROBE_FUNCTIONS.update(
        {
            "postgres": _alive_probe,
            "milvus": _alive_probe,
            "minio": _alive_probe,
            "opensearch": _dead_probe,
            "neo4j": _alive_probe,
            "etcd": _alive_probe,
            "redis": _alive_probe,
            "celery_worker": _dead_probe,
            "mineru": _dead_probe,
            "odl_hybrid": _alive_probe,
            "backend": _alive_probe,
        }
    )
    try:
        items = svc.collect_status(settings).items
    finally:
        svc.PROBE_FUNCTIONS.clear()
        svc.PROBE_FUNCTIONS.update(original_probes)

    by_id = {item.id: item for item in items}
    assert by_id["postgres"].status == ComponentStatus.alive
    assert by_id["opensearch"].status == ComponentStatus.dead
    assert by_id["mineru"].status == ComponentStatus.dead
