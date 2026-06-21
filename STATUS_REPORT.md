# 📊 Recipe Automation Project — Status Report

**Date:** 2026-06-21  
**Status:** 🟡 Phase 2 In Progress (Deployment & Testing)  
**Deployment Location:** Markiz (100.81.127.54)

---

## ✅ What's Been Created

### 1️⃣ Project Repository (GitHub)

**URL:** https://github.com/OleksiiSnikhovskyi/Recipe

**Files Created:** 28 files, 5,551 lines of code

```
Recipe/
├── CLAUDE.md (1,300+ lines - Full architecture)
├── README.md (264 lines - GitHub overview)
├── QUICK_START.md (231 lines - 10-minute setup)
├── TASKS.md (108 lines - Progress tracker)
├── requirements.txt (53 lines - Python dependencies)
├── .env.example (125 lines - Config template)
├── .gitignore (84 lines - Security)
│
├── N8N_WORKFLOW_EXPORTS/
│   ├── WF-01-recipe-monitor-playlist.json (132 lines) ✅
│   ├── WF-02-recipe-extract-data.json (204 lines) ✅
│   ├── WF-03-recipe-generate-docx.json (126 lines) ✅
│   ├── WF-04-recipe-convert-pdf.json (126 lines) ✅
│   ├── WF-05-recipe-upload-nextcloud.json (180 lines) ✅
│   └── WF-06-recipe-telegram-notify.json (153 lines) ✅
│
├── scripts/
│   ├── parse_recipe.py (339 lines) ✅ Ready
│   ├── generate_docx.py (144 lines) 🔄 Skeleton
│   ├── pdf_converter.py (118 lines) 🔄 Skeleton
│   ├── nutrition_calculator.py (82 lines) 🔄 Skeleton
│   ├── nextcloud_uploader.py (162 lines) 🔄 Skeleton
│   ├── import_recipes.py (286 lines) ✅ Ready
│   ├── setup_database.py (249 lines) ✅ Ready
│   └── requirements_servers.txt (37 lines) ✅
│
├── config/
│   ├── SETUP_GUIDE.md (422 lines)
│   ├── N8N_DEPLOYMENT_GUIDE.md (544 lines)
│   ├── nextcloud_structure.md (260 lines)
│   ├── environment_template.env (123 lines)
│   └── youtube_api_setup.md (stub)
│
├── database/
│   ├── schema.sql (111 lines) ✅ 4 tables + 8 indexes + 3 views
│   └── migrations/
│       └── 001_create_recipe_db.sql (46 lines)
│
└── docs/
    └── RECIPE_FORMAT.md (384 lines - JSON schema)
```

---

## 🗄️ Database (PostgreSQL on Markiz)

### Server Details
- **Host:** `localhost` (from Markiz)
- **Port:** `5432`
- **Database:** `recipe_db` ✅ Created
- **User:** `recipe_user` ✅ Created
- **Password:** `RecipeSecure2026!`
- **Admin User:** `oleksiisnikhovskyi`

### Tables Created (4 tables)

#### 1. `recipes` — Main Recipe Data
```sql
Columns:
  - id (SERIAL PRIMARY KEY)
  - video_id (VARCHAR 255, UNIQUE) — YouTube video ID
  - title (VARCHAR 255) — Recipe name
  - description (TEXT) — Extended description
  - category (VARCHAR 50) — Recipe category (Перші страви, Десерти, etc.)
  - recipe_text (TEXT) — Full recipe JSON as text
  - ingredients (JSONB) — Structured ingredients array
  - steps (JSONB) — Cooking instructions array
  - nutrition (JSONB) — Nutrition facts (per 100g, per serving)
  - youtube_url (VARCHAR 500) — Link to source video
  - youtube_channel (VARCHAR 255) — Channel name
  - thumbnail_url (VARCHAR 500) — Recipe image URL
  - docx_path (VARCHAR 500) — Local DOCX file path
  - pdf_path (VARCHAR 500) — Local PDF file path
  - nextcloud_docx_url (VARCHAR 500) — Public Nextcloud DOCX link
  - nextcloud_pdf_url (VARCHAR 500) — Public Nextcloud PDF link
  - processed (BOOLEAN) — TRUE when fully processed
  - created_at (TIMESTAMP) — Record creation time
  - updated_at (TIMESTAMP) — Last modification time
  - error_message (TEXT) — Error details if processing failed
```

#### 2. `video_log` — Processing Status Tracking
```sql
Columns:
  - id (SERIAL PRIMARY KEY)
  - video_id (VARCHAR 255) — YouTube video ID (NOT UNIQUE, allows retries)
  - playlist_id (VARCHAR 255) — YouTube playlist ID
  - processed (BOOLEAN) — Quick flag for completion
  - status (VARCHAR 50) — Detailed status:
      • 'pending' — Waiting for processing
      • 'processing' — Currently being processed
      • 'completed' — Successfully processed
      • 'failed' — Error during processing
      • 'skipped' — Intentionally skipped
  - error_details (TEXT) — Full error description
  - created_at (TIMESTAMP) — When video was detected
  - updated_at (TIMESTAMP) — Last status change
```

#### 3. `playlist_tracking` — YouTube Playlist Metadata
```sql
Columns:
  - id (SERIAL PRIMARY KEY)
  - playlist_id (VARCHAR 255, UNIQUE) — YouTube playlist ID
  - playlist_title (VARCHAR 255) — Playlist name
  - last_checked (TIMESTAMP) — Last poll time
  - video_count (INTEGER) — Total videos detected
  - enabled (BOOLEAN) — Is this playlist being monitored?
```

#### 4. `execution_log` — n8n Workflow Execution History
```sql
Columns:
  - id (SERIAL PRIMARY KEY)
  - recipe_id (INTEGER, FK) — Reference to recipes.id
  - workflow_name (VARCHAR 100) — WF-01, WF-02, etc.
  - workflow_id (VARCHAR 255) — n8n internal workflow ID
  - n8n_execution_id (VARCHAR 255) — n8n execution ID
  - status (VARCHAR 50) — success / failed / timeout
  - output_data (JSONB) — Workflow output (URLs, results)
  - error_message (TEXT) — Error if failed
  - duration_ms (INTEGER) — Execution time
  - created_at (TIMESTAMP) — When executed
```

### Indexes (8 total)
- `idx_recipes_video_id` — Fast lookup by video
- `idx_recipes_category` — Filter by recipe type
- `idx_recipes_processed` — Find pending recipes
- `idx_recipes_created_at` — Sort by date
- `idx_video_log_video_id` — Track video status
- `idx_video_log_status` — Filter by status
- `idx_execution_log_recipe_id` — Link executions to recipes
- `idx_execution_log_workflow_name` — Filter by workflow

### Views (3 views)
- `pending_recipes` — Recipes awaiting processing
- `recent_recipes` — Last 20 completed recipes
- `processing_stats` — Total/completed/pending counts

---

## 🤖 Python Services

### 1. `parse_recipe.py` ✅ **READY**
**Purpose:** Extract recipe data from YouTube description using AI

**Capabilities:**
- CLI mode: `python scripts/parse_recipe.py --input "description"`
- Server mode: `python scripts/parse_recipe.py --server --port 5010`
- Supports Ollama (local) and OpenAI (cloud)
- Returns structured JSON with title, ingredients, steps, nutrition

**Status on Markiz:**
- ✅ Service running on port 5010
- ✅ Health check responding: `{"status":"ok","provider":"ollama"}`
- ✅ Ready to integrate with n8n

### 2. `generate_docx.py` 🔄 **SKELETON**
**Purpose:** Generate DOCX files from recipe JSON

**To Implement:**
- [ ] Create Word document with python-docx
- [ ] Add recipe title, image, ingredients table
- [ ] Add cooking instructions (numbered steps)
- [ ] Add nutrition facts table
- [ ] Return base64-encoded DOCX
- [ ] Flask HTTP endpoint at `/generate`

### 3. `pdf_converter.py` 🔄 **SKELETON**
**Purpose:** Convert DOCX to PDF using LibreOffice

**To Implement:**
- [ ] Accept base64-encoded DOCX
- [ ] Call LibreOffice Headless: `soffice --headless --convert-to pdf`
- [ ] Return base64-encoded PDF
- [ ] Flask HTTP endpoint at `/convert`

### 4. `nutrition_calculator.py` 🔄 **SKELETON**
**Purpose:** Calculate nutrition facts from ingredients

**To Implement:**
- [ ] Load USDA nutrition database
- [ ] Lookup each ingredient
- [ ] Calculate totals per serving
- [ ] Normalize to per 100g
- [ ] Handle unit conversions (g, ml, cups, tbsp)

### 5. `nextcloud_uploader.py` 🔄 **SKELETON**
**Purpose:** Upload DOCX/PDF to Nextcloud via WebDAV

**To Implement:**
- [ ] Accept base64-encoded files
- [ ] Create category folders in Nextcloud
- [ ] Upload via WebDAV PUT
- [ ] Generate public share links
- [ ] Return URLs

### 6. `import_recipes.py` ✅ **READY**
**Purpose:** Import recipes from Nextcloud or YouTube

**Capabilities:**
- Import from Nextcloud: `python scripts/import_recipes.py --source nextcloud`
- Import from YouTube: `python scripts/import_recipes.py --source youtube`
- Saves to database

### 7. `setup_database.py` ✅ **READY**
**Purpose:** Create PostgreSQL database and user

**Completed:**
- ✅ Created `recipe_db` database
- ✅ Created `recipe_user` user
- ✅ Initialized schema from `database/schema.sql`
- ✅ All 4 tables created
- ✅ All indexes and views created

---

## 🔀 n8n Workflows (6 Workflows)

### WF-01: Monitor Playlist
**Status:** 🟡 Imported to n8n (but needs fixing)
**URL:** https://n8n.csc-ua.tech/workflow/9QXzE48DP7rcZ0ft

**Design:**
- Trigger: Scheduler (every 3 hours)
- Action: Poll YouTube Data API
- Extracts: video_id, title, description, thumbnail, channel
- Logs to: `video_log` table
- Calls: WF-02 webhook

**Current Issues:**
- ❌ PostgreSQL credential not properly linked
- ❌ Nodes appear "broken" in UI

### WF-02: Extract Recipe Data
**Status:** 🟡 Designed (not yet tested)

**Design:**
- Trigger: Webhook (`/recipe-extract`)
- Input: YouTube video metadata
- Action: Call `parse_recipe.py` HTTP service (port 5010)
- Saves to: `recipes` table
- Calls: WF-03 webhook

**Nodes:**
- Webhook → parse_recipe.py → Save to DB → Trigger WF-03

### WF-03: Generate DOCX
**Status:** 🟡 Designed (not yet tested)

**Design:**
- Trigger: Webhook (`/recipe-docx`)
- Action: Call `generate_docx.py` HTTP service
- Receives: base64-encoded DOCX
- Calls: WF-04 webhook

### WF-04: Convert to PDF
**Status:** 🟡 Designed (not yet tested)

**Design:**
- Trigger: Webhook (`/recipe-pdf`)
- Action: Call `pdf_converter.py` HTTP service
- Receives: base64-encoded PDF
- Calls: WF-05 webhook

### WF-05: Upload to Nextcloud
**Status:** 🟡 Designed (not yet tested)

**Design:**
- Trigger: Webhook (`/recipe-nextcloud`)
- Action: Call `nextcloud_uploader.py` HTTP service
- Updates: `recipes` table with URLs
- Calls: WF-06 webhook

### WF-06: Telegram Notify & Log
**Status:** 🟡 Designed (not yet tested)

**Design:**
- Trigger: Webhook (`/recipe-telegram`)
- Action: Send Telegram message via Bot API
- Message includes: recipe title, category, Nextcloud links, YouTube URL
- Updates: `video_log` status to 'completed'

**Telegram Bot:**
- Credential ID: `15FBWslyV5AvsHZc`
- Name: `Telegram Recipe_Oleksii_bot`
- Status: ✅ Ready to use

---

## 📋 Configuration Files

### .env Template
Located: `.env.example` in repository

**Configured on Markiz:**
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recipe_db
DB_USER=recipe_user
DB_PASSWORD=RecipeSecure2026!

OLLAMA_BASE_URL=http://100.81.127.54:11434
OLLAMA_MODEL=qwen3:8b

NEXTCLOUD_URL=https://nextcloud.csc-ua.tech
NEXTCLOUD_USER=vagmechanik26@gmail.com
NEXTCLOUD_PASSWORD=kJBKJb,wdms527

YOUTUBE_PLAYLIST_URL=https://youtube.com/playlist?list=PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz

N8N_WEBHOOK_BASE_URL=https://n8n.csc-ua.tech/webhook
SCRIPTS_BASE_URL=http://localhost:5010
```

### Nextcloud Folder Structure
**Created:** Folders for 8 recipe categories
```
Рецепти/
├── Перші страви/ (First courses)
├── Другі страви/ (Main dishes)
├── Салати/ (Salads)
├── Закуски/ (Appetizers)
├── Випічка/ (Baked goods)
├── Десерти/ (Desserts)
├── Напої/ (Drinks)
└── Інше/ (Other)
```

---

## 🎯 Current Status Summary

### ✅ Completed
1. GitHub repository with 28 files
2. PostgreSQL database `recipe_db` with 4 tables
3. Database schema, indexes, views
4. Python script: `parse_recipe.py` (AI extraction) ✅ Running on port 5010
5. 6 n8n workflows designed and exported as JSON
6. Configuration templates
7. Comprehensive documentation (3,000+ lines)
8. Environment setup on Markiz

### 🟡 In Progress
1. n8n workflow imports (partially done, needs credential fixes)
2. Implementing skeleton scripts:
   - `generate_docx.py` (needs python-docx implementation)
   - `pdf_converter.py` (needs LibreOffice wrapper)
   - `nutrition_calculator.py` (needs USDA database)
   - `nextcloud_uploader.py` (needs WebDAV implementation)

### ❌ Blockers
1. **WF-01 PostgreSQL Credential:** Imported workflow nodes lost credential references
   - n8n credentials ID: `MHjN5hbuya1gKM8g` (Postgres_Recipe)
   - Need to manually link nodes to credential in UI

2. **Workflow Node Connections:** Webhooks may not be properly configured

3. **Python Service Integration:** WF-02 through WF-05 reference HTTP endpoints that need to be fully implemented

---

## 🚀 Next Steps (Priority Order)

1. **Fix WF-01 in n8n UI:**
   - Open each PostgreSQL node
   - Select "Postgres_Recipe" credential
   - Test connection
   - Save workflow

2. **Implement Skeleton Scripts:**
   - `generate_docx.py` — Use python-docx library
   - `pdf_converter.py` — Wrap LibreOffice CLI
   - `nextcloud_uploader.py` — Implement WebDAV upload

3. **Test Individual Workflows:**
   - Test WF-02 with curl to webhook
   - Test WF-03, WF-04, WF-05 with test data
   - Verify database logging

4. **Deploy All Services:**
   - Start all 4 Python services as systemd services
   - Configure n8n credentials properly
   - Activate WF-01 scheduler

5. **End-to-End Test:**
   - Add test video to YouTube playlist
   - Monitor workflow execution
   - Verify Nextcloud uploads
   - Verify Telegram notification

---

## 📞 Support

- **Documentation:** See CLAUDE.md, QUICK_START.md, SETUP_GUIDE.md
- **Database Schema:** See database/schema.sql
- **Workflow Design:** See N8N_DEPLOYMENT_GUIDE.md
- **Recipe Format:** See docs/RECIPE_FORMAT.md

---

**Last Updated:** 2026-06-21  
**Next Review:** After WF-01 is fixed  
**Prepared By:** Claude Code
