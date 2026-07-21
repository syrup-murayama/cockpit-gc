# cockpit-gc

[日本語版 README](README_JA.md)

Conservative AGI Cockpit task cleanup reporter, planner, and review helper.

`cockpit-gc` is a small Python CLI plus Codex skill for people who use AGI
Cockpit long enough for task history to pile up. It helps answer:

- How many tasks are still waiting?
- Which old tasks are probably just stale sessions?
- Which completed/tmp tasks look safe to archive or remove later?
- Which candidates should a human review before completing?

The tool is intentionally conservative: it scans and plans first. Interactive
cleanup is a two-phase flow because `cockpit ask` resolves asynchronously:
`--ask` schedules the checkbox dialog and `resolve-ask` applies only the labels
returned by the later `cockpit.ask.resolved` event.

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
PYTHONPATH=src python3 -m cockpit_gc review-remove    # safe-to-remove checklist (read-only)
PYTHONPATH=src python3 -m cockpit_gc resolve-ask ASK_ID --answers-json '...'
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
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --with-snippet
```

To schedule an interactive completion review, run phase 1 with `--ask`:

```bash
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --ask
```

The command prints an `askId` and stores the offered labels in
`.cockpit_gc_state/pending_asks/<askId>.json`. It exits immediately; the Python
process that scheduled the ask cannot receive the later Cockpit event. When the
calling agent receives `cockpit.ask.resolved` as a new turn, pass that event to
phase 2:

```bash
PYTHONPATH=src python3 -m cockpit_gc resolve-ask ask_xxx \
  --answers-json '{"event":"cockpit.ask.resolved","ask_id":"ask_xxx","outcome":"answered","answers":[{"type":"choices","values":["..."]}]}'
```

`resolve-ask` maps only labels saved for that `askId` to task IDs. A dismissed
ask is a no-op. The state file is removed after dismissal or after all selected
tasks have been attempted.

`review-complete` shows only `safe-to-complete` candidates. Without `--ask`, it
prints a Markdown checklist and makes no changes. With `--ask`, it schedules
the asynchronous phase-1 dialog; it does not complete tasks in that process.

`review-waiting` reviews broader stale `waiting_confirmation` tasks (default:
last activity at least 3 days ago). Use `--include-needs-resume` to include
tasks that need resume. It follows the same read-only / phase-1 `--ask` /
phase-2 `resolve-ask` model as `review-complete`.

`review-remove` shows `safe-to-remove` candidates. It has no `--apply` flag;
use `--ask` followed by `resolve-ask` after an explicit checkbox answer.

```bash
PYTHONPATH=src python3 -m cockpit_gc review-complete
PYTHONPATH=src python3 -m cockpit_gc review-complete --limit 10
PYTHONPATH=src python3 -m cockpit_gc review-complete --ask
PYTHONPATH=src python3 -m cockpit_gc review-complete --with-snippet --ask

PYTHONPATH=src python3 -m cockpit_gc review-waiting
PYTHONPATH=src python3 -m cockpit_gc review-waiting --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --stale-days 7 --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --include-needs-resume --limit 50
PYTHONPATH=src python3 -m cockpit_gc review-waiting --with-snippet --ask

PYTHONPATH=src python3 -m cockpit_gc review-remove
PYTHONPATH=src python3 -m cockpit_gc review-remove --limit 10 --ask
```

## Safety

- Default is read-only.
- Cockpit must already be running; the CLI checks `~/.agi-tools/data/cockpit/cli-runtime.json` PID before calling `cockpit`.
- `review-complete` and `review-waiting` `--ask` only schedule an asynchronous dialog and persist its label mapping; they do not change task state.
- `resolve-ask` changes state only for labels returned by an answered Cockpit event. Prefer reviewing with `--stale-days` before broad cleanup.
- `review-remove` uses the same explicit answered-event flow and never removes tasks without selected labels.
- `cockpit-gc apply` is intentionally not implemented.
- Never complete or remove tasks without an explicit checkbox answer and human review.
- The tool may list orphan processes, but it never kills them.

## Codex Skill

Agent guidance lives in `skills/cockpit-gc/SKILL.md`. The skill tells Codex to
run `scan` first, summarize the backlog, and avoid mutating commands until the
user explicitly approves selected task IDs.

## Tests

```bash
python3 -m pytest
```

## Status

This is an early local workflow tool shared as a code sample. Treat it as
alpha-quality and run the read-only commands first.
