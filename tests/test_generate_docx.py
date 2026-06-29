import importlib.util
from pathlib import Path

from docx import Document


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_docx.py"
SPEC = importlib.util.spec_from_file_location("generate_docx", MODULE_PATH)
generate_docx = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generate_docx)


def sample_recipe():
    return {
        "title": "Борщ український",
        "category": "Перші страви",
        "description": "Насичений домашній борщ.",
        "servings": 6,
        "prep_time_minutes": 20,
        "cook_time_minutes": 90,
        "ingredients": [
            {"name": "Буряк", "quantity": 2, "unit": "шт", "notes": "середній"},
            {"name": "Капуста", "quantity": 300, "unit": "г"},
        ],
        "steps": [
            {"step_number": 1, "instruction": "Підготуйте овочі.", "duration_minutes": 15},
            {"step_number": 2, "instruction": "Зваріть бульйон."},
        ],
        "nutrition": {
            "per_serving": {"calories": 180, "protein": 6, "fat": 8, "carbohydrates": 20}
        },
        "source": {
            "video_id": "abc123",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "youtube_channel": "Кухня",
        },
        "transcription": {
            "source": "youtube_auto_captions",
            "language": "uk",
            "warning": "",
        },
    }


def test_generate_docx_returns_readable_word_document():
    docx_bytes = generate_docx.generate_docx(sample_recipe())

    assert docx_bytes.startswith(b"PK")

    output = Path("tmp_test_recipe.docx")
    try:
        output.write_bytes(docx_bytes)
        document = Document(output)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        assert "Борщ український" in text
        assert "Інгредієнти" in text
        assert "Приготування" in text
        assert "Транскрипція" not in text
        assert "youtube_auto_captions" not in text
    finally:
        if output.exists():
            output.unlink()


def test_recipe_from_db_row_merges_structured_columns():
    row = {
        "id": 7,
        "video_id": "abc123",
        "title": "Борщ",
        "category": "Перші страви",
        "description": "Опис",
        "recipe_text": "{}",
        "ingredients": '[{"name":"Вода","quantity":1,"unit":"л"}]',
        "steps": '[{"step_number":1,"instruction":"Закипʼятити воду"}]',
        "nutrition": '{"per_serving":{"calories":50}}',
        "youtube_url": "https://youtu.be/abc123",
        "youtube_channel": "Канал",
        "thumbnail_url": "",
        "transcript_source": "youtube_captions",
        "transcript_language": "uk",
        "transcription_warning": "",
    }

    recipe = generate_docx.recipe_from_db_row(row)

    assert recipe["id"] == 7
    assert recipe["ingredients"][0]["name"] == "Вода"
    assert recipe["steps"][0]["instruction"] == "Закипʼятити воду"
    assert recipe["source"]["video_id"] == "abc123"
