#!/usr/bin/env python3
"""Deploy Recipe workflows to n8n via the public API."""

from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = PROJECT_DIR / "N8N_WORKFLOW_EXPORTS"
load_dotenv(PROJECT_DIR / ".env")
N8N_BASE = os.environ.get("N8N_BASE_URL", "https://n8n.csc-ua.tech").rstrip("/")
N8N_API_BASE = f"{N8N_BASE}/api/v1"
DEPLOY_ORDER = [
    "WF-01-recipe-monitor-playlist.json",
    "WF-02-recipe-extract-data.json",
    "WF-03-recipe-generate-docx.json",
    "WF-04-recipe-convert-pdf.json",
    "WF-05-recipe-upload-nextcloud.json",
    "WF-06-recipe-telegram-notify.json",
]


def load_workflow(path: Path) -> dict[str, Any]:
    raw_workflow = path.read_text(encoding="utf-8")
    if "__YOUTUBE_API_KEY__" in raw_workflow:
        youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
        if not youtube_api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required to deploy WF-01")
        raw_workflow = raw_workflow.replace("__YOUTUBE_API_KEY__", youtube_api_key)
    workflow = json.loads(raw_workflow)
    payload = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings", {"executionOrder": "v1"}),
    }
    return payload


def find_existing_workflows(client: httpx.Client, headers: dict[str, str]) -> dict[str, dict[str, Any]]:
    response = client.get(f"{N8N_API_BASE}/workflows", headers=headers, params={"limit": 250})
    response.raise_for_status()
    data = response.json()
    workflows = data.get("data", data if isinstance(data, list) else [])
    return {workflow.get("name"): workflow for workflow in workflows if workflow.get("name")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Recipe workflows to n8n")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=DEPLOY_ORDER,
        help="Deploy only the selected workflow export files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("ERROR: N8N_API_KEY is not set", file=sys.stderr)
        return 2

    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    deploy_order = args.only or DEPLOY_ORDER
    missing = [name for name in deploy_order if not (WORKFLOW_DIR / name).exists()]
    if missing:
        print(f"ERROR: missing workflow files: {', '.join(missing)}", file=sys.stderr)
        return 2

    with httpx.Client(timeout=60.0) as client:
        existing_by_name = find_existing_workflows(client, headers)
        results: list[tuple[str, str, str]] = []

        for file_name in deploy_order:
            path = WORKFLOW_DIR / file_name
            payload = load_workflow(path)
            existing = existing_by_name.get(payload["name"])

            if existing:
                workflow_id = existing["id"]
                response = client.put(
                    f"{N8N_API_BASE}/workflows/{workflow_id}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                action = "updated"
            else:
                response = client.post(
                    f"{N8N_API_BASE}/workflows",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                workflow_id = response.json()["id"]
                action = "created"

            results.append((file_name, action, workflow_id))

    for file_name, action, workflow_id in results:
        print(f"{action:7} {workflow_id}  {file_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
