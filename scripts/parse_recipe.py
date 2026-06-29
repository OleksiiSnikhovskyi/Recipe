#!/usr/bin/env python3
"""
parse_recipe.py

AI-powered recipe extraction from YouTube video description.
Accepts unstructured text and returns structured recipe JSON.

Usage:
    python parse_recipe.py --input "description text" --model ollama:qwen3:8b

    or as HTTP endpoint:
    POST /extract
    {"description": "...", "video_id": "...", "youtube_channel": "..."}
"""

import json
import sys
import argparse
import requests
import tempfile
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://100.100.209.24:11434")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
MAX_SOURCE_TEXT_CHARS = int(os.getenv("MAX_SOURCE_TEXT_CHARS", "24000"))
TRANSCRIPTION_ENABLED = os.getenv("TRANSCRIPTION_ENABLED", "true").lower() == "true"
WHISPER_FALLBACK_ENABLED = os.getenv("WHISPER_FALLBACK_ENABLED", "true").lower() == "true"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

_whisper_model = None

VALID_CATEGORIES = {
    "Перші страви",
    "Другі страви",
    "Салати",
    "Закуски",
    "Випічка",
    "Десерти",
    "Напої",
    "Інше",
}

CATEGORY_ALIASES = {
    "main course": "Другі страви",
    "main dish": "Другі страви",
    "entree": "Другі страви",
    "second course": "Другі страви",
    "soup": "Перші страви",
    "first course": "Перші страви",
    "salad": "Салати",
    "appetizer": "Закуски",
    "starter": "Закуски",
    "baking": "Випічка",
    "bakery": "Випічка",
    "dessert": "Десерти",
    "drink": "Напої",
    "beverage": "Напої",
}

UNIT_ALIASES = {
    "гр": "г",
    "грам": "г",
    "грамів": "г",
    "кг": "кг",
    "мл": "мл",
    "л": "л",
    "шт": "шт",
    "штук": "шт",
    "яйця": "шт",
    "яйце": "шт",
    "зуб": "зубчик",
    "зуб.": "зубчик",
    "зубчики": "зубчик",
    "ч л": "ч. л.",
    "ч. л": "ч. л.",
    "ч.л": "ч. л.",
    "ст л": "ст. л.",
    "ст. л": "ст. л.",
    "ст.л": "ст. л.",
}

UNIT_PATTERN = (
    r"кг|гр|г|грам(?:ів)?|мл|л|шт\.?|штук|зуб(?:\.|чики?)?|"
    r"ч\.?\s*л\.?|ст\.?\s*л\.?"
)

RECIPE_SCHEMA_PROMPT = """Return ONLY valid JSON matching Recipe Schema v1.1:
{
  "schema_version": "1.1",
  "title": "Recipe name in Ukrainian",
  "category": "One of: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше",
  "description": "Short summary in Ukrainian",
  "servings": number or null,
  "prep_time_minutes": number or null,
  "cook_time_minutes": number or null,
  "total_time_minutes": number or null,
  "difficulty": "easy|medium|hard|null",
  "ingredients": [
    {"name": "...", "quantity": number or null, "unit": "...", "notes": ""}
  ],
  "steps": [
    {"step_number": number, "instruction": "...", "duration_minutes": number or null, "notes": ""}
  ],
  "nutrition": {
    "per_100g": {"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null},
    "per_serving": {"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null}
  },
  "tags": ["optional Ukrainian tags"],
  "warnings": ["optional uncertainty warnings"]
}"""


def _transcript_text(fetched: Any) -> str:
    """Normalize youtube-transcript-api results across supported versions."""
    snippets = getattr(fetched, "snippets", fetched)
    parts = []
    for snippet in snippets:
        text = getattr(snippet, "text", None)
        if text is None and isinstance(snippet, dict):
            text = snippet.get("text")
        if text:
            parts.append(str(text).strip())
    return " ".join(part for part in parts if part)


def fetch_youtube_captions(video_id: str) -> Dict[str, Any]:
    """Return manual captions first, then auto-generated captions."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    if hasattr(api, "list"):
        transcripts = list(api.list(video_id))
        if not transcripts:
            raise RuntimeError("No YouTube captions available")
        transcripts.sort(key=lambda item: bool(getattr(item, "is_generated", True)))
        selected = transcripts[0]
        text = _transcript_text(selected.fetch())
        language = getattr(selected, "language_code", "")
        source = "youtube_auto_captions" if getattr(selected, "is_generated", False) else "youtube_captions"
    else:
        rows = YouTubeTranscriptApi.get_transcript(video_id)
        text = _transcript_text(rows)
        language = ""
        source = "youtube_captions"

    if not text:
        raise RuntimeError("YouTube captions are empty")
    return {"text": text, "language": language, "source": source, "warning": ""}


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def transcribe_youtube_audio(video_id: str) -> Dict[str, Any]:
    """Download audio only and transcribe it with local multilingual Whisper."""
    from yt_dlp import YoutubeDL

    with tempfile.TemporaryDirectory(prefix="recipe-transcript-") as temp_dir:
        output_template = str(Path(temp_dir) / "audio.%(ext)s")
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "128",
            }],
        }
        with YoutubeDL(options) as downloader:
            downloader.download([f"https://www.youtube.com/watch?v={video_id}"])

        audio_path = Path(temp_dir) / "audio.wav"
        if not audio_path.exists():
            raise RuntimeError("yt-dlp did not create the expected audio file")

        segments, info = _get_whisper_model().transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        if not text:
            raise RuntimeError("Whisper returned an empty transcript")
        return {
            "text": text,
            "language": getattr(info, "language", ""),
            "source": "whisper_audio",
            "warning": "",
        }


def get_video_transcription(video_id: str) -> Dict[str, Any]:
    """Use captions, then local Whisper, and degrade safely to description-only."""
    empty = {"text": "", "language": "", "source": "description_only", "warning": ""}
    if not TRANSCRIPTION_ENABLED or not video_id:
        return empty

    errors = []
    try:
        return fetch_youtube_captions(video_id)
    except Exception as exc:
        errors.append(f"captions: {exc}")

    if WHISPER_FALLBACK_ENABLED:
        try:
            return transcribe_youtube_audio(video_id)
        except Exception as exc:
            errors.append(f"whisper: {exc}")

    empty["warning"] = "; ".join(errors)
    return empty


def build_source_text(title: str, description: str, transcription: Dict[str, Any]) -> str:
    """Build one multilingual source document for recipe extraction."""
    sections = []
    if title:
        sections.append(f"VIDEO TITLE:\n{title}")
    if description:
        sections.append(f"VIDEO DESCRIPTION:\n{description}")
    if transcription.get("text"):
        sections.append(
            "VIDEO TRANSCRIPT "
            f"(language: {transcription.get('language') or 'unknown'}):\n"
            f"{transcription['text']}"
        )
    source_text = "\n\n".join(sections)
    if MAX_SOURCE_TEXT_CHARS > 0 and len(source_text) > MAX_SOURCE_TEXT_CHARS:
        return (
            source_text[:MAX_SOURCE_TEXT_CHARS]
            + "\n\n[TRUNCATED: source text exceeded MAX_SOURCE_TEXT_CHARS]"
        )
    return source_text


def _number_or_none(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _text_or_empty(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_category(value: Any) -> str:
    category = _text_or_empty(value)
    if category in VALID_CATEGORIES:
        return category
    return CATEGORY_ALIASES.get(category.lower(), "Інше")


def _normalize_unit(value: Any) -> str:
    unit = re.sub(r"\s+", " ", _text_or_empty(value).lower()).strip(" .")
    return UNIT_ALIASES.get(unit, _text_or_empty(value))


def _clean_ingredient_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" .,:;-")
    value = re.sub(r"^(рецепт|млинці|начинка|курка)\s*:\s*", "", value, flags=re.IGNORECASE)
    return value.strip(" .,:;-")


def _parse_ingredient_fragment(fragment: str) -> Optional[Dict[str, Any]]:
    fragment = _clean_ingredient_name(fragment)
    if not fragment:
        return None

    lower = fragment.lower()
    if any(skip in lower for skip in ("youtube.com", "tiktok.com", "instagram.com", "більше рецептів")):
        return None

    quantity = None
    unit = ""
    name = fragment
    notes = ""

    number = r"\d+(?:[,.]\d+)?(?:\s*-\s*\d+(?:[,.]\d+)?)?"
    leading = re.match(rf"^(?P<qty>{number})\s*(?P<unit>{UNIT_PATTERN})?\s+(?P<name>.+)$", fragment, re.IGNORECASE)
    trailing = re.match(rf"^(?P<name>.+?)\s+(?P<qty>{number})\s*(?P<unit>{UNIT_PATTERN})?$", fragment, re.IGNORECASE)
    upto = re.match(rf"^(?P<name>.+?)\s+до\s+(?P<qty>{number})\s*(?P<unit>{UNIT_PATTERN})$", fragment, re.IGNORECASE)
    spoon_without_number = re.match(rf"^(?P<unit>ст\.?\s*л\.?|ч\.?\s*л\.?)\s+(?P<name>.+)$", fragment, re.IGNORECASE)

    match = leading or upto or trailing
    if match:
        raw_quantity = match.group("qty").replace(",", ".").replace(" ", "")
        if "-" in raw_quantity:
            notes = f"кількість у джерелі: {match.group('qty')}"
        else:
            quantity = _number_or_none(raw_quantity)
        unit = _normalize_unit(match.groupdict().get("unit") or "")
        name = _clean_ingredient_name(match.group("name"))
        if not unit and name.lower() in {"яйце", "яйця"}:
            unit = "шт"
            name = "яйця"
        if upto:
            notes = f"до {match.group('qty')} {unit}".strip()
    elif spoon_without_number:
        quantity = 1
        unit = _normalize_unit(spoon_without_number.group("unit"))
        name = _clean_ingredient_name(spoon_without_number.group("name"))
    else:
        egg_count = re.match(r"^(?P<qty>\d+(?:[,.]\d+)?)\s+(?P<name>яйц[яе])$", fragment, re.IGNORECASE)
        if egg_count:
            quantity = _number_or_none(egg_count.group("qty"))
            unit = "шт"
            name = "яйця"

    if not name:
        return None

    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "notes": notes,
    }


def extract_explicit_ingredients_from_description(description: str) -> List[Dict[str, Any]]:
    """Parse explicit semicolon-separated ingredient lists from video descriptions."""
    if not description:
        return []

    text = re.sub(r"https?://\S+", " ", description)
    recipe_match = re.search(
        r"(?:рецепт|інгредієнти)\s*:?(?P<body>.+?)(?:\n\s*\n|більше рецептів|підпис|instagram|tiktok|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = recipe_match.group("body") if recipe_match else text
    body = body.replace("\n", " ")
    body = re.sub(r"\.\s+(?=[А-ЯІЇЄҐA-Z])", "; ", body)
    fragments = re.split(r"[;•\n]+", body)

    ingredients = []
    seen = set()
    for fragment in fragments:
        item = _parse_ingredient_fragment(fragment)
        if not item:
            continue
        key = (item["name"].lower(), item["quantity"], item["unit"])
        if key in seen:
            continue
        seen.add(key)
        ingredients.append(item)

    return ingredients


def _ingredient_quality_score(ingredients: List[Dict[str, Any]]) -> int:
    score = 0
    for item in ingredients:
        if item.get("name"):
            score += 1
        if item.get("quantity") is not None:
            score += 2
        if item.get("unit"):
            score += 1
    return score


def _prefer_explicit_ingredients(
    llm_ingredients: List[Dict[str, Any]],
    explicit_ingredients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if len(explicit_ingredients) < 4:
        return llm_ingredients
    if _ingredient_quality_score(explicit_ingredients) >= _ingredient_quality_score(llm_ingredients):
        return explicit_ingredients
    return llm_ingredients


def _normalize_ingredients(value: Any) -> list:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            normalized.append({"name": item, "quantity": None, "unit": "", "notes": ""})
            continue
        if not isinstance(item, dict):
            continue
        normalized.append({
            "name": _text_or_empty(item.get("name")),
            "quantity": _number_or_none(item.get("quantity")),
            "unit": _text_or_empty(item.get("unit")),
            "notes": _text_or_empty(item.get("notes")),
        })
    return [item for item in normalized if item["name"]]


def _normalize_steps(value: Any) -> list:
    if not isinstance(value, list):
        return []
    normalized = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, str):
            instruction = item
            duration = None
            notes = ""
            step_number = index
        elif isinstance(item, dict):
            instruction = item.get("instruction") or item.get("text") or item.get("description")
            duration = item.get("duration_minutes")
            notes = item.get("notes")
            step_number = _number_or_none(item.get("step_number")) or index
        else:
            continue
        instruction = _text_or_empty(instruction)
        if instruction:
            normalized.append({
                "step_number": int(step_number),
                "instruction": instruction,
                "duration_minutes": _number_or_none(duration),
                "notes": _text_or_empty(notes),
            })
    return normalized


def _normalize_nutrition(value: Any) -> Dict[str, Any]:
    value = value if isinstance(value, dict) else {}

    def block(name: str) -> Dict[str, Any]:
        data = value.get(name) if isinstance(value.get(name), dict) else {}
        return {
            "calories": _number_or_none(data.get("calories")),
            "protein": _number_or_none(data.get("protein")),
            "fat": _number_or_none(data.get("fat")),
            "carbohydrates": _number_or_none(data.get("carbohydrates")),
        }

    return {"per_100g": block("per_100g"), "per_serving": block("per_serving")}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_recipe(
    recipe: Dict[str, Any],
    video_metadata: Dict[str, Any],
    transcription: Optional[Dict[str, Any]],
    extraction_method: str,
) -> Dict[str, Any]:
    """Normalize LLM output to Recipe Schema v1.1."""
    transcription = transcription or {
        "text": "",
        "language": "",
        "source": "description_only",
        "warning": "",
    }
    recipe = recipe if isinstance(recipe, dict) else {}
    source = recipe.get("source") if isinstance(recipe.get("source"), dict) else {}
    metadata = recipe.get("metadata") if isinstance(recipe.get("metadata"), dict) else {}
    prep_time = _number_or_none(recipe.get("prep_time_minutes"))
    cook_time = _number_or_none(recipe.get("cook_time_minutes"))
    total_time = _number_or_none(recipe.get("total_time_minutes"))
    if total_time is None and (prep_time is not None or cook_time is not None):
        total_time = (prep_time or 0) + (cook_time or 0)

    normalized = {
        "schema_version": "1.1",
        "title": _text_or_empty(recipe.get("title")) or _text_or_empty(video_metadata.get("title")) or "Рецепт",
        "category": _normalize_category(recipe.get("category")),
        "description": _text_or_empty(recipe.get("description")),
        "servings": _number_or_none(recipe.get("servings")),
        "prep_time_minutes": prep_time,
        "cook_time_minutes": cook_time,
        "total_time_minutes": total_time,
        "difficulty": recipe.get("difficulty") if recipe.get("difficulty") in {"easy", "medium", "hard"} else None,
        "ingredients": _normalize_ingredients(recipe.get("ingredients")),
        "steps": _normalize_steps(recipe.get("steps")),
        "nutrition": _normalize_nutrition(recipe.get("nutrition")),
        "tags": recipe.get("tags") if isinstance(recipe.get("tags"), list) else [],
        "warnings": recipe.get("warnings") if isinstance(recipe.get("warnings"), list) else [],
        "source": {
            "video_id": video_metadata.get("video_id") or source.get("video_id"),
            "video_url": video_metadata.get("video_url") or source.get("video_url"),
            "youtube_channel": video_metadata.get("youtube_channel") or source.get("youtube_channel"),
            "youtube_channel_url": video_metadata.get("youtube_channel_url") or source.get("youtube_channel_url"),
            "thumbnail_url": video_metadata.get("thumbnail_url") or source.get("thumbnail_url"),
            "published_date": video_metadata.get("published_date") or source.get("published_date"),
        },
        "metadata": {
            "recipe_id": metadata.get("recipe_id"),
            "video_id": video_metadata.get("video_id") or metadata.get("video_id"),
            "extracted_at": metadata.get("extracted_at") or _iso_now(),
            "extraction_method": extraction_method,
            "language": "uk",
        },
        "transcription": {
            "source": transcription.get("source", "description_only"),
            "language": transcription.get("language", ""),
            "warning": transcription.get("warning", ""),
            "text": transcription.get("text", ""),
        },
    }
    return normalized


def extract_recipe_ollama(description: str, video_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract recipe using Ollama local model.

    Args:
        description: YouTube video description text
        video_metadata: Dict with video_id, youtube_channel, video_url, thumbnail_url

    Returns:
        Structured recipe JSON
    """

    # System prompt for recipe extraction
    system_prompt = """You are a precise culinary data extraction specialist.
Extract a complete, structured recipe from the provided YouTube source text.
The source may contain a title, description, and transcript in any language.
Translate the final recipe into Ukrainian while preserving quantities and cooking details.

Rules:
1. Recipe must be in Ukrainian (Українська мова)
2. Output must be valid JSON matching the provided schema
3. If the description contains an explicit recipe/ingredient list, treat it as the most authoritative source
4. Split semicolon-separated ingredients into individual ingredient objects
5. Preserve exact quantities and units from the source; do not guess missing quantities
6. Do not invent ingredients, steps, nutrition, times, or servings
7. Use null for unknown numeric values and empty strings for unknown text notes
8. Steps must describe actual cooking actions only; remove greetings, channel promos, and social links
9. Keep the description short: 1-2 Ukrainian sentences about the dish, not the raw YouTube description
10. Nutrition values must be null unless explicitly present in the source

Valid categories: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше

Return ONLY valid JSON, no markdown formatting, no explanations."""

    user_prompt = f"""Extract recipe from this YouTube source text:

{description}

Return this JSON structure:
{{
  "title": "Recipe name in Ukrainian",
  "category": "One of the valid categories",
  "servings": number,
  "prep_time_minutes": number or null,
  "cook_time_minutes": number or null,
  "ingredients": [
    {{"name": "...", "quantity": number, "unit": "...", "notes": "..."}}
  ],
  "steps": [
    {{"step_number": number, "instruction": "...", "duration_minutes": number or null}}
  ],
  "nutrition": {{
    "per_100g": {{"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null}},
    "per_serving": {{"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null}}
  }}
}}

{RECIPE_SCHEMA_PROMPT}"""

    try:
        # Call Ollama API
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False
            },
            timeout=OLLAMA_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        result = response.json()
        content = result["message"]["content"]

        # Parse JSON from response
        try:
            recipe_data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            recipe_data = json.loads(content)

        return normalize_recipe(recipe_data, video_metadata, None, f"ollama:{OLLAMA_MODEL}")

    except Exception as e:
        print(f"Error calling Ollama: {str(e)}", file=sys.stderr)
        raise


def extract_recipe_openai(description: str, video_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract recipe using OpenAI API.

    Args:
        description: YouTube video description text
        video_metadata: Dict with video metadata

    Returns:
        Structured recipe JSON
    """

    try:
        import openai
    except ImportError:
        print("Error: OpenAI library not installed. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = """You are a precise culinary data extraction specialist.
Extract a complete, structured recipe from the provided YouTube source text.
The source may contain a title, description, and transcript in any language.
Translate the final recipe into Ukrainian while preserving quantities and cooking details.
If the description contains an explicit recipe/ingredient list, treat it as the most authoritative source.
Never invent ingredients, steps, nutrition, times, or servings. Use null for unknown numeric values.
Steps must describe actual cooking actions only; remove greetings, channel promos, and social links.
Keep description to 1-2 Ukrainian sentences, not the raw YouTube description.
Return ONLY valid JSON matching the schema provided, with no markdown formatting."""

    user_prompt = f"""Extract recipe from this YouTube source text:

{description}

Return this JSON structure:
{{
  "title": "Recipe name in Ukrainian",
  "category": "One of: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше",
  "servings": number,
  "prep_time_minutes": number or null,
  "cook_time_minutes": number or null,
  "ingredients": [
    {{"name": "...", "quantity": number, "unit": "...", "notes": "..."}}
  ],
  "steps": [
    {{"step_number": number, "instruction": "...", "duration_minutes": number or null}}
  ],
  "nutrition": {{
    "per_100g": {{"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null}},
    "per_serving": {{"calories": number or null, "protein": number or null, "fat": number or null, "carbohydrates": number or null}}
  }}
}}

{RECIPE_SCHEMA_PROMPT}"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )

        content = response.choices[0].message.content
        recipe_data = json.loads(content)

        return normalize_recipe(recipe_data, video_metadata, None, f"openai:{OPENAI_MODEL}")

    except Exception as e:
        print(f"Error calling OpenAI: {str(e)}", file=sys.stderr)
        raise


def extract_recipe(
    description: str,
    video_metadata: Dict[str, Any],
    transcription: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main extraction function. Routes to appropriate LLM provider.
    """

    transcription = transcription or {
        "text": "",
        "language": "",
        "source": "description_only",
        "warning": "",
    }
    source_text = build_source_text(
        video_metadata.get("title", ""),
        description,
        transcription,
    )
    if not source_text:
        raise ValueError("title, description, or video transcription is required")

    if LLM_PROVIDER == "openai":
        recipe = extract_recipe_openai(source_text, video_metadata)
    else:
        recipe = extract_recipe_ollama(source_text, video_metadata)

    normalized = normalize_recipe(
        recipe,
        video_metadata,
        transcription,
        recipe.get("metadata", {}).get("extraction_method", LLM_PROVIDER),
    )
    explicit_ingredients = _normalize_ingredients(
        extract_explicit_ingredients_from_description(description)
    )
    normalized["ingredients"] = _prefer_explicit_ingredients(
        normalized["ingredients"],
        explicit_ingredients,
    )
    if not normalized["description"]:
        normalized["description"] = _text_or_empty(video_metadata.get("title")) or normalized["title"]
    if explicit_ingredients and explicit_ingredients == normalized["ingredients"]:
        normalized["warnings"].append("Інгредієнти взято з явного списку в описі відео.")
    return normalized


# =============================================
# HTTP Flask Server (Optional)
# =============================================

def create_flask_app():
    """Create Flask app for HTTP API."""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        return None

    app = Flask(__name__)

    @app.route("/extract", methods=["POST"])
    def extract_endpoint():
        """HTTP endpoint for recipe extraction."""
        try:
            data = request.json
            description = data.get("description", "")
            video_id = data.get("video_id", "")

            if not description and not video_id:
                return jsonify({"error": "description or video_id is required"}), 400

            # Build video metadata
            video_metadata = {
                "video_id": video_id,
                "title": data.get("title", ""),
                "video_url": data.get("video_url", ""),
                "youtube_channel": data.get("youtube_channel", "Unknown Channel"),
                "youtube_channel_url": data.get("youtube_channel_url", ""),
                "thumbnail_url": data.get("thumbnail_url", ""),
                "published_date": data.get("published_date", "")
            }

            transcription = get_video_transcription(video_id)
            recipe = extract_recipe(description, video_metadata, transcription)
            return jsonify(recipe), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "provider": LLM_PROVIDER,
            "ollama_base_url": OLLAMA_BASE_URL,
            "ollama_model": OLLAMA_MODEL,
            "ollama_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "max_source_text_chars": MAX_SOURCE_TEXT_CHARS,
            "transcription_enabled": TRANSCRIPTION_ENABLED,
            "whisper_fallback_enabled": WHISPER_FALLBACK_ENABLED,
            "whisper_model": WHISPER_MODEL,
        }), 200

    return app


# =============================================
# CLI Interface
# =============================================

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Extract recipe from YouTube description")
    parser.add_argument("--input", "-i", help="Input description text or file path")
    parser.add_argument("--video-id", default="unknown", help="YouTube video ID")
    parser.add_argument("--channel", default="Unknown Channel", help="YouTube channel name")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5000, type=int, help="Server port (default: 5000)")

    args = parser.parse_args()

    if args.server:
        app = create_flask_app()
        if not app:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)
        print(f"Starting Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)
    else:
        if not args.input:
            parser.print_help()
            sys.exit(1)

        # Read input from file or command line
        if os.path.isfile(args.input):
            with open(args.input, 'r', encoding='utf-8') as f:
                description = f.read()
        else:
            description = args.input

        # Extract recipe
        video_metadata = {
            "video_id": args.video_id,
            "title": "",
            "youtube_channel": args.channel,
            "video_url": f"https://www.youtube.com/watch?v={args.video_id}"
        }

        try:
            transcription = get_video_transcription(args.video_id) if args.video_id != "unknown" else None
            recipe = extract_recipe(description, video_metadata, transcription)
            print(json.dumps(recipe, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Extraction failed: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
