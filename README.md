# 🍽️ Recipe Automation System

An automated YouTube-to-Nextcloud recipe processing system. Monitors YouTube playlists, extracts recipe data using AI, generates formatted DOCX/PDF documents, and delivers them to Nextcloud with Telegram notifications.

## 🚀 Features

- **YouTube Monitoring:** Automatically detect new videos in a playlist (every 1-3 hours)
- **AI Recipe Extraction:** Parse unstructured video descriptions into structured recipes using Ollama or OpenAI
- **Smart Categorization:** Auto-categorize recipes (Desserts, Main Dishes, Soups, etc.)
- **Document Generation:** Create professional DOCX files with images, ingredients, instructions, and nutrition facts
- **PDF Conversion:** Automatically convert DOCX to PDF via LibreOffice
- **Nextcloud Storage:** Upload files to organized Nextcloud folders
- **Telegram Notifications:** Send formatted notifications with file links and YouTube source
- **Full Logging:** Track all operations in PostgreSQL database

## 📋 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL
- Ollama or OpenAI API
- Nextcloud instance with WebDAV access
- Telegram Bot token
- n8n instance (v1.0+)
- LibreOffice (for PDF conversion)

### Installation

1. **Clone repository**
   ```bash
   git clone https://github.com/OleksiiSnikhovskyi/Recipe.git
   cd Recipe
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp config/environment_template.env .env
   # Edit .env with your credentials
   ```

4. **Initialize database**
   ```bash
   psql -h localhost -U postgres -d recipes_db -f database/schema.sql
   ```

5. **Configure n8n workflows**
   - Import workflow files from `N8N_WORKFLOW_EXPORTS/`
   - Add credentials (YouTube API, Nextcloud, Telegram)
   - Deploy workflows

## 📁 Project Structure

```
Recipe/
├── CLAUDE.md                    # Full project documentation
├── TASKS.md                     # Task tracker & session log
├── config/                      # Configuration & setup guides
│   ├── environment_template.env
│   ├── nextcloud_structure.md
│   ├── youtube_api_setup.md
│   └── telegram_bot_setup.md
├── database/                    # Database schema & migrations
│   ├── schema.sql
│   └── migrations/
├── docs/                        # Technical documentation
│   ├── RECIPE_FORMAT.md         # JSON schema specification
│   ├── NEXTCLOUD_WEBDAV.md
│   └── TROUBLESHOOTING.md
├── N8N_WORKFLOW_EXPORTS/        # n8n workflow JSON files
├── scripts/                     # Python helper scripts
│   ├── parse_recipe.py          # AI recipe extraction
│   ├── generate_docx.py         # DOCX document generation
│   ├── pdf_converter.py         # DOCX → PDF conversion
│   ├── nutrition_calculator.py  # Nutrition facts calculation
│   └── nextcloud_uploader.py    # Nextcloud WebDAV upload
└── tests/                       # Unit & integration tests
```

## 🔧 Workflows

### WF-01: Monitor Playlist
**Trigger:** Scheduler (every 1-3 hours)
- Poll YouTube for new videos
- Check if already processed
- Queue for extraction

### WF-02: Extract Recipe Data
**Trigger:** Webhook
- Call AI (Ollama/OpenAI) to extract recipe
- Validate JSON structure
- Queue for DOCX generation

### WF-03: Generate DOCX
**Trigger:** Webhook
- Create formatted Word document
- Embed thumbnail image
- Add ingredients table, instructions, nutrition

### WF-04: Convert to PDF
**Trigger:** Webhook
- Use LibreOffice Headless
- Generate matching PDF file

### WF-05: Upload to Nextcloud
**Trigger:** Webhook
- Create category folder if needed
- Upload DOCX and PDF via WebDAV
- Generate public share links

### WF-06: Notify & Log
**Trigger:** Webhook
- Send Telegram message
- Record in PostgreSQL
- Mark as completed

## 🤖 AI Models

### Ollama (Recommended)
```
Default: qwen3:8b
Fallback: qwen2.5:7b, llama3.2:3b
Endpoint: http://100.81.127.54:11434
```

### OpenAI
```
Model: gpt-4
Requires: OPENAI_API_KEY
```

## 📊 Recipe Categories

- Перші страви (First courses / Soups)
- Другі страви (Second courses / Main dishes)
- Салати (Salads)
- Закуски (Appetizers)
- Випічка (Baked goods)
- Десерти (Desserts)
- Напої (Beverages)
- Інше (Other)

## 🗄️ Database

PostgreSQL tables:
- `recipes` — Extracted recipe data
- `video_log` — Processing status tracking
- `playlist_tracking` — YouTube playlist metadata
- `execution_log` — n8n workflow execution logs

## 📝 Recipe JSON Format

See [docs/RECIPE_FORMAT.md](docs/RECIPE_FORMAT.md) for complete schema.

**Example:**
```json
{
  "title": "Пісташкове тірамісу",
  "category": "Десерти",
  "servings": 8,
  "ingredients": [
    {"name": "Печиво Ladyfinger", "quantity": 400, "unit": "г"},
    {"name": "Маскарпоне", "quantity": 300, "unit": "г"}
  ],
  "steps": [
    {"step_number": 1, "instruction": "Крок 1: ..."},
    {"step_number": 2, "instruction": "Крок 2: ..."}
  ],
  "source": {
    "video_id": "dQw4w9WgXcQ",
    "youtube_channel": "Мої Рецепти"
  }
}
```

## 🚦 Status & Roadmap

### Phase 1: Foundation ✅ Planned
- [ ] PostgreSQL schema
- [ ] Python scripts (parse, generate, convert)
- [ ] Environment configuration

### Phase 2: n8n Workflows 🔄 Next
- [ ] WF-01 Monitor Playlist
- [ ] WF-02 Extract Recipe Data
- [ ] WF-03 Generate DOCX
- [ ] WF-04 Convert to PDF
- [ ] WF-05 Upload to Nextcloud
- [ ] WF-06 Notify & Log

### Phase 3: Integration & Testing
- [ ] End-to-end testing
- [ ] Error handling
- [ ] Performance optimization

### Phase 4: Enhancements
- [ ] Telegram bot manual trigger
- [ ] Recipe regeneration
- [ ] Support for additional sources (Instagram, TikTok)

## 🛠️ Development

### Testing

```bash
# Test recipe extraction
python scripts/parse_recipe.py --input "recipe description" --channel "Channel Name"

# Test DOCX generation
python scripts/generate_docx.py --recipe recipe.json --output output.docx

# Test PDF conversion
python scripts/pdf_converter.py --input recipe.docx --output recipe.pdf
```

### Running Python Scripts as HTTP Servers

```bash
# Recipe extraction service
python scripts/parse_recipe.py --server --port 5000

# DOCX generation service
python scripts/generate_docx.py --server --port 5001

# PDF conversion service
python scripts/pdf_converter.py --server --port 5002

# Nextcloud upload service
python scripts/nextcloud_uploader.py --server --port 5003
```

## 📖 Documentation

- **[CLAUDE.md](CLAUDE.md)** — Full project architecture and implementation guide
- **[TASKS.md](TASKS.md)** — Task tracker and session continuity
- **[docs/RECIPE_FORMAT.md](docs/RECIPE_FORMAT.md)** — JSON schema specification
- **[config/nextcloud_structure.md](config/nextcloud_structure.md)** — Nextcloud organization
- **[config/environment_template.env](config/environment_template.env)** — Environment setup

## 🐛 Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues and solutions.

## 📄 License

Project for internal use. Contact for licensing questions.

## 👤 Author

Oleksii Snikhovskyi

---

**Project Status:** Initialization Complete (2026-06-21)
See [TASKS.md](TASKS.md) for next steps and progress tracking.
