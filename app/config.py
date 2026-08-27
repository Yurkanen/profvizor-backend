"""Конфигурация приложения и справочные данные (перенесены из прототипа без изменений)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Справочные данные из ТЗ (раздел 8) — единственный источник истины на бэкенде.
# Фронтенд запрашивает их через GET /api/config, чтобы не дублировать и не
# рассинхронизироваться со списком на сервере.
# ---------------------------------------------------------------------------

PROFILES = [
    {"id": "corrugated", "label": "Профнастил С8"},
    {"id": "louvre", "label": "Жалюзи, ламели 45°"},
    {"id": "picket-gap", "label": "Штакетник, с зазором"},
    {"id": "picket-solid", "label": "Штакетник, без зазора"},
]

RAL_PALETTE = [
    {"code": "RAL 9003", "name": "Сигнальный белый", "hex": "#EDEDEB"},
    {"code": "RAL 7024", "name": "Графитовый серый", "hex": "#43484B"},
    {"code": "RAL 6005", "name": "Зелёный мох", "hex": "#0F4336"},
    {"code": "RAL 6002", "name": "Лиственно-зелёный", "hex": "#31563A"},
    {"code": "RAL 3005", "name": "Винно-красный", "hex": "#5E2129"},
    {"code": "RAL 8017", "name": "Шоколадно-коричневый", "hex": "#442F29"},
    {"code": "RAL 8004", "name": "Медно-коричневый", "hex": "#8D4931"},
    {"code": "RAL 9005", "name": "Чёрный", "hex": "#17171B"},
]

PROFILE_BY_ID = {p["id"]: p for p in PROFILES}
RAL_BY_CODE = {r["code"]: r for r in RAL_PALETTE}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- провайдер генерации ---
    image_provider: str = "mock"  # mock | gemini | flux-pro | flux-max | seedream
    provider_timeout_s: int = 30

    # --- лимиты (раздел 9 ТЗ) ---
    daily_limit: int = 50
    monthly_limit: int = 800

    # --- загрузка фото ---
    max_upload_mb: int = 10

    # --- доступ к странице (открытый вопрос ТЗ §12, решено: общий пароль) ---
    site_password: str | None = None

    # --- ключи провайдеров (только на бэкенде, см. NFR §9) ---
    gemini_api_key: str | None = None
    bfl_api_key: str | None = None
    fal_api_key: str | None = None
    fal_seedream_model: str | None = None  # переопределить slug модели, если поменяется у fal.ai

    # --- прочее ---
    prompt_template_path: str = str(BASE_DIR / "app" / "prompt_template.txt")
    db_path: str = str(BASE_DIR / "data" / "profvizor.db")
    cors_allow_origins: str = "*"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
