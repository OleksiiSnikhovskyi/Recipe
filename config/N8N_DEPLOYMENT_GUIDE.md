# Recipe Automation — n8n Deployment Guide

Complete instructions for deploying 6 n8n workflows with Python backend services on Markiz.

---

## 📋 Architecture Overview

```
n8n (https://n8n.csc-ua.tech)
  ↓
  WF-01-recipe (Monitor YouTube Playlist) [Scheduler]
    ↓ (POST /recipe-extract)
  WF-02-recipe (Extract Recipe) [Webhook] → parse_recipe.py (port 5000)
    ↓ (POST /recipe-docx)
  WF-03-recipe (Generate DOCX) [Webhook] → generate_docx.py (port 5001)
    ↓ (POST /recipe-pdf)
  WF-04-recipe (Convert PDF) [Webhook] → pdf_converter.py (port 5002)
    ↓ (POST /recipe-nextcloud)
  WF-05-recipe (Upload Nextcloud) [Webhook] → nextcloud_uploader.py (port 5003)
    ↓ (POST /recipe-telegram)
  WF-06-recipe (Telegram Notify) [Webhook] → Telegram Bot API
    ↓
  Database (PostgreSQL on Markiz)
```

---

## Step 1: Prepare Environment on Markiz

### 1.1 SSH to Markiz

```bash
ssh user@100.81.127.54
```

### 1.2 Create Recipe App Directory

```bash
sudo mkdir -p /opt/recipe-automation
sudo chown $USER:$USER /opt/recipe-automation
cd /opt/recipe-automation

# Clone repository
git clone https://github.com/OleksiiSnikhovskyi/Recipe.git .
```

### 1.3 Set Up Python Environment

```bash
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r scripts/requirements_servers.txt
```

### 1.4 Create .env File

```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**Critical settings to verify:**

```bash
DB_HOST=100.81.127.54
DB_PORT=5432
DB_NAME=recipe_db
DB_USER=recipe_user
DB_PASSWORD=<your_password>

YOUTUBE_API_KEY=<your_key>
YOUTUBE_PLAYLIST_URL=https://youtube.com/playlist?list=PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz

NEXTCLOUD_URL=https://nextcloud.csc-ua.tech
NEXTCLOUD_USER=vagmechanik26@gmail.com
NEXTCLOUD_PASSWORD=<your_password>

TELEGRAM_BOT_TOKEN=<from_n8n_credentials>
TELEGRAM_CHAT_ID=<your_chat_id>

OLLAMA_BASE_URL=http://100.81.127.54:11434
OLLAMA_MODEL=qwen3:8b

N8N_WEBHOOK_BASE_URL=https://n8n.csc-ua.tech/webhook
SCRIPTS_BASE_URL=http://localhost:5000
```

---

## Step 2: Create PostgreSQL Database

```bash
python scripts/setup_database.py --env .env
```

Verify:

```bash
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "SELECT COUNT(*) FROM recipes;"
```

---

## Step 3: Run Python Services

### Option A: Foreground (Testing)

```bash
# Terminal 1: Recipe extraction
python scripts/parse_recipe.py --server --port 5000

# Terminal 2: DOCX generation
python scripts/generate_docx.py --server --port 5001

# Terminal 3: PDF conversion
python scripts/pdf_converter.py --server --port 5002

# Terminal 4: Nextcloud upload
python scripts/nextcloud_uploader.py --server --port 5003
```

Test each service:

```bash
# From another terminal
curl -X POST http://localhost:5000/health
curl -X POST http://localhost:5001/health
curl -X POST http://localhost:5002/health
curl -X POST http://localhost:5003/health
```

### Option B: Background with Systemd (Production)

Create systemd service files:

```bash
sudo tee /etc/systemd/system/recipe-parse-recipe.service > /dev/null <<EOF
[Unit]
Description=Recipe Automation - Parse Recipe Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=recipe
WorkingDirectory=/opt/recipe-automation
Environment="PATH=/opt/recipe-automation/venv/bin"
ExecStart=/opt/recipe-automation/venv/bin/python scripts/parse_recipe.py --server --port 5000

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/recipe-generate-docx.service > /dev/null <<EOF
[Unit]
Description=Recipe Automation - Generate DOCX Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=recipe
WorkingDirectory=/opt/recipe-automation
Environment="PATH=/opt/recipe-automation/venv/bin"
ExecStart=/opt/recipe-automation/venv/bin/python scripts/generate_docx.py --server --port 5001

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/recipe-pdf-converter.service > /dev/null <<EOF
[Unit]
Description=Recipe Automation - PDF Converter Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=recipe
WorkingDirectory=/opt/recipe-automation
Environment="PATH=/opt/recipe-automation/venv/bin"
ExecStart=/opt/recipe-automation/venv/bin/python scripts/pdf_converter.py --server --port 5002

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/recipe-nextcloud-uploader.service > /dev/null <<EOF
[Unit]
Description=Recipe Automation - Nextcloud Uploader Service
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=recipe
WorkingDirectory=/opt/recipe-automation
Environment="PATH=/opt/recipe-automation/venv/bin"
ExecStart=/opt/recipe-automation/venv/bin/python scripts/nextcloud_uploader.py --server --port 5003

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable recipe-parse-recipe.service recipe-generate-docx.service recipe-pdf-converter.service recipe-nextcloud-uploader.service
sudo systemctl start recipe-parse-recipe.service recipe-generate-docx.service recipe-pdf-converter.service recipe-nextcloud-uploader.service

# Check status
sudo systemctl status recipe-*.service
```

Monitor logs:

```bash
sudo journalctl -u recipe-parse-recipe.service -f
sudo journalctl -u recipe-generate-docx.service -f
sudo journalctl -u recipe-pdf-converter.service -f
sudo journalctl -u recipe-nextcloud-uploader.service -f
```

---

## Step 4: Configure n8n Credentials

Login to https://n8n.csc-ua.tech

### 4.1 YouTube Data API v3

**Credentials** → **Create new** → **YouTube Data v3**

- API Key: `<your_YOUTUBE_API_KEY>`

### 4.2 Telegram

Use existing: `Telegram Recipe_Oleksii_bot` (ID: `15FBWslyV5AvsHZc`)

### 4.3 Nextcloud

**Credentials** → **Create new** → **Nextcloud**

- Host: `https://nextcloud.csc-ua.tech`
- Username: `vagmechanik26@gmail.com`
- Password: `<your_password>`

### 4.4 PostgreSQL

**Credentials** → **Create new** → **Postgres**

- Host: `100.81.127.54`
- Port: `5432`
- Database: `recipe_db`
- User: `recipe_user`
- Password: `<your_password>`
- SSL: false

---

## Step 5: Import n8n Workflows

### 5.1 Export from Repository

Workflows are in `N8N_WORKFLOW_EXPORTS/`:
- `WF-01-recipe-monitor-playlist.json`
- `WF-02-recipe-extract-data.json`
- `WF-03-recipe-generate-docx.json`
- `WF-04-recipe-convert-pdf.json`
- `WF-05-recipe-upload-nextcloud.json`
- `WF-06-recipe-telegram-notify.json`

### 5.2 Import in n8n UI

1. Go to n8n: https://n8n.csc-ua.tech
2. **Menu** → **Import from File**
3. Select each workflow JSON file and import
4. For each workflow:
   - Click **Edit**
   - Check credentials are assigned correctly
   - Verify environment variables (${DB_HOST}, etc.)
   - Click **Save**

### 5.3 Verify Webhook URLs

Each workflow needs webhook URL. After import:

1. **WF-01-recipe:** Scheduler node should be configured for "every 3 hours"
2. **WF-02 through WF-06:** Each should have unique webhook path:
   - WF-02: `/recipe-extract`
   - WF-03: `/recipe-docx`
   - WF-04: `/recipe-pdf`
   - WF-05: `/recipe-nextcloud`
   - WF-06: `/recipe-telegram`

Full webhook URLs:
```
https://n8n.csc-ua.tech/webhook/recipe-extract
https://n8n.csc-ua.tech/webhook/recipe-docx
https://n8n.csc-ua.tech/webhook/recipe-pdf
https://n8n.csc-ua.tech/webhook/recipe-nextcloud
https://n8n.csc-ua.tech/webhook/recipe-telegram
```

---

## Step 6: Test Workflows

### 6.1 Test WF-02 Directly (without YouTube monitor)

Manually trigger webhook:

```bash
curl -X POST https://n8n.csc-ua.tech/webhook/recipe-extract \
  -H "Content-Type: application/json" \
  -d '{
    "videoId": "test001",
    "title": "Тесто Рецепт",
    "description": "Інгредієнти: 200г борошна, 100мл молока, 2 яйця. Приготування: змішати, запікти 30 хв при 180°C",
    "youtubeChannel": "Test Channel",
    "thumbnail": "https://via.placeholder.com/100",
    "publishedAt": "2026-06-21"
  }'
```

### 6.2 Monitor Database

```bash
psql -h 100.81.127.54 -U recipe_user -d recipe_db

SELECT * FROM recipes;
SELECT * FROM video_log;
SELECT * FROM execution_log;
```

### 6.3 Test Full Pipeline

1. Activate **WF-01-recipe** (Monitor Playlist)
2. Wait for scheduler to run (or manually trigger)
3. Watch workflows execute in n8n Dashboard
4. Check Telegram for notifications
5. Verify files in Nextcloud

---

## Step 7: Configure Monitoring

### 7.1 n8n Logging

In n8n: **Admin** → **Settings** → **Logging**
- Enable detailed logging
- Set retention to 30 days

### 7.2 Python Service Logging

Each Python service logs to stdout. For persistent logs:

```bash
mkdir -p /var/log/recipe-automation
chmod 755 /var/log/recipe-automation

# Redirect logs in systemd services:
# Add this line to each [Service] section:
StandardOutput=append:/var/log/recipe-automation/service-name.log
StandardError=append:/var/log/recipe-automation/service-name.log
```

View logs:

```bash
tail -f /var/log/recipe-automation/*.log
```

### 7.3 Database Audit

Query execution logs:

```bash
SELECT workflow_name, status, COUNT(*) as count
FROM execution_log
GROUP BY workflow_name, status;
```

---

## Troubleshooting

### Python Service Won't Start

```bash
# Check Python version
python3 --version  # Must be 3.8+

# Check dependencies
pip list | grep psycopg2

# Try running manually
python scripts/parse_recipe.py --server --port 5000
```

### Workflow Execution Fails

1. Check n8n logs: **Admin** → **Execution History**
2. Look at execution details:
   - Which node failed?
   - What was the error?
   - Was timeout reached?

### HTTP Request Timeout

If Python services are slow:
- Increase timeout in n8n workflow: **HTTP Request** → **Options** → **Timeout**
- Check server load: `top` on Markiz
- Check network connectivity: `ping 100.81.127.54`

### Database Connection Error

```bash
# Test connection
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "SELECT 1;"

# Check credentials in .env
grep DB_ .env

# Verify recipe_user has permissions
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "\dt"
```

### Ollama Model Not Found

```bash
# SSH to Markiz and check
curl http://100.81.127.54:11434/api/tags

# Pull model if missing
curl -X POST http://100.81.127.54:11434/api/pull \
  -d '{"name": "qwen3:8b"}'
```

---

## Performance Optimization

### 1. Parallel Processing

Workflows are designed for sequential processing (WF-01 → WF-02 → ... → WF-06).

For future parallel processing:
- Cache recipe extraction results
- Run PDF conversion in parallel with Nextcloud upload
- Use Redis for job queue

### 2. Database Optimization

```bash
# Create indexes (already in schema.sql)
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "
CREATE INDEX IF NOT EXISTS idx_recipes_processed ON recipes(processed);
CREATE INDEX IF NOT EXISTS idx_video_log_status ON video_log(status);
"

# Vacuum table periodically
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "VACUUM recipes;"
```

### 3. Python Service Optimization

Uncomment production settings in `.env`:

```bash
GUNICORN_WORKERS=4  # Number of worker processes
GUNICORN_THREADS=2  # Threads per worker
```

---

## Production Deployment Checklist

- [ ] Database created and schema initialized
- [ ] .env file configured (no secrets in git)
- [ ] Python services running (systemd or Docker)
- [ ] n8n credentials configured correctly
- [ ] All 6 workflows imported
- [ ] Webhook paths verified
- [ ] WF-01 scheduler activated
- [ ] Test workflow executed end-to-end
- [ ] Telegram notifications working
- [ ] Nextcloud uploads verified
- [ ] Database logging working
- [ ] Monitoring and alerts configured
- [ ] Logs retained and rotated

---

## Maintenance

### Weekly

- Check execution logs for errors
- Verify YouTube playlist is monitored
- Monitor disk space for temp files

### Monthly

- Backup PostgreSQL database
- Review performance metrics
- Update Python packages (`pip install --upgrade -r requirements.txt`)

### Quarterly

- Archive old recipes (move to cold storage)
- Review and optimize slow workflows
- Test disaster recovery

---

## Next Steps

1. ✅ Prepare Markiz environment
2. ✅ Run Python services
3. ✅ Import n8n workflows
4. ✅ Test end-to-end
5. ⏳ **Activate WF-01** (Monitor Playlist)
6. ⏳ **Monitor & Iterate**

---

**Deployment Date:** 2026-06-21
**Status:** Ready for testing
**Support:** See config/SETUP_GUIDE.md for detailed troubleshooting
