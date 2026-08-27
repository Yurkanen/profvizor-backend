"""Выбор провайдера через IMAGE_PROVIDER в .env — раздел 6 ТЗ (P1: быстрое
переключение провайдера через конфиг)."""
from ..config import settings
from .base import ImageProvider
from .flux import FluxKontextMaxProvider, FluxKontextProProvider
from .gemini import GeminiProvider
from .mock import MockProvider
from .seedream import SeedreamProvider

_PROVIDERS: dict[str, type[ImageProvider]] = {
    "mock": MockProvider,
    "gemini": GeminiProvider,
    "flux-pro": FluxKontextProProvider,
    "flux-max": FluxKontextMaxProvider,
    "seedream": SeedreamProvider,
}


def get_provider() -> ImageProvider:
    provider_cls = _PROVIDERS.get(settings.image_provider)
    if provider_cls is None:
        known = ", ".join(_PROVIDERS)
        raise ValueError(f"Неизвестный IMAGE_PROVIDER={settings.image_provider!r}. Доступные: {known}")
    return provider_cls()
