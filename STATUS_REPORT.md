# Recipe Automation Project - Status Report

**Date:** 2026-07-09
**Status:** Stable recovery mode with safe backfill tooling.

## Current Checkpoint - 2026-07-09

Database is normalized after Nextcloud recovery:

| Metric | Count |
|---|---:|
| Recipes total | 173 |
| Recipes processed | 173 |
| Missing DOCX | 0 |
| Missing PDF | 0 |
| Missing Nextcloud DOCX | 0 |
| Missing Nextcloud PDF | 0 |
| `video_log completed` | 173 |
| `video_log skipped` | 278 |
| `video_log failed` | 0 |
| `video_log processing` | 0 |

`WF-05` was updated to normalize Nextcloud paths before upload/share. This fixed failures caused by special characters such as `#`, emoji, punctuation, and long filenames.

New safe backfill tooling:

- `scripts/safe_playlist_backfill.py`
- minimum delay between processed videos: `10` seconds;
- recommended production delay: `300`-`600` seconds;
- completed recipes are skipped by default;
- bad transcript reprocessing is opt-in via `--reprocess-bad-transcripts`;
- dry-run is supported and should be used first.

## Executive Summary

The main Recipe pipeline is structurally working. The project remains conservative around YouTube access because of the previous rate-limit/IP-block incident.

What happened:

- `WF-08` full playlist backfill was launched too aggressively.
- YouTube started blocking transcript/audio requests from the Markiz IP.
- n8n received a storm of webhook executions and became unstable for a while.
- Many recipes were created from description-only fallback instead of real transcript/audio.
- Some Python services were later found offline after restart/recovery.

Current operating rule:

- Do not run `WF-08`.
- Do not run aggressive YouTube backfill from Markiz.
- Use `scripts/safe_playlist_backfill.py` for controlled playlist work.
- Reprocess bad transcriptions only in small batches with long delays.

## Last Known Database Snapshot

Last confirmed full DB snapshot from 2026-07-04:

| Metric | Count |
|---|---:|
| Recipes total | 173 |
| Processed / uploaded | 66 |
| Not processed | 107 |
| `transcription_warning` | 120 |
| `transcript_source = description_only` | 120 |
| `missing_or_short_transcript` | 120 |
| `video_log completed` | 59 |
| `video_log failed` | 171 |
| `video_log processing` | 221 |

All `processing` records were stale at that point and should be treated as retry candidates, not active work.

## Current Workflow State

Checked on 2026-07-09:

| Workflow | ID | Active | Notes |
|---|---|---:|---|
| `WF-01` | `9QXzE48DP7rcZ0ft` | yes | Daily newest-50 monitor. Should be disabled if services are down or YouTube remains blocked. |
| `WF-02` | `BWXYVoSggcCS2xX6` | yes | Extraction chain works when Python services are up. |
| `WF-03` | webhook `/recipe-docx` | yes | Standalone DOCX generation. |
| `WF-04` | `bIII3NYyZMdEVbdd` | yes | PDF conversion. Needs `5012` service. |
| `WF-05` | `BlhGzvMRKvml1s1k` | yes | Nextcloud upload. Can fail when local files are missing. |
| `WF-07` | `k9A9VLRcUuU9zFBJ` | yes | Telegram search works. |
| `WF-08` | `4mdyTlugsBwpBtW0` | no | Must remain disabled until redesigned slow-mode backfill is ready. |

## Python Services

Required services on Markiz:

| Port | Script | Purpose |
|---:|---|---|
| `5010` | `scripts/parse_recipe.py` | Transcription + LLM recipe extraction |
| `5011` | `scripts/generate_docx.py` | DOCX generation |
| `5012` | `scripts/pdf_converter.py` | PDF conversion through LibreOffice |
| `5013` | `scripts/nextcloud_uploader.py` | Nextcloud payload helper |

Recovery commands:

```bash
cd /opt/recipe-automation
source venv/bin/activate
mkdir -p logs output/docx output/pdf

nohup python scripts/parse_recipe.py --server --port 5010 > logs/parse_recipe.log 2>&1 &
nohup python scripts/generate_docx.py --server --port 5011 > logs/generate_docx.log 2>&1 &
nohup python scripts/pdf_converter.py --server --port 5012 > logs/pdf_converter.log 2>&1 &
nohup python scripts/nextcloud_uploader.py --server --port 5013 > logs/nextcloud_uploader.log 2>&1 &
```

Verify from host and n8n container:

```bash
curl http://127.0.0.1:5010/health
curl http://127.0.0.1:5011/health
curl http://127.0.0.1:5012/health
curl http://127.0.0.1:5013/health

docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5010/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5011/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5012/health || true"
docker exec -it n8n-docker_n8n_1 sh -c "wget -T 10 -S -O- http://172.18.0.1:5013/health || true"
```

## Latest Recovery Test

Tested `recipe_id = 18`, video `qQULTXDO6bM`:

- `/recipe-extract` succeeded.
- Recipe and transcript were saved.
- DOCX generation succeeded.
- PDF step initially failed because `5012` was offline.
- After `5012` came up, WF-04 still required `docx_path`; a hotfix was implemented locally in `scripts/pdf_converter.py` so PDF conversion can resolve `docx_path` by `recipe_id`.

Local commit:

```text
3e1a8d8 Allow PDF conversion by recipe id
```

This commit still needs to be pushed to GitHub and pulled on Markiz before `recipe-pdf` can be called with only `{"recipe_id": 18}`.

## Known Problems

### YouTube Blocking

Symptoms:

```text
YouTube is blocking requests from your IP
Sign in to confirm you’re not a bot
Use --cookies-from-browser or --cookies
```

Affected records:

- `transcript_source = description_only`
- `transcription_warning IS NOT NULL`
- missing or very short `transcript`

These recipes should be reprocessed later through a safer route:

- Miledy server with different IP.
- VPN from Markiz.
- Browser cookies for `yt-dlp` / transcript extraction.
- Very slow queue with human-like delays.

### n8n Execution Storm

Cause:

- WF-08 self-triggered too quickly across playlist pages.

Current mitigation:

- WF-08 is disabled.
- Do not activate it until redesigned with strict rate limits and backpressure.

### Stale Processing Records

`video_log.status = 'processing'` records from the incident are stale. They should be converted to a retry state or failed state after a backup.

Recommended future migration:

```sql
UPDATE video_log
SET status = 'failed',
    processed = false,
    error_details = COALESCE(error_details, '') || E'\nMarked failed during post-incident cleanup.',
    updated_at = NOW()
WHERE status = 'processing'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

Run this only after confirming no real workflow is processing.

## Next Steps

1. Push and deploy the `pdf_converter.py` hotfix.
2. Restart `5012` on Markiz after `git pull`.
3. Finish `recipe_id = 18`: PDF then Nextcloud upload.
4. Disable or pause `WF-01` until all four Python services run persistently.
5. Create a cleanup migration/report for stale `processing`, failed, and `description_only` records.
6. Design safe reprocess pipeline:
   - one video at a time;
   - large delays;
   - optional Miledy/VPN/cookies;
   - no page storm;
   - no retry storm.

## Security Note

Secrets appeared during interactive setup. After stabilization, rotate exposed `N8N_API_KEY`, database passwords, Telegram tokens, and Nextcloud credentials that were pasted into chat or screenshots.
