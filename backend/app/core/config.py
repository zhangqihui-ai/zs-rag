from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env（与 app 包同级），避免在容器内用 ../.env 误指向根目录 /.env
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ENV = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ENV if _BACKEND_ENV.is_file() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "zs-rag"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/zs_rag"
    db_pool_size: int = Field(default=10, description="SQLAlchemy 连接池常驻连接数")
    db_max_overflow: int = Field(default=20, description="SQLAlchemy 连接池可溢出连接数")
    db_pool_timeout: int = Field(default=30, description="等待空闲连接的超时（秒）")
    doc_parse_max_concurrency: int = Field(
        default=3,
        description="文档解析/重建的全局最大并发数；超出的任务排队等待，保护 CPU/内存与数据库连接池",
    )
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:80,http://localhost:3000")
    cors_allow_lan_regex: bool = Field(
        default=True,
        description="为 true 时除 CORS_ORIGINS 外，正则放行 localhost/127.0.0.1/192.168.* 任意端口",
    )
    request_id_header: str = "X-Request-ID"
    
    # Admin initialization
    admin_username: str = Field(default="admin", description="管理员用户名")
    admin_email: str = Field(default="admin@example.com", description="管理员邮箱")
    admin_password: str = Field(default="ChangeMe123!", description="管理员初始密码")
    
    # Security
    jwt_secret: str = Field(default="change-me-in-production", description="JWT 密钥")
    embed_api_key_pepper: str = Field(
        default="",
        description="嵌入 API Key 哈希用盐；为空则回退使用 jwt_secret",
    )

    # Milvus runtime configuration (ops-managed)
    milvus_host: str = Field(default="milvus", description="Milvus 服务地址")
    milvus_port: int = Field(default=19530, description="Milvus 服务端口")
    milvus_db_name: str = Field(default="default", description="Milvus 数据库名（LightRAG MilvusVectorDBStorage 必填）")
    milvus_username: str | None = Field(default=None, description="Milvus 用户名")
    milvus_password: str | None = Field(default=None, description="Milvus 密码")

    # Neo4j（LightRAG 图库 / 图谱可视化；平台级连接，按 workspace 隔离）
    neo4j_uri: str | None = Field(default=None, description="Neo4j Bolt URI")
    neo4j_username: str | None = Field(default=None, description="Neo4j 用户名")
    neo4j_password: str | None = Field(default=None, description="Neo4j 密码")
    neo4j_database: str | None = Field(default=None, description="Neo4j 数据库名（可选）")

    lightrag_storage_root: str | None = Field(
        default=None,
        description="LightRAG JsonKV 等工作目录根路径；默认 backend/storage/lightrag",
    )
    lightrag_use_tiktoken: bool = Field(
        default=False,
        description="LightRAG 使用 tiktoken 分块（默认 false：离线字符分词，不访问 openaipublic.blob.core.windows.net）",
    )
    lightrag_tiktoken_model: str = Field(
        default="gpt-4o-mini",
        description="lightrag_use_tiktoken=true 时使用的 tiktoken 模型名",
    )
    lightrag_llm_timeout_sec: int = Field(
        default=600,
        ge=60,
        le=3600,
        description=(
            "LightRAG 实体/关系抽取 LLM 单次读超时（秒）；"
            "同时作为 LightRAG default_llm_timeout，其 worker 层超时为 2× 该值"
        ),
    )
    lightrag_llm_max_retries: int = Field(
        default=3,
        description="LightRAG LLM 读超时等可重试错误的最大重试次数",
    )
    lightrag_chunk_token_size: int = Field(
        default=4096,
        ge=512,
        le=32768,
        description="LightRAG 单段 token 上限；图知识库复用解析切片时需覆盖 Excel 等大块（约 4000 字）",
    )
    lightrag_chunk_overlap_token_size: int = Field(
        default=50,
        ge=0,
        le=512,
        description="LightRAG 分块重叠 token 数",
    )
    lightrag_milvus_upsert_batch_size: int = Field(
        default=128,
        ge=1,
        le=2000,
        description="LightRAG 写入 Milvus 时每批向量条数，避免单次 gRPC 超过 64MB",
    )
    lightrag_prechunk_min_chars: int = Field(
        default=150_000,
        ge=10_000,
        le=5_000_000,
        description="解析全文超过该字符数时，图入库复用解析切片作为 LightRAG 索引大段；小文档走 LightRAG 原生分块",
    )
    lightrag_insert_wait_timeout_sec: int = Field(
        default=7200,
        ge=300,
        le=86400,
        description="单文档 LightRAG 图谱入库最长等待时间（秒）",
    )
    lightrag_delete_lock_wait_sec: int = Field(
        default=120,
        ge=10,
        le=600,
        description="删除文档时等待图知识库入库锁的最长时间（秒）；入库进行中会先尝试取消任务",
    )
    lightrag_embedding_batch_num: int = Field(
        default=4,
        ge=1,
        le=32,
        description="LightRAG 单次调用 Embedding 的文本条数；大表格 chunk 建议 2–4",
    )
    agentic_rag_enabled: bool = Field(default=True, description="是否启用独立 Agentic RAG 端点")
    agentic_rag_max_iterations: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Agentic RAG 单轮最多检索/改写迭代次数",
    )
    agentic_rag_grade_batch_size: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Agentic RAG 相关性评估单批片段数（预留配置，当前按 Top K 一批评估）",
    )
    agentic_rag_min_relevant_docs: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Agentic RAG 判定检索结果足够的最少相关片段数",
    )
    agentic_route_doc_titles_per_kb: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Agentic 路由注入每库文档标题数上限",
    )
    agentic_route_pre_retrieve_top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Agentic 路由轻量预检索 Top K",
    )
    agentic_route_pre_retrieve_enabled: bool = Field(
        default=True,
        description="Agentic 路由在首轮判定 retrieve 后是否做预检索二次路由",
    )
    agentic_route_kb_context_max_chars: int = Field(
        default=3000,
        ge=500,
        le=12000,
        description="Agentic 路由知识库元数据上下文最大字符数",
    )
    embedding_timeout_sec: int = Field(
        default=300,
        ge=60,
        le=3600,
        description=(
            "Embedding API 单次批量请求读超时（秒）；"
            "同时作为 LightRAG default_embedding_timeout，worker 层超时为 2× 该值"
        ),
    )
    embedding_max_retries: int = Field(
        default=3,
        description="Embedding 超时/网络错误最大重试次数",
    )
    embedding_batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
        description="单次调用 Embedding API 的文本条数（大批量文档索引时可适当增大）",
    )
    embedding_max_concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description=(
            "向量化（embedding）并发度默认值：同时向 Embedding 服务发起的请求数。"
            "仅在 Embedding 后端为多实例/可并行时才有提速效果；"
            "单实例服务设为 1 即可。知识库可在配置页单独覆盖该值。"
        ),
    )
    embedding_cache_enabled: bool = Field(
        default=True,
        description=(
            "是否启用持久化 embedding 缓存（按模型+内容哈希缓存向量）。"
            "开启后重解析/续传/重建索引时命中缓存的段无需再次调用 GPU 计算向量。"
        ),
    )
    embedding_cache_ttl_sec: int = Field(
        default=1_209_600,
        ge=60,
        le=31_536_000,
        description="embedding 缓存条目存活时间（秒），默认 14 天。",
    )
    tiktoken_cache_dir: str | None = Field(
        default=None,
        description="tiktoken 离线缓存目录（对应环境变量 TIKTOKEN_CACHE_DIR）",
    )
    opensearch_url: str | None = Field(
        default=None,
        description="OpenSearch REST 基址，如 http://opensearch:9200；未设置则保持仅用 PG 全文",
    )
    opensearch_index_chunks: str = Field(
        default="zs_rag_chunks",
        description="知识库切片全文索引名称（接入同步时使用）",
    )

    redis_url: str | None = Field(default=None, description="Redis URL，供 Celery 与分布式限流")
    celery_enabled: bool = Field(default=False, description="是否启用 Celery 文档任务队列")
    rate_limit_enabled: bool = Field(default=True, description="是否启用 API 限流")
    chat_api_rate_limit_per_minute: int = Field(default=120, description="Chat/Embed API 每分钟请求上限")
    auth_login_rate_limit_per_minute: int = Field(default=30, description="登录接口每分钟请求上限")
    embed_api_key_daily_quota: int = Field(default=5000, description="单个 Embed Key 日调用配额（0=不限制）")
    space_max_documents: int = Field(default=0, description="企业空间最大文档数（0=不限制）")
    space_max_storage_bytes: int = Field(
        default=0,
        description="企业空间最大存储字节数（0=不限制）",
    )

    # MinIO（Milvus 对象存储依赖；Console 登录凭据）
    minio_root_user: str = Field(default="minioadmin", description="MinIO 管理员用户名")
    minio_root_password: str = Field(default="minioadmin", description="MinIO 管理员密码")

    # MinerU 文档解析（PDF/图片及可选 Office·CSV·文本；具体引擎由知识库 parsers 配置）
    mineru_enabled: bool = Field(default=False, description="是否启用 MinerU HTTP 解析服务")
    mineru_base_url: str = Field(default="http://mineru:8000", description="MinerU HTTP API base URL")
    mineru_backend: str = Field(
        default="pipeline",
        description="MinerU 推理后端：pipeline（CPU/GPU 轻量）| vlm-vllm-engine（GPU VLM）",
    )
    mineru_lang: str = Field(default="ch", description="MinerU OCR 语言：ch/en/korean/japan...")
    mineru_timeout: int = Field(default=300, description="单文件解析超时（秒），扫描件建议更大")
    mineru_formats: str = Field(
        default="pdf,png,jpg,jpeg,bmp,tif,tiff,webp,docx,xlsx,xlsm,csv,md,txt",
        description="MinerU 可解析后缀白名单（逗号分隔）；图片等自动路径使用；知识库显式选 mineru 引擎时不强制在此列表",
    )

    @property
    def mineru_format_set(self) -> set[str]:
        return {s.strip().lower().lstrip(".") for s in self.mineru_formats.split(",") if s.strip()}

    # OpenDataLoader PDF（进程内 Python SDK + JVM；PDF 默认解析引擎）
    odl_enabled: bool = Field(default=True, description="是否启用 OpenDataLoader 解析 PDF")
    odl_default_parser: str = Field(
        default="opendataloader",
        description="未在知识库 config 指定 pdf_parser 时的默认 PDF 引擎",
    )
    odl_hybrid: bool = Field(default=False, description="OpenDataLoader 是否默认走 Hybrid（需 sidecar）")
    odl_hybrid_url: str = Field(
        default="http://opendataloader-hybrid:5002",
        description="OpenDataLoader Hybrid 后端 URL",
    )
    odl_timeout: int = Field(default=120, description="OpenDataLoader Hybrid 单次请求超时（秒）")

    # 宿主机暴露端口（未设置或 0 表示未映射，前端不可直接访问）
    postgres_exposed_port: int | None = Field(default=None, description="PostgreSQL 宿主机映射端口")
    milvus_exposed_port: int | None = Field(default=None, description="Milvus gRPC 宿主机映射端口")
    milvus_web_exposed_port: int | None = Field(default=None, description="Milvus WebUI HTTP 宿主机映射端口")
    minio_console_exposed_port: int | None = Field(default=None, description="MinIO Console 宿主机映射端口")
    opensearch_exposed_port: int | None = Field(default=None, description="OpenSearch 宿主机映射端口")
    neo4j_http_exposed_port: int | None = Field(default=None, description="Neo4j Browser HTTP 宿主机映射端口")
    backend_exposed_port: int | None = Field(default=None, description="后端 API 宿主机映射端口")
    frontend_container_port: int = Field(default=80, description="前端容器内监听端口（生产 80，开发 5173）")
    frontend_exposed_port: int | None = Field(default=None, description="前端 Web 宿主机映射端口")
    mineru_exposed_port: int | None = Field(default=None, description="MinerU 宿主机映射端口")
    odl_hybrid_exposed_port: int | None = Field(default=None, description="ODL Hybrid 宿主机映射端口")
    redis_exposed_port: int | None = Field(default=None, description="Redis 宿主机映射端口")

    @field_validator(
        "postgres_exposed_port",
        "milvus_exposed_port",
        "milvus_web_exposed_port",
        "minio_console_exposed_port",
        "opensearch_exposed_port",
        "neo4j_http_exposed_port",
        "backend_exposed_port",
        "frontend_exposed_port",
        "mineru_exposed_port",
        "odl_hybrid_exposed_port",
        "redis_exposed_port",
        mode="before",
    )
    @classmethod
    def _optional_exposed_port(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    @property
    def normalized_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins

    @property
    def cors_lan_origin_regex_pattern(self) -> str:
        """内网常见入口：localhost、127.0.0.1、192.168.*（任意端口）。"""
        return r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"

    @property
    def cors_allow_origin_regex(self) -> str | None:
        if self.cors_allow_lan_regex:
            return self.cors_lan_origin_regex_pattern
        if self.app_env.lower() == "development":
            return self.cors_lan_origin_regex_pattern
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
