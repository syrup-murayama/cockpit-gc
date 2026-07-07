"""Task classification for cleanup planning."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .models import (
    HEAVY_INSTRUCTION_CHARS,
    HEAVY_NAME_CHARS,
    RECENT_DAYS,
    Category,
    ClassifiedTask,
    TaskSummary,
)
from .time_utils import age_days


def looks_like_autorun(task: dict[str, Any]) -> bool:
    agent_type = str(task.get("agentType", ""))
    name = str(task.get("name", ""))
    directory = str(task.get("directory", ""))
    return (
        agent_type == "terminal"
        or "autorun" in name.lower()
        or "日次" in name
        or "dependency-watcher" in name
        or "recovery-warden" in name
        or "/T/agi-cockpit" in directory
        or "/tmp/agi-cockpit" in directory
    )


def looks_like_worktree(task: dict[str, Any]) -> bool:
    directory = str(task.get("directory", ""))
    instruction = str(task.get("instruction", ""))
    return (
        "/.worktrees/" in directory
        or "worktree" in directory.lower()
        or "worktree" in instruction.lower()
    )


def is_heavy_history(task: dict[str, Any]) -> bool:
    instruction = str(task.get("instruction", ""))
    name = str(task.get("name", ""))
    return len(instruction) > HEAVY_INSTRUCTION_CHARS or len(name) > HEAVY_NAME_CHARS


def is_safe_to_remove(task: dict[str, Any]) -> tuple[bool, str]:
    name = str(task.get("name", ""))
    instruction = str(task.get("instruction", ""))
    directory = str(task.get("directory", ""))

    if "TASK_RUN_RESPONSE_SHAPE_TEST" in name:
        return True, "response-shape test task"
    if not name.strip() and not instruction.strip():
        return True, "empty name and instruction"
    if "/tmp/agi-cockpit" in directory or "/T/agi-cockpit" in directory:
        return True, "temporary cockpit workspace"
    if name.strip().lower().startswith("test ") or name.strip().lower().endswith(" test"):
        return True, "test task name"
    if "起動失敗" in name or "startup failed" in name.lower():
        return True, "startup failure task"
    if "duplicate" in name.lower() or "重複" in name:
        return True, "duplicate task marker"
    return False, ""


def is_active(task: dict[str, Any], now: datetime) -> tuple[bool, str]:
    status = task.get("status")
    if status == "running":
        return True, "running"
    if task.get("isPinned"):
        return True, "pinned"
    if task.get("needsResume"):
        return True, "needs resume"
    if task.get("isMaster"):
        return True, "master task"
    if looks_like_worktree(task):
        return True, "worktree task"

    days = age_days(task, now)
    if days is not None and days <= RECENT_DAYS:
        return True, f"recent activity ({days}d)"

    return False, ""


def is_safe_to_complete(task: dict[str, Any], now: datetime) -> tuple[bool, str]:
    status = task.get("status")
    if status != "waiting_confirmation":
        return False, ""

    days = age_days(task, now)

    if looks_like_autorun(task):
        return True, "autorun/terminal waiting for confirmation"
    if str(task.get("agentType", "")) == "terminal":
        return True, "terminal agent waiting for confirmation"
    if (
        days is not None
        and days >= 14
        and looks_like_autorun(task)
    ):
        return True, f"stale autorun waiting ({days}d)"
    if str(task.get("name", "")).startswith("--resume"):
        return True, "resume shell one-off"
    return False, ""


def needs_summary(task: dict[str, Any], now: datetime) -> tuple[bool, str]:
    status = task.get("status")
    if status != "waiting_confirmation":
        return False, ""

    agent_type = str(task.get("agentType", ""))
    if agent_type not in {"codex", "claude", "cursor", "antigravity"}:
        return False, ""

    days = age_days(task, now)
    if days is None or days >= 3:
        return True, "implementation agent waiting; capture summary before complete"
    return False, ""


def classify_task(task: dict[str, Any], now: datetime | None = None) -> ClassifiedTask:
    now = now or datetime.now(timezone.utc)
    heavy = is_heavy_history(task)

    active, active_reason = is_active(task, now)
    if active:
        return ClassifiedTask(task, Category.ACTIVE, active_reason, heavy=heavy)

    removable, remove_reason = is_safe_to_remove(task)
    if removable:
        return ClassifiedTask(task, Category.SAFE_TO_REMOVE, remove_reason, heavy=heavy)

    completable, complete_reason = is_safe_to_complete(task, now)
    if completable:
        return ClassifiedTask(task, Category.SAFE_TO_COMPLETE, complete_reason, heavy=heavy)

    summary_needed, summary_reason = needs_summary(task, now)
    if summary_needed:
        return ClassifiedTask(task, Category.NEEDS_SUMMARY, summary_reason, heavy=heavy)

    if heavy:
        return ClassifiedTask(task, Category.HEAVY_HISTORY, "large instruction or name", heavy=True)

    status = task.get("status")
    if status == "waiting_confirmation":
        return ClassifiedTask(
            task,
            Category.NEEDS_SUMMARY,
            "waiting confirmation without stronger signal",
            heavy=heavy,
        )

    if status == "completed":
        days = age_days(task, now)
        if days is not None and days >= 90:
            return ClassifiedTask(
                task,
                Category.HEAVY_HISTORY,
                f"old completed archive review ({days}d)",
                heavy=heavy,
            )
        return ClassifiedTask(task, Category.ACTIVE, "completed", heavy=heavy)

    return ClassifiedTask(task, Category.ACTIVE, "default keep", heavy=heavy)


def classify_tasks(
    tasks: list[dict[str, Any]], now: datetime | None = None
) -> list[ClassifiedTask]:
    now = now or datetime.now(timezone.utc)
    return [classify_task(task, now) for task in tasks]


def summarize(tasks: list[dict[str, Any]], now: datetime | None = None) -> TaskSummary:
    now = now or datetime.now(timezone.utc)
    by_status = Counter(str(task.get("status", "unknown")) for task in tasks)

    old_completed_30d = 0
    old_completed_90d = 0
    autorun_waiting = 0
    for task in tasks:
        status = task.get("status")
        days = age_days(task, now)
        if status == "completed" and days is not None:
            if days >= 30:
                old_completed_30d += 1
            if days >= 90:
                old_completed_90d += 1
        if status == "waiting_confirmation" and looks_like_autorun(task):
            autorun_waiting += 1

    return TaskSummary(
        total=len(tasks),
        by_status=dict(sorted(by_status.items())),
        needs_resume=sum(1 for task in tasks if task.get("needsResume")),
        pinned=sum(1 for task in tasks if task.get("isPinned")),
        autorun_waiting=autorun_waiting,
        old_completed_30d=old_completed_30d,
        old_completed_90d=old_completed_90d,
    )


def category_counts(classified: list[ClassifiedTask]) -> dict[str, int]:
    counts = Counter(item.category.value for item in classified)
    return dict(sorted(counts.items()))
