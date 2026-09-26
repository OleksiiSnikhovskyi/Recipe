#!/usr/bin/env python3
"""
Backfill photos for already-imported OneDrive recipes.

Only single-recipe source files are eligible (video_id has no '-N' suffix):
a compilation file's embedded images can't be reliably matched to the right
recipe section, so those are left without a photo, same as during the main
import run.

For each eligible recipe: extract the best embedded image from its original
source .docx, regenerate the DOCX/PDF with the photo included, and re-upload
to Nextcloud if credentials are configured and it was already uploaded once.

Usage:
    python scripts/backfill_onedrive_photos.py --log logs/onedrive_photo_backfill.jsonl
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
import psycopg2.extras

import generate_docx as docx_module
import pdf_converter
import nextcloud_uploader as nc_module
from import_onedrive_recipes import extract_best_image, find_qr_youtube_link, nextcloud_ready

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")


def db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def update_thumbnail_url(recipe_id: int, thumbnail_url: str) -> None:
    """Persist the photo path so future regeneration (including via the n8n
    WF-03 webhook) doesn't silently lose it — it isn't otherwise stored
    anywhere but the generated document itself."""
    conn = db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE recipes SET thumbnail_url = %s, updated_at = NOW() WHERE id = %s",
                    (thumbnail_url, recipe_id),
                )
    finally:
        conn.close()


def fetch_eligible_rows():
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, title, category, description, ingredients, steps,
                       nutrition, youtube_url, docx_path, pdf_path, nextcloud_pdf_url
                FROM recipes
                WHERE video_id ~ '^onedrive:[0-9a-f]{16}$'
                  AND youtube_url IS NOT NULL
                  AND docx_path IS NOT NULL
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def process_row(row: dict) -> dict:
    source_path = Path(row["youtube_url"])
    if not source_path.exists() or source_path.suffix.lower() != ".docx":
        return {"id": row["id"], "status": "skipped_no_source"}

    try:
        image_path = extract_best_image(source_path, row["video_id"])
    except Exception as exc:
        return {"id": row["id"], "status": "error_extract_image", "error": str(exc)}

    try:
        video_url = find_qr_youtube_link(source_path, row["video_id"])
    except Exception:
        video_url = ""

    if not image_path and not video_url:
        return {"id": row["id"], "status": "skipped_no_image"}

    recipe = {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "steps": row["steps"],
        "nutrition": row["nutrition"],
        "source": {"thumbnail_url": image_path, "video_url": video_url},
    }

    try:
        docx_result = docx_module.write_docx(recipe)
        docx_module.update_docx_path(row["id"], None, docx_result["docx_path"])
        pdf_path = pdf_converter.convert_docx_to_pdf(docx_result["docx_path"])
        pdf_converter.update_pdf_path(row["id"], None, pdf_path)
        if image_path:
            update_thumbnail_url(row["id"], image_path)
    except Exception as exc:
        return {"id": row["id"], "status": "error_regenerate", "error": str(exc)}

    if row.get("nextcloud_pdf_url") and nextcloud_ready():
        try:
            nc_module.upload_to_nextcloud(
                recipe_id=row["id"], title=row["title"], category=row["category"],
                docx_path=docx_result["docx_path"], pdf_path=pdf_path,
            )
        except Exception as exc:
            return {"id": row["id"], "status": "regenerated_upload_failed", "error": str(exc)}

    return {"id": row["id"], "status": "ok", "title": row["title"], "image": image_path, "video_url": video_url}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = fetch_eligible_rows()
    if args.limit:
        rows = rows[: args.limit]
    print(f"Eligible recipes: {len(rows)}")

    counts = {}
    with Path(args.log).open("a", encoding="utf-8") as log_file:
        for index, row in enumerate(rows, start=1):
            result = process_row(row)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            log_file.flush()
            print(f"[{index}/{len(rows)}] {result['status']}: {row['title']}")

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
