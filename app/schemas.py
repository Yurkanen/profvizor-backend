"""Pydantic-схемы ответов API."""
from pydantic import BaseModel


class VisualizeResponse(BaseModel):
    requestId: str
    imageBase64: str
    provider: str
    generationMs: int


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class UsageResponse(BaseModel):
    daily: int
    dailyLimit: int
    monthly: int
    monthlyLimit: int
