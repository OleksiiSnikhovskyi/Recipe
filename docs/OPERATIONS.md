# Recipe Operations Guide

Операційна інструкція для production-конвеєра Recipe на Markiz.

## 1. Що Робить Система

Система бере відео з YouTube playlist, послідовно обробляє кожне відео, формує структурований рецепт українською, генерує DOCX/PDF, зберігає файли в Nextcloud і надсилає повідомлення в Telegram.

Після наповнення бази Telegram bot також працює як пошук по рецептах.

## 2. Production Services

На Markiz у `/opt/recipe-automation` мають бути запущені:

| Port | Service | Endpoint |
|---|---|---|
| `5010` | `scripts/parse_recipe.py` | `/health`, `/extract` |
| `5011` | `scripts/generate_docx.py` | `/health`, `/generate` |
| `5012` | `scripts/pdf_converter.py` | `/health`, `/convert` |
| `5013` | `scripts/nextcloud_uploader.py` | `/health`, `/payload` |

Health check:

```bash
cd /opt/recipe-automation
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health
```

Якщо n8n працює в Docker, з контейнера сервіси мають бути доступні через gateway:

```bash
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 5 -S -O- http://172.18.0.1:5010/health"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 5 -S -O- http://172.18.0.1:5011/health"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 5 -S -O- http://172.18.0.1:5012/health"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 5 -S -O- http://172.18.0.1:5013/health"
```

## 3. Service Restart

```bash
cd /opt/recipe-automation
source venv/bin/activate
mkdir -p logs output/docx output/pdf

sudo pkill -f "scripts/parse_recipe.py" || true
sudo pkill -f "scripts/generate_docx.py" || true
sudo pkill -f "scripts/pdf_converter.py" || true
sudo pkill -f "scripts/nextcloud_uploader.py" || true

nohup python scripts/parse_recipe.py --server --port 5010 > logs/parse_recipe.log 2>&1 &
nohup python scripts/generate_docx.py --server --port 5011 > logs/generate_docx.log 2>&1 &
nohup python scripts/pdf_converter.py --server --port 5012 > logs/pdf_converter.log 2>&1 &
nohup python scripts/nextcloud_uploader.py --server --port 5013 > logs/nextcloud_uploader.log 2>&1 &
```

## 4. n8n Workflows

| Workflow | Purpose | Notes |
|---|---|---|
| `WF-01` | Fetch newest 50 playlist videos and process sequentially | ID `9QXzE48DP7rcZ0ft` |
| `WF-02` | Extract recipe, generate files, upload, notify | Production webhook `/recipe-extract` |
| `WF-03` | Standalone DOCX generation webhook | Kept for isolated tests |
| `WF-04` | Standalone PDF conversion webhook | Kept for isolated tests |
| `WF-05` | Native Nextcloud upload workflow | Production webhook `/recipe-nextcloud` |
| `WF-06` | Legacy Telegram notify/log workflow | No longer critical in main chain |
| `WF-07` | Telegram recipe search bot | Search + numbered selection |
| `WF-08` | Full playlist backfill | Manual admin workflow, all pages |

Deploy workflows:

```bash
cd /opt/recipe-automation
source venv/bin/activate
python scripts/deploy_recipe_workflows.py
```

Deploy only one workflow:

```bash
python scripts/deploy_recipe_workflows.py --only WF-07-recipe-search-telegram.json
```

## 5. One-Time Backfill: Newest 50 Playlist Recipes

Мета: один раз прогнати останні 50 відео зі списку відтворення й наповнити `recipe_db`.

Перед запуском перевір:

```bash
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health
```

Запуск WF-01 з CLI n8n:

```bash
docker exec -d n8n-docker_n8n_1 n8n execute --id 9QXzE48DP7rcZ0ft
```

Інтерактивний запуск із логом:

```bash
docker exec -it n8n-docker_n8n_1 n8n execute --id=9QXzE48DP7rcZ0ft
```

Очікувана поведінка:

- WF-01 бере `maxResults=50` із YouTube playlist.
- Відео обробляються строго по одному.
- Уже завершені відео пропускаються.
- Нові або retryable failed/stale записи запускають WF-02.
- Помилка одного відео не має зупиняти весь список.

## 5.1. Full Backfill: All Playlist Recipes

YouTube API повертає максимум 50 playlist items за один запит. Для playlist із 700+ відео використовуй `WF-08-recipe Backfill All Playlist`.

Deploy:

```bash
cd /opt/recipe-automation
source venv/bin/activate
python scripts/deploy_recipe_workflows.py --only WF-08-recipe-backfill-all-playlist.json
```

Запам'ятай workflow ID із виводу deploy.

Activate `WF-08` in n8n UI, then run the production webhook:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-backfill-all
```

WF-08:

- проходить усі сторінки YouTube API через `nextPageToken`;
- збирає всі відео в один список;
- обробляє строго по одному;
- пропускає повністю завершені рецепти;
- повторно обробляє `failed`, stale `processing`, а також записи, де `video_log=completed`, але `recipes.processed=false` або відсутні Nextcloud links.

Цей запуск може тривати багато годин або довше, залежно від кількості нових відео, транскрипції та швидкості LLM.

## 6. Monitoring

Логи Python-сервісів:

```bash
cd /opt/recipe-automation
tail -f \
  logs/parse_recipe.log \
  logs/generate_docx.log \
  logs/pdf_converter.log \
  logs/nextcloud_uploader.log
```

Загальний прогрес:

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT
  COUNT(*) AS recipes,
  COUNT(*) FILTER (WHERE processed = true) AS processed,
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded
FROM recipes;
"
```

Останні рецепти:

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT id, title, category, processed, nextcloud_pdf_url, updated_at
FROM recipes
ORDER BY updated_at DESC
LIMIT 10;
"
```

Статус відео:

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT status, COUNT(*)
FROM video_log
GROUP BY status
ORDER BY status;
"
```

## 7. Telegram Search

WF-07 дає пошук по `recipes`.

Приклади повідомлень:

```text
курка
пирог з вишнею
десерт
печериці
```

Бот повертає до 10 результатів із номерами й посиланнями PDF/DOCX.

Вибір:

```text
1
```

Прямий рецепт:

```text
/recipe 35
```

Сесія номерів зберігається в `telegram_search_sessions` 6 годин.

## 8. Nextcloud Storage

Файли зберігаються в:

```text
/Documents/Recipe/{Категорія}/
```

У базі зберігаються public share links:

- `recipes.nextcloud_docx_url`
- `recipes.nextcloud_pdf_url`

## 9. Migrations

Застосувати міграції на Markiz:

```bash
cd /opt/recipe-automation
sudo -u postgres psql -d recipe_db -f database/migrations/002_sequential_video_processing.sql
sudo -u postgres psql -d recipe_db -f database/migrations/003_recipe_search_sessions.sql
```

`003_recipe_search_sessions.sql` також видає права `recipe_user` на таблицю пошукових сесій.

## 10. Common Fixes

### n8n container cannot reach Python service

Перевір Docker gateway:

```bash
docker exec -it n8n-docker_n8n_1 sh -c "ip route | awk '/default/ {print \$3; exit}'"
```

Якщо UFW блокує:

```bash
sudo ufw allow from 172.16.0.0/12 to any port 5010 proto tcp
sudo ufw allow from 172.16.0.0/12 to any port 5011 proto tcp
sudo ufw allow from 172.16.0.0/12 to any port 5012 proto tcp
sudo ufw allow from 172.16.0.0/12 to any port 5013 proto tcp
```

### `relation "recipes" does not exist`

Сервіс читає неправильну БД. Перевір `.env`:

```bash
grep -E '^(DB_HOST|DB_NAME|DB_USER)=' .env
```

Очікувано:

```text
DB_HOST=127.0.0.1
DB_NAME=recipe_db
DB_USER=recipe_user
```

Після зміни `.env` перезапусти сервіси.

### Permission denied for `telegram_search_sessions`

Повторно застосуй міграцію:

```bash
sudo -u postgres psql -d recipe_db -f database/migrations/003_recipe_search_sessions.sql
```

### Ollama timeout

Перевір Miledy:

```bash
curl --max-time 10 http://100.100.209.24:11434/api/tags
```

## 11. Security Notes

- Не комітити `.env`.
- Не вставляти API keys у documentation.
- Якщо `N8N_API_KEY`, DB password або Telegram token потрапили в чат чи скріншот, перевипустити їх після завершення стабілізації.
