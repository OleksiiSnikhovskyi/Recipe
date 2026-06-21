# 🚀 Recipe Automation System — Quick Start

Get the Recipe system running in 10 minutes.

---

## 1️⃣ Clone & Setup

```bash
git clone https://github.com/OleksiiSnikhovskyi/Recipe.git
cd Recipe

# Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Time:** 2-3 minutes

---

## 2️⃣ Configure Credentials

```bash
# Copy template
cp .env.example .env

# Edit with your credentials
nano .env  # or use your editor
```

**Required:**
- `NEXTCLOUD_URL`, `NEXTCLOUD_USER`, `NEXTCLOUD_PASSWORD`
- `YOUTUBE_PLAYLIST_URL`
- `YOUTUBE_API_KEY` (optional for initial testing)
- `DB_HOST`, `DB_USER`, `DB_PASSWORD` (Markiz admin credentials)

**Time:** 2 minutes

---

## 3️⃣ Create PostgreSQL Database

### Easiest: Run Setup Script

```bash
python scripts/setup_database.py --env .env
```

This will:
✅ Connect to Markiz PostgreSQL
✅ Create `recipe_db` database
✅ Create `recipe_user` user
✅ Initialize schema from `database/schema.sql`
✅ Grant all necessary privileges

**Expected output:**
```
🔗 Connecting to PostgreSQL at 100.81.127.54:5432...
✅ Connection successful!
📦 Creating database 'recipe_db'...
✅ Database 'recipe_db' created!
👤 Creating user 'recipe_user'...
✅ User 'recipe_user' created!
🔐 Granting privileges to 'recipe_user'...
✅ Privileges granted!

✨ Database setup complete!
   Database: recipe_db
   User: recipe_user
   Host: 100.81.127.54:5432
```

**Time:** 1 minute

---

## 4️⃣ Test Database Connection

```bash
# Quick test
python -c "
import psycopg2
conn = psycopg2.connect('dbname=recipe_db user=recipe_user host=100.81.127.54')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM recipes;')
print(f'✅ Database ready! Recipes in DB: {cursor.fetchone()[0]}')
conn.close()
"
```

**Expected:** `✅ Database ready! Recipes in DB: 0`

**Time:** 30 seconds

---

## 5️⃣ Test Recipe Extraction (AI)

```bash
# Test Ollama recipe extraction
python scripts/parse_recipe.py \
  --input "Інгредієнти: 200г борошна, 100мл молока, 2 яйця. Приготування: змішати, запікти 30 хв при 180°C" \
  --video-id "test001" \
  --channel "Test Channel"
```

**Expected:** JSON output with structured recipe

**Time:** 30 seconds

---

## 6️⃣ (Optional) Test Nextcloud Connection

```bash
python -c "
import requests
from requests.auth import HTTPBasicAuth

# Test WebDAV access
url = 'https://nextcloud.csc-ua.tech/remote.php/dav/files/VAGMechanik/'
auth = HTTPBasicAuth('vagmechanik26@gmail.com', 'your_password')

response = requests.request('PROPFIND', url, auth=auth, headers={'Depth': '1'})
if response.status_code in [207, 200]:
    print('✅ Nextcloud connected!')
else:
    print(f'❌ Nextcloud error: {response.status_code}')
"
```

**Time:** 30 seconds

---

## ✅ All Set!

You've successfully:
- ✅ Set up Python environment
- ✅ Configured credentials
- ✅ Created PostgreSQL database on Markiz
- ✅ Tested database connection
- ✅ Tested AI recipe extraction
- ✅ (Optional) Tested Nextcloud access

---

## 📚 Next Steps

### For Frontend Testing:
```bash
# Import existing recipes from Nextcloud
python scripts/import_recipes.py --env .env --source nextcloud

# Check database
sqlite3 recipe_db "SELECT COUNT(*) FROM recipes;"
```

### For n8n Integration:
1. Visit https://n8n.csc-ua.tech
2. Import workflows from `N8N_WORKFLOW_EXPORTS/`
3. Configure credentials
4. Activate workflows

### For Full Documentation:
- 📖 **CLAUDE.md** — Architecture & workflow design
- 🔧 **config/SETUP_GUIDE.md** — Detailed setup instructions
- 🗂️ **docs/RECIPE_FORMAT.md** — Recipe JSON schema
- 📋 **TASKS.md** — Project status & progress

---

## ⚠️ Troubleshooting

### "psycopg2 not installed"
```bash
pip install psycopg2-binary
```

### "Connection refused to Markiz"
```bash
# Check if host is reachable
ping 100.81.127.54

# Verify credentials in .env
cat .env | grep "DB_"
```

### "Nextcloud authentication failed"
```bash
# If using 2FA, generate app password instead
# https://nextcloud.csc-ua.tech/settings/user/security
```

### "Ollama model not found"
```bash
# Pull the model
curl -X POST http://100.81.127.54:11434/api/pull \
  -d '{"name": "qwen3:8b"}'
```

---

## 📊 Quick Reference

| Component | Status | Command |
|---|---|---|
| Python env | ✅ Ready | `python --version` |
| Dependencies | ✅ Ready | `pip list | grep psycopg2` |
| PostgreSQL | ✅ Ready | `python scripts/setup_database.py --env .env` |
| Database | ✅ Ready | `echo "SELECT 1;" \| psql -h 100.81.127.54 -U recipe_user -d recipe_db` |
| Nextcloud | ⏳ Optional | `python scripts/import_recipes.py --env .env --source nextcloud` |
| YouTube API | ⏳ Optional | Set `YOUTUBE_API_KEY` in .env |
| Telegram Bot | ⏳ Optional | Set `TELEGRAM_BOT_TOKEN` in .env |

---

## 🎯 You're Ready!

Proceed to Phase 2: **n8n Workflow Implementation**

See: https://github.com/OleksiiSnikhovskyi/Recipe/blob/main/CLAUDE.md#n8n-workflows

---

**Time to completion:** ~10 minutes
**Last updated:** 2026-06-21
