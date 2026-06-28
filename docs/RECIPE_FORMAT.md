# Recipe JSON Format Specification

## Overview

This document defines the stable recipe contract used by WF-02 through WF-06.
The canonical runtime format is **Recipe Schema v1.1**.

All final recipe content must be in Ukrainian, regardless of the original YouTube
title, description, or transcript language.

## Schema v1.1

```json
{
  "schema_version": "1.1",
  "title": "Борщ український",
  "category": "Перші страви",
  "description": "Короткий опис рецепта українською.",
  "servings": 6,
  "prep_time_minutes": 20,
  "cook_time_minutes": 90,
  "total_time_minutes": 110,
  "difficulty": "medium",
  "ingredients": [
    {
      "name": "Буряк",
      "quantity": 2,
      "unit": "шт",
      "notes": "середнього розміру"
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "instruction": "Підготуйте овочі.",
      "duration_minutes": 15,
      "notes": ""
    }
  ],
  "nutrition": {
    "per_100g": {
      "calories": 45,
      "protein": 1.5,
      "fat": 2,
      "carbohydrates": 6
    },
    "per_serving": {
      "calories": 180,
      "protein": 6,
      "fat": 8,
      "carbohydrates": 24
    }
  },
  "tags": ["домашнє", "обід"],
  "warnings": [],
  "source": {
    "video_id": "abc123",
    "video_url": "https://www.youtube.com/watch?v=abc123",
    "youtube_channel": "Канал",
    "youtube_channel_url": "",
    "thumbnail_url": "https://i.ytimg.com/...",
    "published_date": "2026-06-20T17:28:32Z"
  },
  "metadata": {
    "recipe_id": null,
    "video_id": "abc123",
    "extracted_at": "2026-06-28T10:00:00Z",
    "extraction_method": "ollama:qwen3:8b",
    "language": "uk"
  },
  "transcription": {
    "source": "youtube_captions",
    "language": "uk",
    "warning": "",
    "text": "Повний текст транскрипції для діагностики."
  }
}
```

## Required Fields

These fields must exist after `parse_recipe.py` normalization:

- `schema_version`: always `"1.1"`.
- `title`: non-empty string, Ukrainian when known.
- `category`: one of the valid categories below.
- `description`: string, may be empty.
- `servings`: number or `null`.
- `prep_time_minutes`, `cook_time_minutes`, `total_time_minutes`: number or `null`.
- `difficulty`: `"easy"`, `"medium"`, `"hard"`, or `null`.
- `ingredients`: array of ingredient objects.
- `steps`: array of step objects.
- `nutrition`: object with `per_100g` and `per_serving`.
- `tags`: array of strings.
- `warnings`: array of strings.
- `source`: YouTube metadata object.
- `metadata`: extraction metadata object.
- `transcription`: transcription diagnostics object.

## Categories

Use exact spelling:

- `Перші страви`
- `Другі страви`
- `Салати`
- `Закуски`
- `Випічка`
- `Десерти`
- `Напої`
- `Інше`

Unknown or invalid categories are normalized to `Інше`.

## Ingredients

Each ingredient:

```json
{
  "name": "Борошно",
  "quantity": 300,
  "unit": "г",
  "notes": "просіяти"
}
```

Rules:

- `name` is required and should be Ukrainian.
- `quantity` is a number or `null`.
- `unit` is a string. Examples: `г`, `кг`, `мл`, `л`, `шт`, `ч. л.`, `ст. л.`, `за смаком`.
- `notes` is a string, empty if not needed.

## Steps

Each step:

```json
{
  "step_number": 1,
  "instruction": "Змішайте сухі інгредієнти.",
  "duration_minutes": 5,
  "notes": ""
}
```

Rules:

- `step_number` starts at `1` and is sequential.
- `instruction` is required and should be Ukrainian.
- `duration_minutes` is a number or `null`.
- `notes` is a string, empty if not needed.

## Nutrition

```json
{
  "per_100g": {
    "calories": 250,
    "protein": 8,
    "fat": 10,
    "carbohydrates": 30
  },
  "per_serving": {
    "calories": 420,
    "protein": 15,
    "fat": 18,
    "carbohydrates": 50
  }
}
```

Each value is a number or `null`. If nutrition cannot be estimated, keep the
object shape and use `null` values.

## Source

`source` stores YouTube origin data:

- `video_id`
- `video_url`
- `youtube_channel`
- `youtube_channel_url`
- `thumbnail_url`
- `published_date`

WF-02 writes these fields into PostgreSQL columns as well as into `recipe_text`.

## Transcription

`transcription.source` values:

- `youtube_captions`: manual YouTube subtitles.
- `youtube_auto_captions`: automatic YouTube subtitles.
- `whisper_audio`: local Whisper fallback from downloaded audio.
- `description_only`: no transcript available; title/description were used.

`transcription.text` may be long. It is stored for diagnostics and future
reprocessing, but DOCX output normally shows only source/language/warnings.

## PostgreSQL Mapping

WF-02 stores:

- Full normalized recipe JSON into `recipes.recipe_text`.
- `ingredients` into `recipes.ingredients`.
- `steps` into `recipes.steps`.
- `nutrition` into `recipes.nutrition`.
- Transcript text/source/language/warning into transcript columns.
- YouTube metadata into `video_id`, `youtube_url`, `youtube_channel`, `thumbnail_url`.

WF-03 and later should prefer `recipes.recipe_text`, but may safely fall back to
the structured columns.

## Compatibility

Schema v1.1 is compatible with:

- WF-02 Extract Recipe
- WF-03 Generate DOCX
- WF-04 Convert PDF
- WF-05 Upload Nextcloud
- WF-06 Telegram Notify

Future optional fields may be added, but existing fields should not be renamed.
