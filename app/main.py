"""ПрофВизор — бэкенд генеративного визуализатора забора (фаза 2.1).

Точка входа FastAPI: POST /api/visualize (раздел 7 ТЗ) + отдача фронтенда.
"""
import base64
import logging
import time
import uuid

from fastapi import Depends, FastAPI, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import errors
from .auth import require_site_access
from .config import BASE_DIR, PROFILE_BY_ID, PROFILES, RAL_BY_CODE, RAL_PALETTE, settings
from .errors import ApiError
from .limits import LimitExceeded, check_and_increment, current_usage
from .logging_conf import configure_logging
from .providers.base import ProviderError, ProviderTimeout, VisualizeParams
from .providers.factory import get_provider
from .schemas import UsageResponse, VisualizeResponse

configure_logging()
logger = logging.getLogger("profvizor.api")

app = FastAPI(title="ПрофВизор API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_allow_origins] if settings.cors_allow_origins != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def api_error_handler(request, exc: ApiError):
    # Контракт раздела 7 ТЗ: тело ошибки — {"error": {"code", "message"}}.
    # FastAPI по умолчанию завернул бы exc.detail в {"detail": ...} — переопределяем.
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    # Не хватает поля / нечисловое значение и т.п. — тоже 400 bad_request
    # с понятным сообщением на русском (раздел 7 ТЗ), а не сырой pydantic-текст.
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "bad_request", "message": "Некорректные или отсутствующие поля запроса."}},
    )


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/config", dependencies=[Depends(require_site_access)])
async def get_config():
    """Справочные данные раздела 8 ТЗ + границы полей — единый источник для фронтенда."""
    return {
        "profiles": PROFILES,
        "ralPalette": RAL_PALETTE,
        "limits": {
            "heightM": {"min": 1.2, "max": 2.5, "step": 0.1},
            "leftPct": {"min": 0, "max": 100},
            "widthPct": {"min": 5, "max": 100},
        },
        "provider": settings.image_provider,
    }


@app.get("/api/usage", response_model=UsageResponse, dependencies=[Depends(require_site_access)])
async def get_usage():
    """P1: расход бюджета генераций за день/месяц — для владельца бизнеса."""
    return current_usage()


async def _call_provider_with_retry(params: VisualizeParams, request_id: str):
    """Один автоматический повтор при 502/504 от провайдера (раздел 9 НФТ)."""
    provider = get_provider()
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            check_and_increment()
        except LimitExceeded as exc:
            scope = "дневной" if exc.scope == "daily" else "месячный"
            raise errors.rate_limited(
                f"Превышен {scope} лимит генераций. Попробуйте позже или обратитесь к владельцу инструмента."
            )

        try:
            image_bytes = await provider.generate(params)
            if attempt == 2:
                logger.info("request_id=%s provider retry succeeded", request_id)
            return provider.name, image_bytes
        except ProviderTimeout as exc:
            last_error = exc
            logger.warning("request_id=%s attempt=%s provider timeout: %s", request_id, attempt, exc)
        except ProviderError as exc:
            last_error = exc
            logger.warning("request_id=%s attempt=%s provider error: %s", request_id, attempt, exc)

    if isinstance(last_error, ProviderTimeout):
        raise errors.timeout(
            "Провайдер генерации не ответил вовремя. Попробуйте ещё раз через минуту."
        )
    raise errors.provider_error(
        "Не удалось сгенерировать изображение — сбой на стороне провайдера. Попробуйте ещё раз."
    )


@app.post("/api/visualize", response_model=VisualizeResponse, dependencies=[Depends(require_site_access)])
async def visualize(
    photo: UploadFile,
    profileType: str = Form(...),
    ralCode: str = Form(...),
    heightM: float = Form(...),
    leftPct: float = Form(...),
    widthPct: float = Form(...),
):
    request_id = str(uuid.uuid4())
    started = time.monotonic()

    # --- валидация (раздел 7 ТЗ: 400 bad_request с понятным сообщением) ---
    profile = PROFILE_BY_ID.get(profileType)
    if profile is None:
        known = ", ".join(PROFILE_BY_ID)
        raise errors.bad_request(f"Неизвестный тип профиля «{profileType}». Допустимые: {known}.")

    ral = RAL_BY_CODE.get(ralCode)
    if ral is None:
        raise errors.bad_request(f"Неизвестный код RAL «{ralCode}».")

    if not (1.2 <= heightM <= 2.5):
        raise errors.bad_request("Высота забора должна быть от 1.2 до 2.5 м.")
    if not (0 <= leftPct <= 100):
        raise errors.bad_request("Отступ слева должен быть от 0 до 100%.")
    if not (5 <= widthPct <= 100):
        raise errors.bad_request("Ширина забора в кадре должна быть от 5 до 100%.")

    if photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise errors.bad_request("Фото должно быть в формате JPEG, PNG или WEBP.")

    photo_bytes = await photo.read()
    if len(photo_bytes) > settings.max_upload_bytes:
        raise errors.payload_too_large(
            f"Фото слишком большое — максимум {settings.max_upload_mb} МБ."
        )
    if not photo_bytes:
        raise errors.bad_request("Файл фото пустой.")

    params = VisualizeParams(
        photo_bytes=photo_bytes,
        photo_content_type=photo.content_type,
        profile_id=profile["id"],
        profile_label=profile["label"],
        ral_code=ral["code"],
        ral_name=ral["name"],
        ral_hex=ral["hex"],
        height_m=heightM,
        left_pct=leftPct,
        width_pct=widthPct,
    )

    logger.info(
        "request_id=%s profile=%s ral=%s height=%.1f provider=%s",
        request_id, profile["id"], ral["code"], heightM, settings.image_provider,
    )

    provider_name, image_bytes = await _call_provider_with_retry(params, request_id)

    generation_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "request_id=%s status=200 provider=%s generation_ms=%d",
        request_id, provider_name, generation_ms,
    )

    return VisualizeResponse(
        requestId=request_id,
        imageBase64=base64.b64encode(image_bytes).decode("ascii"),
        provider=provider_name,
        generationMs=generation_ms,
    )


# --- фронтенд: один самодостаточный index.html (раздел 5 ТЗ) ---
frontend_dir = BASE_DIR / "frontend"


@app.get("/", dependencies=[Depends(require_site_access)])
async def index():
    return FileResponse(frontend_dir / "index.html")
