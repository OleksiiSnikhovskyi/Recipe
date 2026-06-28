import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "parse_recipe.py"
SPEC = importlib.util.spec_from_file_location("parse_recipe", MODULE_PATH)
parse_recipe = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(parse_recipe)


def test_build_source_text_includes_all_available_sources():
    result = parse_recipe.build_source_text(
        "Pasta",
        "Ingredient list",
        {"text": "Boil for ten minutes", "language": "en"},
    )

    assert "VIDEO TITLE:\nPasta" in result
    assert "VIDEO DESCRIPTION:\nIngredient list" in result
    assert "VIDEO TRANSCRIPT (language: en):\nBoil for ten minutes" in result


def test_build_source_text_truncates_large_context(monkeypatch):
    monkeypatch.setattr(parse_recipe, "MAX_SOURCE_TEXT_CHARS", 40)

    result = parse_recipe.build_source_text(
        "Long recipe",
        "x" * 100,
        {"text": "y" * 100, "language": "en"},
    )

    assert len(result) > 40
    assert "[TRUNCATED:" in result


def test_transcription_prefers_youtube_captions(monkeypatch):
    expected = {
        "text": "caption text",
        "language": "uk",
        "source": "youtube_captions",
        "warning": "",
    }
    monkeypatch.setattr(parse_recipe, "fetch_youtube_captions", lambda _video_id: expected)
    monkeypatch.setattr(
        parse_recipe,
        "transcribe_youtube_audio",
        lambda _video_id: pytest.fail("Whisper fallback must not run"),
    )

    assert parse_recipe.get_video_transcription("video123") == expected


def test_transcription_falls_back_to_whisper(monkeypatch):
    monkeypatch.setattr(
        parse_recipe,
        "fetch_youtube_captions",
        lambda _video_id: (_ for _ in ()).throw(RuntimeError("no captions")),
    )
    expected = {
        "text": "audio transcript",
        "language": "pl",
        "source": "whisper_audio",
        "warning": "",
    }
    monkeypatch.setattr(parse_recipe, "transcribe_youtube_audio", lambda _video_id: expected)

    assert parse_recipe.get_video_transcription("video123") == expected


def test_transcription_degrades_to_description_only(monkeypatch):
    monkeypatch.setattr(
        parse_recipe,
        "fetch_youtube_captions",
        lambda _video_id: (_ for _ in ()).throw(RuntimeError("no captions")),
    )
    monkeypatch.setattr(
        parse_recipe,
        "transcribe_youtube_audio",
        lambda _video_id: (_ for _ in ()).throw(RuntimeError("download failed")),
    )

    result = parse_recipe.get_video_transcription("video123")

    assert result["source"] == "description_only"
    assert result["text"] == ""
    assert "no captions" in result["warning"]
    assert "download failed" in result["warning"]


def test_extract_recipe_enriches_result_with_transcription(monkeypatch):
    monkeypatch.setattr(
        parse_recipe,
        "extract_recipe_ollama",
        lambda _source_text, metadata: parse_recipe.normalize_recipe(
            {
                "title": "Борщ",
                "category": "Перші страви",
                "ingredients": [{"name": "Буряк", "quantity": "2", "unit": "шт"}],
                "steps": ["Додати буряк"],
            },
            metadata,
            None,
            "ollama:test",
        ),
    )
    monkeypatch.setattr(parse_recipe, "LLM_PROVIDER", "ollama")
    transcription = {
        "text": "Add beetroot",
        "language": "en",
        "source": "youtube_captions",
        "warning": "",
    }

    result = parse_recipe.extract_recipe(
        "Vegetable soup",
        {"title": "Borscht", "video_id": "video123"},
        transcription,
    )

    assert result["description"] == "Vegetable soup"
    assert result["schema_version"] == "1.1"
    assert result["category"] == "Перші страви"
    assert result["ingredients"][0]["quantity"] == 2.0
    assert result["transcription"] == transcription


def test_normalize_recipe_applies_schema_defaults():
    result = parse_recipe.normalize_recipe(
        {
            "title": "Cake",
            "category": "unknown",
            "prep_time_minutes": "10",
            "cook_time_minutes": "20",
            "ingredients": ["Sugar"],
            "steps": [{"instruction": "Mix"}],
            "nutrition": {},
        },
        {"video_id": "abc123", "video_url": "https://youtu.be/abc123"},
        {"source": "description_only", "language": "", "warning": "", "text": ""},
        "ollama:test",
    )

    assert result["schema_version"] == "1.1"
    assert result["category"] == "Інше"
    assert result["total_time_minutes"] == 30.0
    assert result["ingredients"][0] == {"name": "Sugar", "quantity": None, "unit": "", "notes": ""}
    assert result["steps"][0]["step_number"] == 1
    assert result["metadata"]["extraction_method"] == "ollama:test"
