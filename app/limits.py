"""Дневной/месячный лимит генераций — SQLite, переживает рестарт сервера
(в отличие от in-memory счётчика). Раздел 9 ТЗ.

Важно: увеличиваем счётчик на каждый ФАКТИЧЕСКИЙ вызов провайдера, а не на
каждый HTTP-запрос — повтор при 502/504 (раздел 9) тоже стоит денег и должен
расходовать лимит.
"""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import settings


class LimitExceeded(Exception):
    def __init__(self, scope: str):
        self.scope = scope  # "daily" | "monthly"
        super().__init__(f"{scope} limit exceeded")


_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_counters (
            period_key TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    _conn = conn
    return conn


def _period_keys(now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now(timezone.utc)
    return {
        "daily": now.strftime("d:%Y-%m-%d"),
        "monthly": now.strftime("m:%Y-%m"),
    }


def _read_counts(conn: sqlite3.Connection, keys: dict[str, str]) -> dict[str, int]:
    cur = conn.cursor()
    counts = {}
    for scope, key in keys.items():
        row = cur.execute(
            "SELECT count FROM generation_counters WHERE period_key = ?", (key,)
        ).fetchone()
        counts[scope] = row[0] if row else 0
    return counts


def check_and_increment() -> None:
    """Атомарно проверяет дневной и месячный лимиты и увеличивает оба счётчика,
    либо бросает LimitExceeded, ничего не меняя."""
    conn = _connect()
    keys = _period_keys()
    with _lock:
        counts = _read_counts(conn, keys)
        if counts["daily"] >= settings.daily_limit:
            raise LimitExceeded("daily")
        if counts["monthly"] >= settings.monthly_limit:
            raise LimitExceeded("monthly")

        cur = conn.cursor()
        for key in keys.values():
            cur.execute(
                """
                INSERT INTO generation_counters (period_key, count) VALUES (?, 1)
                ON CONFLICT(period_key) DO UPDATE SET count = count + 1
                """,
                (key,),
            )
        conn.commit()


def current_usage() -> dict:
    conn = _connect()
    keys = _period_keys()
    with _lock:
        counts = _read_counts(conn, keys)
    return {
        "daily": counts["daily"],
        "dailyLimit": settings.daily_limit,
        "monthly": counts["monthly"],
        "monthlyLimit": settings.monthly_limit,
    }
