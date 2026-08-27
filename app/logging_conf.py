"""Логи — только метаданные запроса, никогда содержимое фото (раздел 9 ТЗ)."""
import logging
import sys


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger("profvizor")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.propagate = False
