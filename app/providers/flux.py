"""FLUX.1 Kontext Pro / Max (Black Forest Labs) — контекстное редактирование
с сохранением сцены. Раздел 6 ТЗ.

Асинхронный паттерн BFL (подтверждено документацией на момент написания):
  1. POST {endpoint} с prompt + input_image (base64) → {id, polling_url}
  2. GET polling_url до status == "Ready"
  3. result.sample — ссылка на готовую картинку, ЖИВЁТ ~10 МИНУТ — скачиваем
     сразу же, не откладываем.

Точный slug модели (flux-kontext-pro / flux-kontext-max) и набор полей тела
запроса стоит свериться с https://docs.bfl.ml перед P0-тестами — здесь взят
наиболее задокументированный вариант.
"""
import asyncio
import base64
import time

import httpx

from ..config import settings
from .base import ImageProvider, ProviderError, ProviderTimeout, VisualizeParams
from .prompt import build_prompt

BFL_BASE = "https://api.bfl.ai/v1"
POLL_INTERVAL_S = 0.5


class _FluxProvider(ImageProvider):
    model_slug: str

    async def generate(self, params: VisualizeParams) -> bytes:
        if not settings.bfl_api_key:
            raise ProviderError("BFL_API_KEY не задан на сервере")

        prompt = build_prompt(params.profile_label, params.ral_code, params.ral_name, params.height_m)
        photo_b64 = base64.b64encode(params.photo_bytes).decode("ascii")

        headers = {"accept": "application/json", "x-key": settings.bfl_api_key, "Content-Type": "application/json"}
        payload = {"prompt": prompt, "input_image": photo_b64}

        deadline = time.monotonic() + settings.provider_timeout_s
        try:
            async with httpx.AsyncClient(timeout=settings.provider_timeout_s) as client:
                resp = await client.post(f"{BFL_BASE}/{self.model_slug}", headers=headers, json=payload)
                if resp.status_code != 200:
                    raise ProviderError(f"FLUX вернул {resp.status_code}: {resp.text[:300]}")

                created = resp.json()
                polling_url = created.get("polling_url")
                if not polling_url:
                    raise ProviderError("FLUX не вернул polling_url")

                while True:
                    if time.monotonic() > deadline:
                        raise ProviderTimeout(f"FLUX не завершил генерацию за {settings.provider_timeout_s} с")

                    poll_resp = await client.get(polling_url, headers=headers)
                    if poll_resp.status_code != 200:
                        raise ProviderError(f"FLUX polling вернул {poll_resp.status_code}: {poll_resp.text[:300]}")

                    status_data = poll_resp.json()
                    status = status_data.get("status")

                    if status == "Ready":
                        image_url = status_data.get("result", {}).get("sample")
                        if not image_url:
                            raise ProviderError("FLUX сообщил Ready, но не вернул ссылку на картинку")
                        image_resp = await client.get(image_url)
                        if image_resp.status_code != 200:
                            raise ProviderError("Не удалось скачать результат FLUX по ссылке result.sample")
                        return image_resp.content

                    if status in ("Error", "Failed", "Content Moderated", "Request Moderated"):
                        raise ProviderError(f"FLUX вернул статус {status}")

                    await asyncio.sleep(POLL_INTERVAL_S)
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"FLUX не ответил за {settings.provider_timeout_s} с") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ошибка сети при обращении к FLUX: {exc}") from exc


class FluxKontextProProvider(_FluxProvider):
    name = "flux-kontext-pro"
    model_slug = "flux-kontext-pro"


class FluxKontextMaxProvider(_FluxProvider):
    name = "flux-kontext-max"
    model_slug = "flux-kontext-max"
