# ⛏ Minecraft Resource Bot

Бесплатный Telegram-бот — каталог ресурсов для **Minecraft Bedrock Edition**.

## 📦 Возможности

| Раздел | Файл в репо | Создание |
|---|---|---|
| 🎨 Текстур-паки / Ресурс-паки | `texture_packs.txt` | ✅ Через бота |
| ➕ Аддоны | `addons.txt` | 👁 Только просмотр |
| 🗺 Карты | `maps.txt` | 👁 Только просмотр |
| 🌱 Сиды (Seeds) | `seeds.txt` | 👁 Только просмотр |
| 📐 Шаблоны миров | `world_templates.txt` | 👁 Только просмотр |

Репозиторий каталога: **[Georgiy00987/Shop-Minecraft](https://github.com/Georgiy00987/Shop-Minecraft)**

---

## 🚀 Установка

```bash
git clone https://github.com/yourname/minecraft-resource-bot
cd minecraft-resource-bot
pip install -r requirements.txt
cp .env.example .env
# Заполни .env
python main.py
```

---

## ⚙️ Переменные окружения (`.env`)

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `ADMIN_IDS` | ID администраторов через запятую |
| `GITHUB_REPO` | Репозиторий каталога `owner/repo` |
| `GITHUB_TOKEN` | GitHub Personal Access Token (Contents: Read & Write) |
| `POPULAR_LIKES_LIMIT` | Порог лайков/скачиваний для тега `popular` (по умолчанию 50) |
| `SUPPORT_URL` | Ссылка на чат поддержки |
| `DONATE_URL` | Ссылка для доната |

---

## 📁 Структура репозитория каталога

Репозиторий: **`Georgiy00987/Shop-Minecraft`**

```
texture_packs.txt
addons.txt
maps.txt
seeds.txt
world_templates.txt
```

### Формат каждой строки:

```
url;title;description;author;likes;downloads;tag
```

- **url** — прямая ссылка для скачивания
- **title** — название
- **description** — описание
- **author** — автор
- **likes** — количество лайков (число)
- **downloads** — количество скачиваний (число)
- **tag** — `normal` | `popular` | `unpopular`

### Пример:

```
https://example.com/pack.mcpack;Faithful 32x;Классический HD пак;Steve;120;340;popular
```

Пример файлов смотри в папке `catalog_example/`.

---

## 🗂 Структура проекта

```
minecraft_bot/
├── main.py                   # Точка входа
├── requirements.txt
├── .env.example
├── bot/
│   ├── __init__.py
│   ├── errors.py             # Классы исключений
│   ├── github_loader.py      # GitHub Contents API (чтение/запись)
│   └── utils.py              # Форматирование карточек, метки
└── handlers/
    ├── __init__.py
    ├── loader.py             # Проверка env + настройка логирования
    ├── markups.py            # Все клавиатуры (InlineKeyboard)
    └── handlers.py           # Все хэндлеры + FSM
```

---

## 🔑 GitHub Token

1. Открой [github.com/settings/tokens](https://github.com/settings/tokens)
2. Создай **Fine-grained token**
3. Выбери свой репозиторий каталога
4. Разрешения: `Contents` → **Read and write**
5. Скопируй токен в `.env`

---

## 💬 Поддержка

Задай вопрос в чате поддержки или открой Issue на GitHub.
