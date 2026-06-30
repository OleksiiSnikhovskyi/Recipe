# Recipe Quick Start

Коротка інструкція для запуску й перевірки production-конвеєра на Markiz.

## 1. Оновити Код

```bash
cd /opt/recipe-automation
git pull --ff-only origin main
source venv/bin/activate
```

## 2. Встановити Залежності

```bash
pip install -r requirements.txt
```

Перевір системні залежності:

```bash
ffmpeg -version
soffice --version
```

## 3. Застосувати Міграції

```bash
sudo -u postgres psql -d recipe_db -f database/migrations/002_sequential_video_processing.sql
sudo -u postgres psql -d recipe_db -f database/migrations/003_recipe_search_sessions.sql
```

## 4. Запустити Python-Сервіси

```bash
mkdir -p logs output/docx output/pdf

nohup python scripts/parse_recipe.py --server --port 5010 > logs/parse_recipe.log 2>&1 &
nohup python scripts/generate_docx.py --server --port 5011 > logs/generate_docx.log 2>&1 &
nohup python scripts/pdf_converter.py --server --port 5012 > logs/pdf_converter.log 2>&1 &
nohup python scripts/nextcloud_uploader.py --server --port 5013 > logs/nextcloud_uploader.log 2>&1 &
```

Health check:

```bash
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health
```

## 5. Deploy n8n Workflows

```bash
python scripts/deploy_recipe_workflows.py
```

Після deploy перевір credentials у n8n:

- `Postgres_Recipe`
- `NextCloud account`
- `Telegram Recipe_Oleksii_bot`

## 6. One-Time Backfill Останніх 50 Рецептів

Запусти WF-01 вручну з n8n контейнера:

```bash
docker exec -d n8n-docker_n8n_1 n8n execute --id 9QXzE48DP7rcZ0ft
```

WF-01 бере останні 50 відео з playlist і обробляє тільки ті, яких ще немає як completed.

## 6.1. Full Backfill Усіх Рецептів

Якщо в playlist більше 50 відео, використовуй `WF-08-recipe Backfill All Playlist`. Він сам проходить YouTube pagination через `nextPageToken`.

Після deploy знайди ID workflow у виводі:

```bash
python scripts/deploy_recipe_workflows.py --only WF-08-recipe-backfill-all-playlist.json
```

Запуск:

```bash
docker exec -d n8n-docker_n8n_1 n8n execute --id 4mdyTlugsBwpBtW0
```

Для інтерактивного запуску з логом:

```bash
docker exec -it n8n-docker_n8n_1 n8n execute --id=4mdyTlugsBwpBtW0
```

WF-08 може працювати дуже довго, бо обробляє відео строго по одному.

## 7. Моніторинг

```bash
tail -f logs/parse_recipe.log logs/generate_docx.log logs/pdf_converter.log logs/nextcloud_uploader.log
```

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT
  COUNT(*) AS recipes,
  COUNT(*) FILTER (WHERE processed = true) AS processed,
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded
FROM recipes;
"
```

## 8. Telegram-Пошук

У Telegram bot напиши:

```text
курка
пирог з вишнею
десерт
```

Після списку результатів вибери номер:

```text
1
```

Або відкрий напряму:

```text
/recipe 35
```

## Детальніше

Повна операційна інструкція: [docs/OPERATIONS.md](docs/OPERATIONS.md).
