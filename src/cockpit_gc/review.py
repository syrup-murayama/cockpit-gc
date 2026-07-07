"""Interactive review helpers for safe-to-complete and waiting_confirmation tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .classify import looks_like_worktree
from .models import Category, ClassifiedTask
from .time_utils import age_days

LABEL_NAME_MAX = 55
SNIPPET_MAX = 80
LABEL_ID_SEPARATOR = " · "
IMPLEMENTATION_AGENTS = frozenset({"claude", "codex", "cursor", "antigravity"})


def review_candidates(
    classified: list[ClassifiedTask],
    category: Category = Category.SAFE_TO_COMPLETE,
    limit: int = 20,
) -> list[ClassifiedTask]:
    items = [item for item in classified if item.category == category]
    return items[:limit]


def _compact_name(name: str) -> str:
    collapsed = " ".join(name.split())
    if len(collapsed) <= LABEL_NAME_MAX:
        return collapsed
    return collapsed[: LABEL_NAME_MAX - 1] + "…"


def _compact_snippet(snippet: str) -> str:
    collapsed = " ".join(snippet.split())
    if len(collapsed) <= SNIPPET_MAX:
        return collapsed
    return collapsed[: SNIPPET_MAX - 1] + "…"


def format_age_label(task: dict, now: datetime) -> str:
    days = age_days(task, now)
    if days is None:
        return "日付不明"
    if days == 0:
        return "今日"
    if days == 1:
        return "1日前"
    return f"{days}日前"


def compact_task_label(
    item: ClassifiedTask,
    snippet: str | None = None,
    *,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    task = item.task
    task_id = str(task.get("id", ""))
    name = _compact_name(str(task.get("name", "")))
    agent_type = str(task.get("agentType", ""))

    parts = [agent_type, format_age_label(task, now)]

    directory = str(task.get("directory", ""))
    if directory:
        dir_name = Path(directory).name
        if dir_name:
            parts.append(dir_name)

    parent_id = task.get("parentMasterId") or task.get("parentTaskId")
    if parent_id:
        parts.append(f"parent:{str(parent_id)[:8]}")

    label = f"{name} — {' / '.join(parts)}"
    if snippet:
        label = f"{label} / last: {_compact_snippet(snippet)}"
    return f"{label}{LABEL_ID_SEPARATOR}{task_id}"


def is_waiting_review_candidate(
    task: dict[str, Any],
    now: datetime,
    *,
    stale_days: int,
    include_needs_resume: bool,
    include_master: bool,
) -> bool:
    if task.get("status") != "waiting_confirmation":
        return False
    if task.get("isPinned"):
        return False
    if looks_like_worktree(task):
        return False
    if task.get("isMaster") and not include_master:
        return False
    if task.get("needsResume") and not include_needs_resume:
        return False

    days = age_days(task, now)
    if days is None or days < stale_days:
        return False
    return True


def waiting_review_candidates(
    tasks: list[dict[str, Any]],
    classified: list[ClassifiedTask],
    *,
    now: datetime | None = None,
    stale_days: int = 3,
    include_needs_resume: bool = False,
    include_master: bool = False,
    limit: int = 30,
) -> list[ClassifiedTask]:
    now = now or datetime.now(timezone.utc)
    classified_by_id = {item.task.get("id"): item for item in classified}

    eligible: list[ClassifiedTask] = []
    for task in tasks:
        if not is_waiting_review_candidate(
            task,
            now,
            stale_days=stale_days,
            include_needs_resume=include_needs_resume,
            include_master=include_master,
        ):
            continue
        item = classified_by_id.get(task.get("id"))
        if item is None:
            item = ClassifiedTask(task, Category.ACTIVE, "unclassified", heavy=False)
        eligible.append(item)

    eligible.sort(key=lambda item: age_days(item.task, now) or 0, reverse=True)
    return eligible[:limit]


def waiting_summary_flag(task: dict[str, Any], classified: ClassifiedTask | None) -> bool:
    if classified is not None and classified.category == Category.NEEDS_SUMMARY:
        return True
    return str(task.get("agentType", "")) in IMPLEMENTATION_AGENTS


def compact_waiting_label(
    task: dict[str, Any],
    *,
    classified: ClassifiedTask | None = None,
    snippet: str | None = None,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    task_id = str(task.get("id", ""))
    name = _compact_name(str(task.get("name", "")))
    agent_type = str(task.get("agentType", ""))

    parts = [agent_type, format_age_label(task, now)]

    directory = str(task.get("directory", ""))
    if directory:
        dir_name = Path(directory).name
        if dir_name:
            parts.append(dir_name)

    if task.get("needsResume"):
        parts.append("resume")
    if task.get("isMaster"):
        parts.append("master")
    if task.get("parentMasterId") or task.get("parentTaskId"):
        parts.append("child")
    if waiting_summary_flag(task, classified):
        parts.append("summary")

    label = f"{name} — {' / '.join(parts)}"
    if snippet:
        label = f"{label} / last: {_compact_snippet(snippet)}"
    return f"{label}{LABEL_ID_SEPARATOR}{task_id}"


def task_id_from_label(label: str) -> str:
    if LABEL_ID_SEPARATOR not in label:
        return label.strip()
    return label.rsplit(LABEL_ID_SEPARATOR, 1)[-1].strip()


def labels_to_task_ids(labels: list[str]) -> list[str]:
    return [task_id_from_label(label) for label in labels]


def render_checklist(
    labels: list[str],
    *,
    title: str = "Safe-to-complete review",
) -> str:
    lines = [
        f"# {title}",
        "",
        f"{len(labels)} candidate(s). Read-only checklist; use --ask to select interactively.",
        "",
    ]
    for label in labels:
        lines.append(f"- [ ] {label}")
    lines.append("")
    return "\n".join(lines)


def format_planned_completes(task_ids: list[str]) -> str:
    lines = ["Selected task IDs:"]
    if task_ids:
        for task_id in task_ids:
            lines.append(f"- {task_id}")
    else:
        lines.append("- (none)")

    lines.extend(["", "Planned commands:"])
    if task_ids:
        for task_id in task_ids:
            lines.append(f"- cockpit task complete {task_id}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)
