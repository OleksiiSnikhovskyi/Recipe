#!/usr/bin/env python3
"""
Build a deduplicated inventory of recipe source files across the three
OneDrive folders the user pointed at. Dedup key is filename (case-folded);
when the same filename appears in multiple folders, the newest mtime wins.

Usage:
    python scripts/onedrive_inventory.py --out /path/to/inventory.json
"""

import argparse
import json
import os
from pathlib import Path

SOURCE_FOLDERS = [
    "/mnt/raid0/OneDrive/My Documents/Рецепты",
    "/mnt/raid0/OneDrive/Документы/Рецепты",
    "/mnt/raid0/OneDrive/Семейные фото и видео/Документы/Рецепты",
]

SUPPORTED_EXTENSIONS = {".docx", ".doc", ".pdf"}


def build_inventory() -> list:
    best_by_key = {}
    for folder in SOURCE_FOLDERS:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            continue
        for entry in folder_path.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            key = entry.name.strip().lower()
            mtime = entry.stat().st_mtime
            candidate = {
                "key": key,
                "filename": entry.name,
                "path": str(entry),
                "folder": folder,
                "mtime": mtime,
                "size": entry.stat().st_size,
            }
            current = best_by_key.get(key)
            if current is None or mtime > current["mtime"]:
                best_by_key[key] = candidate

    return sorted(best_by_key.values(), key=lambda item: item["filename"].lower())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    inventory = build_inventory()
    Path(args.out).write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Deduplicated files: {len(inventory)}")
    by_ext = {}
    for item in inventory:
        ext = Path(item["filename"]).suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
    for ext, count in sorted(by_ext.items()):
        print(f"  {ext}: {count}")


if __name__ == "__main__":
    main()
