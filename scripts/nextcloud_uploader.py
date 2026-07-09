#!/usr/bin/env python3
"""
Upload generated recipe DOCX/PDF files to Nextcloud via WebDAV.

HTTP usage:
    POST /upload
    {"recipe_id": 35}

The service can fetch missing local paths/title/category from PostgreSQL,
upload existing local files, update recipes.nextcloud_*_url, and mark the
video as completed.
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "https://nextcloud.csc-ua.tech").rstrip("/")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "")
NEXTCLOUD_DAV_USER = os.getenv("NEXTCLOUD_DAV_USER") or NEXTCLOUD_USER
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "")
NEXTCLOUD_RECIPE_FOLDER = os.getenv("NEXTCLOUD_RECIPE_FOLDER", "/Documents/Recipe")
NEXTCLOUD_CREATE_SHARES = os.getenv("NEXTCLOUD_CREATE_SHARES", "true").lower() in {"1", "true", "yes"}
NEXTCLOUD_ENSURE_FOLDERS = os.getenv("NEXTCLOUD_ENSURE_FOLDERS", "false").lower() in {"1", "true", "yes"}
NEXTCLOUD_TIMEOUT_SECONDS = int(os.getenv("NEXTCLOUD_TIMEOUT_SECONDS", "120"))
ALLOWED_CATEGORIES = {
    "Перші страви",
    "Другі страви",
    "Десерти",
    "Закуски",
    "Салати",
    "Випічка",
    "Напої",
    "Консервація",
    "Інше",
}

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")


def db_connection():
    import psycopg2
    import psycopg2.extras

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_recipe(recipe_id: Optional[int] = None, video_id: Optional[str] = None) -> Dict[str, Any]:
    if not recipe_id and not video_id:
        return {}

    where = "id = %s" if recipe_id else "video_id = %s"
    value = recipe_id if recipe_id else video_id

    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM recipes WHERE {where} LIMIT 1", (value,))
            row = cursor.fetchone()

    if not row:
        raise LookupError(f"Recipe not found: {value}")
    return dict(row)


def update_recipe_urls(
    recipe_id: Optional[int],
    video_id: Optional[str],
    docx_url: str,
    pdf_url: str,
    docx_share_link: str = "",
    pdf_share_link: str = "",
) -> None:
    if not recipe_id and not video_id:
        return

    where = "id = %s" if recipe_id else "video_id = %s"
    value = recipe_id if recipe_id else video_id

    # Prefer public share links when available; otherwise store WebDAV URLs.
    stored_docx_url = docx_share_link or docx_url
    stored_pdf_url = pdf_share_link or pdf_url

    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE recipes
                SET nextcloud_docx_url = %s,
                    nextcloud_pdf_url = %s,
                    processed = TRUE,
                    updated_at = NOW()
                WHERE {where}
                RETURNING video_id
                """,
                (stored_docx_url, stored_pdf_url, value),
            )
            row = cursor.fetchone()
            final_video_id = video_id or (row and row.get("video_id"))
            if final_video_id:
                cursor.execute(
                    """
                    UPDATE video_log
                    SET processed = TRUE,
                        status = 'completed',
                        error_details = NULL,
                        updated_at = NOW()
                    WHERE video_id = %s
                    """,
                    (final_video_id,),
                )


def normalize_remote_folder(folder: str, category: str = "") -> str:
    parts = [part.strip("/") for part in [folder, category] if part and part.strip("/")]
    return "/" + "/".join(parts)


def safe_filename(value: str, fallback: str = "recipe") -> str:
    value = (value or fallback).strip()
    value = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value)
    value = re.sub(r"[’'`]", "", value)
    value = re.sub(r"\.+", " ", value)
    value = re.sub(r"[^\w\s()\-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = value or fallback
    return value[:70].strip()


def safe_category(value: str) -> str:
    category = safe_filename(value or "", "Інше")
    return category if category in ALLOWED_CATEGORIES else "Інше"


def build_remote_paths(inputs: Dict[str, Any]) -> Dict[str, str]:
    recipe_id = inputs.get("recipe_id")
    title = safe_filename(inputs.get("title"), "recipe")
    base_name = f"{recipe_id} - {title}" if recipe_id else title
    category = safe_category(inputs.get("category"))
    remote_folder = normalize_remote_folder(NEXTCLOUD_RECIPE_FOLDER, category)

    return {
        "category": category,
        "remote_folder": remote_folder,
        "remote_docx_path": f"{remote_folder}/{base_name}.docx",
        "remote_pdf_path": f"{remote_folder}/{base_name}.pdf",
    }


def remote_path_to_webdav_url(remote_path: str) -> str:
    dav_user = quote(NEXTCLOUD_DAV_USER.strip("/"), safe="")
    encoded_path = "/".join(quote(part, safe="") for part in remote_path.strip("/").split("/") if part)
    return f"{NEXTCLOUD_URL}/remote.php/dav/files/{dav_user}/{encoded_path}"


def remote_path_to_files_path(remote_path: str) -> str:
    return "/" + "/".join(part for part in remote_path.strip("/").split("/") if part)


def ensure_remote_folders(session: requests.Session, remote_folder: str) -> None:
    current = ""
    for part in [p for p in remote_folder.strip("/").split("/") if p]:
        current = f"{current}/{part}"
        url = remote_path_to_webdav_url(current)
        response = session.request("MKCOL", url, timeout=NEXTCLOUD_TIMEOUT_SECONDS)
        if response.status_code not in {201, 405}:
            raise RuntimeError(f"Failed to create Nextcloud folder {current}: {response.status_code} {response.text}")


def upload_file(session: requests.Session, local_path: Path, remote_path: str) -> str:
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")
    if not local_path.is_file():
        raise ValueError(f"Path is not a file: {local_path}")

    content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    url = remote_path_to_webdav_url(remote_path)
    with local_path.open("rb") as file_obj:
        response = session.put(
            url,
            data=file_obj,
            headers={"Content-Type": content_type},
            timeout=NEXTCLOUD_TIMEOUT_SECONDS,
        )
    if response.status_code not in {200, 201, 204}:
        raise RuntimeError(f"Failed to upload {local_path.name}: {response.status_code} {response.text}")
    return url


def create_share_link(session: requests.Session, remote_path: str) -> str:
    if not NEXTCLOUD_CREATE_SHARES:
        return ""

    response = session.post(
        f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares",
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
        data={
            "path": remote_path_to_files_path(remote_path),
            "shareType": 3,
            "permissions": 1,
        },
        timeout=NEXTCLOUD_TIMEOUT_SECONDS,
    )
    if response.status_code not in {200, 201}:
        return ""

    try:
        payload = response.json()
    except ValueError:
        return ""

    data = payload.get("ocs", {}).get("data", {})
    if isinstance(data, list):
        data = data[0] if data else {}
    return data.get("url", "") if isinstance(data, dict) else ""


def write_base64_file(encoded: str, filename: str, suffix: str) -> Path:
    output_dir = Path(os.getenv("NEXTCLOUD_UPLOAD_TMP_DIR", "/tmp/recipe-nextcloud-upload"))
    output_dir.mkdir(parents=True, exist_ok=True)
    name = safe_filename(filename, f"recipe{suffix}")
    if not name.lower().endswith(suffix):
        name += suffix
    path = output_dir / name
    path.write_bytes(base64.b64decode(encoded))
    return path


def build_upload_inputs(data: Dict[str, Any]) -> Dict[str, Any]:
    recipe_id = data.get("recipe_id")
    video_id = data.get("video_id")
    recipe: Dict[str, Any] = {}
    needs_recipe_lookup = any(
        not data.get(field)
        for field in ("title", "category", "docx_path", "pdf_path")
    )
    if needs_recipe_lookup and (recipe_id or video_id):
        recipe = fetch_recipe(recipe_id=recipe_id, video_id=video_id)

    title = data.get("title") or recipe.get("title") or "Recipe"
    category = data.get("category") or recipe.get("category") or "Інше"
    docx_path = data.get("docx_path") or recipe.get("docx_path")
    pdf_path = data.get("pdf_path") or recipe.get("pdf_path")

    if data.get("docx_base64"):
        docx_path = str(write_base64_file(data["docx_base64"], title, ".docx"))
    if data.get("pdf_base64"):
        pdf_path = str(write_base64_file(data["pdf_base64"], title, ".pdf"))

    return {
        "recipe_id": recipe_id or recipe.get("id"),
        "video_id": video_id or recipe.get("video_id"),
        "title": title,
        "category": category,
        "docx_path": docx_path,
        "pdf_path": pdf_path,
    }


def upload_to_nextcloud(**kwargs: Any) -> Dict[str, Any]:
    inputs = build_upload_inputs(kwargs)
    docx_path_value = inputs.get("docx_path")
    pdf_path_value = inputs.get("pdf_path")

    if not docx_path_value:
        raise ValueError("docx_path or docx_base64 is required")
    if not pdf_path_value:
        raise ValueError("pdf_path or pdf_base64 is required")
    if not NEXTCLOUD_USER or not NEXTCLOUD_PASSWORD or not NEXTCLOUD_DAV_USER:
        raise ValueError("NEXTCLOUD_USER/NEXTCLOUD_DAV_USER and NEXTCLOUD_PASSWORD are required")

    docx_path = Path(docx_path_value)
    pdf_path = Path(pdf_path_value)

    remote = build_remote_paths(inputs)
    remote_folder = remote["remote_folder"]
    remote_docx_path = remote["remote_docx_path"]
    remote_pdf_path = remote["remote_pdf_path"]

    session = requests.Session()
    session.auth = (NEXTCLOUD_USER, NEXTCLOUD_PASSWORD)

    if NEXTCLOUD_ENSURE_FOLDERS:
        ensure_remote_folders(session, remote_folder)
    docx_url = upload_file(session, docx_path, remote_docx_path)
    pdf_url = upload_file(session, pdf_path, remote_pdf_path)
    docx_share_link = create_share_link(session, remote_docx_path)
    pdf_share_link = create_share_link(session, remote_pdf_path)

    update_recipe_urls(
        recipe_id=inputs.get("recipe_id"),
        video_id=inputs.get("video_id"),
        docx_url=docx_url,
        pdf_url=pdf_url,
        docx_share_link=docx_share_link,
        pdf_share_link=pdf_share_link,
    )

    return {
        "ok": True,
        "recipe_id": inputs.get("recipe_id"),
        "video_id": inputs.get("video_id"),
        "title": inputs["title"],
        "category": remote["category"],
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
        "nextcloud_folder": remote_folder,
        "nextcloud_docx_url": docx_share_link or docx_url,
        "nextcloud_pdf_url": pdf_share_link or pdf_url,
        "docx_webdav_url": docx_url,
        "pdf_webdav_url": pdf_url,
        "docx_share_link": docx_share_link,
        "pdf_share_link": pdf_share_link,
    }


def recipe_file_payload(**kwargs: Any) -> Dict[str, Any]:
    """Return local recipe files as base64 for n8n native Nextcloud upload."""
    inputs = build_upload_inputs(kwargs)
    docx_path_value = inputs.get("docx_path")
    pdf_path_value = inputs.get("pdf_path")

    if not docx_path_value:
        raise ValueError("docx_path or docx_base64 is required")
    if not pdf_path_value:
        raise ValueError("pdf_path or pdf_base64 is required")

    docx_path = Path(docx_path_value)
    pdf_path = Path(pdf_path_value)
    if not docx_path.exists() or not docx_path.is_file():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    remote = build_remote_paths(inputs)
    remote_folder = remote["remote_folder"]
    remote_docx_path = remote["remote_docx_path"]
    remote_pdf_path = remote["remote_pdf_path"]

    return {
        "ok": True,
        "recipe_id": inputs.get("recipe_id"),
        "video_id": inputs.get("video_id"),
        "title": inputs["title"],
        "category": remote["category"],
        "docx_path": str(docx_path),
        "pdf_path": str(pdf_path),
        "nextcloud_root_folder": normalize_remote_folder(NEXTCLOUD_RECIPE_FOLDER),
        "nextcloud_folder": remote_folder,
        "remote_docx_path": remote_docx_path,
        "remote_pdf_path": remote_pdf_path,
        "docx_filename": Path(remote_docx_path).name,
        "pdf_filename": Path(remote_pdf_path).name,
        "docx_base64": base64.b64encode(docx_path.read_bytes()).decode("ascii"),
        "pdf_base64": base64.b64encode(pdf_path.read_bytes()).decode("ascii"),
    }


def create_app():
    try:
        from flask import Flask, jsonify, request
    except ImportError as exc:
        raise RuntimeError("Flask is required for server mode") from exc

    app = Flask(__name__)

    @app.route("/upload", methods=["POST"])
    def upload_endpoint():
        try:
            data = request.get_json(silent=True) or {}
            result = upload_to_nextcloud(**data)
            return jsonify(result), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/payload", methods=["POST"])
    def payload_endpoint():
        try:
            data = request.get_json(silent=True) or {}
            result = recipe_file_payload(**data)
            return jsonify(result), 200
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "nextcloud_url": NEXTCLOUD_URL,
            "nextcloud_folder": NEXTCLOUD_RECIPE_FOLDER,
            "has_credentials": bool(NEXTCLOUD_USER and NEXTCLOUD_PASSWORD and NEXTCLOUD_DAV_USER),
            "db_host": DB_HOST,
            "db_name": DB_NAME,
        }), 200

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload recipe files to Nextcloud")
    parser.add_argument("--recipe-id", type=int, help="Recipe database ID")
    parser.add_argument("--video-id", help="YouTube video ID")
    parser.add_argument("--docx", dest="docx_path", help="Path to DOCX file")
    parser.add_argument("--pdf", dest="pdf_path", help="Path to PDF file")
    parser.add_argument("--category", help="Recipe category")
    parser.add_argument("--recipe-name", dest="title", help="Recipe title")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=int(os.getenv("NEXTCLOUD_UPLOADER_PORT", "5013")), type=int)
    args = parser.parse_args()

    if args.server:
        app = create_app()
        print(f"Starting Nextcloud uploader Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)
        return

    try:
        result = upload_to_nextcloud(
            recipe_id=args.recipe_id,
            video_id=args.video_id,
            docx_path=args.docx_path,
            pdf_path=args.pdf_path,
            category=args.category,
            title=args.title,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
