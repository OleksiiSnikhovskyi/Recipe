#!/usr/bin/env python3
"""
nextcloud_uploader.py

Upload DOCX and PDF files to Nextcloud via WebDAV.

Usage:
    python nextcloud_uploader.py --docx recipe.docx --pdf recipe.pdf --category "Десерти" --recipe-name "Тірамісу"

    or as HTTP endpoint:
    POST /upload
    {"docx_base64": "...", "pdf_base64": "...", "category": "Десерти", "recipe_name": "Тірамісу"}
"""

import os
import sys
import argparse
import json
import base64
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

# Configuration
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "https://nextcloud.domain")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "")
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD", "")
NEXTCLOUD_RECIPE_FOLDER = os.getenv("NEXTCLOUD_RECIPE_FOLDER", "/Рецепти")


# TODO: Implement Nextcloud WebDAV upload
# Features:
# 1. Validate credentials
# 2. Create category folder if not exists
# 3. Upload DOCX file via WebDAV PUT
# 4. Upload PDF file via WebDAV PUT
# 5. Generate public share links
# 6. Handle errors and retries
# 7. Return URLs of uploaded files

def upload_to_nextcloud(
    docx_path: str = None,
    pdf_path: str = None,
    docx_base64: str = None,
    pdf_base64: str = None,
    category: str = "Інше",
    recipe_name: str = "Recipe"
) -> Dict[str, str]:
    """
    Upload files to Nextcloud.

    Args:
        docx_path: Path to local DOCX file (or docx_base64 if file not local)
        pdf_path: Path to local PDF file (or pdf_base64 if file not local)
        docx_base64: Base64-encoded DOCX content
        pdf_base64: Base64-encoded PDF content
        category: Recipe category (for folder organization)
        recipe_name: Recipe name (for file naming)

    Returns:
        Dict with keys:
        {
            "docx_url": "https://nextcloud/.../recipe.docx",
            "pdf_url": "https://nextcloud/.../recipe.pdf",
            "docx_share_link": "https://nextcloud/s/xxx",
            "pdf_share_link": "https://nextcloud/s/yyy"
        }
    """

    # TODO: Implement
    # 1. Authenticate with Nextcloud
    # 2. Build WebDAV URL for category folder
    # 3. Create folder if not exists
    # 4. Upload DOCX with PUT request
    # 5. Upload PDF with PUT request
    # 6. Create public share links
    # 7. Return URLs

    raise NotImplementedError("Nextcloud upload not yet implemented")


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Upload recipe files to Nextcloud")
    parser.add_argument("--docx", help="Path to DOCX file")
    parser.add_argument("--pdf", help="Path to PDF file")
    parser.add_argument("--category", default="Інше", help="Recipe category")
    parser.add_argument("--recipe-name", required=True, help="Recipe name")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5003, type=int, help="Server port (default: 5003)")

    args = parser.parse_args()

    if args.server:
        # TODO: Implement Flask server
        # POST /upload
        # Input: {"docx_base64": "...", "pdf_base64": "...", "category": "...", "recipe_name": "..."}
        # Output: {"docx_url": "...", "pdf_url": "...", "docx_share_link": "...", "pdf_share_link": "..."}

        try:
            from flask import Flask, request, jsonify
        except ImportError:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)

        app = Flask(__name__)

        @app.route("/upload", methods=["POST"])
        def upload_endpoint():
            try:
                data = request.json

                docx_base64 = data.get("docx_base64")
                pdf_base64 = data.get("pdf_base64")
                category = data.get("category", "Інше")
                recipe_name = data.get("recipe_name")

                if not docx_base64 or not pdf_base64 or not recipe_name:
                    return jsonify({"error": "docx_base64, pdf_base64, and recipe_name required"}), 400

                urls = upload_to_nextcloud(
                    docx_base64=docx_base64,
                    pdf_base64=pdf_base64,
                    category=category,
                    recipe_name=recipe_name
                )

                return jsonify(urls), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok"}), 200

        print(f"Starting Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)

    else:
        # CLI mode
        if not args.docx or not args.pdf:
            print("Error: --docx and --pdf paths required", file=sys.stderr)
            sys.exit(1)

        try:
            urls = upload_to_nextcloud(
                docx_path=args.docx,
                pdf_path=args.pdf,
                category=args.category,
                recipe_name=args.recipe_name
            )

            print(json.dumps(urls, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Upload failed: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
