---
name: cockpit-gc
description: Diagnose AGI Cockpit task backlog and cleanup candidates with the local cockpit-gc CLI. Use when the user says Cockpit feels heavy, wants GC/cleanup, has too many waiting_confirmation tasks, opencode serve buildup, or wants to organize old tasks without auto-deleting anything. Supports read-only scan/plan plus explicitly approved interactive completion.
---

# Cockpit GC

Use the local `cockpit-gc` CLI from `/path/to/cockpit-gc` for diagnosis and carefully approved cleanup.

## Safety rules

1. **Never** run `cockpit task complete`, `remove`, `send`, `resume`, `goto`, `pin`, or `unpin` unless the user explicitly approves specific task IDs.
2. **Never** kill processes (`kill`, `pkill`, `killall`). `scan` may list orphan `opencode serve` processes; report only.
3. Before any `cockpit` CLI call, confirm AGI Cockpit is already running. The CLI refuses to auto-start Cockpit.
4. `cockpit-gc apply` is intentionally unimplemented.

## Workflow

From the repo root (`/path/to/cockpit-gc`):

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
PYTHONPATH=src python3 -m cockpit_gc plan
PYTHONPATH=src python3 -m cockpit_gc review-complete
PYTHONPATH=src python3 -m cockpit_gc review-waiting
PYTHONPATH=src python3 -m cockpit_gc report
```

Optional flags: `--json`, `--write`, `--output-dir reports`, `plan --limit N`.

For interactive completion of autorun/terminal waiting tasks:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-complete              # read-only checklist
PYTHONPATH=src python3 -m cockpit_gc review-complete --ask        # checkbox selection only
PYTHONPATH=src python3 -m cockpit_gc review-complete --ask --apply  # complete selected IDs
PYTHONPATH=src python3 -m cockpit_gc review-complete --with-snippet --ask
```

For broader stale `waiting_confirmation` cleanup review:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --ask
PYTHONPATH=src python3 -m cockpit_gc review-waiting --ask --apply
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask --apply
```

`review-complete` never includes `safe-to-remove`. `review-waiting` excludes pinned, worktree, recent, and by default master / needsResume tasks. Use `review-waiting --include-needs-resume --ask --apply` only when the user explicitly asks to review stopped sessions too and complete the checkbox-selected IDs.

## How to respond

1. Run `scan` first. Summarize totals, `waiting_confirmation` vs budget (20), pinned vs budget (5), orphan processes, and warnings.
2. Run `plan` and present categories:
   - `safe-to-complete` — use `review-complete` for a compact checklist, or `review-complete --ask --apply` only after explicit user approval
   - `waiting_confirmation` backlog — use `review-waiting --stale-days 7` for a broader read-only checklist; include `--include-needs-resume` when the user wants to review stopped sessions too
   - `safe-to-remove` — suggest remove only for tests/tmp/empty/duplicates
   - `needs-summary` — ask user to capture learnings into files before complete
   - `active` / `heavy-history` — do not touch without user direction
3. Propose next actions as a short numbered list. Wait for explicit approval before any mutating Cockpit command.

## Common approved cleanup command

If the user explicitly says to proceed with the recent interactive cleanup flow, run:

```bash
cd /path/to/cockpit-gc
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask --apply
```

This command still uses checkbox selection; it completes only task IDs selected in the Cockpit ask dialog.

## Operating principles

- Tasks are sessions; durable knowledge belongs in `CURRENT_TASK.md`, docs, commits, or README.
- Prefer **complete** over **remove**. Remove only low-value test/tmp/duplicate tasks.
- Child tasks can be completed after the parent received a summary.
- Implementation tasks can be completed after merge/abandon is decided.

For category heuristics, read [references/categories.md](references/categories.md) only when explaining a classification decision.
