"""Простая защита доступа общим паролем — открытый вопрос ТЗ §12,
рекомендация ТЗ: "да, хотя бы простой общий пароль на старте".
Если SITE_PASSWORD не задан в .env — доступ открытый (например, для
локальной разработки)."""
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import settings

_security = HTTPBasic(auto_error=False)


def require_site_access(credentials: HTTPBasicCredentials | None = Depends(_security)) -> None:
    if not settings.site_password:
        return  # пароль не настроен — доступ открыт

    valid = credentials is not None and hmac.compare_digest(
        credentials.password, settings.site_password
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется пароль доступа",
            headers={"WWW-Authenticate": "Basic"},
        )
