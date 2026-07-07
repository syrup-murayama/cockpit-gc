"""Tests for scan warnings."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import unittest

from cockpit_gc.models import Category, ClassifiedTask, OrphanProcess, TaskSummary
from cockpit_gc.scan import build_warnings, scan_orphan_processes


class ScanWarningTests(unittest.TestCase):
    def test_waiting_confirmation_budget_warning(self):
        summary = TaskSummary(
            total=30,
            by_status={"waiting_confirmation": 30},
            needs_resume=0,
            pinned=0,
            autorun_waiting=0,
            old_completed_30d=0,
            old_completed_90d=0,
        )
        warnings = build_warnings(summary, [], [])
        self.assertTrue(any("waiting_confirmation" in item for item in warnings))

    def test_orphan_opencode_warning(self):
        summary = TaskSummary(
            total=1,
            by_status={"completed": 1},
            needs_resume=0,
            pinned=0,
            autorun_waiting=0,
            old_completed_30d=0,
            old_completed_90d=0,
        )
        orphans = [
            OrphanProcess(pid=1, kind="opencode-serve", command="opencode serve", rss_kb=2048),
            OrphanProcess(pid=2, kind="opencode-serve", command="opencode serve", rss_kb=1024),
        ]
        warnings = build_warnings(summary, [], orphans)
        self.assertTrue(any("opencode serve" in item for item in warnings))

    def test_heavy_task_warning(self):
        summary = TaskSummary(
            total=1,
            by_status={"completed": 1},
            needs_resume=0,
            pinned=0,
            autorun_waiting=0,
            old_completed_30d=0,
            old_completed_90d=0,
        )
        classified = [
            ClassifiedTask({"id": "1"}, Category.ACTIVE, "x", heavy=True),
        ]
        warnings = build_warnings(summary, classified, [])
        self.assertTrue(any("heavy" in item for item in warnings))

    def test_process_scan_ignores_prompt_text_mentions(self):
        fake_ps = "123 2048 /usr/bin/cursor-agent -f please inspect opencode serve logs\n"

        class Proc:
            stdout = fake_ps

        from unittest import mock

        with mock.patch("cockpit_gc.scan.subprocess.run", return_value=Proc()):
            self.assertEqual(scan_orphan_processes(), [])


if __name__ == "__main__":
    unittest.main()
