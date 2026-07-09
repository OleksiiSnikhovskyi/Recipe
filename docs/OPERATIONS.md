# Recipe Operations Guide

Операційна інструкція для production-конвеєра Recipe на Markiz.

## 1. Поточний Режим

Станом на 2026-07-09 проєкт у режимі recovery після блокування YouTube-запитів.

Правила:

- `WF-08` не запускати.
- Масовий backfill з Markiz не запускати.
- YouTube не чіпати пачками.
- Працювати точково з уже збереженими рецептами.
- Перед будь-яким workflow перевіряти Python-сервіси `5010`-`5013`.

## 2. Production Services

На Markiz у `/opt/recipe-automation` мають бути запущені:

| Port | Service | Endpoint |
|---:|---|---|
| `5010` | `scripts/parse_recipe.py` | `/health`, `/extract` |
| `5011` | `scripts/generate_docx.py` | `/health`, `/generate` |
| `5012` | `scripts/pdf_converter.py` | `/health`, `/convert` |
| `5013` | `scripts/nextcloud_uploader.py` | `/health`, `/payload` |

Restart all services:

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

Health checks from host:

```bash
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health
```

Health checks from n8n container:

```bash
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5010/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5011/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5012/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5013/health || true"
```

## 3. Workflow Map

| Workflow | Purpose | Status |
|---|---|---|
| `WF-01` | Newest-50 playlist monitor | Active, but should be paused if services are down |
| `WF-02` | Extract recipe + generate + upload + notify | Active |
| `WF-03` | Standalone DOCX generation | Active |
| `WF-04` | Standalone PDF conversion | Active |
| `WF-05` | Native Nextcloud upload | Active |
| `WF-07` | Telegram search | Active |
| `WF-08` | Full playlist backfill | Disabled; do not run |

## 4. Known Incident: YouTube Blocking

Symptoms:

```text
YouTube is blocking requests from your IP
Sign in to confirm you’re not a bot
Use --cookies-from-browser or --cookies
```

Database indicators:

```sql
SELECT COUNT(*)
FROM recipes
WHERE transcript_source = 'description_only'
   OR transcription_warning IS NOT NULL
   OR transcript IS NULL
   OR length(trim(transcript)) < 100;
```

These records are not necessarily unusable, but they are low confidence and should be reprocessed later with a safer route.

Preferred future routes:

- Miledy server with another IP.
- VPN for Markiz.
- YouTube cookies for `yt-dlp`.
- Slow queue with long delays and strict concurrency `1`.

## 5. Safe Single-Recipe Recovery

Use this path when the recipe was already extracted and only DOCX/PDF/Nextcloud failed.

Generate DOCX:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-docx \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
```

Generate PDF:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-pdf \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
```

Upload to Nextcloud:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-nextcloud \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
```

Important:

- Do not call `/recipe-extract` again unless you intentionally want a new YouTube transcript attempt.
- If `recipe-pdf` fails with `docx_path or docx_base64 is required`, deploy the `pdf_converter.py` hotfix that resolves `docx_path` by `recipe_id`.

## 6. Backfill Policy

`WF-08` must remain disabled until redesigned.

Required redesign:

- no webhook storm;
- no page self-trigger storm;
- one video at a time;
- delay between videos: 5-10 minutes minimum;
- delay between playlist pages: 30-60 minutes minimum;
- retry queue table with `next_attempt_at`;
- hard daily cap;
- optional Miledy/VPN/cookies route for YouTube transcript/audio.

## 7. Cleanup SQL

Before cleanup, confirm no workflow is actively processing.

Find stale processing records:

```sql
SELECT COUNT(*)
FROM video_log
WHERE status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

Mark stale records failed for controlled retry:

```sql
UPDATE video_log
SET status = 'failed',
    processed = false,
    error_details = COALESCE(error_details, '') || E'\nMarked failed during post-incident cleanup.',
    updated_at = NOW()
WHERE status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

Find bad transcript records:

```sql
SELECT id, video_id, title, transcript_source, transcription_warning
FROM recipes
WHERE transcript_source = 'description_only'
   OR transcription_warning IS NOT NULL
   OR transcript IS NULL
   OR length(trim(transcript)) < 100
ORDER BY updated_at DESC;
```

## 8. Monitoring

Python logs:

```bash
cd /opt/recipe-automation
tail -f \
  logs/parse_recipe.log \
  logs/generate_docx.log \
  logs/pdf_converter.log \
  logs/nextcloud_uploader.log
```

Recipe progress:

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT
  COUNT(*) AS recipes,
  COUNT(*) FILTER (WHERE processed = true) AS processed,
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded_pdf,
  COUNT(*) FILTER (WHERE transcript_source = 'description_only') AS description_only,
  COUNT(*) FILTER (WHERE transcription_warning IS NOT NULL) AS transcription_warning
FROM recipes;
"
```

Video log:

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT status, COUNT(*)
FROM video_log
GROUP BY status
ORDER BY status;
"
```

## 9. Common Errors

### `ECONNREFUSED 172.18.0.1:5010`

`parse_recipe.py` is offline. Restart port `5010`.

### `ECONNREFUSED 172.18.0.1:5011`

`generate_docx.py` is offline. Restart port `5011`.

### `ECONNREFUSED 172.18.0.1:5012`

`pdf_converter.py` is offline. Restart port `5012`.

### `docx_path or docx_base64 is required`

WF-04 was called with only `recipe_id`, but the old PDF service could not resolve `docx_path`.

Fix:

- deploy the `pdf_converter.py` hotfix;
- restart `5012`;
- call `/recipe-pdf` with `{"recipe_id": ...}` again.

### Nextcloud says file/path missing

Usually DOCX/PDF local path is missing or the previous step failed. Verify:

```sql
SELECT id, title, docx_path, pdf_path, nextcloud_docx_url, nextcloud_pdf_url
FROM recipes
WHERE id = 18;
```

## 10. Security Notes

- Do not commit `.env`.
- Do not paste API keys into documentation.
- Rotate exposed `N8N_API_KEY`, DB password, Telegram token, and Nextcloud credentials after stabilization.
