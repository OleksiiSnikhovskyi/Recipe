# TASKS.md - Recipe Automation Project

## Current Session: 2026-07-09 - Recovery After YouTube Blocking

### Current State

- Phase: `Recovery / stabilization`
- n8n: `WF-08` is disabled and must stay disabled.
- YouTube: Markiz IP was blocked/rate-limited during aggressive backfill.
- Database: contains completed recipes plus many stale/failed/incomplete records from the incident.
- Python services: must be manually checked on ports `5010`-`5013`.
- Telegram search and Nextcloud upload remain part of the target production chain.

## Completed

- [x] Create PostgreSQL schema and migrations.
- [x] Implement Python services:
  - [x] `parse_recipe.py`
  - [x] `generate_docx.py`
  - [x] `pdf_converter.py`
  - [x] `nextcloud_uploader.py`
- [x] Implement sequential WF-01 monitor for newest 50 playlist items.
- [x] Implement WF-02 extraction/document/upload chain.
- [x] Implement WF-03 DOCX generation.
- [x] Implement WF-04 PDF conversion.
- [x] Implement WF-05 Nextcloud upload.
- [x] Implement WF-07 Telegram recipe search.
- [x] Add WF-08 full playlist backfill attempt.
- [x] Stop WF-08 after execution storm.
- [x] Restart `parse_recipe.py` on `5010`.
- [x] Restart `generate_docx.py` on `5011`.
- [x] Restart `pdf_converter.py` on `5012`.
- [x] Test extraction for `recipe_id=18`: extraction and DOCX succeeded.
- [x] Add local hotfix so `pdf_converter.py` can resolve `docx_path` by `recipe_id`.

## In Progress

- [ ] Push commit `3e1a8d8 Allow PDF conversion by recipe id`.
- [ ] Pull latest code on Markiz.
- [ ] Restart `5012` after pulling the hotfix.
- [ ] Re-run PDF for `recipe_id=18`.
- [ ] Upload `recipe_id=18` to Nextcloud.
- [ ] Verify `recipes.nextcloud_pdf_url` and `recipes.nextcloud_docx_url` for `recipe_id=18`.

## Recovery Queue

- [ ] Confirm all four services are reachable from n8n container:
  - [ ] `172.18.0.1:5010`
  - [ ] `172.18.0.1:5011`
  - [ ] `172.18.0.1:5012`
  - [ ] `172.18.0.1:5013`
- [ ] Decide whether to temporarily disable `WF-01` while services are not managed by systemd/Docker.
- [ ] Create SQL report for:
  - [ ] stale `video_log.status = 'processing'`;
  - [ ] `video_log.status = 'failed'`;
  - [ ] `recipes.transcript_source = 'description_only'`;
  - [ ] `recipes.transcription_warning IS NOT NULL`;
  - [ ] missing Nextcloud URLs.
- [ ] Create cleanup migration for stale `processing` records.
- [ ] Create reprocess workflow/script for bad records.

## Do Not Do Yet

- [ ] Do not run `WF-08`.
- [ ] Do not run mass YouTube backfill from Markiz.
- [ ] Do not retry all failed records at once.
- [ ] Do not query YouTube aggressively while IP reputation is cooling down.

## Safe Manual Test Commands

Generate DOCX for an already extracted recipe:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-docx \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
```

Generate PDF after the `pdf_converter.py` hotfix is deployed:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-pdf \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
```

Upload to Nextcloud after DOCX and PDF exist:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-nextcloud \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": 18}'
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
  COUNT(*) FILTER (WHERE nextcloud_pdf_url IS NOT NULL) AS uploaded_pdf,
  COUNT(*) FILTER (WHERE transcript_source = 'description_only') AS description_only,
  COUNT(*) FILTER (WHERE transcription_warning IS NOT NULL) AS transcription_warning
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

## Later Improvements

- [ ] Convert Python services to systemd units or Docker services.
- [ ] Add health-check workflow before WF-01 processes videos.
- [ ] Add global rate limiter for YouTube work.
- [ ] Add reprocess queue table with `next_attempt_at`.
- [ ] Add support for Miledy/VPN/cookies transcript extraction.
- [ ] Add Telegram admin commands:
  - [ ] `/latest`
  - [ ] `/categories`
  - [ ] `/recipe <id>`
  - [ ] `/failed`
- [ ] Rotate exposed secrets after stabilization.

## Last Updated

2026-07-09 by Codex
