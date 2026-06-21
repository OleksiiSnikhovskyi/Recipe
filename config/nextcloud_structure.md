# Nextcloud Folder Structure for Recipe Storage

## Overview

All recipes are organized in a hierarchical structure under the main `Рецепти` (Recipes) folder. Each category has a dedicated subfolder, and each recipe is stored as a pair of files: DOCX and PDF.

---

## Folder Hierarchy

```
Рецепти/
├── Перші страви/           (First courses / Soups)
│   ├── Борщ червоний.docx
│   ├── Борщ червоний.pdf
│   ├── Суп грибний.docx
│   ├── Суп грибний.pdf
│   └── ...
│
├── Другі страви/           (Second courses / Main dishes)
│   ├── Плов з курою.docx
│   ├── Плов з курою.pdf
│   ├── Котлети мясні.docx
│   ├── Котлети мясні.pdf
│   └── ...
│
├── Салати/                 (Salads)
│   ├── Салат "Грецький".docx
│   ├── Салат "Грецький".pdf
│   ├── Цезар.docx
│   ├── Цезар.pdf
│   └── ...
│
├── Закуски/                (Appetizers / Starters)
│   ├── Брускетта.docx
│   ├── Брускетта.pdf
│   ├── Сицилійська мелянза.docx
│   ├── Сицилійська мелянза.pdf
│   └── ...
│
├── Випічка/                (Baked goods / Bread)
│   ├── Сирники.docx
│   ├── Сирники.pdf
│   ├── Хліб пшеничний.docx
│   ├── Хліб пшеничний.pdf
│   └── ...
│
├── Десерти/                (Desserts / Sweets)
│   ├── Пісташкове тірамісу.docx
│   ├── Пісташкове тірамісу.pdf
│   ├── Торт Чорна Лісна.docx
│   ├── Торт Чорна Лісна.pdf
│   └── ...
│
├── Напої/                  (Drinks / Beverages)
│   ├── Смузі полуниця.docx
│   ├── Смузі полуниця.pdf
│   ├── Морс журавлина.docx
│   ├── Морс журавлина.pdf
│   └── ...
│
└── Інше/                   (Other / Miscellaneous)
    ├── [uncategorized recipes]
    └── ...
```

---

## Category Mapping

| Ukrainian Category | English | Recipe Type |
|---|---|---|
| **Перші страви** | First courses | Soups, broths, consommé |
| **Другі страви** | Second courses | Main dishes, meat, fish, pasta |
| **Салати** | Salads | Cold salads, vegetable preparations |
| **Закуски** | Appetizers | Starters, finger food, spreads |
| **Випічка** | Baked goods | Bread, rolls, pastries, cakes |
| **Десерти** | Desserts | Sweet treats, puddings, confections |
| **Напої** | Beverages | Drinks, juices, smoothies, teas |
| **Інше** | Other | Sauces, condiments, uncategorized |

---

## AI-Powered Category Detection

When WF-02 processes a recipe, it automatically categorizes based on:

### Detection Rules (for LLM prompt)

1. **Soup/Broth keywords:** борщ, суп, юлієнн, бульйон, consommé
   - **Category:** Перші страви

2. **Meat/Main dish keywords:** м'ясо, ребра, стейк, карі, плов, паста, ризотто
   - **Category:** Другі страви

3. **Salad keywords:** салат, микс, листя, редиска, грецький
   - **Category:** Салати

4. **Appetizer keywords:** закуска, брускетта, крем, паштет, намаз
   - **Category:** Закуски

5. **Baked goods keywords:** хліб, булка, сирники, сухофрукти, тісто, п'існе
   - **Category:** Випічка

6. **Dessert keywords:** десерт, торт, тірамісу, чизкейк, печиво, мус, маршмелоу
   - **Category:** Десерти

7. **Beverage keywords:** напій, сік, смузі, чай, кава, морс, компот
   - **Category:** Напої

If no clear match, default to **Інше**.

---

## Nextcloud WebDAV API Usage

### Creating Folders

```bash
curl -u username:password -X MKCOL \
  "https://nextcloud.domain/remote.php/dav/files/username/Рецепти/"
```

### Uploading Files

```bash
curl -u username:password -X PUT \
  --data-binary @recipe.docx \
  "https://nextcloud.domain/remote.php/dav/files/username/Рецепти/Десерти/Recipe%20Name.docx"
```

### Getting Public Share Link

```bash
# Create share (requires Nextcloud API, not WebDAV)
curl -u username:password -X POST \
  -H "OCS-APIRequest: true" \
  -d "path=/Рецепти/Десерти/Recipe Name.docx" \
  -d "shareType=3" \
  "https://nextcloud.domain/ocs/v2.php/apps/files_sharing/api/v1/shares"

# Returns: <url>https://nextcloud.domain/s/ABC123</url>
```

---

## Python WebDAV Uploader

### Using `easywebdav` library

```python
import easywebdav

webdav = easywebdav.connect(
    host='nextcloud.domain',
    username='username',
    password='password',
    protocol='https'
)

# Create folder if needed
webdav.mkdir('/Рецепти/Десерти')

# Upload file
webdav.upload('/local/path/recipe.docx', '/Рецепти/Десерти/recipe.docx')

# Get public share link (requires additional API call)
```

### Using `requests` library

```python
import requests
from requests.auth import HTTPBasicAuth

url = "https://nextcloud.domain/remote.php/dav/files/username/Рецепти/Десерти/recipe.docx"

with open('/local/path/recipe.docx', 'rb') as f:
    response = requests.put(
        url,
        data=f,
        auth=HTTPBasicAuth('username', 'password'),
        headers={'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    )

if response.status_code == 201:
    print("File uploaded successfully")
```

---

## File Naming Convention

**Pattern:** `{Recipe Title}.{extension}`

### Examples:
- `Пісташкове тірамісу.docx`
- `Пісташкове тірамісу.pdf`
- `Борщ червоний.docx`
- `Борщ червоний.pdf`

**Rules:**
- Use recipe title as returned by AI extraction
- No leading/trailing spaces
- Special characters (/, \, :, *, ?, ", <, >) replaced with underscore
- Maximum 200 characters
- Ukrainian spelling preserved

---

## Folder Permission Setup

In Nextcloud, set the `Рецепти` folder permissions:

- **Owner (you):** Full access (read, write, delete, share)
- **Public share link:** Read-only (for Telegram notifications)
- **Other users (optional):** Read-only or specific access

### Setup in Nextcloud UI:
1. Right-click `Рецепти` folder
2. Share → Create public link
3. Set permissions: Read only
4. Generate link (example: `https://nextcloud.domain/s/ABC123`)

Use this public link format in Telegram notifications instead of direct file URLs.

---

## Sync Recommendations

- **Sync to Desktop:** Enable Nextcloud Desktop client to keep local copies
- **Mobile Access:** Use Nextcloud mobile app (iOS/Android)
- **Browser:** Access via `https://nextcloud.domain/` web interface

---

## Backup & Archive

After 6 months, consider:
- Creating year/month subfolders for organization
- Archiving old recipes (zip and export to cold storage)
- Pruning duplicate recipes

---

## Troubleshooting

### File Upload Fails
- Check file size (max 2GB per Nextcloud default)
- Verify username/password
- Ensure folder exists in Nextcloud

### Permission Denied
- Check Nextcloud user has write access to folder
- Verify WebDAV is enabled (usually is by default)

### Public Share Link Not Working
- Ensure sharing app is enabled in Nextcloud
- Check link permissions (should be "Read only")
- Try regenerating link
