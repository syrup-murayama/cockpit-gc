"""Tests for rendering helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import unittest

from cockpit_gc.classify import classify_task
from cockpit_gc.models import Category, ClassifiedTask, OrphanProcess, ScanResult, TaskSummary
from cockpit_gc.render import (
    plan_to_json,
    render_plan_markdown,
    render_report_markdown,
    render_scan_markdown,
    scan_to_json,
)


NOW_FIXTURE = None


class RenderTests(unittest.TestCase):
    def test_render_report_markdown_contains_totals(self):
        summary = TaskSummary(
            total=10,
            by_status={"completed": 8, "waiting_confirmation": 2},
            needs_resume=1,
            pinned=2,
            autorun_waiting=1,
            old_completed_30d=3,
            old_completed_90d=1,
        )
        text = render_report_markdown(summary)
        self.assertIn("Total tasks: 10", text)
        self.assertIn("`waiting_confirmation`: 2", text)
        self.assertIn("read-only", text.lower())

    def test_render_scan_markdown_includes_warnings(self):
        summary = TaskSummary(
            total=30,
            by_status={"waiting_confirmation": 25},
            needs_resume=0,
            pinned=0,
            autorun_waiting=5,
            old_completed_30d=0,
            old_completed_90d=0,
        )
        result = ScanResult(
            cockpit_running=True,
            summary=summary,
            classified=[],
            orphans=[OrphanProcess(pid=99, kind="opencode-serve", command="opencode serve", rss_kb=1024)],
            warnings=["waiting_confirmation is 25 (budget 20)"],
            category_counts={"active": 5},
        )
        text = render_scan_markdown(result)
        self.assertIn("Warnings", text)
        self.assertIn("opencode-serve", text)

    def test_render_plan_markdown_groups_categories(self):
        classified = [
            ClassifiedTask(
                {"id": "1", "name": "autorun", "status": "waiting_confirmation"},
                Category.SAFE_TO_COMPLETE,
                "autorun",
            ),
            ClassifiedTask(
                {"id": "2", "name": "keep", "status": "running"},
                Category.ACTIVE,
                "running",
            ),
        ]
        text = render_plan_markdown(classified)
        self.assertIn("safe-to-complete", text)
        self.assertIn("`1`", text)
        self.assertIn("active", text)

    def test_scan_to_json_shape(self):
        summary = TaskSummary(
            total=1,
            by_status={"completed": 1},
            needs_resume=0,
            pinned=0,
            autorun_waiting=0,
            old_completed_30d=0,
            old_completed_90d=0,
        )
        result = ScanResult(
            cockpit_running=True,
            summary=summary,
            classified=[],
            warnings=[],
            category_counts={},
        )
        payload = scan_to_json(result)
        self.assertTrue(payload["cockpit_running"])
        self.assertEqual(payload["summary"]["total"], 1)

    def test_plan_to_json_includes_totals(self):
        classified = [
            classify_task(
                {
                    "id": "1",
                    "name": "x",
                    "status": "completed",
                    "createdAt": "2026-05-01T00:00:00.000Z",
                    "lastActivityAt": "2026-05-01T00:00:00.000Z",
                }
            )
        ]
        payload = plan_to_json(classified, limit_per_category=5)
        self.assertIn("categories", payload)
        self.assertIn("safe-to-complete_total", payload["categories"])


if __name__ == "__main__":
    unittest.main()
