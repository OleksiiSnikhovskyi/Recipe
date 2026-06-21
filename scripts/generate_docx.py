#!/usr/bin/env python3
"""
generate_docx.py

Generate formatted Microsoft Word (.docx) documents from recipe JSON.

Usage:
    python generate_docx.py --recipe recipe.json --output output.docx

    or as HTTP endpoint:
    POST /generate
    {"recipe": {...recipe JSON...}}
"""

# TODO: Implement with python-docx library
# Features to include:
# - Title heading with category badge
# - Recipe image (thumbnail)
# - Ingredients table with quantity and unit columns
# - Step-by-step instructions (numbered)
# - Nutrition facts table (per 100g and per serving)
# - Cooking time indicators
# - Source attribution (YouTube channel + link)
# - Professional formatting with fonts, colors, spacing

import json
import sys
import argparse
import os
from io import BytesIO
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("Error: python-docx not installed. Install with: pip install python-docx", file=sys.stderr)
    sys.exit(1)


def generate_docx(recipe: Dict[str, Any]) -> bytes:
    """
    Generate DOCX document from recipe data.

    Args:
        recipe: Recipe data dictionary (JSON)

    Returns:
        DOCX file content as bytes
    """

    doc = Document()

    # TODO: Implement document generation
    # 1. Set document margins
    # 2. Add title
    # 3. Add category badge
    # 4. Add image
    # 5. Add ingredients table
    # 6. Add cooking instructions
    # 7. Add nutrition facts
    # 8. Add source attribution

    # For now, return placeholder
    raise NotImplementedError("DOCX generation not yet implemented")


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Generate DOCX from recipe JSON")
    parser.add_argument("--recipe", "-r", required=True, help="Recipe JSON file path")
    parser.add_argument("--output", "-o", required=True, help="Output DOCX file path")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5001, type=int, help="Server port (default: 5001)")

    args = parser.parse_args()

    if args.server:
        # TODO: Implement Flask server
        # POST /generate
        # Returns: {"docx_base64": "...", "filename": "..."}
        try:
            from flask import Flask, request, jsonify
            import base64
        except ImportError:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)

        app = Flask(__name__)

        @app.route("/generate", methods=["POST"])
        def generate_endpoint():
            try:
                data = request.json
                recipe = data.get("recipe")

                if not recipe:
                    return jsonify({"error": "recipe field required"}), 400

                docx_bytes = generate_docx(recipe)
                filename = recipe.get("title", "recipe") + ".docx"

                return jsonify({
                    "docx_base64": base64.b64encode(docx_bytes).decode(),
                    "filename": filename
                }), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok"}), 200

        print(f"Starting Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)

    else:
        # CLI mode
        if not os.path.exists(args.recipe):
            print(f"Error: Recipe file not found: {args.recipe}", file=sys.stderr)
            sys.exit(1)

        with open(args.recipe, 'r', encoding='utf-8') as f:
            recipe = json.load(f)

        try:
            docx_bytes = generate_docx(recipe)

            with open(args.output, 'wb') as f:
                f.write(docx_bytes)

            print(f"✓ Generated: {args.output}")
        except Exception as e:
            print(f"Generation failed: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
