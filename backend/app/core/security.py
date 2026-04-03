from app.core.config import get_settings


def get_security_settings() -> get_settings().__class__:
    """获取安全相关配置"""
    return get_settings()
