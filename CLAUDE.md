# CLAUDE.md — Recipe Automation Project

## Project Overview

**Recipe** is an automated YouTube-to-Nextcloud recipe processing system. It monitors a YouTube playlist, extracts recipe data via AI, generates formatted DOCX/PDF documents, and delivers them to Nextcloud with Telegram notifications.

**Language:** Ukrainian (Українська) for user-facing content; English for code and documentation.
**Infrastructure:** n8n (Markiz), Nextcloud (WebDAV), Ollama (local AI), PostgreSQL (recipe tracking).

---

## System Architecture

### Data Flow

```
YouTube Playlist
    ↓ (every 1-3 hours)
n8n Scheduler (WF-01: Monitor Playlist)
    ↓ (fetch new videos)
n8n Webhook Listener
    ↓
WF-02: Extract Recipe Data (AI + YouTube API)
    ↓ (structure ingredients, steps, nutrition)
WF-03: Generate DOCX (python-docx)
    ↓
WF-04: Convert to PDF (LibreOffice Headless)
    ↓
WF-05: Upload to Nextcloud (WebDAV)
    ↓
WF-06: Notify Telegram + Log to DB
```

### n8n Workflows

| Workflow ID | Name | Trigger | Purpose |
|---|---|---|---|
| WF-01 | Monitor Playlist | Scheduler (1-3h) | Poll YouTube, detect new videos |
| WF-02 | Extract Recipe Data | Webhook | Parse title, description, AI-generate ingredients/steps |
| WF-03 | Generate DOCX | Webhook | Create Word document with recipe content |
| WF-04 | Convert to PDF | Webhook | Transform DOCX → PDF via LibreOffice |
| WF-05 | Upload to Nextcloud | Webhook | Save files to Nextcloud folders by category |
| WF-06 | Notify & Log | Webhook | Send Telegram message, record to database |

---

## Data Structures

### Recipe Database Schema (PostgreSQL)

```sql
CREATE TABLE recipes (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    recipe_text TEXT,
    ingredients JSONB,
    steps JSONB,
    nutrition JSONB,
    youtube_url VARCHAR(500),
    youtube_channel VARCHAR(255),
    thumbnail_url VARCHAR(500),
    docx_path VARCHAR(500),
    pdf_path VARCHAR(500),
    nextcloud_docx_url VARCHAR(500),
    nextcloud_pdf_url VARCHAR(500),
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE video_log (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(255) NOT NULL,
    playlist_id VARCHAR(255),
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50)
);
```

### Recipe Content Structure (JSON)

```json
{
  "title": "Пісташкове тірамісу",
  "category": "Десерти",
  "image_url": "https://...",
  "ingredients": [
    {"name": "Печиво Ladyfinger", "quantity": "400", "unit": "г"},
    {"name": "Сливки 35%", "quantity": "500", "unit": "мл"},
    {"name": "Маскарпоне", "quantity": "300", "unit": "г"}
  ],
  "steps": [
    "Крок 1: Розбити печиво на половини...",
    "Крок 2: Збити сливки зі смаком...",
    "Крок 3: Шаруватим способом укласти..."
  ],
  "nutrition_per_100g": {
    "calories": 285,
    "protein": 4.2,
    "fat": 16.5,
    "carbs": 32.1
  },
  "nutrition_per_serving": {
    "calories": 450,
    "protein": 6.5,
    "fat": 26.0,
    "carbs": 50.0
  },
  "source": {
    "youtube_channel": "Канал назва",
    "video_url": "https://youtube.com/watch?v=..."
  }
}
```

---

## Project Directories

```
Recipe/
├── CLAUDE.md                          # This file
├── TASKS.md                           # Task tracker & session log
├── README.md                          # GitHub repo overview
├── N8N_WORKFLOW_EXPORTS/              # n8n workflow JSON files
│   ├── WF-01_Monitor_Playlist.json
│   ├── WF-02_Extract_Recipe_Data.json
│   ├── WF-03_Generate_DOCX.json
│   ├── WF-04_Convert_PDF.json
│   ├── WF-05_Upload_Nextcloud.json
│   └── WF-06_Notify_Telegram.json
├── scripts/                           # Python/Node scripts
│   ├── generate_docx.py               # DOCX generation (python-docx)
│   ├── parse_recipe.py                # AI recipe parsing (Ollama/OpenAI)
│   ├── nutrition_calculator.py        # Nutrition data calculation
│   ├── pdf_converter.py               # DOCX → PDF (LibreOffice)
│   └── nextcloud_uploader.py          # WebDAV upload
├── config/                            # Configuration templates
│   ├── nextcloud_structure.md         # Nextcloud folder layout
│   ├── youtube_api_setup.md           # YouTube API key config
│   ├── telegram_bot_setup.md          # Telegram Bot token setup
│   ├── openai_ollama_config.md        # AI model configuration
│   └── environment_template.env       # Sample .env
├── docs/                              # Documentation
│   ├── RECIPE_FORMAT.md               # Recipe JSON schema
│   ├── NEXTCLOUD_WEBDAV.md            # WebDAV API integration
│   ├── OLLAMA_MODELS.md               # Ollama model selection
│   └── TROUBLESHOOTING.md             # Common issues & fixes
└── database/                          # DB migrations & queries
    ├── schema.sql                     # Create tables
    └── migrations/                    # Version-controlled schema changes
```

---

## Configuration & Credentials

### Environment Variables (.env)

```env
# YouTube API
YOUTUBE_API_KEY=your_key_here
YOUTUBE_PLAYLIST_ID=PLxxxxxxxx

# Nextcloud
NEXTCLOUD_URL=https://nextcloud.domain/
NEXTCLOUD_USER=username
NEXTCLOUD_PASSWORD=password
NEXTCLOUD_RECIPE_FOLDER=/Рецепти

# Telegram
TELEGRAM_BOT_TOKEN=123:ABC...
TELEGRAM_CHAT_ID=12345678

# AI (Ollama or OpenAI)
LLM_PROVIDER=ollama  # or "openai"
OLLAMA_BASE_URL=http://100.81.127.54:11434
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recipes_db
DB_USER=recipes_user
DB_PASSWORD=password

# n8n
N8N_BASE_URL=https://n8n.csc-ua.tech
N8N_API_KEY=your_api_key
```

### Key Configuration Files

- **Nextcloud Folder Structure:** See `config/nextcloud_structure.md`
- **AI Model Selection:** See `docs/OLLAMA_MODELS.md` for Ollama model recommendations
- **YouTube API:** See `config/youtube_api_setup.md` for playlist monitoring setup

---

## Workflow Design Patterns

### WF-01: Monitor Playlist (Scheduler Trigger)

```
Scheduler (every 1-3 hours)
    ↓
HTTP Request → YouTube Data API
    ↓
Extract: video_id, title, description, publishedAt, thumbnailUrl
    ↓
Check video_log table: already processed?
    ↓ NO
Call WF-02 webhook (pass video metadata)
    ↓
Log to video_log: processed = FALSE, status = 'pending'
```

### WF-02: Extract Recipe Data (HTTP Request + Code Node)

```
Input: { videoId, title, description, thumbnailUrl, youtubeUrl }
    ↓
Call LLM (Ollama/OpenAI):
  "Extract structured recipe from this YouTube description..."
    ↓
Parse LLM response → JSON
  {
    title, ingredients[], steps[], nutrition, category
  }
    ↓
Save to recipes table (processed=FALSE)
    ↓
Call WF-03 webhook
```

### WF-03: Generate DOCX (HTTP Request to Python script)

```
Input: recipe JSON
    ↓
Call HTTP → Python script (generate_docx.py)
    ↓
Python returns: base64-encoded DOCX file
    ↓
Save to S3/temp storage
    ↓
Call WF-04 webhook
```

### WF-04: Convert to PDF (LibreOffice Headless)

```
Input: DOCX file path
    ↓
Call: soffice --headless --convert-to pdf input.docx
    ↓
Output: PDF file in same directory
    ↓
Call WF-05 webhook
```

### WF-05: Upload to Nextcloud (WebDAV)

```
Input: { docxPath, pdfPath, category, recipeName }
    ↓
Determine category folder: /Рецепти/{category}/
    ↓
Upload DOCX via WebDAV PUT
    ↓
Upload PDF via WebDAV PUT
    ↓
Capture public share URLs
    ↓
Update recipes table: docx_path, pdf_path, nextcloud_docx_url, nextcloud_pdf_url
    ↓
Call WF-06 webhook
```

### WF-06: Notify & Log (Telegram)

```
Input: { recipeName, category, nextcloud_urls, youtubeUrl }
    ↓
Build Telegram message (Ukrainian):
  ✅ Новий рецепт оброблено
  Назва: {recipeName}
  Категорія: {category}
  DOCX: {nextcloud_docx_url}
  PDF: {nextcloud_pdf_url}
  YouTube: {youtubeUrl}
    ↓
POST → Telegram Bot API
    ↓
Update recipes table: processed=TRUE, updated_at=NOW()
    ↓
Log to video_log: status='completed'
```

---

## Python Scripts

### generate_docx.py

Uses `python-docx` to create formatted Word documents with:
- Recipe title
- Category badge
- Image (thumbnail)
- Ingredients table
- Step-by-step instructions
- Nutrition facts (per 100g and per serving)
- Source attribution (YouTube channel + link)

**Input:** `recipe.json`
**Output:** `Recipe Name.docx` (binary encoded for n8n HTTP response)

### parse_recipe.py

Calls Ollama or OpenAI with:
```
You are a professional recipe extractor. Extract a structured recipe from the following YouTube video description.
Return valid JSON with: title, ingredients (name, quantity, unit), steps (numbered list), nutrition facts, category.
Description: {description}
```

**Input:** YouTube description text
**Output:** Structured recipe JSON

### nutrition_calculator.py

Estimates USDA nutrition data from ingredient list:
- Lookup each ingredient in a local DB or API
- Calculate totals per serving
- Normalize to per 100g

### pdf_converter.py

Wraps LibreOffice Headless:
```bash
soffice --headless --convert-to pdf --outdir /output /input.docx
```

### nextcloud_uploader.py

WebDAV client using `requests`:
```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.put(
    f"{NEXTCLOUD_URL}/remote.php/dav/files/{USER}/{path}",
    data=open(file_path, 'rb'),
    auth=HTTPBasicAuth(USER, PASSWORD)
)
```

---

## Nextcloud Folder Structure

```
Рецепти/
├── Перші страви/       (Soups)
├── Другі страви/       (Main dishes)
├── Салати/             (Salads)
├── Закуски/            (Appetizers)
├── Випічка/            (Baked goods)
├── Десерти/            (Desserts)
├── Напої/              (Drinks)
└── Інше/               (Other)
```

Each category folder contains `.docx` and `.pdf` pairs for each recipe.

---

## AI Model Selection

### Ollama (Local, Recommended)

- **Recipe Extraction:** `qwen3:8b` (multilingual, instruction-following)
- **Fallback:** `llama3.2:3b`, `qwen2.5:7b`
- **Embeddings:** `bge-m3` (for similarity search / future phases)

### OpenAI (Cloud Alternative)

- **Model:** `gpt-4` or `gpt-4-turbo`
- **Cost:** ~$0.02 per recipe extraction
- **Speed:** Faster than Ollama 8b, but requires API key

---

## Integration with n8n

### Credentials Setup in n8n

1. **YouTube Data v3:** Create credential with API key
2. **Telegram:** Create credential with bot token
3. **Nextcloud:** Create credential with WebDAV URL + auth
4. **HTTP:** Pre-configured, no credentials needed

### Webhook URLs (n8n)

```
https://n8n.csc-ua.tech/webhook/recipe-extract
https://n8n.csc-ua.tech/webhook/recipe-docx
https://n8n.csc-ua.tech/webhook/recipe-pdf
https://n8n.csc-ua.tech/webhook/recipe-nextcloud
https://n8n.csc-ua.tech/webhook/recipe-telegram
```

---

## Error Handling & Logging

All workflows include:
- **Try/Catch:** Wrap each major step
- **Error Notification:** Slack/Telegram message on failure
- **Database Logging:** status field in video_log (pending, processing, failed, completed)
- **Retry Logic:** Max 3 retries with exponential backoff

---

## Deployment Checklist

- [ ] PostgreSQL schema initialized (database/schema.sql)
- [ ] .env file created with all credentials
- [ ] Python scripts tested locally
- [ ] Nextcloud folder structure created
- [ ] n8n workflows imported and tested
- [ ] YouTube API key configured and quota verified
- [ ] Telegram bot token added
- [ ] LibreOffice installed on Markiz
- [ ] Ollama running with `qwen3:8b` loaded

---

## Next Steps

1. Create `TASKS.md` with implementation phases
2. Export workflow JSON files from n8n into `N8N_WORKFLOW_EXPORTS/`
3. Implement Python scripts in `scripts/`
4. Test WF-01 (scheduler) with sample data
5. Iterate through each workflow, testing in isolation

---

## Session Continuity

Check `TASKS.md` at session start for context on:
- Which workflows are complete
- Which scripts are tested
- Current blockers
- Next priority
