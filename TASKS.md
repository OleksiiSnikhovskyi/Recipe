# TASKS.md - Recipe Automation Project

## Current Session: 2026-06-30 - Checkpoint, Documentation, Backfill

### Current State

- Phase: `Production backfill and usage`
- Database: `recipe_db` on Markiz is created and initialized
- n8n: `WF-01` through `WF-07` are deployed
- Backfill: `WF-08` export is prepared for full playlist pagination
- Python services: `5010` through `5013` are implemented and tested
- Nextcloud: files are stored under `/Documents/Recipe/{category}`
- Telegram: notifications and recipe search are working

## Completed

- [x] Create project documentation set
- [x] Create repository structure
- [x] Create PostgreSQL schema:
  - [x] `recipes`
  - [x] `video_log`
  - [x] `playlist_tracking`
  - [x] `execution_log`
  - [x] `telegram_search_sessions`
- [x] Add indexes and analytics views
- [x] Implement `scripts/setup_database.py`
- [x] Implement `scripts/parse_recipe.py`
- [x] Implement `scripts/import_recipes.py`
- [x] Implement `scripts/generate_docx.py`
- [x] Implement `scripts/pdf_converter.py`
- [x] Implement `scripts/nextcloud_uploader.py`
- [x] Export all `7` n8n workflow JSON files
- [x] Prepare Telegram bot credential for notifications
- [x] Rebuild WF-01 as a batch-size-1 sequential loop
- [x] Add atomic video claiming, duplicate protection, retries, and failure status handling
- [x] Fix WF-02 webhook body access and delayed completion response
- [x] Add multilingual YouTube caption/Whisper transcription to `parse_recipe.py`
- [x] Add migration `002_sequential_video_processing.sql`
- [x] Add migration `003_recipe_search_sessions.sql`
- [x] Confirm imported workflows use connected credentials
- [x] Test workflow chain from `WF-02` through Nextcloud upload
- [x] Add `WF-07` Telegram recipe search workflow with numbered result selection
- [x] Verify Telegram search works
- [x] Update usage and operations documentation
- [x] Add `WF-08` full playlist backfill workflow export

## In Progress

- [ ] Deploy `WF-08-recipe-backfill-all-playlist.json`
- [ ] Run one-time WF-08 backfill for all playlist recipes
- [ ] Monitor Python logs and n8n executions during backfill
- [ ] Confirm counts in `recipes`, `video_log`, and Nextcloud links

## Later Improvements

- [ ] Implement or refine `nutrition_calculator.py`
- [ ] Add Telegram commands:
  - [ ] `/latest`
  - [ ] `/categories`
  - [ ] `/recipe <id>`
- [ ] Add inline buttons for search results if needed
- [ ] Convert Python services to systemd units or Docker services
- [ ] Rotate exposed keys after stabilization

## Backfill Command

Run newest 50 on Markiz:

```bash
cd /opt/recipe-automation
docker exec -d n8n-docker_n8n_1 n8n execute --id 9QXzE48DP7rcZ0ft
```

WF-01 processes the newest 50 playlist videos sequentially. Already completed recipes are skipped.

Run all playlist videos after deploying WF-08:

```bash
cd /opt/recipe-automation
python scripts/deploy_recipe_workflows.py --only WF-08-recipe-backfill-all-playlist.json
docker exec -d n8n-docker_n8n_1 n8n execute --id 4mdyTlugsBwpBtW0
```

## Monitoring Commands

```bash
cd /opt/recipe-automation
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

```bash
psql -h 127.0.0.1 -U recipe_user -d recipe_db -P pager=off -c "
SELECT status, COUNT(*)
FROM video_log
GROUP BY status
ORDER BY status;
"
```

## Risks

- Public n8n API is not reliable for manual workflow execution. Use `docker exec ... n8n execute` on Markiz for one-time backfill.
- Full 50-video backfill can take a long time because transcription and LLM extraction are sequential.
- Exposed secrets should be rotated after stabilization.

## Notes

- `WF-01` URL: `https://n8n.csc-ua.tech/workflow/9QXzE48DP7rcZ0ft`
- `WF-07` Telegram search workflow ID: `k9A9VLRcUuU9zFBJ`
- Main runbook: `docs/OPERATIONS.md`

## Last Updated

2026-06-30 by Codex
