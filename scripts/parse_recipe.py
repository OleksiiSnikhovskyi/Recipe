#!/usr/bin/env python3
"""
parse_recipe.py

AI-powered recipe extraction from YouTube video description.
Accepts unstructured text and returns structured recipe JSON.

Usage:
    python parse_recipe.py --input "description text" --model ollama:qwen3:8b

    or as HTTP endpoint:
    POST /extract
    {"description": "...", "video_id": "...", "youtube_channel": "..."}
"""

import json
import sys
import argparse
import requests
from datetime import datetime
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://100.81.127.54:11434")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")


def extract_recipe_ollama(description: str, video_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract recipe using Ollama local model.

    Args:
        description: YouTube video description text
        video_metadata: Dict with video_id, youtube_channel, video_url, thumbnail_url

    Returns:
        Structured recipe JSON
    """

    # System prompt for recipe extraction
    system_prompt = """You are a professional recipe extraction specialist.
Extract a complete, structured recipe from the provided YouTube video description.

Rules:
1. Recipe must be in Ukrainian (Українська мова)
2. Output must be valid JSON matching the provided schema
3. Automatically detect category based on recipe content
4. All steps must be numbered sequentially
5. Include ingredients with quantities
6. Clean and structure the text: remove filler, reorganize steps logically
7. Estimate nutrition data if not provided

Valid categories: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше

Return ONLY valid JSON, no markdown formatting, no explanations."""

    user_prompt = f"""Extract recipe from this YouTube description:

{description}

Return this JSON structure:
{{
  "title": "Recipe name in Ukrainian",
  "category": "One of the valid categories",
  "servings": number,
  "prep_time_minutes": number or null,
  "cook_time_minutes": number or null,
  "ingredients": [
    {{"name": "...", "quantity": number, "unit": "...", "notes": "..."}}
  ],
  "steps": [
    {{"step_number": number, "instruction": "...", "duration_minutes": number or null}}
  ],
  "nutrition": {{
    "per_100g": {{"calories": number, "protein": number, "fat": number, "carbohydrates": number}},
    "per_serving": {{"calories": number, "protein": number, "fat": number, "carbohydrates": number}}
  }}
}}"""

    try:
        # Call Ollama API
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        content = result["message"]["content"]

        # Parse JSON from response
        try:
            recipe_data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            recipe_data = json.loads(content)

        # Enrich with video metadata
        recipe_data["source"] = {
            "video_id": video_metadata.get("video_id"),
            "video_url": video_metadata.get("video_url"),
            "youtube_channel": video_metadata.get("youtube_channel"),
            "youtube_channel_url": video_metadata.get("youtube_channel_url"),
            "thumbnail_url": video_metadata.get("thumbnail_url"),
            "published_date": video_metadata.get("published_date")
        }

        recipe_data["metadata"] = {
            "video_id": video_metadata.get("video_id"),
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "extraction_method": f"ollama:{OLLAMA_MODEL}",
            "language": "uk"
        }

        return recipe_data

    except Exception as e:
        print(f"Error calling Ollama: {str(e)}", file=sys.stderr)
        raise


def extract_recipe_openai(description: str, video_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract recipe using OpenAI API.

    Args:
        description: YouTube video description text
        video_metadata: Dict with video metadata

    Returns:
        Structured recipe JSON
    """

    try:
        import openai
    except ImportError:
        print("Error: OpenAI library not installed. Install with: pip install openai", file=sys.stderr)
        sys.exit(1)

    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    system_prompt = """You are a professional recipe extraction specialist.
Extract a complete, structured recipe from the provided YouTube video description.
Return ONLY valid JSON matching the schema provided, with no markdown formatting."""

    user_prompt = f"""Extract recipe from this YouTube description:

{description}

Return this JSON structure:
{{
  "title": "Recipe name in Ukrainian",
  "category": "One of: Перші страви, Другі страви, Салати, Закуски, Випічка, Десерти, Напої, Інше",
  "servings": number,
  "prep_time_minutes": number or null,
  "cook_time_minutes": number or null,
  "ingredients": [
    {{"name": "...", "quantity": number, "unit": "...", "notes": "..."}}
  ],
  "steps": [
    {{"step_number": number, "instruction": "...", "duration_minutes": number or null}}
  ],
  "nutrition": {{
    "per_100g": {{"calories": number, "protein": number, "fat": number, "carbohydrates": number}},
    "per_serving": {{"calories": number, "protein": number, "fat": number, "carbohydrates": number}}
  }}
}}"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        content = response.choices[0].message.content
        recipe_data = json.loads(content)

        # Enrich with metadata
        recipe_data["source"] = {
            "video_id": video_metadata.get("video_id"),
            "video_url": video_metadata.get("video_url"),
            "youtube_channel": video_metadata.get("youtube_channel"),
            "youtube_channel_url": video_metadata.get("youtube_channel_url"),
            "thumbnail_url": video_metadata.get("thumbnail_url"),
            "published_date": video_metadata.get("published_date")
        }

        recipe_data["metadata"] = {
            "video_id": video_metadata.get("video_id"),
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "extraction_method": f"openai:{OPENAI_MODEL}",
            "language": "uk"
        }

        return recipe_data

    except Exception as e:
        print(f"Error calling OpenAI: {str(e)}", file=sys.stderr)
        raise


def extract_recipe(description: str, video_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main extraction function. Routes to appropriate LLM provider.
    """

    if LLM_PROVIDER == "openai":
        return extract_recipe_openai(description, video_metadata)
    else:
        return extract_recipe_ollama(description, video_metadata)


# =============================================
# HTTP Flask Server (Optional)
# =============================================

def create_flask_app():
    """Create Flask app for HTTP API."""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        return None

    app = Flask(__name__)

    @app.route("/extract", methods=["POST"])
    def extract_endpoint():
        """HTTP endpoint for recipe extraction."""
        try:
            data = request.json
            description = data.get("description", "")

            if not description:
                return jsonify({"error": "description field required"}), 400

            # Build video metadata
            video_metadata = {
                "video_id": data.get("video_id", ""),
                "video_url": data.get("video_url", ""),
                "youtube_channel": data.get("youtube_channel", "Unknown Channel"),
                "youtube_channel_url": data.get("youtube_channel_url", ""),
                "thumbnail_url": data.get("thumbnail_url", ""),
                "published_date": data.get("published_date", "")
            }

            recipe = extract_recipe(description, video_metadata)
            return jsonify(recipe), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"status": "ok", "provider": LLM_PROVIDER}), 200

    return app


# =============================================
# CLI Interface
# =============================================

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="Extract recipe from YouTube description")
    parser.add_argument("--input", "-i", help="Input description text or file path")
    parser.add_argument("--video-id", default="unknown", help="YouTube video ID")
    parser.add_argument("--channel", default="Unknown Channel", help="YouTube channel name")
    parser.add_argument("--server", action="store_true", help="Run as Flask server")
    parser.add_argument("--port", default=5000, type=int, help="Server port (default: 5000)")

    args = parser.parse_args()

    if args.server:
        app = create_flask_app()
        if not app:
            print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
            sys.exit(1)
        print(f"Starting Flask server on port {args.port}...")
        app.run(host="0.0.0.0", port=args.port, debug=False)
    else:
        if not args.input:
            parser.print_help()
            sys.exit(1)

        # Read input from file or command line
        if os.path.isfile(args.input):
            with open(args.input, 'r', encoding='utf-8') as f:
                description = f.read()
        else:
            description = args.input

        # Extract recipe
        video_metadata = {
            "video_id": args.video_id,
            "youtube_channel": args.channel,
            "video_url": f"https://www.youtube.com/watch?v={args.video_id}"
        }

        try:
            recipe = extract_recipe(description, video_metadata)
            print(json.dumps(recipe, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Extraction failed: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
