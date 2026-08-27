"""Провайдер-заглушка: работает без ключей и денег, чтобы можно было
протестировать весь путь (загрузка → API → результат → скачивание) уже
сегодня. По сути серверный вариант canvas-имитации из прототипа, только на
Pillow. НЕ фотореалистичен — это ожидаемо, замените IMAGE_PROVIDER на
настоящего провайдера, когда появятся ключи (раздел 6 ТЗ)."""
import asyncio
import io

from PIL import Image, ImageDraw

from .base import ImageProvider, VisualizeParams


class MockProvider(ImageProvider):
    name = "mock"

    async def generate(self, params: VisualizeParams) -> bytes:
        # имитируем задержку реального провайдера, чтобы фронтенд/индикатор
        # прогресса можно было проверить на реалистичных таймингах
        await asyncio.sleep(0.6)

        img = Image.open(io.BytesIO(params.photo_bytes)).convert("RGB")
        w, h = img.size
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        baseline_y = h * 0.85
        px_per_m = h * 0.16
        fence_h = params.height_m * px_per_m
        x0 = w * (params.left_pct / 100)
        fence_w = w * (params.width_pct / 100)
        y0 = baseline_y - fence_h

        hex_color = params.ral_hex.lstrip("#")
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        draw.rectangle([x0, y0, x0 + fence_w, baseline_y], fill=rgb + (235,))

        # лёгкая имитация штакетника/жалюзи полосами, чтобы разные профили
        # визуально отличались даже в заглушке
        if params.profile_id in ("picket-gap", "picket-solid", "louvre"):
            stripe_w = max(3, fence_w / 24)
            gap = stripe_w if params.profile_id == "picket-gap" else 0
            x = x0
            while x < x0 + fence_w:
                draw.rectangle([x, y0, x + stripe_w * 0.55, baseline_y], fill=(0, 0, 0, 40))
                x += stripe_w + gap

        composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        out = io.BytesIO()
        composed.save(out, format="JPEG", quality=88)
        return out.getvalue()
