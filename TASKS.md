# TASKS.md — Recipe Automation Project

## Current Session: 2026-06-21 — Sequential Processing & Transcription

### Current State
- Phase: `Deployment & Testing`
- Repository: `28 files`, `5,551` lines
- Database: `recipe_db` on Markiz is created and initialized
- n8n: sequential replacements for `WF-01` and `WF-02` are ready locally
- Python services: `parse_recipe.py` supports captions-first transcription with local Whisper fallback

### Completed ✅
- [x] Create project documentation set (`CLAUDE.md`, `README.md`, `QUICK_START.md`, setup guides)
- [x] Create repository structure (`config/`, `docs/`, `scripts/`, `database/`, `N8N_WORKFLOW_EXPORTS/`)
- [x] Create PostgreSQL schema with:
  - [x] `recipes`
  - [x] `video_log`
  - [x] `playlist_tracking`
  - [x] `execution_log`
- [x] Add `8` indexes for lookup and monitoring queries
- [x] Add `3` analytics views
- [x] Implement `scripts/setup_database.py`
- [x] Implement `scripts/parse_recipe.py`
- [x] Implement `scripts/import_recipes.py`
- [x] Scaffold `scripts/generate_docx.py`
- [x] Scaffold `scripts/pdf_converter.py`
- [x] Scaffold `scripts/nutrition_calculator.py`
- [x] Scaffold `scripts/nextcloud_uploader.py`
- [x] Export all `6` n8n workflow JSON files
- [x] Prepare Telegram bot credential for notifications

### In Progress 🔄
- [x] Rebuild WF-01 as a batch-size-1 sequential loop
- [x] Add atomic video claiming, duplicate protection, retries, and failure status handling
- [x] Fix WF-02 webhook body access and delayed completion response
- [x] Add multilingual YouTube caption/Whisper transcription to `parse_recipe.py`
- [x] Add migration `002_sequential_video_processing.sql`
- [x] Add and pass transcription fallback tests
- [ ] Apply migration and service update on Markiz (network/SSH unavailable to Codex sandbox)
- [ ] Deploy updated WF-01/WF-02 through n8n API (network unavailable to Codex sandbox)
- [x] Confirm imported workflows use the connected `Postgres_Recipe` credential
- [ ] Implement HTTP/CLI logic for `generate_docx.py`
- [ ] Implement HTTP/CLI logic for `pdf_converter.py`
- [ ] Implement upload/share logic for `nextcloud_uploader.py`
- [ ] Implement nutrition calculation logic for `nutrition_calculator.py`
- [ ] Test workflow chain from `WF-02` through `WF-06`

### Immediate Next Steps
- [x] Relink PostgreSQL nodes to `Postgres_Recipe`
- [x] Re-test the PostgreSQL credential connection
- [ ] Decide implementation order for remaining services:
  - [ ] `generate_docx.py`
  - [ ] `pdf_converter.py`
  - [ ] `nextcloud_uploader.py`
  - [ ] `nutrition_calculator.py`
- [ ] Run an isolated webhook test for `WF-02`
- [ ] Perform first end-to-end dry run with a sample video payload

## Blockers & Risks

### Active Blockers
- Codex sandbox cannot establish TCP/SSH connectivity to Markiz or `n8n.csc-ua.tech`; live migration and deployment remain pending.
- `WF-02` through `WF-05` depend on Python services that are still skeletons.

### Security Note
- Repository documentation must not contain live secrets.
- `STATUS_REPORT.md` was sanitized on `2026-06-21`; keep real passwords only in local `.env` or secret storage.

## Notes

### n8n
- `WF-01` URL: `https://n8n.csc-ua.tech/workflow/9QXzE48DP7rcZ0ft`
- Telegram credential ID is present and appears ready for `WF-06`.

### Services
- `parse_recipe.py` is the only confirmed running service at this stage.
- Remaining service scripts still raise `NotImplementedError`, so they are not deployment-ready yet.

## Last Updated
2026-06-21 by Codex
