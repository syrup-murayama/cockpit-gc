# cockpit-gc

[日本語版 README](README_JA.md)

Read-only AGI Cockpit task cleanup reporter, planner, and review helper.

`cockpit-gc` is a small Python CLI plus Codex skill for people who use AGI
Cockpit long enough for task history to pile up. It helps answer:

- How many tasks are still waiting?
- Which old tasks are probably just stale sessions?
- Which completed/tmp tasks look safe to archive or remove later?
- Which candidates should a human review before completing?

The tool is intentionally conservative: it scans and plans first, and only
changes Cockpit task state when an explicit `--apply` flow is used.

## Requirements

- macOS
- AGI Cockpit installed
- `cockpit` CLI available in `PATH`
- Python 3.10+
- Cockpit app already running

No Python package dependencies are required.

## Install

Clone the repository:

```bash
git clone <repo-url>
cd cockpit-gc
```

Run commands with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
```

Optional: install the Codex skill locally:

```bash
mkdir -p ~/.codex/skills/cockpit-gc
rsync -a skills/cockpit-gc/ ~/.codex/skills/cockpit-gc/
```

Then start a new Codex session and invoke:

```text
$cockpit-gc scan my Cockpit backlog
```

## Commands

```bash
PYTHONPATH=src python3 -m cockpit_gc report   # legacy summary
PYTHONPATH=src python3 -m cockpit_gc scan     # health scan (Markdown default, --json)
PYTHONPATH=src python3 -m cockpit_gc plan       # categorized cleanup candidates
PYTHONPATH=src python3 -m cockpit_gc review-complete  # safe-to-complete checklist (read-only)
PYTHONPATH=src python3 -m cockpit_gc review-waiting   # stale waiting_confirmation checklist (read-only)
PYTHONPATH=src python3 -m cockpit_gc apply    # not implemented by design
```

Use `--write` to save under `reports/`.

## Common Workflow

Start read-only:

```bash
PYTHONPATH=src python3 -m cockpit_gc scan
PYTHONPATH=src python3 -m cockpit_gc plan
```

Review stale waiting tasks without changing anything:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --with-snippet --ask
```

If you intentionally want to complete selected tasks, use the interactive
checkbox flow with `--apply`:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask --apply
```

`review-complete` shows only `safe-to-complete` candidates. Without `--ask`, it prints a Markdown checklist and makes no changes. With `--ask`, it uses `cockpit ask --multiple` for checkbox selection. With `--ask --apply`, it completes only the selected task IDs.

`review-waiting` reviews broader stale `waiting_confirmation` tasks (default: last activity at least 3 days ago). Use `--include-needs-resume` to include tasks that need resume. It follows the same read-only / `--ask` / `--ask --apply` safety model as `review-complete`.

```bash
PYTHONPATH=src python3 -m cockpit_gc review-complete
PYTHONPATH=src python3 -m cockpit_gc review-complete --limit 10
PYTHONPATH=src python3 -m cockpit_gc review-complete --ask
PYTHONPATH=src python3 -m cockpit_gc review-complete --ask --apply
PYTHONPATH=src python3 -m cockpit_gc review-complete --with-snippet --ask

PYTHONPATH=src python3 -m cockpit_gc review-waiting
PYTHONPATH=src python3 -m cockpit_gc review-waiting --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --with-snippet --ask
PYTHONPATH=src python3 -m cockpit_gc review-waiting --ask --apply
```

## Safety

- Default is read-only.
- Cockpit must already be running; the CLI checks `~/.agi-tools/data/cockpit/cli-runtime.json` PID before calling `cockpit`.
- `review-complete` changes Cockpit state only with both `--ask` and `--apply`, and only for checkbox-selected task IDs.
- `review-waiting` follows the same rule. Prefer reviewing with `--stale-days` before broad cleanup.
- `cockpit-gc apply` is intentionally not implemented.
- Never complete or remove tasks without explicit `--apply` and human review.
- The tool may list orphan processes, but it never kills them.

## Codex Skill

Agent guidance lives in `skills/cockpit-gc/SKILL.md`. The skill tells Codex to
run `scan` first, summarize the backlog, and avoid mutating commands until the
user explicitly approves selected task IDs.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Status

This is an early local workflow tool shared as a code sample. Treat it as
alpha-quality and run the read-only commands first.
