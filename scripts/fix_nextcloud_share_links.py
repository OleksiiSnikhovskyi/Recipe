#!/usr/bin/env python3
"""
Replace login-only WebDAV URLs with real public share links.

A mass upload run triggered Nextcloud's rate limit (HTTP 429) on the share
creation endpoint; nextcloud_uploader.create_share_link() used to treat that
as "no share" and silently fall back to storing the raw WebDAV URL, which
requires a Nextcloud login to open — not what recipients should need.

This walks every recipe whose stored URL is a WebDAV path (not a /s/ share
link) and creates the missing share, pacing calls to stay under the limiter.

Usage:
    python scripts/fix_nextcloud_share_links.py --log logs/fix_share_links.jsonl
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

import requests
import psycopg2
import psycopg2.extras

import nextcloud_uploader as nc

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")

PACE_SECONDS = 2.0


def db_connection():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_webdav_fallback_rows():
    conn = db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, category, nextcloud_docx_url, nextcloud_pdf_url
                FROM recipes
                WHERE nextcloud_pdf_url LIKE '%%/remote.php/dav/%%'
                   OR nextcloud_docx_url LIKE '%%/remote.php/dav/%%'
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def update_urls(recipe_id: int, docx_url: str, pdf_url: str) -> None:
    conn = db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE recipes SET nextcloud_docx_url = %s, nextcloud_pdf_url = %s, updated_at = NOW() WHERE id = %s",
                    (docx_url, pdf_url, recipe_id),
                )
    finally:
        conn.close()


def webdav_url_to_remote_path(url: str) -> str:
    marker = f"/remote.php/dav/files/{nc.NEXTCLOUD_DAV_USER}/"
    idx = url.find(marker)
    if idx == -1:
        return ""
    encoded = url[idx + len(marker):]
    from urllib.parse import unquote
    return "/" + unquote(encoded)


def process_row(session: requests.Session, row: dict) -> dict:
    docx_url = row["nextcloud_docx_url"]
    pdf_url = row["nextcloud_pdf_url"]
    changed = False

    if docx_url and "/remote.php/dav/" in docx_url:
        remote_path = webdav_url_to_remote_path(docx_url)
        share = nc.create_share_link(session, remote_path) if remote_path else ""
        if share:
            docx_url = share
            changed = True

    if pdf_url and "/remote.php/dav/" in pdf_url:
        remote_path = webdav_url_to_remote_path(pdf_url)
        share = nc.create_share_link(session, remote_path) if remote_path else ""
        if share:
            pdf_url = share
            changed = True

    if not changed:
        return {"id": row["id"], "status": "no_share_created"}

    try:
        update_urls(row["id"], docx_url, pdf_url)
    except Exception as exc:
        return {"id": row["id"], "status": "error_db", "error": str(exc)}

    return {"id": row["id"], "status": "ok", "title": row["title"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = fetch_webdav_fallback_rows()
    if args.limit:
        rows = rows[: args.limit]
    print(f"Recipes with WebDAV-only links: {len(rows)}")

    session = requests.Session()
    session.auth = (nc.NEXTCLOUD_USER, nc.NEXTCLOUD_PASSWORD)

    counts = {}
    try:
        with Path(args.log).open("a", encoding="utf-8") as log_file:
            for index, row in enumerate(rows, start=1):
                result = process_row(session, row)
                counts[result["status"]] = counts.get(result["status"], 0) + 1
                log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                log_file.flush()
                print(f"[{index}/{len(rows)}] {result['status']}: {row['title']}")
                time.sleep(PACE_SECONDS)
    finally:
        session.close()

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
