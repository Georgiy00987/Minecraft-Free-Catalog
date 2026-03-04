"""
Локальное хранилище на JSON-файлах.
Хранит:
  - users.json      — {user_id: {"name": ..., "username": ..., "joined": ...}}
  - likes.json      — {"category:line_idx": [user_id, ...]}
"""

import json
import os
import logging
from datetime import datetime

log = logging.getLogger(__name__)

DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
LIKES_FILE = os.path.join(DATA_DIR, "likes.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read(path: str) -> dict:
    _ensure_dir()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Storage read error {path}: {e}")
        return {}


def _write(path: str, data: dict):
    _ensure_dir()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Storage write error {path}: {e}")


# ─── Users ────────────────────────────────────────────────────────────────────

def register_user(user_id: int, first_name: str, username: str | None):
    """Добавляет пользователя если ещё нет."""
    users = _read(USERS_FILE)
    key = str(user_id)
    if key not in users:
        users[key] = {
            "name":     first_name,
            "username": username or "",
            "joined":   datetime.now().isoformat(timespec="seconds"),
        }
        _write(USERS_FILE, users)
        log.info(f"New user registered: {user_id} ({first_name})")


def get_all_user_ids() -> list[int]:
    users = _read(USERS_FILE)
    return [int(k) for k in users.keys()]


def get_users_count() -> int:
    return len(_read(USERS_FILE))


# ─── Likes ────────────────────────────────────────────────────────────────────

def _like_key(category: str, line_idx: int) -> str:
    return f"{category}:{line_idx}"


def has_liked(user_id: int, category: str, line_idx: int) -> bool:
    likes = _read(LIKES_FILE)
    key   = _like_key(category, line_idx)
    return user_id in likes.get(key, [])


def add_like(user_id: int, category: str, line_idx: int):
    likes = _read(LIKES_FILE)
    key   = _like_key(category, line_idx)
    if key not in likes:
        likes[key] = []
    if user_id not in likes[key]:
        likes[key].append(user_id)
        _write(LIKES_FILE, likes)
