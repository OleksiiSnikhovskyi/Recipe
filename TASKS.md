# TASKS.md — Recipe Automation Project

## Current Session: 2026-06-21 — Project Initialization

### Completed ✅
- [x] Clone GitHub repository
- [x] Create CLAUDE.md with full architecture documentation
- [x] Create TASKS.md tracker

### In Progress 🔄
- [ ] Create directory structure
- [ ] Create configuration templates
- [ ] Create database schema file
- [ ] Create initial Python script stubs

### TODO 📋

#### Phase 1: Foundation (Week 1)
- [ ] Set up PostgreSQL database with schema
- [ ] Create .env template and document credentials setup
- [ ] Implement `scripts/parse_recipe.py` (Ollama integration)
- [ ] Implement `scripts/generate_docx.py` (python-docx)
- [ ] Test Python scripts locally with sample recipe data
- [ ] Create Nextcloud folder structure

#### Phase 2: n8n Workflows (Week 2)
- [ ] Design and implement WF-01: Monitor Playlist (scheduler)
- [ ] Design and implement WF-02: Extract Recipe Data (HTTP + LLM)
- [ ] Design and implement WF-03: Generate DOCX
- [ ] Design and implement WF-04: Convert to PDF (LibreOffice)
- [ ] Design and implement WF-05: Upload to Nextcloud
- [ ] Design and implement WF-06: Notify & Log (Telegram)
- [ ] Export all workflows to `N8N_WORKFLOW_EXPORTS/`

#### Phase 3: Integration & Testing (Week 3)
- [ ] Test full pipeline end-to-end with sample video
- [ ] Verify Telegram notifications
- [ ] Verify Nextcloud uploads
- [ ] Verify database logging
- [ ] Handle edge cases (duplicates, failed conversions)
- [ ] Set up error notification workflow

#### Phase 4: Enhancements (Week 4)
- [ ] Implement manual trigger via Telegram bot (regenerate recipes)
- [ ] Add recipe regeneration support
- [ ] Add nutrition calculation refinement
- [ ] Support for additional sources (Instagram, TikTok, custom text)
- [ ] Performance optimization (batch processing)

---

## Implementation Notes

### YouTube API
- Setup: https://console.cloud.google.com/
- Quota: 10k units/day (each playlist.list = 1 unit, videoDetails = 1 unit each)
- Fallback: Use n8n's built-in YouTube node if quota insufficient

### Ollama Models
- Primary: `qwen3:8b` (best instruction-following, Ukrainian-aware)
- Fallback: `qwen2.5:7b`, `llama3.2:3b`
- Ensure model is pre-loaded on Markiz before workflows run

### LibreOffice PDF Conversion
- Install: `sudo apt-get install libreoffice`
- Headless mode: `soffice --headless --convert-to pdf`
- Output: Same directory as input DOCX
- Timeout: 30 seconds per file

### Nextcloud WebDAV
- Endpoint: `https://nextcloud.domain/remote.php/dav/files/{user}/{path}`
- Authentication: HTTPBasicAuth (user, password)
- Upload: PUT request with file binary
- Share: Use Nextcloud API to generate public share links

---

## Blockers & Notes

**None currently.** Ready to proceed with Phase 1.

---

## Last Updated
2026-06-21 by Claude Code (initialization)
