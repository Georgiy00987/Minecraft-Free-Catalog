import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.github_loader import GitHubLoader
from bot.throttle import reset as throttle_reset
from bot.texture_pack_creator import MinecraftTexturePackCreator, TexturePackMeta
from bot.utils import format_item_card, category_label
from handlers.markups import (
    main_menu_kb, catalog_categories_kb, items_list_kb,
    filter_kb, item_detail_kb, download_confirm_kb,
    create_category_kb, back_to_main_kb, cancel_create_kb,
    admin_main_kb, admin_add_category_kb, admin_cancel_kb, admin_confirm_kb,
    broadcast_main_kb, broadcast_parse_mode_kb, broadcast_cancel_kb,
    broadcast_confirm_kb, broadcast_buttons_kb, build_user_buttons_kb,
)

logger = logging.getLogger(__name__)

SUPPORT_URL   = os.getenv("SUPPORT_URL", "https://t.me/your_support")
DONATE_URL    = os.getenv("DONATE_URL",  "https://donate.your_link")
POPULAR_LIMIT = int(os.getenv("POPULAR_LIKES_LIMIT", "50"))

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}

BOT_ENABLED: bool = True

loader  = GitHubLoader()
creator = MinecraftTexturePackCreator()

MAIN_TEXT = (
    "⛏ *Добро пожаловать в Minecraft Resource Bot!* 🎮\n\n"
    "Здесь ты найдёшь лучшие ресурс-паки, аддоны,\n"
    "карты и шаблоны для *Minecraft Bedrock Edition*.\n\n"
    "Выбери действие 👇"
)
BOT_DISABLED_TEXT = "🔴 *Бот временно недоступен*\n\nВедутся технические работы. Попробуй позже."


# ══════════════════════════════════════════════
#  FSM States
# ══════════════════════════════════════════════

class CreatePack(StatesGroup):
    """
    Пользователь создаёт .mcpack файл для себя.
    Бот генерирует заготовку и отправляет файл — в каталог НЕ публикует.
    """
    waiting_title       = State()
    waiting_description = State()
    waiting_author      = State()
    waiting_icon        = State()
    confirm             = State()


class AdminAdd(StatesGroup):
    """Админ добавляет товар в каталог на GitHub."""
    choose_category = State()
    waiting_title   = State()
    waiting_desc    = State()
    waiting_author  = State()
    waiting_url     = State()
    confirm         = State()


class Broadcast(StatesGroup):
    menu       = State()
    set_text   = State()
    set_photo  = State()
    add_button = State()
    confirm    = State()


# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════

def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def _safe_delete(msg: Message):
    try:
        await msg.delete()
    except Exception:
        pass


async def _edit_menu(call: CallbackQuery, text: str, kb, parse_mode="Markdown"):
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode=parse_mode)
    except Exception:
        pass
    await call.answer()


async def _send_menu(message: Message, text: str, kb, parse_mode="Markdown") -> Message:
    return await message.answer(text, reply_markup=kb, parse_mode=parse_mode)


async def _check_enabled(call: CallbackQuery) -> bool:
    if not BOT_ENABLED and not _is_admin(call.from_user.id):
        await call.answer(BOT_DISABLED_TEXT, show_alert=True)
        return False
    return True


async def _admin_panel_text() -> str:
    count = await loader.get_users_count()
    return (
        "🛡 *Админ-панель*\n\n"
        f"Статус бота: {'🟢 Включён' if BOT_ENABLED else '🔴 Выключен'}\n"
        f"👥 Пользователей: *{count}*\n\n"
        "Выбери действие:"
    )


# helper для FSM пользователя — редактируем одно меню-сообщение
async def _user_edit(message: Message, state: FSMContext, text: str, kb):
    data    = await state.get_data()
    menu_id = data.get("menu_msg_id")
    await _safe_delete(message)
    if menu_id:
        try:
            await message.bot.edit_message_text(
                text, chat_id=message.chat.id, message_id=menu_id,
                reply_markup=kb, parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"_user_edit: {e}")


# helper для FSM админа
async def _adm_edit(message: Message, state: FSMContext, text: str, kb):
    data    = await state.get_data()
    menu_id = data.get("adm_menu_id")
    await _safe_delete(message)
    if menu_id:
        try:
            await message.bot.edit_message_text(
                text, chat_id=message.chat.id, message_id=menu_id,
                reply_markup=kb, parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"_adm_edit: {e}")


# ══════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════

async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    throttle_reset(message.from_user.id)
    await loader.register_user(
        message.from_user.id,
        message.from_user.first_name,
        message.from_user.username,
    )
    if not BOT_ENABLED and not _is_admin(message.from_user.id):
        await message.answer(BOT_DISABLED_TEXT)
        return
    await _send_menu(message, MAIN_TEXT, main_menu_kb())


# ══════════════════════════════════════════════
#  back:
# ══════════════════════════════════════════════

async def cb_back(call: CallbackQuery, state: FSMContext):
    if not await _check_enabled(call):
        return
    target = call.data.split(":")[1]
    await state.clear()
    if target == "main":
        await _edit_menu(call, MAIN_TEXT, main_menu_kb())
    elif target == "catalog":
        await _edit_menu(call, "📦 *Каталог*\n\nВыбери категорию:", catalog_categories_kb())


# ══════════════════════════════════════════════
#  menu:
# ══════════════════════════════════════════════

async def cb_menu(call: CallbackQuery, state: FSMContext):
    if not await _check_enabled(call):
        return
    action = call.data.split(":")[1]

    if action == "catalog":
        await _edit_menu(call, "📦 *Каталог*\n\nВыбери категорию:", catalog_categories_kb())

    elif action == "create":
        # Объясняем пользователю что здесь — генератор заготовки пака
        await _edit_menu(call,
            "🛠 *Создать текстур-пак*\n\n"
            "Бот создаст для тебя готовую заготовку `.mcpack` файла!\n\n"
            "📦 Внутри будет:\n"
            "• `manifest.json` с твоими данными\n"
            "• `pack_icon.png` — твоя иконка\n\n"
            "Ты сможешь сразу установить пак на Minecraft Bedrock.\n\n"
            "Хочешь создать заготовку?",
            create_category_kb(),
        )

    elif action == "info":
        await _edit_menu(call,
            "ℹ️ *О боте*\n\n"
            "Этот бот — *бесплатный каталог* ресурсов для\n"
            "*Minecraft Bedrock Edition*.\n\n"
            "📦 Категории:\n"
            "• 🎨 Текстур-паки / Ресурс-паки\n"
            "• ➕ Аддоны\n"
            "• 🗺 Карты\n"
            "• 🌱 Сиды (Seeds)\n"
            "• 📐 Шаблоны миров\n\n"
            "🛠 Также ты можешь создать заготовку своего текстур-пака!\n\n"
            "📁 Данные хранятся на GitHub.\n"
            "❤️ Полностью бесплатно!",
            back_to_main_kb(),
        )

    elif action == "donate":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Поддержать", url=DONATE_URL)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")],
        ])
        await _edit_menu(call,
            "💰 *Поддержать создателей*\n\n"
            "Если тебе нравится бот — поддержи нас!\n"
            "Каждый донат очень важен ❤️",
            kb,
        )

    elif action == "support":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")],
        ])
        await _edit_menu(call,
            "🆘 *Поддержка*\n\n"
            "Если возникли вопросы — напиши нам!\n\n"
            "⬇️ Нажми кнопку ниже.",
            kb,
        )


# ══════════════════════════════════════════════
#  cat:
# ══════════════════════════════════════════════

async def cb_catalog_page(call: CallbackQuery):
    if not await _check_enabled(call):
        return
    parts      = call.data.split(":")
    category   = parts[1]
    page       = int(parts[2])
    tag_filter = parts[3] if len(parts) > 3 else "all"

    items = await loader.load_catalog(category)
    if tag_filter != "all":
        items = [i for i in items if i.get("tag") == tag_filter]

    cat_name = category_label(category)
    if not items:
        await _edit_menu(call, f"📦 *{cat_name}*\n\n_Товаров не найдено 😔_",
                         items_list_kb([], page, category, tag_filter))
        return

    total = max(1, (len(items) + 8) // 9)
    text  = (
        f"📦 *{cat_name}*\n\n"
        f"Страница *{page+1}* из *{total}* · Всего: *{len(items)}*\n\n"
        "Выбери товар 👇"
    )
    await _edit_menu(call, text, items_list_kb(items, page, category, tag_filter))


# ══════════════════════════════════════════════
#  filter:
# ══════════════════════════════════════════════

async def cb_filter(call: CallbackQuery):
    if not await _check_enabled(call):
        return
    parts    = call.data.split(":")
    category = parts[1]
    page     = int(parts[2])
    await _edit_menu(call, "🔎 *Выбери фильтр:*", filter_kb(category, page))


# ══════════════════════════════════════════════
#  item:
# ══════════════════════════════════════════════

async def cb_item(call: CallbackQuery):
    if not await _check_enabled(call):
        return
    parts      = call.data.split(":")
    category   = parts[1]
    item_idx   = int(parts[2])
    page       = int(parts[3])
    tag_filter = parts[4] if len(parts) > 4 else "all"

    items = await loader.load_catalog(category)
    if tag_filter != "all":
        items = [i for i in items if i.get("tag") == tag_filter]

    if item_idx >= len(items):
        await call.answer("❌ Товар не найден", show_alert=True)
        return

    item = items[item_idx]
    await _edit_menu(call, format_item_card(item),
                     item_detail_kb(item, category, item_idx, page, tag_filter))


# ══════════════════════════════════════════════
#  dl_ask:
# ══════════════════════════════════════════════

async def cb_dl_ask(call: CallbackQuery):
    if not await _check_enabled(call):
        return
    parts      = call.data.split(":")
    category   = parts[1]
    item_idx   = int(parts[2])
    page       = int(parts[3])
    tag_filter = parts[4] if len(parts) > 4 else "all"

    items = await loader.load_catalog(category)
    if tag_filter != "all":
        items = [i for i in items if i.get("tag") == tag_filter]

    if item_idx >= len(items):
        await call.answer("❌ Товар не найден", show_alert=True)
        return

    item     = items[item_idx]
    real_idx = item.get("_line_idx", item_idx)
    item["downloads"] = item.get("downloads", 0) + 1
    if item["downloads"] >= POPULAR_LIMIT or item.get("likes", 0) >= POPULAR_LIMIT:
        item["tag"] = "popular"

    try:
        await loader.update_item_stats(category, real_idx, item)
    except Exception as e:
        logger.warning(f"Не удалось обновить скачивания: {e}")

    await _edit_menu(call,
        f"⬇️ *Подтверди скачивание*\n\n"
        f"📝 *{item['title']}*\n\n"
        "Нажми кнопку ниже — тебя перенаправит на файл.\n"
        "Или нажми «Отмена» чтобы вернуться.",
        download_confirm_kb(item["url"], category, item_idx, page, tag_filter),
    )


# ══════════════════════════════════════════════
#  like:
# ══════════════════════════════════════════════

async def cb_like(call: CallbackQuery):
    if not await _check_enabled(call):
        return
    parts      = call.data.split(":")
    category   = parts[1]
    item_idx   = int(parts[2])
    page       = int(parts[3])
    tag_filter = parts[4] if len(parts) > 4 else "all"
    user_id    = call.from_user.id

    items = await loader.load_catalog(category)
    if tag_filter != "all":
        items = [i for i in items if i.get("tag") == tag_filter]

    if item_idx >= len(items):
        await call.answer("❌ Товар не найден", show_alert=True)
        return

    item     = items[item_idx]
    real_idx = item.get("_line_idx", item_idx)

    if await loader.has_liked(user_id, category, real_idx):
        await call.answer("❤️ Ты уже лайкал этот товар!", show_alert=True)
        return

    item["likes"] = item.get("likes", 0) + 1
    if item["likes"] >= POPULAR_LIMIT or item.get("downloads", 0) >= POPULAR_LIMIT:
        item["tag"] = "popular"

    try:
        await loader.update_item_stats(category, real_idx, item)
        await loader.add_like(user_id, category, real_idx)
        await call.answer("❤️ Лайк поставлен! Спасибо!")
    except Exception as e:
        logger.warning(f"Не удалось обновить лайки: {e}")
        await call.answer("❌ Ошибка при сохранении", show_alert=True)
        return

    try:
        await call.message.edit_text(
            format_item_card(item),
            reply_markup=item_detail_kb(item, category, item_idx, page, tag_filter),
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ══════════════════════════════════════════════
#  create: — FSM генерации .mcpack для пользователя
#  (в каталог НЕ публикует — только отдаёт файл)
# ══════════════════════════════════════════════

async def cb_create_start(call: CallbackQuery, state: FSMContext):
    if not await _check_enabled(call):
        return
    await state.update_data(menu_msg_id=call.message.message_id)
    await state.set_state(CreatePack.waiting_title)
    await _edit_menu(call,
        "🎨 *Создание заготовки текстур-пака*\n\n"
        "Шаг *1/4* — Введи *название* пака:",
        cancel_create_kb(),
    )


async def fsm_get_title(message: Message, state: FSMContext):
    title = message.text.strip() if message.text else ""
    if len(title) < 3:
        await _user_edit(message, state,
            "🎨 *Создание заготовки*\n\n"
            "❌ Название слишком короткое!\n\n"
            "Шаг *1/4* — Введи *название* (мин. 3 символа):",
            cancel_create_kb())
        return
    await state.update_data(title=title)
    await state.set_state(CreatePack.waiting_description)
    await _user_edit(message, state,
        f"✅ Название: *{title}*\n\nШаг *2/4* — Введи *описание* пака:",
        cancel_create_kb())


async def fsm_get_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip() if message.text else "")
    await state.set_state(CreatePack.waiting_author)
    await _user_edit(message, state,
        "Шаг *3/4* — Введи *имя автора* (твой ник):",
        cancel_create_kb())


async def fsm_get_author(message: Message, state: FSMContext):
    await state.update_data(author=message.text.strip() if message.text else "Unknown")
    await state.set_state(CreatePack.waiting_icon)
    await _user_edit(message, state,
        "Шаг *4/4* — Отправь *иконку* пака 🖼\n\n"
        "Отправь PNG/JPG изображение.\n"
        "Или напиши `пропустить` чтобы создать пак без иконки.",
        cancel_create_kb())


async def fsm_get_icon(message: Message, state: FSMContext):
    icon_bytes = None

    if message.photo:
        # Пользователь прислал фото
        try:
            photo   = message.photo[-1]
            file    = await message.bot.get_file(photo.file_id)
            buf     = await message.bot.download_file(file.file_path)
            icon_bytes = buf.read()
        except Exception as e:
            logger.warning(f"Ошибка загрузки иконки: {e}")
            await _user_edit(message, state,
                "❌ Не удалось загрузить фото. Попробуй ещё раз или напиши `пропустить`:",
                cancel_create_kb())
            return

    elif message.text and message.text.strip().lower() in ("пропустить", "skip"):
        icon_bytes = None  # без иконки
    else:
        await _user_edit(message, state,
            "⚠️ Пожалуйста, отправь *изображение* или напиши `пропустить`:",
            cancel_create_kb())
        return

    await state.update_data(icon_bytes=icon_bytes)
    await state.set_state(CreatePack.confirm)

    data = await state.get_data()
    icon_status = "✅ Иконка добавлена" if icon_bytes else "— Без иконки"
    await _user_edit(message, state,
        "📋 *Проверь данные перед созданием:*\n\n"
        f"📝 Название: *{data['title']}*\n"
        f"📄 Описание: {data['description']}\n"
        f"👤 Автор: `{data['author']}`\n"
        f"🖼 Иконка: {icon_status}\n\n"
        "Создать `.mcpack` файл?",
        InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="create_confirm:yes"),
                InlineKeyboardButton(text="❌ Отмена",  callback_data="back:main"),
            ]
        ]),
    )


async def cb_create_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await call.answer("⏳ Создаю файл...")

    try:
        meta = TexturePackMeta(
            name=data.get("title", "MyPack"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
        )
        zip_buffer = await creator.create_pack(meta, data.get("icon_bytes"))
        filename   = creator.get_zip_filename(meta)

        # Отправляем файл пользователю отдельным сообщением
        await call.message.answer_document(
            BufferedInputFile(file=zip_buffer.read(), filename=filename),
            caption=(
                f"✅ *Твой текстур-пак готов!*\n\n"
                f"📦 *{meta.name}*\n"
                f"👤 Автор: `{meta.author}`\n\n"
                "Установи файл на устройство:\n"
                "1. Скачай `.mcpack`\n"
                "2. Открой файл — Minecraft запустится автоматически\n"
                "3. Пак появится в настройках ресурсов"
            ),
            parse_mode="Markdown",
        )

        # Обновляем меню на главное
        try:
            await call.message.edit_text(MAIN_TEXT, reply_markup=main_menu_kb(), parse_mode="Markdown")
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Ошибка создания пака: {e}")
        try:
            await call.message.edit_text(
                "❌ *Ошибка при создании файла.*\n\nПопробуй позже.",
                reply_markup=back_to_main_kb(),
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ══════════════════════════════════════════════
#  /admin
# ══════════════════════════════════════════════

async def cmd_admin(message: Message, state: FSMContext):
    await _safe_delete(message)
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    sent = await _send_menu(message, await _admin_panel_text(), admin_main_kb(BOT_ENABLED))
    await state.update_data(admin_menu_id=sent.message_id)


# ══════════════════════════════════════════════
#  adm:
# ══════════════════════════════════════════════

async def cb_admin(call: CallbackQuery, state: FSMContext):
    global BOT_ENABLED
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    action = call.data.split(":")[1]

    if action == "back":
        await state.set_state(None)
        await _edit_menu(call, await _admin_panel_text(), admin_main_kb(BOT_ENABLED))

    elif action == "close":
        await state.clear()
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.answer("✅ Панель закрыта")

    elif action == "toggle":
        BOT_ENABLED = not BOT_ENABLED
        await _edit_menu(call, await _admin_panel_text(), admin_main_kb(BOT_ENABLED))
        await call.answer(f"Бот {'включён' if BOT_ENABLED else 'выключен'}")

    elif action == "add":
        await state.set_state(AdminAdd.choose_category)
        await _edit_menu(call, "➕ *Добавление товара в каталог*\n\nВыбери категорию:", admin_add_category_kb())

    elif action == "cancel_add":
        await state.clear()
        await _edit_menu(call, await _admin_panel_text(), admin_main_kb(BOT_ENABLED))

    elif action == "confirm_add":
        data = await state.get_data()
        await state.clear()
        item = {
            "url":         data.get("url", ""),
            "title":       data.get("title", ""),
            "description": data.get("desc", ""),
            "author":      data.get("author", ""),
            "likes":       0,
            "downloads":   0,
            "tag":         "normal",
        }
        try:
            await loader.append_item(data.get("adm_category", "texture"), item)
            await _edit_menu(call,
                f"✅ *Товар добавлен в каталог!*\n\n"
                f"📝 *{item['title']}* опубликован.\n\n" + await _admin_panel_text(),
                admin_main_kb(BOT_ENABLED))
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            await _edit_menu(call, f"❌ *Ошибка:*\n`{e}`", admin_main_kb(BOT_ENABLED))

    elif action in ("flush_cache", "clear_cache"):
        from bot.cache import catalog_cache, likes_cache, users_cache
        catalog_cache.invalidate_all()
        likes_cache.invalidate()
        users_cache.invalidate()
        await _edit_menu(call,
            "✅ *Кэш полностью очищен!*\n\n"
            "Следующие запросы загрузят свежие данные с GitHub.\n\n" + await _admin_panel_text(),
            admin_main_kb(BOT_ENABLED))

    elif action == "broadcast":
        await state.set_state(Broadcast.menu)
        draft = {"text": "", "parse_mode": "Markdown", "photo": None, "buttons": []}
        await state.update_data(bc_draft=draft)
        count = await loader.get_users_count()
        await _edit_menu(call,
            f"📢 *Рассылка*\n\n"
            f"Создай сообщение для отправки всем пользователям.\n\n"
            f"👥 Получателей: *{count}*",
            broadcast_main_kb(draft),
        )


# ══════════════════════════════════════════════
#  adm_cat:
# ══════════════════════════════════════════════

async def cb_admin_cat(call: CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return
    category = call.data.split(":")[1]
    await state.update_data(adm_category=category, adm_menu_id=call.message.message_id)
    await state.set_state(AdminAdd.waiting_title)
    await _edit_menu(call,
        f"➕ *Добавление: {category_label(category)}*\n\nШаг *1/4* — Введи *название*:",
        admin_cancel_kb(),
    )


# ══════════════════════════════════════════════
#  AdminAdd FSM
# ══════════════════════════════════════════════

async def adm_fsm_title(message: Message, state: FSMContext):
    title = message.text.strip() if message.text else ""
    if len(title) < 2:
        await _adm_edit(message, state,
            "❌ Слишком короткое!\n\nШаг *1/4* — Введи *название*:", admin_cancel_kb())
        return
    await state.update_data(title=title)
    await state.set_state(AdminAdd.waiting_desc)
    await _adm_edit(message, state,
        f"✅ Название: *{title}*\n\nШаг *2/4* — Введи *описание*:", admin_cancel_kb())


async def adm_fsm_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text.strip() if message.text else "")
    await state.set_state(AdminAdd.waiting_author)
    await _adm_edit(message, state, "Шаг *3/4* — Введи *имя автора*:", admin_cancel_kb())


async def adm_fsm_author(message: Message, state: FSMContext):
    await state.update_data(author=message.text.strip() if message.text else "")
    await state.set_state(AdminAdd.waiting_url)
    await _adm_edit(message, state, "Шаг *4/4* — Отправь *ссылку для скачивания*:", admin_cancel_kb())


async def adm_fsm_url(message: Message, state: FSMContext):
    url = message.text.strip() if message.text else ""
    if not url.startswith("http"):
        await _adm_edit(message, state,
            "❌ Ссылка должна начинаться с http://\n\nПопробуй ещё раз:", admin_cancel_kb())
        return
    await state.update_data(url=url)
    await state.set_state(AdminAdd.confirm)
    data = await state.get_data()
    await _adm_edit(message, state,
        "📋 *Проверь данные:*\n\n"
        f"📝 Название: *{data['title']}*\n"
        f"📄 Описание: {data['desc']}\n"
        f"👤 Автор: `{data['author']}`\n"
        f"🔗 Ссылка: {data['url']}\n\nВсё верно?",
        admin_confirm_kb())


# ══════════════════════════════════════════════
#  bc: — рассылка
# ══════════════════════════════════════════════

def _get_draft(data: dict) -> dict:
    return data.get("bc_draft", {"text": "", "parse_mode": "Markdown", "photo": None, "buttons": []})


async def _show_broadcast_menu(call: CallbackQuery, state: FSMContext, extra: str = ""):
    data  = await state.get_data()
    draft = _get_draft(data)
    count = await loader.get_users_count()
    text  = f"📢 *Рассылка*\n\n👥 Получателей: *{count}*\n"
    if extra:
        text += f"\n{extra}\n"
    text += (
        "\n📋 *Черновик:*\n"
        f"• Текст: {'✅' if draft.get('text') else '—'}\n"
        f"• Фото: {'✅' if draft.get('photo') else '—'}\n"
        f"• Кнопок: {len(draft.get('buttons', []))}\n"
        f"• Форматирование: `{draft.get('parse_mode') or 'нет'}`"
    )
    await _edit_menu(call, text, broadcast_main_kb(draft))


async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа", show_alert=True)
        return

    parts  = call.data.split(":")
    action = parts[1]

    if action == "back":
        await state.set_state(Broadcast.menu)
        await _show_broadcast_menu(call, state)

    elif action == "set_text":
        await state.set_state(Broadcast.set_text)
        await _edit_menu(call,
            "✏️ *Введи текст рассылки*\n\n"
            "Поддерживаются Markdown и HTML.\n"
            "Просто отправь сообщение с текстом:",
            broadcast_cancel_kb())

    elif action == "set_photo":
        await state.set_state(Broadcast.set_photo)
        await _edit_menu(call,
            "🖼 *Отправь фото для рассылки*\n\n"
            "Прикрепи изображение.\n"
            "Или напиши `убрать` чтобы удалить текущее фото.",
            broadcast_cancel_kb())

    elif action == "set_buttons":
        data    = await state.get_data()
        draft   = _get_draft(data)
        await _edit_menu(call,
            "🔗 *Кнопки рассылки*\n\n"
            "Нажми на кнопку чтобы удалить её.\n"
            "Формат добавления: `Текст | https://url`",
            broadcast_buttons_kb(draft.get("buttons", [])))

    elif action == "add_btn":
        await state.set_state(Broadcast.add_button)
        await _edit_menu(call,
            "➕ *Добавить кнопку*\n\n"
            "Отправь в формате:\n`Текст кнопки | https://ссылка`\n\n"
            "Пример: `Скачать | https://example.com`",
            broadcast_cancel_kb())

    elif action == "del_btn":
        idx   = int(parts[2])
        data  = await state.get_data()
        draft = _get_draft(data)
        btns  = draft.get("buttons", [])
        if 0 <= idx < len(btns):
            btns.pop(idx)
        draft["buttons"] = btns
        await state.update_data(bc_draft=draft)
        await _edit_menu(call,
            "🔗 *Кнопки рассылки*\n\n"
            "Нажми на кнопку чтобы удалить её.",
            broadcast_buttons_kb(btns))

    elif action == "set_parse_mode":
        await _edit_menu(call,
            "📝 *Выбери формат текста:*\n\n"
            "• *Markdown* — `*жирный*`, `_курсив_`\n"
            "• *HTML* — `<b>жирный</b>`, `<i>курсив</i>`\n"
            "• *Без форматирования* — обычный текст",
            broadcast_parse_mode_kb())

    elif action == "pm":
        mode  = parts[2] if len(parts) > 2 else "Markdown"
        data  = await state.get_data()
        draft = _get_draft(data)
        draft["parse_mode"] = None if mode == "none" else mode
        await state.update_data(bc_draft=draft)
        await state.set_state(Broadcast.menu)
        await _show_broadcast_menu(call, state, f"✅ Форматирование: `{mode}`")

    elif action == "preview":
        data  = await state.get_data()
        draft = _get_draft(data)
        text  = draft.get("text") or "_Текст не задан_"
        pm    = draft.get("parse_mode")
        btns  = build_user_buttons_kb(draft.get("buttons", []))
        await call.answer()
        try:
            if draft.get("photo"):
                await call.message.answer_photo(
                    photo=draft["photo"], caption=text, parse_mode=pm, reply_markup=btns)
            else:
                await call.message.answer(text, parse_mode=pm, reply_markup=btns)
        except Exception as e:
            await call.message.answer(f"❌ Ошибка предпросмотра:\n`{e}`", parse_mode="Markdown")

    elif action == "send_confirm":
        count = await loader.get_users_count()
        await _edit_menu(call,
            f"📤 *Подтверди рассылку*\n\n"
            f"Сообщение будет отправлено *{count}* пользователям.\n\n"
            "⚠️ Это действие нельзя отменить.",
            broadcast_confirm_kb(count))

    elif action == "send_go":
        data     = await state.get_data()
        draft    = _get_draft(data)
        await state.set_state(Broadcast.menu)
        user_ids = await loader.get_all_user_ids()
        text     = draft.get("text") or ""
        pm       = draft.get("parse_mode")
        photo    = draft.get("photo")
        btns     = build_user_buttons_kb(draft.get("buttons", []))

        await _edit_menu(call,
            f"📤 *Рассылка запущена...*\n\nОтправляю {len(user_ids)} пользователям...", None)

        ok = fail = 0
        bot: Bot = call.bot
        for uid in user_ids:
            try:
                if photo:
                    await bot.send_photo(uid, photo=photo, caption=text, parse_mode=pm, reply_markup=btns)
                else:
                    await bot.send_message(uid, text=text, parse_mode=pm, reply_markup=btns)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.05)

        await state.update_data(bc_draft={"text": "", "parse_mode": "Markdown", "photo": None, "buttons": []})
        try:
            await call.message.edit_text(
                f"✅ *Рассылка завершена!*\n\n"
                f"📤 Отправлено: *{ok}*\n"
                f"❌ Ошибок: *{fail}*\n\n" + await _admin_panel_text(),
                reply_markup=admin_main_kb(BOT_ENABLED),
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ══════════════════════════════════════════════
#  Broadcast FSM handlers
# ══════════════════════════════════════════════

async def bc_fsm_text(message: Message, state: FSMContext):
    data  = await state.get_data()
    draft = _get_draft(data)
    draft["text"] = message.text.strip() if message.text else ""
    await state.update_data(bc_draft=draft)
    await state.set_state(Broadcast.menu)
    await _safe_delete(message)
    menu_id = data.get("admin_menu_id")
    if menu_id:
        count = await loader.get_users_count()
        try:
            await message.bot.edit_message_text(
                f"📢 *Рассылка*\n\n👥 Получателей: *{count}*\n\n"
                "✅ Текст сохранён.\n\n"
                "📋 *Черновик:*\n"
                f"• Текст: ✅\n"
                f"• Фото: {'✅' if draft.get('photo') else '—'}\n"
                f"• Кнопок: {len(draft.get('buttons', []))}\n"
                f"• Форматирование: `{draft.get('parse_mode') or 'нет'}`",
                chat_id=message.chat.id, message_id=menu_id,
                reply_markup=broadcast_main_kb(draft), parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"bc_fsm_text: {e}")


async def bc_fsm_photo(message: Message, state: FSMContext):
    data  = await state.get_data()
    draft = _get_draft(data)
    await _safe_delete(message)

    if message.text and message.text.strip().lower() == "убрать":
        draft["photo"] = None
    elif message.photo:
        draft["photo"] = message.photo[-1].file_id
    else:
        return

    await state.update_data(bc_draft=draft)
    await state.set_state(Broadcast.menu)
    menu_id = data.get("admin_menu_id")
    if menu_id:
        count = await loader.get_users_count()
        action_text = "✅ Фото сохранено." if draft.get("photo") else "✅ Фото удалено."
        try:
            await message.bot.edit_message_text(
                f"📢 *Рассылка*\n\n👥 Получателей: *{count}*\n\n"
                f"{action_text}\n\n"
                "📋 *Черновик:*\n"
                f"• Текст: {'✅' if draft.get('text') else '—'}\n"
                f"• Фото: {'✅' if draft.get('photo') else '—'}\n"
                f"• Кнопок: {len(draft.get('buttons', []))}\n"
                f"• Форматирование: `{draft.get('parse_mode') or 'нет'}`",
                chat_id=message.chat.id, message_id=menu_id,
                reply_markup=broadcast_main_kb(draft), parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"bc_fsm_photo: {e}")


async def bc_fsm_button(message: Message, state: FSMContext):
    data  = await state.get_data()
    draft = _get_draft(data)
    await _safe_delete(message)
    menu_id = data.get("admin_menu_id")

    raw = message.text.strip() if message.text else ""
    if "|" not in raw:
        if menu_id:
            try:
                await message.bot.edit_message_text(
                    "❌ Неверный формат!\n\nОтправь: `Текст кнопки | https://ссылка`",
                    chat_id=message.chat.id, message_id=menu_id,
                    reply_markup=broadcast_cancel_kb(), parse_mode="Markdown")
            except Exception:
                pass
        return

    btn_text, btn_url = raw.split("|", 1)
    btn_text = btn_text.strip()
    btn_url  = btn_url.strip()

    if not btn_url.startswith("http"):
        if menu_id:
            try:
                await message.bot.edit_message_text(
                    "❌ Ссылка должна начинаться с http://\n\nПопробуй ещё раз:",
                    chat_id=message.chat.id, message_id=menu_id,
                    reply_markup=broadcast_cancel_kb(), parse_mode="Markdown")
            except Exception:
                pass
        return

    buttons = draft.get("buttons", [])
    buttons.append({"text": btn_text, "url": btn_url})
    draft["buttons"] = buttons
    await state.update_data(bc_draft=draft)
    await state.set_state(Broadcast.menu)

    if menu_id:
        try:
            await message.bot.edit_message_text(
                f"🔗 *Кнопки рассылки*\n\n✅ Кнопка «{btn_text}» добавлена.",
                chat_id=message.chat.id, message_id=menu_id,
                reply_markup=broadcast_buttons_kb(buttons), parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"bc_fsm_button: {e}")


# ══════════════════════════════════════════════
#  /cache
# ══════════════════════════════════════════════

async def cmd_cache(message: Message, state: FSMContext):
    await _safe_delete(message)
    if not _is_admin(message.from_user.id):
        return
    from bot.cache import catalog_cache, CACHE_TTL
    stats = catalog_cache.stats()
    await message.answer(
        f"🗄 *Статус кэша*\n\nTTL: *{CACHE_TTL}* сек\n\nКатегории в кэше:\n`{stats}`",
        parse_mode="Markdown",
    )


# ══════════════════════════════════════════════
#  noop
# ══════════════════════════════════════════════

async def cb_noop(call: CallbackQuery):
    await call.answer()


# ══════════════════════════════════════════════
#  Register
# ══════════════════════════════════════════════

def register_handlers(dp: Dispatcher, bot: Bot = None):
    # Commands
    dp.message.register(cmd_start, Command(commands=["start"]))
    dp.message.register(cmd_admin, Command(commands=["admin"]))
    dp.message.register(cmd_cache, Command(commands=["cache"]))

    # FSM — пользователь: генерация .mcpack
    dp.message.register(fsm_get_title,       CreatePack.waiting_title)
    dp.message.register(fsm_get_description, CreatePack.waiting_description)
    dp.message.register(fsm_get_author,      CreatePack.waiting_author)
    dp.message.register(fsm_get_icon,        CreatePack.waiting_icon)

    # FSM — админ: добавление в каталог
    dp.message.register(adm_fsm_title,  AdminAdd.waiting_title)
    dp.message.register(adm_fsm_desc,   AdminAdd.waiting_desc)
    dp.message.register(adm_fsm_author, AdminAdd.waiting_author)
    dp.message.register(adm_fsm_url,    AdminAdd.waiting_url)

    # FSM — рассылка
    dp.message.register(bc_fsm_text,   Broadcast.set_text)
    dp.message.register(bc_fsm_photo,  Broadcast.set_photo)
    dp.message.register(bc_fsm_button, Broadcast.add_button)

    # Callbacks
    dp.callback_query.register(cb_noop,          F.data == "noop")
    dp.callback_query.register(cb_back,          F.data.startswith("back:"))
    dp.callback_query.register(cb_menu,          F.data.startswith("menu:"))
    dp.callback_query.register(cb_catalog_page,  F.data.startswith("cat:"))
    dp.callback_query.register(cb_filter,        F.data.startswith("filter:"))
    dp.callback_query.register(cb_item,          F.data.startswith("item:"))
    dp.callback_query.register(cb_dl_ask,        F.data.startswith("dl_ask:"))
    dp.callback_query.register(cb_like,          F.data.startswith("like:"))
    dp.callback_query.register(cb_create_start,  F.data.startswith("create:"))
    dp.callback_query.register(cb_create_confirm,F.data == "create_confirm:yes")
    dp.callback_query.register(cb_admin,         F.data.startswith("adm:"))
    dp.callback_query.register(cb_admin_cat,     F.data.startswith("adm_cat:"))
    dp.callback_query.register(cb_broadcast,     F.data.startswith("bc:"))
