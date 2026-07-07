"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Category(str, Enum):
    ACTIVE = "active"
    NEEDS_SUMMARY = "needs-summary"
    SAFE_TO_COMPLETE = "safe-to-complete"
    SAFE_TO_REMOVE = "safe-to-remove"
    HEAVY_HISTORY = "heavy-history"


RECENT_DAYS = 7
WAITING_CONFIRMATION_BUDGET = 20
PINNED_BUDGET = 5
HEAVY_INSTRUCTION_CHARS = 2000
HEAVY_NAME_CHARS = 200


@dataclass(frozen=True)
class TaskSummary:
    total: int
    by_status: dict[str, int]
    needs_resume: int
    pinned: int
    autorun_waiting: int
    old_completed_30d: int
    old_completed_90d: int


@dataclass(frozen=True)
class ClassifiedTask:
    task: dict[str, Any]
    category: Category
    reason: str
    heavy: bool = False


@dataclass(frozen=True)
class OrphanProcess:
    pid: int
    kind: str
    command: str
    rss_kb: int | None = None


@dataclass
class ScanResult:
    cockpit_running: bool
    summary: TaskSummary
    classified: list[ClassifiedTask]
    orphans: list[OrphanProcess] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
