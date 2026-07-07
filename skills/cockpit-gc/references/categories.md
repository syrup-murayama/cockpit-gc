# Classification reference

Categories are exclusive; first matching rule wins.

## active

- `running`, `isPinned`, `needsResume`, `isMaster`
- worktree paths (`/.worktrees/`, `worktree` in directory/instruction)
- last activity within 7 days

## safe-to-remove

- `TASK_RUN_RESPONSE_SHAPE_TEST` in name
- empty name and instruction
- `/tmp/agi-cockpit` or `/T/agi-cockpit` directories
- obvious test/duplicate/startup-failure markers

## safe-to-complete

- `waiting_confirmation` only
- autorun/terminal/`日次`/watcher tasks
- terminal agent waiting
- stale autorun waiting 14+ days
- `--resume` one-off shell tasks

## needs-summary

- `waiting_confirmation` on codex/claude/cursor/antigravity agents with activity 3+ days ago
- other `waiting_confirmation` without a stronger signal

## heavy-history

- instruction > 2000 chars or name > 200 chars (metadata estimate from task list)
- `completed` 90+ days ago (archive review)

## orphan-process (scan only)

- `opencode serve` and Cockpit Renderer processes detected via `ps`
- detection only; never kill from this tool
