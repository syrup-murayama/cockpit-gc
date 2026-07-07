# Repository Guidelines

## Project Structure & Module Organization

This repository contains a small Python CLI for read-only AGI Cockpit cleanup
reporting.

- `src/cockpit_gc/` contains the application code.
- `src/cockpit_gc/cli.py` implements the command-line interface and reporting logic.
- `reports/` stores generated Markdown reports; report files are ignored by Git.
- `docs/` is reserved for design notes and operational documentation.
- `pyproject.toml` defines package metadata and future test configuration.

Keep new source modules under `src/cockpit_gc/`. Add tests under `tests/` when
behavior becomes large enough to need regression coverage.

## Build, Test, and Development Commands

- `PYTHONPATH=src python3 -m cockpit_gc report`  
  Runs the read-only report command and prints a summary.
- `PYTHONPATH=src python3 -m cockpit_gc report --write`  
  Writes a Markdown report under `reports/`.
- `python3 -m compileall src`  
  Checks that Python files compile.
- `python3 -m pytest`  
  Runs tests once a `tests/` directory exists.

This project currently has no external runtime dependencies.

## Coding Style & Naming Conventions

Use Python 3.10+ with standard-library APIs only unless a dependency is clearly
justified. Follow PEP 8 conventions: 4-space indentation, snake_case functions,
PascalCase classes, and uppercase constants. Keep functions small and explicit.

Commands should be safe by default. Any future command that mutates Cockpit state
must require an explicit `--apply` flag and should offer a dry-run mode.

## Testing Guidelines

Prefer deterministic unit tests for classification, date handling, and report
rendering. Avoid tests that require a live Cockpit instance unless clearly marked
as integration tests. Name test files `tests/test_*.py` and test functions
`test_*`.

## Commit & Pull Request Guidelines

There is no established Git history yet. Use concise imperative commit messages,
for example `Add read-only report command` or `Classify autorun waiting tasks`.

Pull requests should describe the behavior change, list verification commands,
and call out any command that can modify Cockpit tasks. Include before/after
report snippets when classification rules change.

## Security & Configuration Tips

Do not let the Cockpit CLI auto-start the app unintentionally. Check
`~/.agi-tools/data/cockpit/cli-runtime.json` and verify the PID is alive before
calling `cockpit`. Never complete or remove tasks without explicit user approval.
