import os
import base64
import json
import logging
import asyncio
import aiohttp

from .errors import GitHubEnvError, GitHubLoadError
from .cache import catalog_cache, likes_cache, users_cache

log = logging.getLogger(__name__)

LIKES_FILE = "likes.json"
USERS_FILE = "users.json"


class GitHubLoader:
    """
    Загружает и обновляет каталог товаров + лайки через GitHub Contents API.
    Формат строки каталога: url;title;description;author;likes;downloads;tag
    Лайки хранятся в likes.json: {"category:line_idx": [user_id, ...]}

    Все чтения идут через in-memory кэш.
    Запись инвалидирует соответствующий кэш.
    """

    BASE_API = "https://api.github.com"

    CATALOG_FILES = {
        "texture":  "texture_packs.txt",
        "addon":    "addons.txt",
        "map":      "maps.txt",
        "seed":     "seeds.txt",
        "template": "world_templates.txt",
    }

    def __init__(self):
        self.repo  = os.getenv("GITHUB_REPO")
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.repo or not self.token:
            raise GitHubEnvError()
        log.info(f"GitHubLoader init: repo={self.repo}, token={self.token[:8]}...")

    # ── Headers ──────────────────────────────────────────────────────

    @property
    def _headers(self) -> dict:
        return {
            "Authorization":        f"Bearer {self.token}",
            "Accept":               "application/vnd.github+json",
            "Content-Type":         "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api_url(self, filepath: str) -> str:
        return f"{self.BASE_API}/repos/{self.repo}/contents/{filepath}"

    # ── Low-level GitHub API ──────────────────────────────────────────

    async def _get_file_meta(self, filepath: str) -> dict:
        url = self._api_url(filepath)
        log.info(f"GitHub GET → {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers) as r:
                body = await r.text()
                log.info(f"GitHub GET ← {r.status} [{filepath}]")
                if r.status == 200:
                    return json.loads(body)
                if r.status == 401:
                    log.error("❌ 401 Unauthorized — токен неверный или истёк")
                elif r.status == 403:
                    log.error(f"❌ 403 Forbidden — нет прав на запись в {self.repo}")
                elif r.status == 404:
                    log.error(f"❌ 404 Not Found — файл '{filepath}' не найден")
                else:
                    log.error(f"❌ GitHub GET {r.status} [{filepath}]: {body[:300]}")
                raise GitHubLoadError()

    async def _get_file_meta_or_none(self, filepath: str) -> dict | None:
        """Как _get_file_meta, но возвращает None если файл не существует (404)."""
        url = self._api_url(filepath)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers) as r:
                body = await r.text()
                if r.status == 200:
                    return json.loads(body)
                if r.status == 404:
                    return None
                log.error(f"❌ GitHub GET {r.status} [{filepath}]: {body[:300]}")
                raise GitHubLoadError()

    async def _load_raw_from_github(self, filepath: str) -> str:
        meta = await self._get_file_meta(filepath)
        return base64.b64decode(meta["content"].replace("\n", "")).decode("utf-8")

    async def _put_file(self, filepath: str, content: str, sha: str | None, message: str):
        """
        Создаёт или обновляет файл на GitHub.
        sha=None → создание нового файла (PUT без sha).
        sha=str  → обновление существующего.
        """
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload: dict = {"message": message, "content": encoded}
        if sha:
            payload["sha"] = sha

        url = self._api_url(filepath)
        log.info(f"GitHub PUT → {url}")
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=self._headers, data=json.dumps(payload)) as r:
                body = await r.text()
                if r.status in (200, 201):
                    log.info(f"GitHub PUT ← OK [{filepath}]")
                    return
                if r.status == 401:
                    log.error("❌ PUT 401 — токен не авторизован для записи")
                elif r.status == 403:
                    log.error(f"❌ PUT 403 — нет прав на запись в {self.repo}")
                elif r.status == 422:
                    log.error(f"❌ PUT 422 — неверный SHA или конфликт: {body[:300]}")
                else:
                    log.error(f"❌ GitHub PUT {r.status} [{filepath}]: {body[:300]}")
                raise GitHubLoadError()

    # ── Parse / Encode каталога ───────────────────────────────────────

    @staticmethod
    def _parse_line(line: str) -> dict | None:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 7:
            return None
        return {
            "url":         parts[0],
            "title":       parts[1],
            "description": parts[2],
            "author":      parts[3],
            "likes":       int(parts[4]) if parts[4].isdigit() else 0,
            "downloads":   int(parts[5]) if parts[5].isdigit() else 0,
            "tag":         parts[6],
        }

    @staticmethod
    def _encode_line(item: dict) -> str:
        return ";".join([
            item.get("url", ""),
            item.get("title", ""),
            item.get("description", ""),
            item.get("author", ""),
            str(item.get("likes", 0)),
            str(item.get("downloads", 0)),
            item.get("tag", "normal"),
        ])

    def _parse_items(self, raw: str, category: str) -> list[dict]:
        items = []
        for idx, line in enumerate(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            item = self._parse_line(line)
            if item:
                item["_line_idx"] = idx
                item["_category"] = category
                items.append(item)
        return items

    # ── Каталог: read ─────────────────────────────────────────────────

    async def load_catalog(self, category: str) -> list[dict]:
        cached = catalog_cache.get(category)
        if cached is not None:
            log.debug(f"Cache HIT [{category}]")
            return cached

        async with catalog_cache._lock_for(category):
            cached = catalog_cache.get(category)
            if cached is not None:
                return cached

            filepath = self.CATALOG_FILES.get(category)
            if not filepath:
                return []
            try:
                raw   = await self._load_raw_from_github(filepath)
                items = self._parse_items(raw, category)
                catalog_cache.set(category, items)
                return items
            except GitHubLoadError:
                return []

    # ── Каталог: write ────────────────────────────────────────────────

    async def update_item_stats(self, category: str, line_idx: int, item: dict):
        filepath = self.CATALOG_FILES.get(category)
        if not filepath:
            return
        raw   = await self._load_raw_from_github(filepath)
        lines = raw.splitlines()
        if line_idx >= len(lines):
            log.error(f"update_item_stats: line_idx {line_idx} вне диапазона")
            return
        lines[line_idx] = self._encode_line(item)
        new_content = "\n".join(lines) + "\n"
        meta = await self._get_file_meta(filepath)
        await self._put_file(filepath, new_content, meta["sha"], "bot: update stats")
        catalog_cache.invalidate(category)

    async def append_item(self, category: str, item: dict):
        filepath = self.CATALOG_FILES.get(category)
        if not filepath:
            raise ValueError(f"Неизвестная категория: {category}")
        try:
            raw  = await self._load_raw_from_github(filepath)
            meta = await self._get_file_meta(filepath)
            sha  = meta["sha"]
        except GitHubLoadError:
            raw = ""
            sha = None
        new_content = raw.rstrip("\n") + "\n" + self._encode_line(item) + "\n"
        await self._put_file(filepath, new_content, sha, "bot: add item")
        catalog_cache.invalidate(category)

    # ── Лайки: read ───────────────────────────────────────────────────

    async def _load_likes_from_github(self) -> dict:
        """Загружает likes.json с GitHub. Если файла нет — возвращает {}."""
        meta = await self._get_file_meta_or_none(LIKES_FILE)
        if meta is None:
            log.info("likes.json не найден на GitHub, создадим при первом лайке")
            return {}
        raw = base64.b64decode(meta["content"].replace("\n", "")).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("likes.json повреждён, сбрасываем")
            return {}

    async def _ensure_likes_loaded(self):
        """Загружает лайки в кэш если ещё не загружены."""
        if likes_cache.is_loaded():
            return
        async with likes_cache._lock:
            if likes_cache.is_loaded():
                return
            data = await self._load_likes_from_github()
            likes_cache.set_all(data)

    async def has_liked(self, user_id: int, category: str, line_idx: int) -> bool:
        """Проверяет лайкал ли пользователь этот товар. Читает из кэша."""
        await self._ensure_likes_loaded()
        return likes_cache.has_liked(user_id, category, line_idx)

    # ── Лайки: write ──────────────────────────────────────────────────

    async def add_like(self, user_id: int, category: str, line_idx: int):
        """
        Добавляет лайк пользователя.
        1. Загружает актуальный likes.json с GitHub (свежий GET)
        2. Добавляет запись
        3. Сохраняет обратно на GitHub
        4. Обновляет кэш
        """
        # Всегда берём свежие данные с GitHub перед записью (избегаем конфликтов)
        raw_data = await self._load_likes_from_github()

        key = f"{category}:{line_idx}"
        if key not in raw_data:
            raw_data[key] = []

        if user_id in raw_data[key]:
            # Уже есть — ничего не делаем
            return

        raw_data[key].append(user_id)

        # Сохраняем на GitHub
        content = json.dumps(raw_data, ensure_ascii=False, indent=2)
        meta    = await self._get_file_meta_or_none(LIKES_FILE)
        sha     = meta["sha"] if meta else None
        await self._put_file(LIKES_FILE, content, sha, "bot: add like")

        # Обновляем кэш в памяти
        likes_cache.set_all(raw_data)
        log.info(f"Like added: user={user_id}, {key}")

    # ── Пользователи: read ────────────────────────────────────────────

    async def _load_users_from_github(self) -> dict:
        """Загружает users.json с GitHub. Если файла нет — возвращает {}."""
        meta = await self._get_file_meta_or_none(USERS_FILE)
        if meta is None:
            log.info("users.json не найден на GitHub, создадим при первом /start")
            return {}
        raw = base64.b64decode(meta["content"].replace("\n", "")).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error("users.json повреждён, сбрасываем")
            return {}

    async def _ensure_users_loaded(self):
        if users_cache.is_loaded():
            return
        async with users_cache._lock:
            if users_cache.is_loaded():
                return
            data = await self._load_users_from_github()
            users_cache.set_all(data)

    async def get_users_count(self) -> int:
        await self._ensure_users_loaded()
        return users_cache.count()

    async def get_all_user_ids(self) -> list[int]:
        await self._ensure_users_loaded()
        return users_cache.all_ids()

    # ── Пользователи: write ───────────────────────────────────────────

    async def register_user(
        self, user_id: int, name: str, username: str | None
    ):
        """
        Сохраняет нового пользователя в users.json на GitHub.
        Если пользователь уже есть — ничего не делает (только кэш).
        """
        from datetime import datetime

        # Быстрая проверка через кэш — если уже есть, не делаем запрос
        await self._ensure_users_loaded()
        if users_cache.has_user(user_id):
            return

        # Пользователь новый — загружаем актуальный файл и дописываем
        raw_data = await self._load_users_from_github()

        # Двойная проверка (мог появиться пока грузили)
        if str(user_id) in raw_data:
            users_cache.set_all(raw_data)
            return

        joined = datetime.now().isoformat(timespec="seconds")
        raw_data[str(user_id)] = {
            "name":     name,
            "username": username or "",
            "joined":   joined,
        }

        content = json.dumps(raw_data, ensure_ascii=False, indent=2)
        meta    = await self._get_file_meta_or_none(USERS_FILE)
        sha     = meta["sha"] if meta else None
        await self._put_file(USERS_FILE, content, sha, "bot: new user")

        users_cache.set_all(raw_data)
        log.info(f"New user saved to GitHub: {user_id} ({name})")
