from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils import category_label

ITEMS_PER_PAGE = 9


# ══════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════════

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Каталог",  callback_data="menu:catalog"),
            InlineKeyboardButton(text="🛠 Создать",  callback_data="menu:create"),
        ],
        [InlineKeyboardButton(text="ℹ️ О боте",      callback_data="menu:info")],
        [InlineKeyboardButton(text="💰 Поддержать создателей", callback_data="menu:donate")],
        [InlineKeyboardButton(text="🆘 Поддержка",   callback_data="menu:support")],
    ])


# ══════════════════════════════════════════════
#  КАТАЛОГ
# ══════════════════════════════════════════════

def catalog_categories_kb() -> InlineKeyboardMarkup:
    cats = ["texture", "addon", "map", "seed", "template"]
    rows = []
    for i in range(0, len(cats), 2):
        row = [
            InlineKeyboardButton(text=category_label(c), callback_data=f"cat:{c}:0")
            for c in cats[i:i+2]
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def items_list_kb(items, page, category, tag_filter="all"):
    total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    page_items = items[start: start + ITEMS_PER_PAGE]

    rows = []
    for i in range(0, len(page_items), 3):
        row = []
        for item in page_items[i:i+3]:
            idx = items.index(item)
            short = item["title"][:18] + ("…" if len(item["title"]) > 18 else "")
            row.append(InlineKeyboardButton(
                text=short,
                callback_data=f"item:{category}:{idx}:{page}:{tag_filter}",
            ))
        rows.append(row)

    nav_row = [
        InlineKeyboardButton(text="◀️", callback_data=f"cat:{category}:{page-1}:{tag_filter}")
        if page > 0 else InlineKeyboardButton(text="✖️", callback_data="noop"),

        InlineKeyboardButton(
            text={"all":"🔎 Фильтр","popular":"🔥 Популярные",
                  "normal":"⭐ Обычные","unpopular":"📦 Новинки"}.get(tag_filter,"🔎 Фильтр"),
            callback_data=f"filter:{category}:{page}",
        ),

        InlineKeyboardButton(text="▶️", callback_data=f"cat:{category}:{page+1}:{tag_filter}")
        if page < total_pages - 1 else InlineKeyboardButton(text="✖️", callback_data="noop"),
    ]
    rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filter_kb(category, page):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Популярные", callback_data=f"cat:{category}:{page}:popular"),
            InlineKeyboardButton(text="⭐ Обычные",    callback_data=f"cat:{category}:{page}:normal"),
        ],
        [
            InlineKeyboardButton(text="📦 Новинки",   callback_data=f"cat:{category}:{page}:unpopular"),
            InlineKeyboardButton(text="🔄 Все",        callback_data=f"cat:{category}:{page}:all"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"cat:{category}:{page}:all")],
    ])


def item_detail_kb(item, category, item_idx, page, tag_filter="all"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬇️ Скачать",
                callback_data=f"dl_ask:{category}:{item_idx}:{page}:{tag_filter}",
            ),
            InlineKeyboardButton(
                text=f"❤️ Лайк ({item.get('likes', 0)})",
                callback_data=f"like:{category}:{item_idx}:{page}:{tag_filter}",
            ),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"cat:{category}:{page}:{tag_filter}")],
    ])


def download_confirm_kb(url, category, item_idx, page, tag_filter="all"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить скачивание", url=url)],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"item:{category}:{item_idx}:{page}:{tag_filter}",
        )],
    ])


# ══════════════════════════════════════════════
#  СОЗДАНИЕ (пользователь)
# ══════════════════════════════════════════════

def create_category_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Текстур-пак / Ресурс-пак", callback_data="create:texture")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")],
    ])

def back_to_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back:main")],
    ])

def cancel_create_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back:main")],
    ])


# ══════════════════════════════════════════════
#  АДМИН — ГЛАВНАЯ ПАНЕЛЬ
# ══════════════════════════════════════════════

def admin_main_kb(bot_enabled: bool) -> InlineKeyboardMarkup:
    toggle = "🔴 Выключить бота" if bot_enabled else "🟢 Включить бота"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар",   callback_data="adm:add")],
        [InlineKeyboardButton(text="📢 Рассылка",         callback_data="adm:broadcast")],
        [InlineKeyboardButton(text="🗑 Сбросить кэш",    callback_data="adm:clear_cache")],
        [InlineKeyboardButton(text=toggle,                callback_data="adm:toggle")],
        [InlineKeyboardButton(text="❌ Закрыть панель",   callback_data="adm:close")],
    ])

def admin_add_category_kb() -> InlineKeyboardMarkup:
    cats = ["texture", "addon", "map", "seed", "template"]
    rows = [[InlineKeyboardButton(text=category_label(c), callback_data=f"adm_cat:{c}")] for c in cats]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="adm:cancel_add")],
    ])

def admin_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="adm:confirm_add"),
            InlineKeyboardButton(text="❌ Отмена",       callback_data="adm:cancel_add"),
        ],
    ])


# ══════════════════════════════════════════════
#  РАССЫЛКА — конструктор сообщения
# ══════════════════════════════════════════════

def broadcast_main_kb(draft: dict) -> InlineKeyboardMarkup:
    """
    draft = {
      "text": str,
      "parse_mode": "Markdown" | "HTML" | None,
      "photo": str | None,       # file_id фото
      "buttons": [{"text":..,"url":..}, ...]
    }
    """
    has_text    = bool(draft.get("text"))
    has_photo   = bool(draft.get("photo"))
    has_buttons = bool(draft.get("buttons"))
    pm          = draft.get("parse_mode") or "нет"

    rows = [
        [InlineKeyboardButton(
            text=f"✏️ {'Изменить' if has_text else 'Добавить'} текст",
            callback_data="bc:set_text",
        )],
        [InlineKeyboardButton(
            text=f"🖼 {'Изменить' if has_photo else 'Добавить'} фото",
            callback_data="bc:set_photo",
        )],
        [InlineKeyboardButton(
            text=f"🔗 {'Изменить' if has_buttons else 'Добавить'} кнопки",
            callback_data="bc:set_buttons",
        )],
        [InlineKeyboardButton(
            text=f"📝 Форматирование: *{pm}*",
            callback_data="bc:set_parse_mode",
        )],
    ]

    if has_text or has_photo:
        rows.append([InlineKeyboardButton(text="👁 Предпросмотр", callback_data="bc:preview")])
        rows.append([InlineKeyboardButton(text="📤 Отправить всем", callback_data="bc:send_confirm")])

    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_parse_mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Markdown", callback_data="bc:pm:Markdown"),
            InlineKeyboardButton(text="HTML",     callback_data="bc:pm:HTML"),
            InlineKeyboardButton(text="Без форм.", callback_data="bc:pm:none"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bc:back")],
    ])


def broadcast_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bc:back")],
    ])


def broadcast_confirm_kb(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Да, отправить {count} пользователям", callback_data="bc:send_go")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bc:back")],
    ])


def broadcast_buttons_kb(draft_buttons: list) -> InlineKeyboardMarkup:
    """Меню управления кнопками рассылки."""
    rows = []
    for i, btn in enumerate(draft_buttons):
        rows.append([InlineKeyboardButton(
            text=f"🗑 [{i+1}] {btn['text'][:25]}",
            callback_data=f"bc:del_btn:{i}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Добавить кнопку", callback_data="bc:add_btn")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bc:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_user_buttons_kb(buttons: list) -> InlineKeyboardMarkup | None:
    """Строит клавиатуру из кнопок рассылки для отправки пользователям."""
    if not buttons:
        return None
    rows = []
    for btn in buttons:
        try:
            rows.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
        except Exception:
            pass
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
