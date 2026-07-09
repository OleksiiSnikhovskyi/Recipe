#!/usr/bin/env python3
"""
Safely backfill Recipe records from a YouTube playlist.

The script is intentionally conservative:
- fetches playlist pages through the YouTube Data API;
- processes videos one by one through the existing WF-02 production webhook;
- enforces at least 10 seconds between processing attempts;
- skips completed recipes by default;
- reprocesses low-confidence transcripts only when explicitly requested.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv


load_dotenv(override=True)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "recipe_db")
DB_USER = os.getenv("DB_USER", "recipe_user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("RECIPE_DB_PASSWORD", "")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_PLAYLIST_ID = os.getenv("YOUTUBE_PLAYLIST_ID", "PL3lTxqA4f3PhmxU9HEd1Lk17ZoeP4bhfz")
N8N_WEBHOOK_BASE_URL = os.getenv("N8N_WEBHOOK_BASE_URL") or (
    os.getenv("N8N_BASE_URL", "https://n8n.csc-ua.tech").rstrip("/") + "/webhook"
)

MIN_DELAY_SECONDS = 10
DEFAULT_DELAY_SECONDS = int(os.getenv("RECIPE_BACKFILL_DELAY_SECONDS", "60"))
DEFAULT_REQUEST_TIMEOUT_SECONDS = int(os.getenv("RECIPE_BACKFILL_TIMEOUT_SECONDS", "1200"))


@dataclass
class PlaylistVideo:
    video_id: str
    playlist_id: str
    title: str
    description: str
    thumbnail: str
    youtube_channel: str
    published_at: str

    @property
    def video_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_playlist_page(page_token: str = "") -> Dict[str, Any]:
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not set")

    params = {
        "key": YOUTUBE_API_KEY,
        "playlistId": YOUTUBE_PLAYLIST_ID,
        "part": "snippet",
        "maxResults": 50,
    }
    if page_token:
        params["pageToken"] = page_token

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/playlistItems",
        params=params,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def normalize_playlist_items(payload: Dict[str, Any]) -> List[PlaylistVideo]:
    videos: List[PlaylistVideo] = []
    for item in payload.get("items", []):
        snippet = item.get("snippet") or {}
        resource = snippet.get("resourceId") or {}
        video_id = resource.get("videoId")
        if not video_id:
            continue

        thumbnails = snippet.get("thumbnails") or {}
        thumbnail = (
            (thumbnails.get("maxres") or {}).get("url")
            or (thumbnails.get("high") or {}).get("url")
            or (thumbnails.get("medium") or {}).get("url")
            or (thumbnails.get("default") or {}).get("url")
            or ""
        )
        videos.append(
            PlaylistVideo(
                video_id=str(video_id),
                playlist_id=YOUTUBE_PLAYLIST_ID,
                title=str(snippet.get("title") or ""),
                description=str(snippet.get("description") or ""),
                thumbnail=thumbnail,
                youtube_channel=str(snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle") or ""),
                published_at=str(snippet.get("publishedAt") or ""),
            )
        )
    return videos


def iter_playlist_videos(page_delay_seconds: int = MIN_DELAY_SECONDS) -> Iterable[PlaylistVideo]:
    page_token = ""
    page_index = 0
    while True:
        page_index += 1
        payload = fetch_playlist_page(page_token)
        videos = normalize_playlist_items(payload)
        print(f"Fetched playlist page {page_index}: {len(videos)} videos")
        yield from videos

        page_token = str(payload.get("nextPageToken") or "")
        if not page_token:
            break
        time.sleep(max(MIN_DELAY_SECONDS, page_delay_seconds))


def get_recipe_state(video_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, video_id, title, processed, nextcloud_docx_url, nextcloud_pdf_url,
                       transcript, transcript_source, transcription_warning, updated_at
                FROM recipes
                WHERE video_id = %s
                LIMIT 1
                """,
                (video_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


def is_completed_recipe(recipe: Optional[Dict[str, Any]]) -> bool:
    if not recipe:
        return False
    return bool(recipe.get("processed") and recipe.get("nextcloud_docx_url") and recipe.get("nextcloud_pdf_url"))


def is_bad_transcription(recipe: Optional[Dict[str, Any]], min_transcript_chars: int) -> bool:
    if not recipe:
        return False
    transcript = str(recipe.get("transcript") or "").strip()
    source = str(recipe.get("transcript_source") or "").strip()
    warning = str(recipe.get("transcription_warning") or "").strip()
    return (
        source == "description_only"
        or bool(warning)
        or len(transcript) < min_transcript_chars
    )


def mark_video_claimed(video: PlaylistVideo, reprocess: bool = False) -> None:
    status = "processing"
    message = "Safe playlist backfill"
    if reprocess:
        message = "Safe reprocess of low-confidence transcription"

    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO video_log (video_id, playlist_id, processed, status, error_details, created_at, updated_at)
                VALUES (%s, %s, FALSE, %s, %s, NOW(), NOW())
                ON CONFLICT (video_id) DO UPDATE SET
                    playlist_id = EXCLUDED.playlist_id,
                    processed = FALSE,
                    status = EXCLUDED.status,
                    error_details = EXCLUDED.error_details,
                    updated_at = NOW()
                """,
                (video.video_id, video.playlist_id, status, message),
            )


def mark_video_failed(video_id: str, error: str) -> None:
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE video_log
                SET processed = FALSE,
                    status = 'failed',
                    error_details = %s,
                    updated_at = NOW()
                WHERE video_id = %s
                """,
                (error[:4000], video_id),
            )


def call_extract_workflow(video: PlaylistVideo, timeout_seconds: int) -> Dict[str, Any]:
    url = N8N_WEBHOOK_BASE_URL.rstrip("/") + "/recipe-extract"
    payload = {
        "videoId": video.video_id,
        "title": video.title,
        "description": video.description,
        "thumbnail": video.thumbnail,
        "youtubeChannel": video.youtube_channel,
        "publishedAt": video.published_at,
    }
    response = requests.post(url, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    if not response.text.strip():
        return {"ok": True, "empty_response": True}
    try:
        return response.json()
    except ValueError:
        return {"ok": True, "raw_response": response.text[:1000]}


def decide_action(
    recipe: Optional[Dict[str, Any]],
    *,
    reprocess_bad_transcripts: bool,
    force: bool,
    min_transcript_chars: int,
) -> str:
    if force:
        return "process"
    if not recipe:
        return "process"
    if not is_completed_recipe(recipe):
        return "process"
    if reprocess_bad_transcripts and is_bad_transcription(recipe, min_transcript_chars):
        return "reprocess"
    return "skip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely backfill Recipe videos from the configured YouTube playlist")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of videos to process, 0 means no limit")
    parser.add_argument("--scan-limit", type=int, default=0, help="Maximum number of playlist videos to scan, 0 means no limit")
    parser.add_argument("--delay-seconds", type=int, default=DEFAULT_DELAY_SECONDS, help="Delay between processed videos; minimum 10")
    parser.add_argument("--page-delay-seconds", type=int, default=MIN_DELAY_SECONDS, help="Delay between YouTube playlist pages; minimum 10")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_REQUEST_TIMEOUT_SECONDS, help="WF-02 webhook timeout")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without calling n8n")
    parser.add_argument("--force", action="store_true", help="Process every scanned video, even completed recipes")
    parser.add_argument("--reprocess-bad-transcripts", action="store_true", help="Reprocess completed recipes with low-confidence transcription")
    parser.add_argument("--min-transcript-chars", type=int, default=300, help="Transcript shorter than this is treated as low confidence")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    delay_seconds = max(MIN_DELAY_SECONDS, args.delay_seconds)
    page_delay_seconds = max(MIN_DELAY_SECONDS, args.page_delay_seconds)

    print("Safe Recipe playlist backfill")
    print(f"playlist_id={YOUTUBE_PLAYLIST_ID}")
    print(f"delay_seconds={delay_seconds}")
    print(f"page_delay_seconds={page_delay_seconds}")
    print(f"dry_run={args.dry_run}")
    print(f"reprocess_bad_transcripts={args.reprocess_bad_transcripts}")
    print(f"started_at={datetime.now(timezone.utc).isoformat()}")

    scanned = 0
    processed = 0
    skipped = 0
    failed = 0

    for video in iter_playlist_videos(page_delay_seconds=page_delay_seconds):
        if args.scan_limit and scanned >= args.scan_limit:
            break
        scanned += 1

        recipe = get_recipe_state(video.video_id)
        action = decide_action(
            recipe,
            reprocess_bad_transcripts=args.reprocess_bad_transcripts,
            force=args.force,
            min_transcript_chars=args.min_transcript_chars,
        )

        label = f"{video.video_id} | {video.title[:90]}"
        if action == "skip":
            skipped += 1
            print(f"SKIP    {label}")
            continue

        if args.limit and processed >= args.limit:
            print("Processing limit reached")
            break

        print(f"{action.upper():7} {label}")
        if args.dry_run:
            processed += 1
            continue

        try:
            mark_video_claimed(video, reprocess=(action == "reprocess"))
            result = call_extract_workflow(video, timeout_seconds=args.timeout_seconds)
            print(f"RESULT  {video.video_id}: {json.dumps(result, ensure_ascii=False)[:1000]}")
            processed += 1
        except Exception as exc:
            failed += 1
            error = f"{type(exc).__name__}: {exc}"
            print(f"ERROR   {video.video_id}: {error}", file=sys.stderr)
            mark_video_failed(video.video_id, error)

        time.sleep(delay_seconds)

    print(json.dumps({
        "ok": failed == 0,
        "scanned": scanned,
        "processed_or_planned": processed,
        "skipped": skipped,
        "failed": failed,
    }, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
