"""ByteDance Seedream 4.5, image-to-image редактирование. Раздел 6 ТЗ.

У ByteDance нет единого канонического REST API "из коробки" — доступ обычно
идёт через агрегаторы (fal.ai, BytePlus ModelArk, OpenRouter и т.п.). Здесь
выбран fal.ai как наиболее документированный вариант их очередной (queue)
модели: POST → {status_url, response_url} → поллинг статуса → GET результата.

Slug модели вынесен в FAL_SEEDREAM_MODEL (.env) — его нужно подтвердить в
https://fal.ai/models/fal-ai/bytedance/seedream (или сменить агрегатора
целиком), когда появится ключ. Значение по умолчанию — рабочая гипотеза, не
проверено вызовом.
"""
import asyncio
import base64
import time

import httpx

from ..config import settings
from .base import ImageProvider, ProviderError, ProviderTimeout, VisualizeParams
from .prompt import build_prompt

FAL_QUEUE_BASE = "https://queue.fal.run"
DEFAULT_MODEL_SLUG = "fal-ai/bytedance/seedream/v4-5/edit"
POLL_INTERVAL_S = 0.5


class SeedreamProvider(ImageProvider):
    name = "seedream-4.5"

    async def generate(self, params: VisualizeParams) -> bytes:
        if not settings.fal_api_key:
            raise ProviderError("FAL_API_KEY не задан на сервере")

        prompt = build_prompt(params.profile_label, params.ral_code, params.ral_name, params.height_m)
        data_uri = f"data:{params.photo_content_type};base64,{base64.b64encode(params.photo_bytes).decode('ascii')}"

        headers = {"Authorization": f"Key {settings.fal_api_key}", "Content-Type": "application/json"}
        payload = {"prompt": prompt, "image_urls": [data_uri]}

        deadline = time.monotonic() + settings.provider_timeout_s
        model_slug = getattr(settings, "fal_seedream_model", None) or DEFAULT_MODEL_SLUG

        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_s) as client:
                resp = await client.post(f"{FAL_QUEUE_BASE}/{model_slug}", headers=headers, json=payload)
                if resp.status_code not in (200, 202):
                    raise ProviderError(f"Seedream (fal.ai) вернул {resp.status_code}: {resp.text[:300]}")

                created = resp.json()
                status_url = created.get("status_url")
                response_url = created.get("response_url")
                if not status_url or not response_url:
                    raise ProviderError("Seedream (fal.ai) не вернул status_url/response_url")

                while True:
                    if time.monotonic() > deadline:
                        raise ProviderTimeout(f"Seedream не завершил генерацию за {settings.provider_timeout_s} с")

                    status_resp = await client.get(status_url, headers=headers)
                    if status_resp.status_code != 200:
                        raise ProviderError(f"Seedream polling вернул {status_resp.status_code}")

                    status = status_resp.json().get("status")
                    if status == "COMPLETED":
                        break
                    if status in ("FAILED", "CANCELLED"):
                        raise ProviderError(f"Seedream вернул статус {status}")

                    await asyncio.sleep(POLL_INTERVAL_S)

                result_resp = await client.get(response_url, headers=headers)
                if result_resp.status_code != 200:
                    raise ProviderError(f"Seedream результат вернул {result_resp.status_code}")

                result = result_resp.json()
                images = result.get("images") or []
                if not images or not images[0].get("url"):
                    raise ProviderError("Seedream не вернул изображение в ответе")

                image_resp = await client.get(images[0]["url"])
                if image_resp.status_code != 200:
                    raise ProviderError("Не удалось скачать результат Seedream")
                return image_resp.content
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"Seedream не ответил за {settings.provider_timeout_s} с") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ошибка сети при обращении к Seedream: {exc}") from exc
