"""Markdown and JSON report rendering."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Category, ClassifiedTask, ScanResult, TaskSummary


def task_brief(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "name": task.get("name"),
        "status": task.get("status"),
        "agentType": task.get("agentType"),
        "directory": task.get("directory"),
        "isPinned": task.get("isPinned"),
        "needsResume": task.get("needsResume"),
        "lastActivityAt": task.get("lastActivityAt"),
    }


def render_report_markdown(summary: TaskSummary) -> str:
    lines = [
        "# Cockpit GC Report",
        "",
        f"- Total tasks: {summary.total}",
        f"- Needs resume: {summary.needs_resume}",
        f"- Pinned: {summary.pinned}",
        f"- Autorun/terminal waiting candidates: {summary.autorun_waiting}",
        f"- Completed tasks older than 30 days: {summary.old_completed_30d}",
        f"- Completed tasks older than 90 days: {summary.old_completed_90d}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in summary.by_status.items():
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This report is read-only. No tasks were completed or removed.",
            "",
        ]
    )
    return "\n".join(lines)


def render_scan_markdown(result: ScanResult) -> str:
    summary = result.summary
    lines = [
        "# Cockpit GC Scan",
        "",
        "## Summary",
        "",
        f"- Total tasks: {summary.total}",
        f"- Needs resume: {summary.needs_resume}",
        f"- Pinned: {summary.pinned}",
        f"- Autorun/terminal waiting: {summary.autorun_waiting}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in summary.by_status.items():
        lines.append(f"- `{status}`: {count}")

    lines.extend(["", "## Category Counts", ""])
    for category, count in result.category_counts.items():
        lines.append(f"- `{category}`: {count}")

    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in result.warnings:
            lines.append(f"- {warning}")

    if result.orphans:
        lines.extend(["", "## Orphan Processes (detect only)", ""])
        for orphan in result.orphans[:20]:
            rss = f"{orphan.rss_kb} KB" if orphan.rss_kb is not None else "unknown RSS"
            lines.append(f"- pid {orphan.pid} ({orphan.kind}, {rss}): `{orphan.command[:120]}`")
        if len(result.orphans) > 20:
            lines.append(f"- ... and {len(result.orphans) - 20} more")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Read-only scan. No tasks were completed, removed, or processes killed.",
            "",
        ]
    )
    return "\n".join(lines)


def _group_by_category(classified: list[ClassifiedTask]) -> dict[str, list[ClassifiedTask]]:
    grouped: dict[str, list[ClassifiedTask]] = {category.value: [] for category in Category}
    for item in classified:
        grouped[item.category.value].append(item)
    return grouped


def render_plan_markdown(
    classified: list[ClassifiedTask],
    *,
    limit_per_category: int = 25,
) -> str:
    grouped = _group_by_category(classified)
    lines = [
        "# Cockpit GC Plan",
        "",
        "Cleanup candidates by category. Read-only; nothing was executed.",
        "",
    ]

    order = [
        Category.SAFE_TO_COMPLETE,
        Category.SAFE_TO_REMOVE,
        Category.NEEDS_SUMMARY,
        Category.HEAVY_HISTORY,
        Category.ACTIVE,
    ]
    for category in order:
        items = grouped[category.value]
        lines.extend([f"## {category.value} ({len(items)})", ""])
        if not items:
            lines.append("- (none)")
            lines.append("")
            continue
        for item in items[:limit_per_category]:
            task = item.task
            name = str(task.get("name", "")).replace("\n", " ")[:80]
            lines.append(
                f"- `{task.get('id')}` [{task.get('status')}] {name} — {item.reason}"
            )
        if len(items) > limit_per_category:
            lines.append(f"- ... and {len(items) - limit_per_category} more")
        lines.append("")

    return "\n".join(lines)


def scan_to_json(result: ScanResult) -> dict[str, Any]:
    return {
        "cockpit_running": result.cockpit_running,
        "summary": {
            "total": result.summary.total,
            "by_status": result.summary.by_status,
            "needs_resume": result.summary.needs_resume,
            "pinned": result.summary.pinned,
            "autorun_waiting": result.summary.autorun_waiting,
            "old_completed_30d": result.summary.old_completed_30d,
            "old_completed_90d": result.summary.old_completed_90d,
        },
        "category_counts": result.category_counts,
        "warnings": result.warnings,
        "orphans": [
            {
                "pid": orphan.pid,
                "kind": orphan.kind,
                "rss_kb": orphan.rss_kb,
                "command": orphan.command,
            }
            for orphan in result.orphans
        ],
    }


def plan_to_json(
    classified: list[ClassifiedTask],
    *,
    limit_per_category: int = 25,
) -> dict[str, Any]:
    grouped = _group_by_category(classified)
    payload: dict[str, Any] = {"categories": {}}
    for category in Category:
        items = grouped[category.value][:limit_per_category]
        payload["categories"][category.value] = [
            {
                "reason": item.reason,
                "heavy": item.heavy,
                "task": task_brief(item.task),
            }
            for item in items
        ]
        payload["categories"][f"{category.value}_total"] = len(grouped[category.value])
    return payload


def write_markdown_report(content: str, output_dir: Path, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{prefix}-{stamp}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_json_report(payload: dict[str, Any], output_dir: Path, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"{prefix}-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
