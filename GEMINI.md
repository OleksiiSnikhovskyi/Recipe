<!-- NA10-AGENT-RULES:BEGIN (managed by N10 scripts/agents/sync_project_agent_files.py; do not edit) -->
## NA10 rules for Gemini Code Assist (shared by Claude Code, Codex, Gemini Code Assist)

This repository is part of NA10. **Binding rules: `/mnt/raid0/NA10/AGENTS.md` -
read it at the start of every session**, then `/mnt/raid0/NA10/docs/NA10_OPERATING_NOTES.md`.
NA10 project(s) in this repository: `Recipe` (task file `TASKS.md`).

Session protocol (full text in the NA10 AGENTS.md):
- Start: fetch; clean `main`; no other open session/branch/PR on this project;
  read the task file; take the owner's directives:
  `/mnt/raid0/NA10-data/venvs/na10-platform/bin/python /mnt/raid0/NA10/services/na10-platform/scripts/owner_inbox.py list --project <name>`.
- During: local models first for routine bounded subtasks (qwen2.5-coder:14b code,
  qwen3:14b Ukrainian text, gemma4:12b extraction) via
  `python3 /mnt/raid0/NA10/scripts/ask_model.py --target miledy --model <m> --prompt "..."`;
  you review and test; never delegate architecture/security/production decisions.
- Finish (handoff, mandatory): update the task file and its `## Де зупинились`
  note (date, tool, plain Ukrainian); add an entry to `/mnt/raid0/NA10/docs/execution/IMPORT_LOG.md`
  naming the tool and what was delegated to local models; close handled directives with `owner_inbox.py done <id> --note "..."`;
  short-lived branch -> PR -> merged into `main` the same day.
- Commit trailer: `Agent: Gemini Code Assist`. Never print or commit secrets.
<!-- NA10-AGENT-RULES:END -->
