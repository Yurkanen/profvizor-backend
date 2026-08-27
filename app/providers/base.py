"""Абстракция провайдера генерации изображений — раздел 6 ТЗ.

Любой провайдер получает фото + параметры забора и возвращает готовые байты
картинки. Смена провайдера — это смена IMAGE_PROVIDER в .env, код эндпоинта
/api/visualize провайдера не касается.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VisualizeParams:
    photo_bytes: bytes
    photo_content_type: str
    profile_id: str
    profile_label: str
    ral_code: str
    ral_name: str
    ral_hex: str
    height_m: float
    left_pct: float
    width_pct: float


class ProviderError(Exception):
    """Провайдер ответил ошибкой — маппится в 502 provider_error."""


class ProviderTimeout(Exception):
    """Провайдер не ответил вовремя — маппится в 504 timeout."""


class ImageProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, params: VisualizeParams) -> bytes:
        """Вернуть байты сгенерированного изображения (JPEG/PNG)."""
        raise NotImplementedError
