"""Google Gemini 2.5 Flash Image («Nano Banana»), image-to-image редактирование.

ВАЖНО: реализация основана на публично задокументированном REST-эндпоинте
generateContent (contents/parts/inlineData) — он используется экосистемой
уже больше года и, по нескольким независимым источникам на момент написания,
остаётся рабочим для gemini-2.5-flash-image. Один источник при проверке (см.
обсуждение с пользователем) намекнул на более новый "Interactions API"
(v1beta/interactions) — недостаточно подтверждено, чтобы на него полагаться.
Перед P0-сравнением провайдеров ОБЯЗАТЕЛЬНО проверьте актуальный формат в
https://ai.google.dev/gemini-api/docs/image-generation с реальным ключом —
если Google переехал на новый эндпоинт, здесь нужно будет поправить только
этот файл.
"""
import base64

import httpx

from ..config import settings
from .base import ImageProvider, ProviderError, ProviderTimeout, VisualizeParams
from .prompt import build_prompt

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash-image:generateContent"
)


class GeminiProvider(ImageProvider):
    name = "gemini-2.5-flash-image"

    async def generate(self, params: VisualizeParams) -> bytes:
        if not settings.gemini_api_key:
            raise ProviderError("GEMINI_API_KEY не задан на сервере")

        prompt = build_prompt(params.profile_label, params.ral_code, params.ral_name, params.height_m)
        photo_b64 = base64.b64encode(params.photo_bytes).decode("ascii")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": params.photo_content_type,
                                "data": photo_b64,
                            }
                        },
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_s) as client:
                resp = await client.post(
                    GEMINI_ENDPOINT,
                    headers={"x-goog-api-key": settings.gemini_api_key},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"Gemini не ответил за {settings.provider_timeout_s} с") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ошибка сети при обращении к Gemini: {exc}") from exc

        if resp.status_code != 200:
            raise ProviderError(f"Gemini вернул {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            image_b64 = next(p["inlineData"]["data"] for p in parts if "inlineData" in p)
        except (KeyError, IndexError, StopIteration) as exc:
            raise ProviderError("Gemini не вернул изображение в ответе") from exc

        return base64.b64decode(image_b64)
