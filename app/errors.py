"""Единый формат ошибок API — понятные сообщения на русском (раздел 7 ТЗ)."""
from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException с телом {"error": {"code": ..., "message": ...}}."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def bad_request(message: str) -> ApiError:
    return ApiError(400, "bad_request", message)


def payload_too_large(message: str) -> ApiError:
    return ApiError(413, "payload_too_large", message)


def rate_limited(message: str) -> ApiError:
    return ApiError(429, "rate_limited", message)


def provider_error(message: str) -> ApiError:
    return ApiError(502, "provider_error", message)


def timeout(message: str) -> ApiError:
    return ApiError(504, "timeout", message)
