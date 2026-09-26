#!/usr/bin/env python3
"""
Regenerate DOCX/PDF for every recipe after a template-level fix (e.g. the
ingredient table column widths) that needs to apply retroactively — not just
to newly-processed files.

thumbnail_url and video_url are not persisted as their own DB columns (only
baked into the generated document at creation time), so this reconstructs
them from the photo-backfill and YouTube-match logs rather than losing that
work: without this, a naive "rebuild from DB row" would silently drop every
photo and QR code already attached.

Usage:
    python scripts/regenerate_all_documents.py --log logs/regenerate_all.jsonl
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
import psycopg2.extras

import generate_docx as docx_module
import pdf_converter
import nextcloud_uploader as nc_module
from import_onedrive_recipes import nextcloud_ready

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


def load_photo_map(log_path: Path) -> dict:
    photos = {}
    if not log_path.exists():
        return photos
    for line in log_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("status") == "ok" and d.get("image"):
            photos[d["id"]] = d["image"]
    return photos


def load_youtube_map(log_path: Path) -> dict:
    matches = {}
    if not log_path.exists():
        return matches
    for line in log_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("status") == "matched" and d.get("video_url"):
            matches[d["id"]] = d["video_url"]
    return matches


def fetch_all_rows():
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, title, category, description, ingredients, steps,
                       nutrition, docx_path, pdf_path, nextcloud_pdf_url, youtube_url, youtube_channel,
                       thumbnail_url
                FROM recipes
                WHERE docx_path IS NOT NULL
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def process_row(row: dict, photo_map: dict, youtube_map: dict) -> dict:
    thumbnail_url = row.get("thumbnail_url") or photo_map.get(row["id"], "")
    video_url = youtube_map.get(row["id"], "")
    if not video_url and row.get("youtube_url", "").startswith("https://www.youtube.com/"):
        video_url = row["youtube_url"]

    recipe = {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "steps": row["steps"],
        "nutrition": row["nutrition"],
        "source": {
            "thumbnail_url": thumbnail_url,
            "video_url": video_url,
            "youtube_channel": row.get("youtube_channel") or "",
        },
    }

    try:
        docx_result = docx_module.write_docx(recipe)
        docx_module.update_docx_path(row["id"], None, docx_result["docx_path"])
        pdf_path = pdf_converter.convert_docx_to_pdf(docx_result["docx_path"])
        pdf_converter.update_pdf_path(row["id"], None, pdf_path)
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

    return {"id": row["id"], "status": "ok", "title": row["title"],
            "has_photo": bool(thumbnail_url), "has_video": bool(video_url)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--photo-log", default="logs/onedrive_photo_backfill.jsonl")
    parser.add_argument("--youtube-log", default="logs/youtube_match.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    photo_map = load_photo_map(Path(args.photo_log))
    youtube_map = load_youtube_map(Path(args.youtube_log))
    rows = fetch_all_rows()
    if args.limit:
        rows = rows[: args.limit]
    print(f"Recipes to regenerate: {len(rows)} (photo entries: {len(photo_map)}, youtube matches: {len(youtube_map)})")

    counts = {}
    with Path(args.log).open("a", encoding="utf-8") as log_file:
        for index, row in enumerate(rows, start=1):
            result = process_row(row, photo_map, youtube_map)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            log_file.flush()
            print(f"[{index}/{len(rows)}] {result['status']}: {row['title']}")

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
