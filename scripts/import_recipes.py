#!/usr/bin/env python3
"""
import_recipes.py

Import recipes from Nextcloud and YouTube playlist into PostgreSQL.

Usage:
    python import_recipes.py --env /path/to/.env --source nextcloud
    python import_recipes.py --env /path/to/.env --source youtube
"""

import json
import os
import sys
import argparse
import requests
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

try:
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("Error: requests library not installed. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


class RecipeImporter:
    """Import recipes from various sources."""

    def __init__(self, db_host: str, db_port: int, db_name: str, db_user: str, db_password: str):
        """Initialize database connection."""
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            print(f"🔗 Connecting to {self.db_name}...")
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                connect_timeout=10
            )
            self.cursor = self.conn.cursor()
            print("✅ Connected!")
            return True
        except psycopg2.Error as e:
            print(f"❌ Connection error: {e}")
            return False

    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def insert_recipe(self, recipe: Dict[str, Any]) -> bool:
        """
        Insert recipe into database.

        Args:
            recipe: Recipe dictionary with title, category, ingredients, steps, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.cursor.execute("""
                INSERT INTO recipes (
                    title, category, description, recipe_text,
                    ingredients, steps, nutrition,
                    youtube_url, youtube_channel, thumbnail_url,
                    processed, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (video_id) DO NOTHING;
            """, (
                recipe.get("title", ""),
                recipe.get("category", "Інше"),
                recipe.get("description", ""),
                recipe.get("recipe_text", ""),
                json.dumps(recipe.get("ingredients", []), ensure_ascii=False),
                json.dumps(recipe.get("steps", []), ensure_ascii=False),
                json.dumps(recipe.get("nutrition", {}), ensure_ascii=False),
                recipe.get("youtube_url", ""),
                recipe.get("youtube_channel", ""),
                recipe.get("thumbnail_url", ""),
                False,
                datetime.utcnow()
            ))
            self.conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"❌ Insert error: {e}")
            return False

    def import_from_nextcloud(
        self,
        nextcloud_url: str,
        nextcloud_user: str,
        nextcloud_password: str,
        nextcloud_recipe_folder: str = "/Documents/Recipe"
    ) -> int:
        """
        Import recipes from Nextcloud folder.

        Args:
            nextcloud_url: Nextcloud base URL
            nextcloud_user: Nextcloud username
            nextcloud_password: Nextcloud password
            nextcloud_recipe_folder: Folder path

        Returns:
            Number of recipes imported
        """

        print(f"\n📂 Importing recipes from Nextcloud: {nextcloud_recipe_folder}")

        try:
            # List files in Nextcloud folder
            webdav_url = f"{nextcloud_url}/remote.php/dav/files/{nextcloud_user}{nextcloud_recipe_folder}"

            response = requests.request(
                "PROPFIND",
                webdav_url,
                auth=HTTPBasicAuth(nextcloud_user, nextcloud_password),
                headers={"Depth": "1"}
            )

            if response.status_code not in [207, 200]:
                print(f"❌ Nextcloud error: {response.status_code}")
                return 0

            # Parse response (simplified - would need XML parsing for production)
            print(f"📊 Checking Nextcloud folder structure...")
            print(f"   URL: {webdav_url}")
            print(f"   User: {nextcloud_user}")

            # TODO: Parse WebDAV response and download recipe files
            # For now, return 0 - will implement after testing connection

            print("⚠️  Nextcloud import: Need to implement WebDAV file parsing")
            return 0

        except Exception as e:
            print(f"❌ Nextcloud import error: {e}")
            return 0

    def import_from_youtube_playlist(
        self,
        youtube_playlist_url: str,
        youtube_api_key: str = None
    ) -> int:
        """
        Fetch YouTube playlist metadata (requires YouTube API).

        Args:
            youtube_playlist_url: YouTube playlist URL or ID
            youtube_api_key: YouTube Data API key

        Returns:
            Number of videos detected
        """

        print(f"\n🎬 Importing from YouTube playlist: {youtube_playlist_url}")

        if not youtube_api_key:
            print("⚠️  No YouTube API key. Use --youtube-api-key or set in .env")
            print("   This feature requires: YOUTUBE_API_KEY")
            return 0

        # Extract playlist ID from URL
        playlist_id = None
        if "list=" in youtube_playlist_url:
            playlist_id = youtube_playlist_url.split("list=")[1].split("&")[0]
        else:
            playlist_id = youtube_playlist_url

        print(f"   Playlist ID: {playlist_id}")

        try:
            # TODO: Implement YouTube API integration
            # 1. Fetch playlist videos
            # 2. Get video metadata (title, description, thumbnail)
            # 3. Create recipe entries with unprocessed status
            # 4. Store in database for processing by n8n

            print("⚠️  YouTube import: Need to implement YouTube Data API integration")
            return 0

        except Exception as e:
            print(f"❌ YouTube import error: {e}")
            return 0


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Import recipes from Nextcloud/YouTube")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--source", choices=["nextcloud", "youtube"], required=True, help="Import source")
    parser.add_argument("--youtube-api-key", help="YouTube API key (overrides .env)")
    parser.add_argument("--db-host", help="PostgreSQL host (overrides .env)")
    parser.add_argument("--db-port", type=int, help="PostgreSQL port (overrides .env)")
    parser.add_argument("--db-name", default="recipe_db", help="Database name")
    parser.add_argument("--db-user", default="recipe_user", help="Database user")
    parser.add_argument("--db-password", help="Database password (overrides .env)")

    args = parser.parse_args()

    # Load environment
    if os.path.exists(args.env):
        print(f"📂 Loading .env from {args.env}")
        load_dotenv(args.env)
    else:
        print(f"⚠️  .env not found: {args.env}")

    # Get database credentials
    db_host = args.db_host or os.getenv("DB_HOST", "100.81.127.54")
    db_port = args.db_port or int(os.getenv("DB_PORT", 5432))
    db_user = args.db_user or os.getenv("RECIPE_DB_USER", "recipe_user")
    db_password = args.db_password or os.getenv("RECIPE_DB_PASSWORD", "")

    if not db_password:
        print("❌ Database password required. Set RECIPE_DB_PASSWORD in .env or use --db-password")
        sys.exit(1)

    # Initialize importer
    importer = RecipeImporter(db_host, db_port, args.db_name, db_user, db_password)

    if not importer.connect():
        sys.exit(1)

    try:
        imported_count = 0

        if args.source == "nextcloud":
            nextcloud_url = os.getenv("NEXTCLOUD_URL", "")
            nextcloud_user = os.getenv("NEXTCLOUD_USER", "")
            nextcloud_password = os.getenv("NEXTCLOUD_PASSWORD", "")
            nextcloud_folder = os.getenv("NEXTCLOUD_RECIPE_FOLDER", "/Documents/Recipe")

            if not all([nextcloud_url, nextcloud_user, nextcloud_password]):
                print("❌ Missing Nextcloud credentials in .env")
                sys.exit(1)

            imported_count = importer.import_from_nextcloud(
                nextcloud_url,
                nextcloud_user,
                nextcloud_password,
                nextcloud_folder
            )

        elif args.source == "youtube":
            youtube_api_key = args.youtube_api_key or os.getenv("YOUTUBE_API_KEY", "")
            youtube_playlist_url = os.getenv("YOUTUBE_PLAYLIST_URL", "")

            if not youtube_playlist_url:
                print("❌ YOUTUBE_PLAYLIST_URL not set in .env")
                sys.exit(1)

            imported_count = importer.import_from_youtube_playlist(
                youtube_playlist_url,
                youtube_api_key
            )

        print(f"\n📊 Import Summary: {imported_count} recipes processed")

    finally:
        importer.close()


if __name__ == "__main__":
    main()
