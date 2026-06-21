# Recipe JSON Format Specification

## Overview

This document defines the JSON schema for recipe data throughout the Recipe Automation system. All recipes follow this structure from extraction through storage and document generation.

---

## Complete Recipe Schema

```json
{
  "title": "Пісташкове тірамісу",
  "category": "Десерти",
  "description": "Класичне італійське тісто з пісташками та маскарпоне",
  "servings": 8,
  "prep_time_minutes": 20,
  "cook_time_minutes": 240,
  "difficulty": "medium",
  "image_url": "https://i.ytimg.com/vi/xxx/maxresdefault.jpg",
  
  "ingredients": [
    {
      "name": "Печиво Ladyfinger",
      "quantity": 400,
      "unit": "г",
      "calories_per_unit": 3.8,
      "notes": "Можна замінити на печиво Savoiardi"
    },
    {
      "name": "Сливки 35%",
      "quantity": 500,
      "unit": "мл",
      "calories_per_unit": 3.5,
      "notes": ""
    },
    {
      "name": "Маскарпоне",
      "quantity": 300,
      "unit": "г",
      "calories_per_unit": 4.2,
      "notes": ""
    },
    {
      "name": "Цукор",
      "quantity": 100,
      "unit": "г",
      "calories_per_unit": 3.87,
      "notes": ""
    },
    {
      "name": "Какао порошок",
      "quantity": 30,
      "unit": "г",
      "calories_per_unit": 1.2,
      "notes": ""
    },
    {
      "name": "Фісташки мелені",
      "quantity": 100,
      "unit": "г",
      "calories_per_unit": 5.5,
      "notes": "Для посипки зверху"
    }
  ],
  
  "steps": [
    {
      "step_number": 1,
      "instruction": "Крок 1: Розбити печиво Ladyfinger на половини.",
      "duration_minutes": 5,
      "notes": ""
    },
    {
      "step_number": 2,
      "instruction": "Крок 2: Збити 500 мл холодних сливок зі 100 г цукру до твердих піків (2-3 хвилини на середній швидкості).",
      "duration_minutes": 3,
      "notes": "Сливки мають бути холодними перед збиванням"
    },
    {
      "step_number": 3,
      "instruction": "Крок 3: Розмішати маскарпоне окремо, щоб розпушити.",
      "duration_minutes": 2,
      "notes": "Не перемішувати надто довго, маскарпоне може стати гільным"
    },
    {
      "step_number": 4,
      "instruction": "Крок 4: Акуратно помішати збиті сливки з маскарпоне.",
      "duration_minutes": 2,
      "notes": "Складувати акуратно, щоб зберегти повітря"
    },
    {
      "step_number": 5,
      "instruction": "Крок 5: Шаруватим способом викласти у форму або скляну чашу: печиво – крем – какао – фісташки.",
      "duration_minutes": 5,
      "notes": "Перший шар печиво, останній – фісташки на прикрасу"
    },
    {
      "step_number": 6,
      "instruction": "Крок 6: Охолодити в холодильнику протягом 4 годин (краще на ніч).",
      "duration_minutes": 240,
      "notes": "Мінімум 2 години, але краще залишити на ніч для краще консистенції"
    }
  ],
  
  "nutrition": {
    "per_100g": {
      "calories": 285,
      "protein": 4.2,
      "fat": 16.5,
      "carbohydrates": 32.1
    },
    "per_serving": {
      "calories": 450,
      "protein": 6.5,
      "fat": 26.0,
      "carbohydrates": 50.0
    }
  },
  
  "source": {
    "youtube_channel": "Канал Готування",
    "youtube_channel_url": "https://www.youtube.com/@KanalHotuvannya",
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "video_title": "Піташкове тірамісу за 30 хвилин",
    "published_date": "2025-06-15"
  },
  
  "metadata": {
    "recipe_id": null,
    "video_id": "dQw4w9WgXcQ",
    "extracted_at": "2026-06-21T10:30:00Z",
    "extraction_method": "ollama:qwen3:8b",
    "ai_confidence": 0.92,
    "language": "uk",
    "total_time_minutes": 270
  }
}
```

---

## Field Specifications

### Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | ✅ | Recipe name in Ukrainian |
| `category` | string | ✅ | One of: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше |
| `description` | string | ❌ | Brief recipe description |
| `servings` | number | ✅ | Number of servings this recipe makes |
| `prep_time_minutes` | number | ❌ | Preparation time in minutes |
| `cook_time_minutes` | number | ❌ | Cooking time in minutes |
| `difficulty` | string | ❌ | One of: easy, medium, hard |
| `image_url` | string | ❌ | URL to recipe image (usually YouTube thumbnail) |

### Ingredients Array

Each ingredient object:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Ingredient name |
| `quantity` | number | ✅ | Numeric quantity |
| `unit` | string | ✅ | Unit (г, мл, шт, кг, л, ч.л., ст.л., etc.) |
| `calories_per_unit` | number | ❌ | Estimated calories per unit (for nutrition calc) |
| `notes` | string | ❌ | Optional substitutions or notes |

### Steps Array

Each step object:

| Field | Type | Required | Description |
|---|---|---|---|
| `step_number` | number | ✅ | Sequential step number (1, 2, 3...) |
| `instruction` | string | ✅ | Full instruction text |
| `duration_minutes` | number | ❌ | How long this step takes |
| `notes` | string | ❌ | Tips or warnings |

### Nutrition Object

Contains `per_100g` and `per_serving` objects:

| Field | Type | Required | Description |
|---|---|---|---|
| `calories` | number | ❌ | Kilocalories (ккал) |
| `protein` | number | ❌ | Grams of protein (г) |
| `fat` | number | ❌ | Grams of fat (г) |
| `carbohydrates` | number | ❌ | Grams of carbs (г) |

### Source Object

YouTube metadata:

| Field | Type | Required | Description |
|---|---|---|---|
| `youtube_channel` | string | ✅ | Channel name |
| `youtube_channel_url` | string | ❌ | Channel URL |
| `video_id` | string | ✅ | YouTube video ID (11 chars) |
| `video_url` | string | ✅ | Full video URL |
| `video_title` | string | ❌ | Original video title |
| `published_date` | string | ❌ | ISO 8601 date (YYYY-MM-DD) |

### Metadata Object

Internal tracking:

| Field | Type | Required | Description |
|---|---|---|---|
| `recipe_id` | number | ❌ | Database ID after insertion |
| `video_id` | string | ✅ | Same as source.video_id |
| `extracted_at` | string | ✅ | ISO 8601 timestamp (UTC) |
| `extraction_method` | string | ✅ | AI model used (e.g., "ollama:qwen3:8b") |
| `ai_confidence` | number | ❌ | Confidence score 0-1 |
| `language` | string | ✅ | Language code ("uk" for Ukrainian) |
| `total_time_minutes` | number | ❌ | prep_time + cook_time |

---

## Validation Rules

### Required Fields (MVP)

Minimum valid recipe must have:
```json
{
  "title": "string (non-empty)",
  "category": "string (must be in valid categories list)",
  "servings": "number (> 0)",
  "ingredients": "array (length > 0)",
  "steps": "array (length > 0)",
  "source": {
    "video_id": "string (11 chars)",
    "video_url": "string (valid YouTube URL)",
    "youtube_channel": "string (non-empty)"
  },
  "metadata": {
    "video_id": "string (must match source.video_id)",
    "extracted_at": "ISO 8601 timestamp",
    "extraction_method": "string",
    "language": "uk"
  }
}
```

### Category Validation

Valid categories (must use exact Ukrainian spelling):
- Перші страви
- Другі страви
- Салати
- Закуски
- Випічка
- Десерти
- Напої
- Інше

### Unit Validation

Valid units:
- `г` (gram)
- `мл` (milliliter)
- `л` (liter)
- `кг` (kilogram)
- `шт` (piece)
- `ч.л.` (teaspoon)
- `ст.л.` (tablespoon)
- `чашка` (cup)
- `стакан` (glass)

### Time Fields

- `prep_time_minutes`: >= 0, must be number
- `cook_time_minutes`: >= 0, must be number
- `duration_minutes` (per step): >= 0, must be number
- Total recipe time = prep_time + cook_time

### Nutrition

Per 100g values should be realistic:
- `calories`: 0-900 (typical range)
- `protein`, `fat`, `carbs`: 0-100

---

## Example: Minimal Recipe (JSON)

```json
{
  "title": "Борщ червоний",
  "category": "Перші страви",
  "servings": 6,
  "ingredients": [
    {"name": "Яйця сирі", "quantity": 4, "unit": "шт"},
    {"name": "Цукор", "quantity": 100, "unit": "г"},
    {"name": "Борошно", "quantity": 200, "unit": "г"},
    {"name": "Масло вершкове", "quantity": 100, "unit": "г"}
  ],
  "steps": [
    {"step_number": 1, "instruction": "Крок 1: Збити яйця зі цукром."},
    {"step_number": 2, "instruction": "Крок 2: Додати борошно та масло."},
    {"step_number": 3, "instruction": "Крок 3: Випікати при 180°C 30-40 хвилин."}
  ],
  "source": {
    "youtube_channel": "Мої Рецепти",
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  },
  "metadata": {
    "video_id": "dQw4w9WgXcQ",
    "extracted_at": "2026-06-21T10:30:00Z",
    "extraction_method": "ollama:qwen3:8b",
    "language": "uk"
  }
}
```

---

## Handling Missing Data

### If ingredient quantity is not specified:
```json
{"name": "Сіль", "quantity": null, "unit": "за смаком"}
```

### If nutrition data unavailable:
```json
"nutrition": {
  "per_100g": null,
  "per_serving": null
}
```

### If image not available:
```json
"image_url": null
```

Use `null` for missing optional fields, not empty strings.

---

## AI Extraction Prompt Template

When calling LLM to extract recipe from YouTube description:

```
You are a professional recipe extraction specialist. Extract a complete, structured recipe from the provided YouTube video description. Follow these rules:

1. Recipe must be in Ukrainian (Українська мова)
2. Output must be valid JSON matching the provided schema
3. Automatically detect category based on recipe content
4. If nutrition data is not provided, use estimated USDA database values
5. All monetary values should be ignored; focus on ingredients and instructions
6. Clean and structure the text: remove filler, reorganize steps logically
7. Always include: title, ingredients (with quantities), steps, category

YouTube Description:
{description_text}

JSON Schema:
{full_schema}

Return ONLY valid JSON, no markdown formatting, no explanations.
```

---

## Versioning & Compatibility

**Current Schema Version:** 1.0
- Date: 2026-06-21
- Compatible workflows: WF-02, WF-03, WF-04, WF-05

Future versions may add:
- `cuisine_type` (Italian, Ukrainian, Asian, etc.)
- `allergens` (array: gluten, dairy, nuts, etc.)
- `cost_estimate` (currency, amount per serving)
- `similar_recipes` (array of recipe IDs)

Backward compatibility maintained: new fields are optional.
