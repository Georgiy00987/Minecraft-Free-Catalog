"""
In-memory кэш каталогов.
Данные загружаются с GitHub один раз и хранятся в памяти.
Инвалидация происходит:
  - автоматически через TTL (по умолчанию 10 минут)
  - принудительно при записи (лайк, скачивание, добавление товара)
"""

import time
import logging
import asyncio

log = logging.getLogger(__name__)

# Время жизни кэша в секундах (10 минут)
CACHE_TTL = int(__import__("os").getenv("CACHE_TTL", "600"))


class CatalogCache:
    def __init__(self):
        # { category: {"items": [...], "expires_at": float} }
        self._store: dict[str, dict] = {}
        # Локи чтобы не делать несколько одновременных запросов к одной категории
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, category: str) -> asyncio.Lock:
        if category not in self._locks:
            self._locks[category] = asyncio.Lock()
        return self._locks[category]

    def is_valid(self, category: str) -> bool:
        entry = self._store.get(category)
        if not entry:
            return False
        return time.monotonic() < entry["expires_at"]

    def get(self, category: str) -> list[dict] | None:
        if self.is_valid(category):
            return self._store[category]["items"]
        return None

    def set(self, category: str, items: list[dict]):
        self._store[category] = {
            "items":      items,
            "expires_at": time.monotonic() + CACHE_TTL,
        }
        log.info(f"Cache SET [{category}] — {len(items)} items, TTL {CACHE_TTL}s")

    def invalidate(self, category: str):
        """Принудительно сбросить кэш категории после записи на GitHub."""
        if category in self._store:
            del self._store[category]

    def invalidate_all(self):
        self._store.clear()

    def stats(self) -> str:
        now = time.monotonic()
        lines = []
        for cat, entry in self._store.items():
            ttl_left = max(0, entry["expires_at"] - now)
            lines.append(f"  {cat}: {len(entry['items'])} items, expires in {ttl_left:.0f}s")
        return "\n".join(lines) if lines else "  (пусто)"


# Глобальный экземпляр
catalog_cache = CatalogCache()


# ── Кэш лайков ────────────────────────────────────────────────────────────────
# Хранит likes.json в памяти чтобы не грузить GitHub при каждой проверке
# { "category:line_idx": [user_id, ...] }

class LikesCache:
    def __init__(self):
        self._data: dict | None = None   # None = не загружен
        self._lock = asyncio.Lock()

    def is_loaded(self) -> bool:
        return self._data is not None

    def get_all(self) -> dict:
        return self._data or {}

    def set_all(self, data: dict):
        self._data = data
        log.info(f"LikesCache SET — {sum(len(v) for v in data.values())} total likes")

    def has_liked(self, user_id: int, category: str, line_idx: int) -> bool:
        if self._data is None:
            return False
        key = f"{category}:{line_idx}"
        return user_id in self._data.get(key, [])

    def add_like(self, user_id: int, category: str, line_idx: int):
        if self._data is None:
            self._data = {}
        key = f"{category}:{line_idx}"
        if key not in self._data:
            self._data[key] = []
        if user_id not in self._data[key]:
            self._data[key].append(user_id)

    def invalidate(self):
        self._data = None


likes_cache = LikesCache()


# ── Кэш пользователей ─────────────────────────────────────────────────────────
# Хранит users.json в памяти
# { "user_id": {"name": ..., "username": ..., "joined": ...} }

class UsersCache:
    def __init__(self):
        self._data: dict | None = None
        self._lock = asyncio.Lock()

    def is_loaded(self) -> bool:
        return self._data is not None

    def get_all(self) -> dict:
        return self._data or {}

    def set_all(self, data: dict):
        self._data = data
        log.info(f"UsersCache SET — {len(data)} users")

    def has_user(self, user_id: int) -> bool:
        if self._data is None:
            return False
        return str(user_id) in self._data

    def add_user(self, user_id: int, name: str, username: str | None, joined: str):
        if self._data is None:
            self._data = {}
        self._data[str(user_id)] = {
            "name":     name,
            "username": username or "",
            "joined":   joined,
        }

    def count(self) -> int:
        return len(self._data) if self._data else 0

    def all_ids(self) -> list[int]:
        if not self._data:
            return []
        return [int(k) for k in self._data.keys()]

    def invalidate(self):
        self._data = None


users_cache = UsersCache()
