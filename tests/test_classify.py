"""Tests for task classification."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import unittest
from datetime import datetime, timezone

from cockpit_gc.classify import (
    category_counts,
    classify_task,
    classify_tasks,
    looks_like_autorun,
    summarize,
)
from cockpit_gc.models import Category


NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _task(**overrides):
    base = {
        "id": "abc123",
        "name": "example",
        "directory": "/Users/example/src/project-a",
        "instruction": "",
        "status": "waiting_confirmation",
        "createdAt": "2026-06-01T00:00:00.000Z",
        "lastActivityAt": "2026-06-01T00:00:00.000Z",
        "agentType": "codex",
        "needsResume": False,
        "isPinned": False,
        "isMaster": False,
    }
    base.update(overrides)
    return base


class ClassifyTests(unittest.TestCase):
    def test_running_task_is_active(self):
        item = classify_task(_task(status="running"), NOW)
        self.assertEqual(item.category, Category.ACTIVE)
        self.assertEqual(item.reason, "running")

    def test_pinned_task_is_active(self):
        item = classify_task(_task(isPinned=True), NOW)
        self.assertEqual(item.category, Category.ACTIVE)

    def test_recent_task_is_active(self):
        item = classify_task(
            _task(lastActivityAt="2026-07-05T00:00:00.000Z"),
            NOW,
        )
        self.assertEqual(item.category, Category.ACTIVE)
        self.assertIn("recent", item.reason)

    def test_shape_test_is_safe_to_remove(self):
        item = classify_task(
            _task(name="TASK_RUN_RESPONSE_SHAPE_TEST_OK"),
            NOW,
        )
        self.assertEqual(item.category, Category.SAFE_TO_REMOVE)

    def test_empty_task_is_safe_to_remove(self):
        item = classify_task(_task(name="", instruction=""), NOW)
        self.assertEqual(item.category, Category.SAFE_TO_REMOVE)

    def test_autorun_waiting_is_safe_to_complete(self):
        item = classify_task(
            _task(
                status="waiting_confirmation",
                agentType="terminal",
                name="dependency-watcher",
                lastActivityAt="2026-05-01T00:00:00.000Z",
            ),
            NOW,
        )
        self.assertEqual(item.category, Category.SAFE_TO_COMPLETE)

    def test_old_completed_is_active_or_archive(self):
        item = classify_task(
            _task(
                status="completed",
                lastActivityAt="2026-05-01T00:00:00.000Z",
            ),
            NOW,
        )
        self.assertIn(item.category, {Category.ACTIVE, Category.HEAVY_HISTORY})

    def test_implementation_waiting_needs_summary(self):
        item = classify_task(
            _task(
                status="waiting_confirmation",
                agentType="claude",
                name="Portfolio site update",
                lastActivityAt="2026-06-01T00:00:00.000Z",
            ),
            NOW,
        )
        self.assertEqual(item.category, Category.NEEDS_SUMMARY)

    def test_heavy_instruction_flags_heavy(self):
        item = classify_task(
            _task(instruction="x" * 2500, lastActivityAt="2026-05-01T00:00:00.000Z"),
            NOW,
        )
        self.assertTrue(item.heavy)

    def test_looks_like_autorun(self):
        self.assertTrue(looks_like_autorun(_task(agentType="terminal")))
        self.assertTrue(looks_like_autorun(_task(name="日次レポート")))
        self.assertFalse(looks_like_autorun(_task(name="普通の実装")))

    def test_summarize_counts(self):
        tasks = [
            _task(status="completed", lastActivityAt="2026-05-01T00:00:00.000Z"),
            _task(status="waiting_confirmation", agentType="terminal", name="日次"),
            _task(status="running"),
        ]
        summary = summarize(tasks, NOW)
        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.old_completed_30d, 1)
        self.assertEqual(summary.autorun_waiting, 1)
        self.assertEqual(summary.by_status["running"], 1)

    def test_needs_resume_is_active(self):
        item = classify_task(_task(needsResume=True), NOW)
        self.assertEqual(item.category, Category.ACTIVE)
        self.assertEqual(item.reason, "needs resume")

    def test_worktree_is_active(self):
        item = classify_task(
            _task(directory="/Users/example/.worktrees/feature/foo"),
            NOW,
        )
        self.assertEqual(item.category, Category.ACTIVE)
        self.assertIn("worktree", item.reason)

    def test_tmp_workspace_is_safe_to_remove(self):
        item = classify_task(
            _task(directory="/tmp/agi-cockpit/session-1"),
            NOW,
        )
        self.assertEqual(item.category, Category.SAFE_TO_REMOVE)

    def test_resume_shell_is_safe_to_complete(self):
        item = classify_task(
            _task(
                status="waiting_confirmation",
                name="--resume 1ce5f7ad-8790-4869-ad82-a2705a5b533",
                lastActivityAt="2026-05-01T00:00:00.000Z",
            ),
            NOW,
        )
        self.assertEqual(item.category, Category.SAFE_TO_COMPLETE)

    def test_category_counts(self):
        tasks = [
            _task(status="running"),
            _task(name="TASK_RUN_RESPONSE_SHAPE_TEST_OK"),
        ]
        classified = classify_tasks(tasks, NOW)
        counts = category_counts(classified)
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["safe-to-remove"], 1)

    def test_classify_tasks_preserves_order(self):
        tasks = [_task(id="1"), _task(id="2")]
        classified = classify_tasks(tasks, NOW)
        self.assertEqual([item.task["id"] for item in classified], ["1", "2"])


if __name__ == "__main__":
    unittest.main()
