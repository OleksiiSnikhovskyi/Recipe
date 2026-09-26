#!/usr/bin/env python3
"""
Match OneDrive-imported recipes against the source YouTube playlist
(fetched once via playlistItems.list, ~26 quota units total instead of 100
units per recipe via search.list) and backfill video_url + thumbnail.

Matching uses the recipe's DB title AND the first line of its raw extracted
source text (closer to the original YouTube title before LLM cleanup),
scored against every playlist title with difflib; only accepts a match above
MATCH_THRESHOLD to avoid linking the wrong video.

For a matched recipe: regenerate DOCX (adds QR code + "Джерело" section;
adds the YouTube thumbnail only if the recipe has no photo yet) and PDF,
then re-upload to Nextcloud if credentials are configured.

Usage:
    python scripts/match_youtube_playlist.py --playlist logs/youtube_playlist_items.json --log logs/youtube_match.jsonl
"""

import argparse
import difflib
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

MATCH_THRESHOLD = 0.6


def db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_unmatched_rows():
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, video_id, title, category, description, ingredients, steps,
                       nutrition, recipe_text, docx_path, pdf_path, nextcloud_pdf_url
                FROM recipes
                WHERE video_id LIKE 'onedrive:%%'
                  AND (youtube_url IS NULL OR youtube_url NOT LIKE 'https://www.youtube.com/%%')
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def update_youtube_link(recipe_id: int, video_url: str) -> None:
    conn = db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE recipes SET youtube_url = %s, updated_at = NOW() WHERE id = %s",
                    (video_url, recipe_id),
                )
    finally:
        conn.close()


def update_thumbnail_url(recipe_id: int, thumbnail_url: str) -> None:
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


def normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def best_match(query_texts: list, playlist: list):
    best_score = 0.0
    best_item = None
    for item in playlist:
        candidate = normalize(item["title"])
        for query in query_texts:
            score = difflib.SequenceMatcher(None, query, candidate).ratio()
            if score > best_score:
                best_score = score
                best_item = item
    return best_item, best_score


def process_row(row: dict, playlist: list) -> dict:
    stripped_source = (row.get("recipe_text") or "").strip()
    first_line = stripped_source.splitlines()[0] if stripped_source else ""
    query_texts = [normalize(row["title"]), normalize(first_line)]
    query_texts = [q for q in query_texts if q]
    if not query_texts:
        return {"id": row["id"], "status": "skipped_no_query_text"}

    match, score = best_match(query_texts, playlist)
    if not match or score < MATCH_THRESHOLD:
        return {"id": row["id"], "status": "no_match", "best_score": round(score, 3)}

    video_url = f"https://www.youtube.com/watch?v={match['video_id']}"
    try:
        update_youtube_link(row["id"], video_url)
    except Exception as exc:
        return {"id": row["id"], "status": "error_db", "error": str(exc)}

    has_photo = bool(row.get("thumbnail_url")) or (
        bool(row.get("docx_path")) and _docx_has_photo(row["docx_path"])
    )
    thumbnail_url = "" if has_photo else match.get("thumbnail_url", "")
    recipe = {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "steps": row["steps"],
        "nutrition": row["nutrition"],
        "source": {
            "video_url": video_url,
            "youtube_channel": match.get("channel", ""),
            "thumbnail_url": thumbnail_url,
        },
    }

    try:
        docx_result = docx_module.write_docx(recipe)
        docx_module.update_docx_path(row["id"], None, docx_result["docx_path"])
        pdf_path = pdf_converter.convert_docx_to_pdf(docx_result["docx_path"])
        pdf_converter.update_pdf_path(row["id"], None, pdf_path)
        if thumbnail_url:
            update_thumbnail_url(row["id"], thumbnail_url)
    except Exception as exc:
        return {"id": row["id"], "status": "error_regenerate", "error": str(exc),
                "matched_title": match["title"], "score": round(score, 3)}

    if row.get("nextcloud_pdf_url") and nextcloud_ready():
        try:
            nc_module.upload_to_nextcloud(
                recipe_id=row["id"], title=row["title"], category=row["category"],
                docx_path=docx_result["docx_path"], pdf_path=pdf_path,
            )
        except Exception as exc:
            return {"id": row["id"], "status": "regenerated_upload_failed", "error": str(exc)}

    return {"id": row["id"], "status": "matched", "title": row["title"],
            "matched_title": match["title"], "score": round(score, 3), "video_url": video_url}


def _docx_has_photo(docx_path: str) -> bool:
    """Cheap heuristic: a DOCX with an embedded picture is meaningfully
    larger than a photo-less one for this project's template."""
    try:
        return Path(docx_path).stat().st_size > 60_000
    except (OSError, TypeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    playlist = json.loads(Path(args.playlist).read_text(encoding="utf-8"))
    rows = fetch_unmatched_rows()
    if args.limit:
        rows = rows[: args.limit]
    print(f"Playlist videos: {len(playlist)}; recipes to match: {len(rows)}")

    counts = {}
    with Path(args.log).open("a", encoding="utf-8") as log_file:
        for index, row in enumerate(rows, start=1):
            result = process_row(row, playlist)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            log_file.flush()
            print(f"[{index}/{len(rows)}] {result['status']} ({result.get('best_score', result.get('score',''))}): {row['title']}")

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
