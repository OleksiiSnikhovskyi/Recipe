# Recipe Automation System

Автоматизований конвеєр `YouTube playlist -> структурований рецепт -> DOCX/PDF -> Nextcloud -> Telegram`.

Проєкт працює на Markiz через n8n, PostgreSQL, Python-сервіси, Ollama/Whisper, Nextcloud і Telegram bot.

## Поточний Стан

Станом на `2026-06-30` основний production-конвеєр працює:

- `WF-01` моніторить YouTube playlist і бере останні 50 відео.
- `WF-02` послідовно витягує рецепт, транскрипцію, інгредієнти й кроки.
- `WF-03` генерує DOCX.
- `WF-04` конвертує DOCX у PDF.
- `WF-05` зберігає DOCX/PDF у Nextcloud у `/Documents/Recipe/{Категорія}`.
- `WF-02` надсилає Telegram notification після успішного збереження.
- `WF-07` дає Telegram-пошук по збережених рецептах із вибором за номером.

## Архітектура

```text
YouTube Playlist
  -> WF-01 Monitor Playlist
  -> video_log duplicate guard
  -> WF-02 Extract Recipe
  -> parse_recipe.py :5010
  -> recipes table
  -> generate_docx.py :5011
  -> pdf_converter.py :5012
  -> WF-05 Upload Nextcloud
  -> nextcloud_uploader.py :5013
  -> Telegram notification
```

Пошук працює окремо:

```text
Telegram message
  -> WF-07 Recipe Search
  -> PostgreSQL recipes + telegram_search_sessions
  -> numbered result list
  -> user sends number
  -> recipe card with PDF/DOCX/YouTube links
```

## Основні Компоненти

| Component | Purpose | Status |
|---|---|---|
| PostgreSQL `recipe_db` | recipes, video_log, search sessions | Working |
| `parse_recipe.py` `:5010` | extraction + captions/Whisper transcription | Working |
| `generate_docx.py` `:5011` | formatted DOCX with image and QR code | Working |
| `pdf_converter.py` `:5012` | LibreOffice PDF conversion | Working |
| `nextcloud_uploader.py` `:5013` | payload for native Nextcloud workflow | Working |
| n8n WF-01..WF-07 | orchestration | Working |
| Telegram bot | notifications and search | Working |

## Швидке Користування

### Запустити обробку останніх 50 відео з playlist

На Markiz:

```bash
docker exec -d n8n-docker_n8n_1 n8n execute --id 9QXzE48DP7rcZ0ft
```

WF-01 обробляє всі нові відео з поточної сторінки YouTube API `maxResults=50`. Уже завершені рецепти не дублюються.

### Перевірити сервіси

```bash
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health
```

### Перевірити прогрес

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT
  COUNT(*) AS recipes,
  COUNT(*) FILTER (WHERE processed = true) AS processed,
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded
FROM recipes;
"
```

### Користуватися Telegram-пошуком

Напиши боту:

```text
курка
пирог з вишнею
десерт
печериці
```

Бот поверне список із номерами. Для вибору напиши:

```text
1
```

Також працює прямий виклик:

```text
/recipe 35
```

## Документація

- [docs/OPERATIONS.md](docs/OPERATIONS.md) - основна інструкція з експлуатації.
- [QUICK_START.md](QUICK_START.md) - короткий запуск на Markiz.
- [STATUS_REPORT.md](STATUS_REPORT.md) - поточний checkpoint.
- [docs/RECIPE_FORMAT.md](docs/RECIPE_FORMAT.md) - формат рецепта.
- [CLAUDE.md](CLAUDE.md) - архітектурний контекст.

## Безпека

Не комітити `.env`, API keys, DB passwords, Telegram token або Nextcloud app password. Якщо ключ потрапив у чат чи історію, його треба перевипустити після стабілізації.
