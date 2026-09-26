#!/usr/bin/env python3
"""
Import recipes from the deduplicated OneDrive inventory into recipe_db.

Pipeline per file (sequential, idempotent, resumable):
    extract text (docx2txt / pdfplumber)
    -> parse_recipe.extract_recipe() via Ollama on Miledy
    -> upsert into recipes table (synthetic video_id derived from filename)
    -> generate_docx.write_docx()
    -> pdf_converter.convert_docx_to_pdf()
    -> nextcloud_uploader.upload_to_nextcloud() (only if credentials are configured)

Re-running is safe: a file whose DB row already has docx_path + pdf_path is
skipped unless --force is passed; Nextcloud upload is retried independently
via --nextcloud-only once credentials are available.

Usage:
    python scripts/import_onedrive_recipes.py --inventory /path/inventory.json --log /path/progress.jsonl
    python scripts/import_onedrive_recipes.py --inventory ... --log ... --nextcloud-only
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import docx2txt
import pdfplumber
import psycopg2
import psycopg2.extras
import requests

import parse_recipe
import generate_docx as docx_module
import pdf_converter
import nextcloud_uploader as nc_module

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")

MIN_TEXT_CHARS = 40
MIN_IMAGE_BYTES = 15_000  # filter out small decorative icons/dividers
IMAGE_OUTPUT_DIR = Path(os.getenv("IMAGE_OUTPUT_DIR", "output/images"))


def db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def synthetic_video_id(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"onedrive:{digest}"


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return (docx2txt.process(str(path)) or "").strip()
    if suffix == ".pdf":
        parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    raise ValueError(f"Unsupported extension: {suffix}")


def _extract_images(docx_path: Path, video_id: str) -> list:
    img_dir = IMAGE_OUTPUT_DIR / video_id.replace(":", "_")
    img_dir.mkdir(parents=True, exist_ok=True)
    try:
        docx2txt.process(str(docx_path), str(img_dir))
    except Exception:
        return []
    return [p for p in img_dir.iterdir() if p.is_file()]


def extract_best_image(docx_path: Path, video_id: str) -> str:
    """Pull embedded images out of a source .docx and return the path to the
    largest one (a reasonable proxy for "the actual dish photo" vs small
    decorative icons/dividers), or "" if none qualify."""
    candidates = [p for p in _extract_images(docx_path, video_id) if p.stat().st_size >= MIN_IMAGE_BYTES]
    if not candidates:
        return ""
    return str(max(candidates, key=lambda p: p.stat().st_size))


YOUTUBE_URL_PATTERN = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)[A-Za-z0-9_-]{11}")


def find_qr_youtube_link(docx_path: Path, video_id: str) -> str:
    """Some recipe cards embed a QR code image linking back to the source
    YouTube video. Decode any embedded images and return the first link that
    is directly a YouTube URL (shortlink/redirect services are not chased)."""
    try:
        import cv2
    except Exception:
        return ""
    detector = cv2.QRCodeDetector()
    for image_path in _extract_images(docx_path, video_id):
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                continue
            data, _, _ = detector.detectAndDecode(image)
        except Exception:
            continue
        if data and YOUTUBE_URL_PATTERN.search(data):
            return data
    return ""


def split_into_recipe_sections(text: str) -> list:
    """OneDrive documents are sometimes compilations bundling several distinct
    recipes in one file (e.g. "3 quick snacks in a waffle maker"). Ask the
    model to split those into one section per recipe; on any failure, fall
    back to treating the whole document as a single recipe so we never lose
    a file just because the split call misbehaved."""
    prompt = (
        "The document below may contain ONE recipe or MULTIPLE distinct separate "
        "recipes (a compilation). If it bundles multiple distinct recipes, split it "
        "into separate sections, each containing the full original text for exactly "
        "one recipe (its own title, ingredients and steps). If it contains only one "
        "recipe, or repeats/varies a single dish, return it as a single section "
        "unchanged. Do not summarize or translate; copy the original text verbatim "
        "into each section.\n\n"
        "Return ONLY valid JSON: {\"sections\": [\"...\", \"...\"]}\n\n"
        "Document:\n" + text
    )
    try:
        response = requests.post(
            f"{parse_recipe.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": parse_recipe.OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0.0, "num_ctx": parse_recipe.OLLAMA_NUM_CTX},
            },
            timeout=parse_recipe.OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        data = parse_recipe._parse_json_response(content)
        sections = [s.strip() for s in data.get("sections", []) if isinstance(s, str) and s.strip()]
        if sections:
            return sections
    except Exception:
        pass
    return [text]


def looks_like_garbled_pdf_text(text: str) -> bool:
    """Detect PDFs whose embedded font lacks a ToUnicode map: pdfplumber then
    returns literal '(cid:NNN)' glyph codes instead of real characters."""
    return len(re.findall(r"\(cid:\d+\)", text[:2000])) > 5


def any_done_rows_for_base(base_video_id: str) -> bool:
    """A source file may have produced one row (video_id) or several
    (video_id-1, video_id-2, ...) if it bundled multiple recipes. Treat the
    file as already processed if any of those rows completed DOCX+PDF."""
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM recipes
                WHERE (video_id = %s OR video_id LIKE %s)
                  AND docx_path IS NOT NULL AND pdf_path IS NOT NULL
                LIMIT 1
                """,
                (base_video_id, base_video_id + "-%"),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def upsert_recipe(video_id: str, source_path: str, source_text: str, recipe: Dict[str, Any]) -> int:
    conn = db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO recipes (
                        video_id, title, description, category, recipe_text,
                        ingredients, steps, nutrition, youtube_url, youtube_channel,
                        transcript_source, updated_at
                    ) VALUES (
                        %(video_id)s, %(title)s, %(description)s, %(category)s, %(source_text)s,
                        %(ingredients)s, %(steps)s, %(nutrition)s, %(source_path)s, %(youtube_channel)s,
                        'onedrive_document', NOW()
                    )
                    ON CONFLICT (video_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        recipe_text = EXCLUDED.recipe_text,
                        ingredients = EXCLUDED.ingredients,
                        steps = EXCLUDED.steps,
                        nutrition = EXCLUDED.nutrition,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    {
                        "video_id": video_id,
                        "title": recipe["title"][:255],
                        "description": recipe.get("description") or "",
                        "category": recipe.get("category") or "Інше",
                        "source_path": source_path,
                        "source_text": source_text,
                        "ingredients": json.dumps(recipe.get("ingredients") or [], ensure_ascii=False),
                        "steps": json.dumps(recipe.get("steps") or [], ensure_ascii=False),
                        "nutrition": json.dumps(recipe.get("nutrition") or {}, ensure_ascii=False),
                        "youtube_channel": "Імпорт з OneDrive",
                    },
                )
                recipe_id = cur.fetchone()["id"]
    finally:
        conn.close()
    return recipe_id


def process_section(video_id: str, filename: str, source_path: str, section_text: str, started: float,
                     thumbnail_path: str = "") -> Dict[str, Any]:
    video_metadata = {
        "video_id": video_id,
        "title": "",
        "video_url": "",
        "youtube_channel": "Імпорт з OneDrive",
        "youtube_channel_url": "",
        "thumbnail_url": thumbnail_path,
        "published_date": "",
    }

    try:
        recipe = parse_recipe.extract_recipe(section_text, video_metadata, transcription=None)
    except Exception as exc:
        return {"video_id": video_id, "filename": filename, "status": "error_extraction_llm", "error": str(exc)}

    if not recipe.get("ingredients") and not recipe.get("steps"):
        return {"video_id": video_id, "filename": filename, "status": "skipped_not_a_recipe",
                "title": recipe.get("title")}

    try:
        recipe_id = upsert_recipe(video_id, source_path, section_text, recipe)
    except Exception as exc:
        return {"video_id": video_id, "filename": filename, "status": "error_db", "error": str(exc)}

    recipe["id"] = recipe_id
    try:
        docx_result = docx_module.write_docx(recipe)
        docx_module.update_docx_path(recipe_id, None, docx_result["docx_path"])
    except Exception as exc:
        return {"video_id": video_id, "filename": filename, "recipe_id": recipe_id,
                "status": "error_docx", "error": str(exc)}

    try:
        pdf_path = pdf_converter.convert_docx_to_pdf(docx_result["docx_path"])
        pdf_converter.update_pdf_path(recipe_id, None, pdf_path)
    except Exception as exc:
        return {"video_id": video_id, "filename": filename, "recipe_id": recipe_id,
                "status": "error_pdf", "error": str(exc), "docx_path": docx_result["docx_path"]}

    duration = round(time.time() - started, 1)
    return {
        "video_id": video_id, "filename": filename, "recipe_id": recipe_id,
        "title": recipe["title"], "category": recipe.get("category"),
        "status": "ok", "duration_seconds": duration,
        "docx_path": docx_result["docx_path"], "pdf_path": pdf_path,
    }


def process_one(item: Dict[str, Any], force: bool) -> list:
    """Returns a list of per-recipe results: usually one, but a source file
    that bundles multiple distinct recipes yields one result per recipe."""
    path = Path(item["path"])
    base_video_id = synthetic_video_id(item["key"])

    try:
        already_done = any_done_rows_for_base(base_video_id)
    except Exception as exc:
        return [{"video_id": base_video_id, "filename": item["filename"], "status": "error_db_check", "error": str(exc)}]
    if already_done and not force:
        return [{"video_id": base_video_id, "filename": item["filename"], "status": "skipped_already_done"}]

    try:
        text = extract_text(path)
    except Exception as exc:
        return [{"video_id": base_video_id, "filename": item["filename"], "status": "error_extract", "error": str(exc)}]

    if len(text) < MIN_TEXT_CHARS:
        return [{"video_id": base_video_id, "filename": item["filename"], "status": "skipped_no_text"}]

    if looks_like_garbled_pdf_text(text):
        return [{"video_id": base_video_id, "filename": item["filename"], "status": "skipped_garbled_pdf_font"}]

    try:
        sections = split_into_recipe_sections(text)
    except Exception:
        sections = [text]
    if not sections:
        sections = [text]

    # Only attach a photo when the file holds exactly one recipe: a
    # compilation file's images can't be reliably matched to the right
    # section, and a wrong photo is worse than none.
    thumbnail_path = ""
    if len(sections) == 1 and path.suffix.lower() == ".docx":
        try:
            thumbnail_path = extract_best_image(path, base_video_id)
        except Exception:
            thumbnail_path = ""

    results = []
    for index, section_text in enumerate(sections, start=1):
        section_video_id = base_video_id if len(sections) == 1 else f"{base_video_id}-{index}"
        started = time.time()
        results.append(process_section(section_video_id, item["filename"], item["path"], section_text, started,
                                        thumbnail_path=thumbnail_path))
    return results


def nextcloud_ready() -> bool:
    return bool(
        os.getenv("NEXTCLOUD_USER") and os.getenv("NEXTCLOUD_PASSWORD")
        and os.getenv("NEXTCLOUD_DAV_USER")
    )


def upload_pending_to_nextcloud(log_path: Path) -> None:
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, title, category, docx_path, pdf_path
                FROM recipes
                WHERE docx_path IS NOT NULL AND pdf_path IS NOT NULL
                  AND nextcloud_pdf_url IS NULL
                  AND video_id LIKE 'onedrive:%%'
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"Pending Nextcloud uploads: {len(rows)}")
    with log_path.open("a", encoding="utf-8") as log_file:
        for row in rows:
            try:
                result = nc_module.upload_to_nextcloud(
                    recipe_id=row["id"], title=row["title"], category=row["category"],
                    docx_path=row["docx_path"], pdf_path=row["pdf_path"],
                )
                entry = {"video_id": row["video_id"], "status": "uploaded", "recipe_id": row["id"]}
                print(f"  [{row['id']}] uploaded: {row['title']}")
            except Exception as exc:
                entry = {"video_id": row["video_id"], "status": "error_upload", "error": str(exc), "recipe_id": row["id"]}
                print(f"  [{row['id']}] FAILED: {exc}")
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            log_file.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--nextcloud-only", action="store_true")
    args = parser.parse_args()

    log_path = Path(args.log)

    if args.nextcloud_only:
        if not nextcloud_ready():
            print("NEXTCLOUD_USER/DAV_USER/PASSWORD not configured — nothing to do.")
            sys.exit(1)
        upload_pending_to_nextcloud(log_path)
        return

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    if args.limit:
        inventory = inventory[: args.limit]

    counts: Dict[str, int] = {}
    with log_path.open("a", encoding="utf-8") as log_file:
        for index, item in enumerate(inventory, start=1):
            results = process_one(item, args.force)
            for result in results:
                counts[result["status"]] = counts.get(result["status"], 0) + 1
                log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                log_file.flush()
            statuses = ",".join(r["status"] for r in results)
            print(f"[{index}/{len(inventory)}] {statuses}: {item['filename']}")

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    if not nextcloud_ready():
        print("\nNEXTCLOUD_* not configured yet — DOCX/PDF generated locally, Nextcloud upload pending.")
        print("Run with --nextcloud-only once credentials are set in .env.")


if __name__ == "__main__":
    main()
