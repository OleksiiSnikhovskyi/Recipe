# Recipe Automation Project - Checkpoint

**Date:** 2026-06-30
**Status:** Production pipeline working; initial playlist backfill pending/ready to run.

## What Is Working

- PostgreSQL `recipe_db` on Markiz.
- Tables:
  - `recipes`
  - `video_log`
  - `playlist_tracking`
  - `execution_log`
  - `telegram_search_sessions`
- Python services:
  - `5010` recipe extraction with YouTube captions and Whisper fallback.
  - `5011` DOCX generation with image and QR source link.
  - `5012` PDF conversion through LibreOffice.
  - `5013` Nextcloud payload/upload support.
- n8n workflows:
  - `WF-01` playlist monitor, sequential processing, newest 50 videos.
  - `WF-02` extract + document generation + upload + Telegram notification.
  - `WF-03` standalone DOCX generation.
  - `WF-04` standalone PDF conversion.
  - `WF-05` native Nextcloud upload.
  - `WF-06` legacy Telegram notify/log.
  - `WF-07` Telegram recipe search.
  - `WF-08` full playlist backfill through YouTube pagination.
- Telegram bot:
  - New recipe notifications.
  - Search by text.
  - Numbered result selection.
  - Direct `/recipe <id>` lookup.
- Nextcloud storage:
  - `/Documents/Recipe/{Категорія}`.

## Current Workflow IDs

| Workflow | ID | Purpose |
|---|---|---|
| `WF-01` | `9QXzE48DP7rcZ0ft` | Monitor YouTube playlist |
| `WF-02` | `BWXYVoSggcCS2xX6` | Extract and process recipe |
| `WF-05` | `BlhGzvMRKvml1s1k` | Upload to Nextcloud |
| `WF-07` | `k9A9VLRcUuU9zFBJ` | Telegram recipe search |
| `WF-08` | `4mdyTlugsBwpBtW0` | Full playlist backfill |

## One-Time Action Requested

Run the full playlist pass once to populate the database with the newest 50 playlist recipes:

```bash
cd /opt/recipe-automation
docker exec -d n8n-docker_n8n_1 n8n execute --id 9QXzE48DP7rcZ0ft
```

This does not duplicate already completed recipes. It claims new videos through `video_log` and processes them one by one.

For all 700+ playlist recipes, deploy and run `WF-08-recipe-backfill-all-playlist.json` instead:

```bash
cd /opt/recipe-automation
python scripts/deploy_recipe_workflows.py --only WF-08-recipe-backfill-all-playlist.json
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-backfill-all
```

## Verify Progress

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT
  COUNT(*) AS recipes,
  COUNT(*) FILTER (WHERE processed = true) AS processed,
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded
FROM recipes;
"
```

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT status, COUNT(*)
FROM video_log
GROUP BY status
ORDER BY status;
"
```

## Operator Documentation

Use [docs/OPERATIONS.md](docs/OPERATIONS.md) as the primary runbook.

## Security Note

Secrets have appeared during interactive setup. After the system is stable, rotate exposed `N8N_API_KEY`, database passwords, and any Telegram/Nextcloud credentials that were pasted into chat or screenshots.
