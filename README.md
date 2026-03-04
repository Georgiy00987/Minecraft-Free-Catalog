# ⛏ Minecraft Resource Bot

Бесплатный Telegram-бот — каталог ресурсов для **Minecraft Bedrock Edition**.  
Каталог хранится в отдельном GitHub-репозитории в виде `.txt`-файлов. Бот читает и обновляет их через GitHub Contents API.

---

## 📦 Возможности

**Для пользователей:**
- Просмотр каталога по категориям с пагинацией (9 товаров на странице)
- Фильтрация по тегам: `normal`, `popular`, `unpopular`
- Просмотр карточки товара: название, описание, автор, лайки, скачивания
- Лайк товара (один раз на пользователя)
- Скачивание — бот увеличивает счётчик и перенаправляет на ссылку
- Создание заготовки `.mcpack`-файла: пошаговый FSM (название → описание → автор → иконка), бот генерирует `.zip` с `manifest.json` и `pack_icon.png` и отдаёт файл пользователю

**Для администраторов** (команда `/admin`):
- Включить / выключить бота для всех пользователей
- Добавить товар в каталог (4 шага: категория, название, описание, автор, ссылка)
- Очистить кэш вручную
- Рассылка всем пользователям: текст, фото, inline-кнопки, предпросмотр, выбор формата (Markdown / HTML / без форматирования)
- Просмотр статистики кэша: команда `/cache`

---

## 🗂 Категории каталога

| Категория | Файл в репозитории каталога | Добавление |
|---|---|---|
| 🎨 Текстур-паки / Ресурс-паки | `texture_packs.txt` | Через `/admin` |
| ➕ Аддоны | `addons.txt` | Через `/admin` |
| 🗺 Карты | `maps.txt` | Через `/admin` |
| 🌱 Сиды | `seeds.txt` | Через `/admin` |
| 📐 Шаблоны миров | `world_templates.txt` | Через `/admin` |

### Формат строки в `.txt`-файле

```
url;title;description;author;likes;downloads;tag
```

Пример:
```
https://example.com/pack.mcpack;Faithful 32x;Классический HD пак;Steve;120;340;popular
```

Допустимые значения `tag`: `normal`, `popular`, `unpopular`.  
Тег выставляется в `popular` автоматически, когда `likes` **или** `downloads` достигают порога `POPULAR_LIKES_LIMIT`.

Лайки и пользователи хранятся в том же GitHub-репозитории каталога в файлах `likes.json` и `users.json`.

---

## ⚙️ Требования

- Python **3.11+**
- Зависимости:

```
aiogram==3.22.0
aiohttp>=3.9.0
python-dotenv>=1.0.0
```

---

## 🚀 Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Georgiy00987/Minecraft-Free-Catalog.git
cd Minecraft-Free-Catalog
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Создать файл `.env`

```env
BOT_TOKEN=токен_от_BotFather
ADMIN_IDS=123456789,987654321
GITHUB_REPO=owner/repo
GITHUB_TOKEN=github_pat_...
POPULAR_LIKES_LIMIT=50
SUPPORT_URL=https://t.me/your_support
DONATE_URL=https://donate.your_link
```

> `CACHE_TTL` — опционально, по умолчанию `600` секунд (10 минут).

### 4. Запустить

```bash
python main.py
```

---

## ⚙️ Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен бота от [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | ✅ | Telegram ID администраторов через запятую |
| `GITHUB_REPO` | ✅ | Репозиторий каталога в формате `owner/repo` |
| `GITHUB_TOKEN` | ✅ | GitHub Fine-grained Token с правом `Contents: Read and write` |
| `POPULAR_LIKES_LIMIT` | ✅ | Порог лайков/скачиваний для тега `popular` |
| `SUPPORT_URL` | ✅ | Ссылка на чат поддержки |
| `DONATE_URL` | ✅ | Ссылка для доната |
| `CACHE_TTL` | — | TTL кэша в секундах (по умолчанию `600`) |

Бот не запустится, если хотя бы одна из обязательных переменных не задана — `loader.py` проверяет их при старте.

---

## 🔑 Как получить GitHub Token

1. Открой [github.com/settings/tokens](https://github.com/settings/tokens)
2. Нажми **Generate new token → Fine-grained token**
3. В поле **Repository access** выбери репозиторий каталога
4. В разделе **Permissions** → `Contents` → **Read and write**
5. Скопируй токен в `.env`

---

## 🏗 Структура проекта

```
minecraft_bot/
├── main.py                     # Точка входа, ThrottleMiddleware, фоновый авто-сброс кэша
├── requirements.txt
├── bot/
│   ├── cache.py                # In-memory кэш: каталог (TTL), лайки, пользователи
│   ├── errors.py               # Классы исключений (EnvLoadError, GitHubEnvError, GitHubLoadError)
│   ├── github_loader.py        # Чтение/запись каталога, лайков и пользователей через GitHub API
│   ├── storage.py              # Локальное JSON-хранилище (не используется в основном потоке)
│   ├── texture_pack_creator.py # Генератор .mcpack (zip с manifest.json и иконкой)
│   ├── throttle.py             # Rate limiter: 3 секунды между действиями
│   ├── utils.py                # Форматирование карточек товаров, метки категорий
│   └── cryptobot.py
└── handlers/
    ├── loader.py               # Проверка .env при старте + настройка логирования
    ├── handlers.py             # Все хэндлеры + FSM (пользователь, admin, рассылка)
    └── markups.py              # Все InlineKeyboard-клавиатуры
```

---

## 🗄 Кэширование

Данные с GitHub кэшируются в памяти:
- **Каталог** — по категориям, TTL задаётся через `CACHE_TTL` (по умолчанию 600 сек). Инвалидируется при записи (лайк, скачивание, добавление товара).
- **Лайки** (`likes.json`) и **пользователи** (`users.json`) — загружаются один раз, обновляются при изменении.
- Фоновая задача в `main.py` сбрасывает весь кэш каждые `CACHE_TTL` секунд.
- Администратор может сбросить кэш вручную через `/admin → Очистить кэш`.

---

## ⚡ Rate limiting

Между любыми действиями пользователя — кулдаун **3 секунды** (`throttle.py`).  
Администраторы из `ADMIN_IDS` от rate limit освобождены.  
Кулдаун сбрасывается при каждом `/start`.
