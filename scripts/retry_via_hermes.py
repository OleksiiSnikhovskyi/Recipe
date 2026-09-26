#!/usr/bin/env python3
"""
Retry files that failed extraction during the main OneDrive import — mostly
files that hit a Miledy outage — using the Hermes escalation model instead.

Hermes runs on separate hardware from Miledy (see .claude/CLAUDE.md §2, §5.1),
so this is designed to run concurrently with an ongoing Miledy-based batch
without violating the sequential-execution rule: each machine still does its
own work sequentially, they just don't share one queue.

Routes both the multi-recipe split step and the extraction call to Hermes by
monkeypatching parse_recipe's provider config before calling the same
process_one() pipeline the main import script uses.

Usage:
    python scripts/retry_via_hermes.py --log logs/onedrive_import_progress.jsonl
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent.parent / ".env")  # HERMES_* lives in NA10 root .env

import requests

import parse_recipe
import import_onedrive_recipes as importer

HERMES_BASE_URL = os.getenv("HERMES_BASE_URL", "").rstrip("/")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "")
HERMES_MODEL = os.getenv("HERMES_MODEL", "")


def route_to_hermes() -> None:
    parse_recipe.LLM_PROVIDER = "openai"
    parse_recipe.OPENAI_API_KEY = HERMES_API_KEY
    parse_recipe.OPENAI_MODEL = HERMES_MODEL
    parse_recipe.OPENAI_BASE_URL = HERMES_BASE_URL


def split_via_hermes(text: str) -> list:
    """Same contract as import_onedrive_recipes.split_into_recipe_sections,
    routed to Hermes's OpenAI-compatible chat endpoint instead of Ollama."""
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
            HERMES_BASE_URL + "/chat/completions",
            headers={"Authorization": f"Bearer {HERMES_API_KEY}"},
            json={"model": HERMES_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
            timeout=parse_recipe.OPENAI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = parse_recipe._parse_json_response(content)
        sections = [s.strip() for s in data.get("sections", []) if isinstance(s, str) and s.strip()]
        if sections:
            return sections
    except Exception:
        pass
    return [text]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default="logs/onedrive_inventory.json")
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    if not (HERMES_BASE_URL and HERMES_API_KEY and HERMES_MODEL):
        print("HERMES_BASE_URL / HERMES_API_KEY / HERMES_MODEL not fully set — nothing to do.", file=sys.stderr)
        sys.exit(1)

    route_to_hermes()
    importer.split_into_recipe_sections = split_via_hermes

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    print(f"Retrying against Hermes ({HERMES_MODEL}); scanning {len(inventory)} files for incomplete ones.")

    counts = {}
    with Path(args.log).open("a", encoding="utf-8") as log_file:
        for index, item in enumerate(inventory, start=1):
            results = importer.process_one(item, force=False)
            for result in results:
                counts[result["status"]] = counts.get(result["status"], 0) + 1
                log_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                log_file.flush()
            statuses = ",".join(r["status"] for r in results)
            print(f"[{index}/{len(inventory)}] {statuses}: {item['filename']}")

    print("\n=== Summary ===")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
