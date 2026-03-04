import os
import logging

from bot.errors import EnvLoadError

# ── Проверка обязательных переменных окружения ──────────────────────────────
REQUIRED_ENV = [
    ("BOT_TOKEN",           str),
    ("ADMIN_IDS",           str),   # через запятую: 123456,789012
    ("GITHUB_REPO",         str),   # owner/repo
    ("GITHUB_TOKEN",        str),
    ("POPULAR_LIKES_LIMIT", int),
]

for name, _ in REQUIRED_ENV:
    if not os.getenv(name):
        raise EnvLoadError(name)

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="[LINE:%(lineno)d] [%(levelname)-5s] [%(asctime)s] %(message)s",
    level=logging.INFO,
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)
logging.getLogger("aiogram.middlewares").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("✅ Все переменные окружения загружены")
