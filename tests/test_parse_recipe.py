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
                "description": "Короткий опис борщу",
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

    assert result["description"] == "Короткий опис борщу"
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


def test_category_aliases_are_normalized():
    assert parse_recipe._normalize_category("Main Course") == "Другі страви"
    assert parse_recipe._normalize_category("dessert") == "Десерти"


def test_extract_explicit_ingredients_from_description():
    description = (
        "Рецепт :Млинці : 4 яйця ; 500 мл молока ; 30 гр олії ; "
        "0,5 ч л солі ; ст л цукру ; 0,5 ст л крохмаль ; 180 гр борошно . "
        "Курка до 2 кг ; цибуля ; печериці 200 гр ; майонез 1-2 ст л ; "
        "часник 4 зуб ; морква по корейські 200 гр ; яйце ; 100 мл молоко ."
    )

    result = parse_recipe.extract_explicit_ingredients_from_description(description)

    by_name = {item["name"].lower(): item for item in result}
    assert by_name["яйця"]["quantity"] == 4
    assert by_name["яйця"]["unit"] == "шт"
    assert by_name["молока"]["quantity"] == 500
    assert by_name["молока"]["unit"] == "мл"
    assert by_name["олії"]["quantity"] == 30
    assert by_name["олії"]["unit"] == "г"
    assert by_name["солі"]["quantity"] == 0.5
    assert by_name["солі"]["unit"] == "ч. л."
    assert by_name["цукру"]["quantity"] == 1
    assert by_name["цукру"]["unit"] == "ст. л."
    assert by_name["борошно"]["quantity"] == 180
    assert by_name["борошно"]["unit"] == "г"
    assert by_name["курка"]["unit"] == "кг"
    assert "до 2" in by_name["курка"]["notes"]
    assert by_name["печериці"]["quantity"] == 200
    assert by_name["морква по корейські"]["quantity"] == 200


def test_extract_recipe_prefers_explicit_description_ingredients(monkeypatch):
    monkeypatch.setattr(
        parse_recipe,
        "extract_recipe_ollama",
        lambda _source_text, metadata: parse_recipe.normalize_recipe(
            {
                "title": "Курка з млинцями",
                "category": "Main Course",
                "description": "Фарширована курка з млинцями.",
                "ingredients": [{"name": "лимонний сік", "quantity": 1, "unit": "мл"}],
                "steps": ["Підготувати курку"],
            },
            metadata,
            None,
            "ollama:test",
        ),
    )
    monkeypatch.setattr(parse_recipe, "LLM_PROVIDER", "ollama")

    result = parse_recipe.extract_recipe(
        "Рецепт: Млинці: 4 яйця; 500 мл молока; Курка до 2 кг; печериці 200 гр.",
        {"title": "Курка з млинцями", "video_id": "2XlxQoXUJGE"},
        {"source": "description_only", "language": "", "warning": "", "text": ""},
    )

    names = {item["name"].lower() for item in result["ingredients"]}
    assert "лимонний сік" not in names
    assert {"яйця", "молока", "курка", "печериці"}.issubset(names)
    assert result["category"] == "Другі страви"
    assert result["description"] == "Фарширована курка з млинцями."
