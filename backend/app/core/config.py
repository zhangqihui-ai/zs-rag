from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:80,http://localhost:3000")
    request_id_header: str = "X-Request-ID"
    
    # Admin initialization
    admin_username: str = Field(default="admin", description="管理员用户名")
    admin_email: str = Field(default="admin@example.com", description="管理员邮箱")
    admin_password: str = Field(default="ChangeMe123!", description="管理员初始密码")
    
    # Security
    jwt_secret: str = Field(default="change-me-in-production", description="JWT 密钥")

    # Milvus runtime configuration (ops-managed)
    milvus_host: str = Field(default="milvus", description="Milvus 服务地址")
    milvus_port: int = Field(default=19530, description="Milvus 服务端口")
    milvus_username: str | None = Field(default=None, description="Milvus 用户名")
    milvus_password: str | None = Field(default=None, description="Milvus 密码")

    # MinerU 文档解析（仅用于 PDF + 图片；DOCX/XLSX 仍走本地解析器）
    mineru_enabled: bool = Field(default=False, description="是否启用 MinerU 解析 PDF/图片")
    mineru_base_url: str = Field(default="http://mineru:8000", description="MinerU HTTP API base URL")
    mineru_backend: str = Field(
        default="pipeline",
        description="MinerU 推理后端：pipeline（CPU/GPU 轻量）| vlm-vllm-engine（GPU VLM）",
    )
    mineru_lang: str = Field(default="ch", description="MinerU OCR 语言：ch/en/korean/japan...")
    mineru_timeout: int = Field(default=300, description="单文件解析超时（秒），扫描件建议更大")
    mineru_formats: str = Field(
        default="pdf,png,jpg,jpeg,bmp,tif,tiff,webp",
        description="MinerU 接管的文件后缀白名单（逗号分隔）。DOCX/XLSX/PPTX 不要加进来",
    )

    @property
    def mineru_format_set(self) -> set[str]:
        return {s.strip().lower().lstrip(".") for s in self.mineru_formats.split(",") if s.strip()}

    @property
    def normalized_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins

    @property
    def cors_allow_origin_regex(self) -> str | None:
        """开发环境下允许局域网任意 IP（避免页面与 CORS_ORIGINS 中硬编码 IP 不一致导致 OPTIONS 400）。"""
        if self.app_env.lower() != "development":
            return None
        return r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"


@lru_cache
def get_settings() -> Settings:
    return Settings()
