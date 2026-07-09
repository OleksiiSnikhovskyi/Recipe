#!/usr/bin/env python3
"""Convert recipe DOCX files to PDF using LibreOffice Headless."""

import argparse
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "/usr/bin/soffice")
PDF_CONVERSION_TIMEOUT = int(os.getenv("PDF_CONVERSION_TIMEOUT", "120"))
PDF_OUTPUT_DIR = Path(os.getenv("PDF_OUTPUT_DIR", "output/pdf"))
PDF_PUBLIC_BASE_URL = os.getenv("PDF_PUBLIC_BASE_URL", "")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")


def db_connection():
    import psycopg2

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def update_pdf_path(recipe_id: Optional[int], video_id: Optional[str], pdf_path: str) -> None:
    if not recipe_id and not video_id:
        return
    where = "id = %s" if recipe_id else "video_id = %s"
    value = recipe_id if recipe_id else video_id
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE recipes SET pdf_path = %s, updated_at = NOW() WHERE {where}",
                (pdf_path, value),
            )


def resolve_docx_path(recipe_id: Optional[int], video_id: Optional[str]) -> Optional[str]:
    """Resolve the latest DOCX path from the database when only an ID is provided."""
    if not recipe_id and not video_id:
        return None
    where = "id = %s" if recipe_id else "video_id = %s"
    value = recipe_id if recipe_id else video_id
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT docx_path FROM recipes WHERE {where} LIMIT 1",
                (value,),
            )
            row = cursor.fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])


def expected_pdf_path(docx_path: Path, pdf_path: Optional[str] = None) -> Path:
    if pdf_path:
        return Path(pdf_path)
    return docx_path.with_suffix(".pdf")


def convert_docx_to_pdf(docx_path: str, pdf_path: Optional[str] = None) -> str:
    """Convert DOCX file to PDF using LibreOffice Headless."""
    input_path = Path(docx_path).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input DOCX file not found: {input_path}")
    if input_path.suffix.lower() != ".docx":
        raise ValueError(f"Input file must be .docx: {input_path}")

    output_path = expected_pdf_path(input_path, pdf_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="recipe-libreoffice-") as profile_dir:
        command = [
            LIBREOFFICE_PATH,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{Path(profile_dir).resolve()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_path.parent),
            str(input_path),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PDF_CONVERSION_TIMEOUT,
            check=False,
        )

    generated_path = output_path.parent / f"{input_path.stem}.pdf"
    if generated_path.exists() and generated_path != output_path:
        generated_path.replace(output_path)

    if result.returncode != 0:
        raise RuntimeError(
            "LibreOffice conversion failed: "
            f"exit={result.returncode}; stdout={result.stdout}; stderr={result.stderr}"
        )
    if not output_path.exists():
        raise RuntimeError(
            "LibreOffice did not create expected PDF: "
            f"{output_path}; stdout={result.stdout}; stderr={result.stderr}"
        )
    return str(output_path)


def write_docx_base64(docx_base64: str, filename: str) -> Path:
    PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename or "recipe.docx").name
    if not safe_name.lower().endswith(".docx"):
        safe_name += ".docx"
    docx_path = PDF_OUTPUT_DIR / safe_name
    docx_path.write_bytes(base64.b64decode(docx_base64))
    return docx_path


def public_url_for(path: str) -> str:
    if not PDF_PUBLIC_BASE_URL:
        return ""
    return PDF_PUBLIC_BASE_URL.rstrip("/") + "/" + Path(path).name


def create_flask_app():
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        return None

    app = Flask(__name__)

    @app.route("/convert", methods=["POST"])
    def convert_endpoint():
        try:
            data: Dict[str, Any] = request.get_json(silent=True) or {}
            docx_path = data.get("docx_path")
            recipe_id = data.get("recipe_id")
            video_id = data.get("video_id") or data.get("videoId")
            if not docx_path and data.get("docx_base64"):
                docx_path = str(write_docx_base64(data["docx_base64"], data.get("filename", "recipe.docx")))
            if not docx_path:
                docx_path = resolve_docx_path(recipe_id, video_id)
            if not docx_path:
                return jsonify({
                    "ok": False,
                    "error": "docx_path, docx_base64, or an existing recipe_id/video_id with docx_path is required",
                }), 400

            pdf_path = convert_docx_to_pdf(docx_path, data.get("pdf_path"))
            update_pdf_path(recipe_id, video_id, pdf_path)

            pdf_bytes = Path(pdf_path).read_bytes()
            return jsonify({
                "ok": True,
                "recipe_id": recipe_id,
                "video_id": video_id,
                "filename": Path(pdf_path).name,
                "docx_path": docx_path,
                "pdf_path": pdf_path,
                "pdf_url": public_url_for(pdf_path),
                "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            }), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "libreoffice_path": LIBREOFFICE_PATH,
            "pdf_output_dir": str(PDF_OUTPUT_DIR),
            "pdf_conversion_timeout": PDF_CONVERSION_TIMEOUT,
        }), 200

    return app


def main():
    parser = argparse.ArgumentParser(description="Convert DOCX to PDF")
    parser.add_argument("--input", "-i", help="Input DOCX file path")
    parser.add_argument("--output", "-o", help="Output PDF file path")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5012, type=int, help="Server port (default: 5012)")
    args = parser.parse_args()

    if args.server:
        app = create_flask_app()
        if not app:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)
        print(f"Starting PDF Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    try:
        pdf_path = convert_docx_to_pdf(args.input, args.output)
        print(f"Converted: {pdf_path}")
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
