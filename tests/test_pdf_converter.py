import base64
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pdf_converter.py"
SPEC = importlib.util.spec_from_file_location("pdf_converter", MODULE_PATH)
pdf_converter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pdf_converter)


class FakeCompletedProcess:
    returncode = 0
    stdout = "converted"
    stderr = ""


def test_convert_docx_to_pdf_invokes_libreoffice(monkeypatch, tmp_path):
    docx_path = tmp_path / "recipe.docx"
    docx_path.write_bytes(b"docx")

    def fake_run(command, capture_output, text, timeout, check):
        assert "--headless" in command
        assert "--convert-to" in command
        assert "pdf" in command
        assert str(docx_path.resolve()) in command
        (tmp_path / "recipe.pdf").write_bytes(b"%PDF")
        return FakeCompletedProcess()

    monkeypatch.setattr(pdf_converter.subprocess, "run", fake_run)

    result = pdf_converter.convert_docx_to_pdf(str(docx_path))

    assert result == str((tmp_path / "recipe.pdf").resolve())
    assert Path(result).read_bytes() == b"%PDF"


def test_convert_docx_to_pdf_requires_docx_suffix(tmp_path):
    txt_path = tmp_path / "recipe.txt"
    txt_path.write_text("not docx", encoding="utf-8")

    with pytest.raises(ValueError):
        pdf_converter.convert_docx_to_pdf(str(txt_path))


def test_write_docx_base64_sanitizes_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_converter, "PDF_OUTPUT_DIR", tmp_path)
    encoded = base64.b64encode(b"docx-content").decode("ascii")

    result = pdf_converter.write_docx_base64(encoded, "../bad-name")

    assert result == tmp_path / "bad-name.docx"
    assert result.read_bytes() == b"docx-content"
