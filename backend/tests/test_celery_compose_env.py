"""Celery worker 须继承 backend 的 MinerU / ODL 环境，避免 PDF 解析降级到 pypdf。"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE = _REPO_ROOT / "docker-compose.yml"

_REQUIRED_PARSE_ENV = {
    "MINERU_ENABLED",
    "MINERU_BASE_URL",
    "MINERU_BACKEND",
    "MINERU_LANG",
    "MINERU_TIMEOUT",
    "MINERU_FORMATS",
    "ODL_ENABLED",
    "ODL_DEFAULT_PARSER",
    "ODL_HYBRID",
    "ODL_HYBRID_URL",
    "ODL_TIMEOUT",
    "DOC_PARSE_MAX_CONCURRENCY",
}


def test_dev_celery_worker_has_document_parse_env():
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    celery_env = data["services"]["celery-worker"]["environment"]
    assert isinstance(celery_env, dict)
    missing = sorted(_REQUIRED_PARSE_ENV - set(celery_env.keys()))
    assert not missing, f"celery-worker missing env: {missing}"
