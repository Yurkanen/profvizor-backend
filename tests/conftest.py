import io
import os
import sys
from pathlib import Path

os.environ.setdefault("IMAGE_PROVIDER", "mock")
os.environ.setdefault("DB_PATH", str(Path(__file__).resolve().parent / "_test.db"))
os.environ.setdefault("DAILY_LIMIT", "3")
os.environ.setdefault("MONTHLY_LIMIT", "5")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PIL import Image


def _reset_limits_connection():
    # limits.py кэширует соединение sqlite3 на уровне модуля — если под ним
    # удалить файл БД, соединение останется висеть на старом inode и упадёт
    # с "attempt to write a readonly database". Сбрасываем кэш вместе с файлом.
    from app import limits as limits_module

    if limits_module._conn is not None:
        limits_module._conn.close()
        limits_module._conn = None


@pytest.fixture(autouse=True)
def _reset_db():
    db_path = Path(os.environ["DB_PATH"])
    _reset_limits_connection()
    if db_path.exists():
        db_path.unlink()
    yield
    _reset_limits_connection()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def sample_photo_bytes() -> bytes:
    img = Image.new("RGB", (400, 300), color=(120, 150, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()
