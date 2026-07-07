"""Diagnostics: task scan and orphan process detection."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone

from .classify import category_counts, classify_tasks, summarize
from .models import (
    PINNED_BUDGET,
    WAITING_CONFIRMATION_BUDGET,
    OrphanProcess,
    ScanResult,
)


ORPHAN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)opencode\s+serve\b", re.IGNORECASE), "opencode-serve"),
    (re.compile(r"AGI Cockpit Helper \(Renderer\)", re.IGNORECASE), "cockpit-renderer"),
]


def _parse_ps_rss(fields: list[str]) -> int | None:
    if len(fields) < 6:
        return None
    try:
        return int(fields[5])
    except ValueError:
        return None


def scan_orphan_processes() -> list[OrphanProcess]:
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,rss=,command="],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    orphans: list[OrphanProcess] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"(\d+)\s+(\d+)\s+(.*)", line)
        if not match:
            continue
        pid = int(match.group(1))
        rss_kb = int(match.group(2))
        command = match.group(3)
        for pattern, kind in ORPHAN_PATTERNS:
            if pattern.search(command):
                orphans.append(
                    OrphanProcess(pid=pid, kind=kind, command=command, rss_kb=rss_kb)
                )
                break
    return orphans


def build_warnings(summary, classified, orphans: list[OrphanProcess]) -> list[str]:
    warnings: list[str] = []
    waiting = summary.by_status.get("waiting_confirmation", 0)
    if waiting > WAITING_CONFIRMATION_BUDGET:
        warnings.append(
            f"waiting_confirmation is {waiting} (budget {WAITING_CONFIRMATION_BUDGET})"
        )
    if summary.pinned > PINNED_BUDGET:
        warnings.append(f"pinned tasks are {summary.pinned} (budget {PINNED_BUDGET})")
    if summary.needs_resume > 0:
        warnings.append(f"{summary.needs_resume} tasks need resume")

    orphan_kinds = {item.kind for item in orphans}
    if "opencode-serve" in orphan_kinds:
        count = sum(1 for item in orphans if item.kind == "opencode-serve")
        total_rss = sum(item.rss_kb or 0 for item in orphans if item.kind == "opencode-serve")
        warnings.append(
            f"detected {count} opencode serve process(es) (~{total_rss // 1024} MB RSS total)"
        )

    heavy = sum(1 for item in classified if item.heavy)
    if heavy:
        warnings.append(f"{heavy} tasks look heavy by list metadata")

    return warnings


def run_scan(tasks: list[dict], now: datetime | None = None) -> ScanResult:
    now = now or datetime.now(timezone.utc)
    classified = classify_tasks(tasks, now)
    summary = summarize(tasks, now)
    orphans = scan_orphan_processes()
    warnings = build_warnings(summary, classified, orphans)
    return ScanResult(
        cockpit_running=True,
        summary=summary,
        classified=classified,
        orphans=orphans,
        warnings=warnings,
        category_counts=category_counts(classified),
    )
