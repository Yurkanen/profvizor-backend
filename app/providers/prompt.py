"""Сборка промпта из вынесенного в файл шаблона (раздел 6 ТЗ: шаблон не
зашивается в код, потому что его придётся донастраивать по результатам
тестов на реальных фото)."""
from pathlib import Path

from ..config import settings


def build_prompt(profile_label: str, ral_code: str, ral_name: str, height_m: float) -> str:
    template = Path(settings.prompt_template_path).read_text(encoding="utf-8")
    return template.format(
        profile_label=profile_label,
        ral_code=ral_code,
        ral_name=ral_name,
        height_m=f"{height_m:.1f}",
    )
