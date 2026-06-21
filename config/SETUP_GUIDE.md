# Recipe Automation System — Complete Setup Guide

## Prerequisites

- Python 3.8+
- PostgreSQL client (psql) or Python psycopg2
- Access to Markiz server (100.81.127.54)
- Nextcloud account
- YouTube Data API key
- Telegram Bot token
- Ollama or OpenAI API access

---

## Step 1: Clone and Initial Setup

```bash
git clone https://github.com/OleksiiSnikhovskyi/Recipe.git
cd Recipe

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Configure Environment Variables

```bash
# Copy template
cp config/environment_template.env .env
cp .env.example .env  # Alternative location

# Edit with your actual credentials
nano .env
```

### From c:\Users\hp_sp\n8n\.env (existing workspace):

Fill in these from your workspace .env:

```bash
# Nextcloud
NEXTCLOUD_URL=https://nextcloud.csc-ua.tech
NEXTCLOUD_USER=vagmechanik26@gmail.com
NEXTCLOUD_DAV_USER=VAGMechanik
NEXTCLOUD_PASSWORD=<your_password>

# Markiz PostgreSQL (for admin tasks only)
DB_HOST=100.81.127.54
DB_PORT=5432
DB_USER=oleksiisnikhovskyi
DB_PASSWORD=<your_password>

# Ollama
OLLAMA_BASE_URL=http://100.81.127.54:11434
OLLAMA_MODEL=qwen3:8b

# YouTube Playlist
YOUTUBE_PLAYLIST_URL=https://youtube.com/playlist?list=PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz
```

---

## Step 3: Create PostgreSQL Database on Markiz

### Option A: Using Python (Recommended)

```bash
# Set up database and user
python scripts/setup_database.py \
  --env .env \
  --db-name recipe_db \
  --db-user recipe_user \
  --db-password YourSecurePassword123!
```

**What it does:**
1. Connects to Markiz PostgreSQL using admin credentials
2. Creates `recipe_db` database (with UTF-8, Ukrainian locale)
3. Creates `recipe_user` user with encrypted password
4. Grants necessary privileges
5. Initializes schema from `database/schema.sql`

### Option B: Manual via psql

If psql is installed on Markiz:

```bash
# Connect to Markiz
ssh user@100.81.127.54

# Connect to PostgreSQL as admin
psql -h localhost -U oleksiisnikhovskyi -d postgres

# Run SQL commands:
```

```sql
-- Create database
CREATE DATABASE recipe_db
    ENCODING 'UTF8'
    LC_COLLATE = 'uk_UA.UTF-8'
    LC_CTYPE = 'uk_UA.UTF-8'
    TEMPLATE = template0;

-- Create user
CREATE USER recipe_user WITH ENCRYPTED PASSWORD 'YourSecurePassword123!';

-- Grant privileges
GRANT CONNECT ON DATABASE recipe_db TO recipe_user;
GRANT USAGE ON SCHEMA public TO recipe_user;
GRANT CREATE ON SCHEMA public TO recipe_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO recipe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO recipe_user;
```

Then initialize schema:

```bash
psql -h 100.81.127.54 -U recipe_user -d recipe_db -f database/schema.sql
```

---

## Step 4: Test Database Connection

```bash
# Python test
python -c "
import psycopg2
conn = psycopg2.connect('dbname=recipe_db user=recipe_user password=YourSecurePassword123! host=100.81.127.54')
print('✅ Connected!')
conn.close()
"

# Or with psql
psql -h 100.81.127.54 -U recipe_user -d recipe_db -c "SELECT COUNT(*) FROM recipes;"
```

Expected output:
```
(1 row) count
-----------
          0
```

---

## Step 5: Set Up YouTube API Key

### Get API Key:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Recipe Automation"
3. Enable **YouTube Data API v3**
4. Create API key (Credentials → API key)
5. Copy key to `.env`:

```bash
YOUTUBE_API_KEY=AIzaSyD... (your key)
YOUTUBE_PLAYLIST_URL=https://youtube.com/playlist?list=PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz
```

### Verify:

```bash
curl -s "https://www.googleapis.com/youtube/v3/playlists?key=YOUR_KEY&id=PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz&part=snippet" | head -20
```

---

## Step 6: Set Up Telegram Bot

### Create Bot:

1. Message `@BotFather` on Telegram
2. `/newbot` → Enter name → Enter username
3. Copy token

### Configure:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmno...
TELEGRAM_CHAT_ID=<your_chat_id>
```

### Get Chat ID:

```bash
# Message your bot, then run:
curl -s "https://api.telegram.org/bot123456789:ABCdefGHIjklmno.../getUpdates" | grep from | head -1
```

### Test:

```python
import requests

bot_token = "YOUR_BOT_TOKEN"
chat_id = "YOUR_CHAT_ID"

requests.post(
    f"https://api.telegram.org/bot{bot_token}/sendMessage",
    json={"chat_id": chat_id, "text": "✅ Recipe Bot Connected!"}
)
```

---

## Step 7: Nextcloud Setup

### Create Recipe Folder Structure

```bash
# Use WebDAV to create folders (via python script or curl)
python -c "
import requests
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth('vagmechanik26@gmail.com', 'your_password')
categories = ['Перші страви', 'Другі страви', 'Салати', 'Закуски', 'Випічка', 'Десерти', 'Напої', 'Інше']

for cat in categories:
    url = f'https://nextcloud.csc-ua.tech/remote.php/dav/files/VAGMechanik/Documents/Recipe/{cat}'
    requests.request('MKCOL', url, auth=auth)
    print(f'✓ Created: {cat}')
"
```

### Verify Folder Structure

```bash
# WebDAV PROPFIND request
curl -X PROPFIND \
  -u "vagmechanik26@gmail.com:your_password" \
  "https://nextcloud.csc-ua.tech/remote.php/dav/files/VAGMechanik/Documents/Recipe/" \
  -d '<?xml version="1.0"?><propfind xmlns="DAV:"><prop><resourcetype/></prop></propfind>'
```

---

## Step 8: Test Each Component

### Test 1: Recipe Extraction (AI)

```bash
python scripts/parse_recipe.py \
  --input "Тесто: 200г борошна, 100мл молока. Приготування: змішати, запікти при 180°" \
  --video-id "test123" \
  --channel "Test Channel"
```

Expected: JSON with title, ingredients, steps

### Test 2: Database Connection

```bash
python scripts/setup_database.py --env .env
```

### Test 3: Nextcloud Upload

```bash
# Create dummy file
echo "Test" > test.txt

# Upload via WebDAV
python -c "
import requests
from requests.auth import HTTPBasicAuth

with open('test.txt', 'rb') as f:
    requests.put(
        'https://nextcloud.csc-ua.tech/remote.php/dav/files/VAGMechanik/Documents/Recipe/test.txt',
        data=f,
        auth=HTTPBasicAuth('vagmechanik26@gmail.com', 'your_password')
    )
print('✅ Uploaded')
"
```

---

## Step 9: Import Existing Recipes (Optional)

If you have recipes in Nextcloud or want to pre-populate from YouTube:

```bash
# From Nextcloud
python scripts/import_recipes.py --env .env --source nextcloud

# From YouTube playlist
python scripts/import_recipes.py --env .env --source youtube --youtube-api-key YOUR_KEY
```

---

## Step 10: Set Up n8n Workflows

1. Login to n8n: https://n8n.csc-ua.tech
2. Go to **Credentials** → Add new:
   - **YouTube Data API v3** → Add API key
   - **Nextcloud (WebDAV)** → Add credentials
   - **Telegram** → Add bot token
   - **HTTP** → Pre-configured

3. Import workflow files from `N8N_WORKFLOW_EXPORTS/`:
   - WF-01_Monitor_Playlist.json
   - WF-02_Extract_Recipe_Data.json
   - etc.

4. Update workflow settings:
   - Set Python script endpoints (if running locally)
   - Configure poll intervals
   - Test with sample data

---

## Troubleshooting

### Database Connection Fails

```bash
# Check if Markiz is reachable
ping 100.81.127.54

# Try connecting with psql
psql -h 100.81.127.54 -U oleksiisnikhovskyi -d postgres -c "SELECT 1"

# Check password (try escaping special chars)
# If password has special chars, may need quotes or escaping in psycopg2
```

### Nextcloud Authentication Error

```bash
# Verify credentials
curl -u "vagmechanik26@gmail.com:your_password" \
  "https://nextcloud.csc-ua.tech/remote.php/dav/files/"

# If error, check:
# 1. User is correct (email or DAV username)
# 2. Password is correct
# 3. 2FA might be enabled → use app password instead
```

### YouTube API Quota Exceeded

```
Error: User Rate Limit Exceeded

Solution:
1. YouTube API free quota: 10,000 units/day
2. Each playlist.list = 1 unit
3. Each video details = 1 unit
4. Reduce poll frequency or use OAuth with higher quota tier
5. Switch to Innertube API (undocumented, higher limits)
```

### Ollama Model Not Found

```bash
# Check available models
curl http://100.81.127.54:11434/api/tags

# Pull qwen3:8b if missing
curl -X POST http://100.81.127.54:11434/api/pull -d '{"name": "qwen3:8b"}'
```

---

## Verification Checklist

- [ ] PostgreSQL database created on Markiz
- [ ] `recipe_user` can connect and query tables
- [ ] YouTube API key working (quota check)
- [ ] Nextcloud login successful
- [ ] Telegram bot responds to messages
- [ ] Ollama model loaded (qwen3:8b)
- [ ] Python scripts can import required libraries
- [ ] `.env` file created and secured (not in git)
- [ ] n8n workflows imported
- [ ] Test workflow runs without errors

---

## Next Steps

1. ✅ **Foundation Complete** — Database, credentials, scripts ready
2. 🔄 **Implement n8n Workflows** — Create WF-01 through WF-06
3. 📊 **Test End-to-End** — Run full pipeline with sample recipe
4. 🚀 **Deploy** — Activate on production schedule

---

## Support

For issues, see:
- `docs/TROUBLESHOOTING.md`
- `CLAUDE.md` → Architecture section
- `TASKS.md` → Current progress and blockers

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` to git (add to `.gitignore`)
- Use `.env.example` as template for documentation
- Rotate credentials periodically
- Use strong passwords (min 12 chars, mix case/numbers/symbols)
- For production, use secret management (Vault, AWS Secrets, etc.)
- Restrict API keys to specific IPs/domains if possible

---

**Last Updated:** 2026-06-21
**Next Review:** After Phase 1 completion
