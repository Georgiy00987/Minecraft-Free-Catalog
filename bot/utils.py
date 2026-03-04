import os
import platform


def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")


def tag_label(tag: str) -> str:
    mapping = {
        "popular":   "🔥 Популярный",
        "normal":    "⭐ Обычный",
        "unpopular": "📦 Новинка",
    }
    return mapping.get(tag, "⭐ Обычный")


def category_label(category: str) -> str:
    mapping = {
        "texture":  "🎨 Текстур-паки",
        "addon":    "➕ Аддоны",
        "map":      "🗺 Карты",
        "seed":     "🌱 Сиды (Seeds)",
        "template": "📐 Шаблоны миров",
    }
    return mapping.get(category, category)


def format_item_card(item: dict) -> str:
    tag = tag_label(item.get("tag", "normal"))
    title = item.get("title", "—")
    description = item.get("description", "—")
    author = item.get("author", "—")
    likes = item.get("likes", 0)
    downloads = item.get("downloads", 0)

    return (
        f"╔══════════════════════╗\n"
        f"  *{title}*\n"
        f"╚══════════════════════╝\n\n"
        f"📝 *Описание:*\n{description}\n\n"
        f"👤 *Автор:* `{author}`\n"
        f"🏷 *Статус:* {tag}\n\n"
        f"❤️ Лайков: *{likes}*   ⬇️ Скачиваний: *{downloads}*"
    )
