import asyncio
import logging
import os

from dotenv import load_dotenv
load_dotenv()

import handlers.loader  # noqa: env check + logging setup

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from handlers.handlers import register_handlers
from bot.throttle import is_allowed, remaining
from bot.cache import catalog_cache, likes_cache, users_cache, CACHE_TTL

BOT_TOKEN = os.getenv("BOT_TOKEN")

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  Rate-limit middleware
# ══════════════════════════════════════════════

class ThrottleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            if user_id not in _get_admin_ids():
                if not is_allowed(user_id):
                    secs = remaining(user_id)
                    await event.answer(
                        f"⏳ Не так быстро! Подожди ещё {secs:.1f} сек.",
                        show_alert=False,
                    )
                    return

        elif isinstance(event, Message):
            user_id = event.from_user.id
            if user_id not in _get_admin_ids():
                if not is_allowed(user_id):
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    logger.debug(f"Throttled message from {user_id}")
                    return

        return await handler(event, data)


def _get_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


# ══════════════════════════════════════════════
#  Фоновая задача: автосброс кэша
# ══════════════════════════════════════════════

async def _cache_auto_invalidate():
    """
    Тихо сбрасывает весь кэш каждые CACHE_TTL секунд.
    Кэш и так истекает по TTL при чтении, но эта задача
    гарантирует что память не накапливает устаревшие записи
    и данные обновятся даже если никто не открывал каталог.
    """
    while True:
        await asyncio.sleep(CACHE_TTL)
        catalog_cache.invalidate_all()
        likes_cache.invalidate()   # сбрасываем и кэш лайков
        users_cache.invalidate()   # сбрасываем и кэш пользователей


# ══════════════════════════════════════════════
#  Run
# ══════════════════════════════════════════════

async def run():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ThrottleMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())

    register_handlers(dp, bot)

    # Запускаем фоновую задачу автосброса кэша
    asyncio.create_task(_cache_auto_invalidate())
    logger.info(f"🗄 Авто-сброс кэша каждые {CACHE_TTL} сек")

    logger.info("🚀 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
