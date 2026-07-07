"""Tests for review-complete helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import unittest
from datetime import datetime, timezone

from cockpit_gc.classify import classify_tasks
from cockpit_gc.models import Category, ClassifiedTask
from cockpit_gc.review import (
    compact_task_label,
    format_age_label,
    format_planned_completes,
    labels_to_task_ids,
    render_checklist,
    review_candidates,
    task_id_from_label,
)


NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _task(**overrides):
    base = {
        "id": "07e6cba6",
        "name": "Morning briefing",
        "directory": "/Users/example/src/task-manager-app",
        "instruction": "",
        "status": "waiting_confirmation",
        "createdAt": "2026-06-01T00:00:00.000Z",
        "lastActivityAt": "2026-05-30T00:00:00.000Z",
        "agentType": "terminal",
        "needsResume": False,
        "isPinned": False,
        "isMaster": False,
    }
    base.update(overrides)
    return base


class ReviewTests(unittest.TestCase):
    def test_review_candidates_filters_safe_to_complete(self):
        tasks = [
            _task(id="complete-me", agentType="terminal"),
            _task(id="keep-me", agentType="claude", name="実装タスク"),
        ]
        classified = classify_tasks(tasks, NOW)
        candidates = review_candidates(classified, limit=10)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task["id"], "complete-me")
        self.assertEqual(candidates[0].category, Category.SAFE_TO_COMPLETE)

    def test_review_candidates_respects_limit(self):
        tasks = [
            _task(id=f"id-{index}", agentType="terminal", name=f"task {index}")
            for index in range(5)
        ]
        classified = classify_tasks(tasks, NOW)
        candidates = review_candidates(classified, limit=2)
        self.assertEqual(len(candidates), 2)

    def test_format_age_label(self):
        self.assertEqual(
            format_age_label(_task(lastActivityAt="2026-07-07T00:00:00.000Z"), NOW),
            "今日",
        )
        self.assertEqual(
            format_age_label(_task(lastActivityAt="2026-07-06T00:00:00.000Z"), NOW),
            "1日前",
        )
        self.assertEqual(
            format_age_label(_task(lastActivityAt="2026-05-30T00:00:00.000Z"), NOW),
            "38日前",
        )

    def test_compact_task_label(self):
        item = ClassifiedTask(
            _task(),
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        label = compact_task_label(item, now=NOW)
        self.assertTrue(label.startswith("Morning briefing — "))
        self.assertIn("terminal / 38日前 / task-manager-app", label)
        self.assertTrue(label.endswith(" · 07e6cba6"))
        self.assertFalse(label.startswith("07e6cba6"))
        self.assertNotIn("waiting_confirmation", label)

    def test_compact_task_label_truncates_long_name(self):
        item = ClassifiedTask(
            _task(name="x" * 80),
            Category.SAFE_TO_COMPLETE,
            "terminal agent waiting for confirmation",
        )
        label = compact_task_label(item, now=NOW)
        name_part = label.split(" — ", 1)[0]
        self.assertLessEqual(len(name_part), 55)
        self.assertTrue(name_part.endswith("…"))

    def test_compact_task_label_includes_parent(self):
        item = ClassifiedTask(
            _task(parentMasterId="master-1234567890"),
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        label = compact_task_label(item, now=NOW)
        self.assertIn("parent:master-1", label)
        self.assertTrue(label.endswith(" · 07e6cba6"))

    def test_compact_task_label_includes_snippet(self):
        item = ClassifiedTask(
            _task(),
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        label = compact_task_label(
            item,
            snippet="今日が期限のタスクがあります",
            now=NOW,
        )
        self.assertIn("/ last: 今日が期限のタスクがあります", label)
        self.assertTrue(label.endswith(" · 07e6cba6"))

    def test_task_id_from_label(self):
        label = (
            "Morning briefing — terminal / 38日前 / task-manager-app "
            "/ last: 今日が期限... · 9817a194"
        )
        self.assertEqual(task_id_from_label(label), "9817a194")

    def test_task_id_from_label_without_separator(self):
        self.assertEqual(task_id_from_label("legacy-id-only"), "legacy-id-only")

    def test_labels_to_task_ids(self):
        labels = [
            "task one — terminal / 38日前 / repo-a · abc123",
            "task two — terminal / 1日前 / repo-b / last: done · def456",
        ]
        self.assertEqual(labels_to_task_ids(labels), ["abc123", "def456"])

    def test_render_checklist(self):
        labels = ["task — terminal / 38日前 / repo · abc123"]
        content = render_checklist(labels)
        self.assertIn("# Safe-to-complete review", content)
        self.assertIn("- [ ] task — terminal / 38日前 / repo · abc123", content)

    def test_format_planned_completes(self):
        text = format_planned_completes(["abc123", "def456"])
        self.assertIn("Selected task IDs:", text)
        self.assertIn("- abc123", text)
        self.assertIn("Planned commands:", text)
        self.assertIn("cockpit task complete abc123", text)

    def test_format_planned_completes_empty(self):
        text = format_planned_completes([])
        self.assertIn("- (none)", text)


if __name__ == "__main__":
    unittest.main()
