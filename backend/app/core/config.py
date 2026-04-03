from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
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

    @property
    def normalized_cors_origins(self) -> list[str]:
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
