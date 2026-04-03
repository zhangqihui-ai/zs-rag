from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

ph = PasswordHasher()


def hash_password(password: str) -> str:
    """对密码进行安全散列"""
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """验证密码是否正确"""
    try:
        ph.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建 JWT access token"""
    settings = get_settings()

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expiration_minutes if hasattr(settings, 'jwt_expiration_minutes') else 60 * 24))
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm="HS256",
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """解码 JWT access token"""
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        return payload
    except jwt.PyJWTError:
        return None
