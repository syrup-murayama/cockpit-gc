"""Tests for review-complete CLI command."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import io
import unittest
from unittest import mock

from cockpit_gc.cli import cmd_review_complete


class ReviewCompleteCliTests(unittest.TestCase):
    def _args(self, **overrides):
        base = {
            "limit": 10,
            "ask": False,
            "apply": False,
            "with_snippet": False,
        }
        base.update(overrides)
        return mock.Mock(**base)

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    def test_no_candidates_message(self, classify_mock, load_mock):
        classify_mock.return_value = []
        load_mock.return_value = []
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            code = cmd_review_complete(self._args())
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "No safe-to-complete candidates.\n")

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    def test_checklist_mode_is_read_only(self, review_mock, classify_mock, load_mock):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "terminal",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-07-07T00:00:00.000Z",
            },
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]

        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
            with mock.patch("cockpit_gc.cli.ask_multiple") as ask_mock:
                with mock.patch("sys.stdout", buffer):
                    code = cmd_review_complete(self._args(apply=True))
        self.assertEqual(code, 0)
        complete_mock.assert_not_called()
        ask_mock.assert_not_called()
        self.assertIn(" · abc123", buffer.getvalue())
        self.assertNotIn("- [ ] abc123 |", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    def test_ask_without_apply_shows_planned_commands(
        self, ask_mock, review_mock, classify_mock, load_mock
    ):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "terminal",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-07-07T00:00:00.000Z",
            },
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        label = "task — terminal / 今日 / example-project · abc123"
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = [label]

        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
            with mock.patch("sys.stdout", buffer):
                code = cmd_review_complete(self._args(ask=True))
        self.assertEqual(code, 0)
        complete_mock.assert_not_called()
        self.assertIn("Planned commands:", buffer.getvalue())
        self.assertIn("cockpit task complete abc123", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    @mock.patch("cockpit_gc.cli.complete_task")
    def test_ask_with_apply_completes_selected(
        self, complete_mock, ask_mock, review_mock, classify_mock, load_mock
    ):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "terminal",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-07-07T00:00:00.000Z",
            },
            Category.SAFE_TO_COMPLETE,
            "autorun/terminal waiting",
        )
        label = "task — terminal / 今日 / example-project · abc123"
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = [label]

        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            code = cmd_review_complete(self._args(ask=True, apply=True))
        self.assertEqual(code, 0)
        complete_mock.assert_called_once_with("abc123")
        self.assertIn("Completed tasks:", buffer.getvalue())


class ReviewWaitingCliTests(unittest.TestCase):
    def _args(self, **overrides):
        base = {
            "limit": 30,
            "stale_days": 3,
            "include_needs_resume": False,
            "include_master": False,
            "ask": False,
            "apply": False,
            "with_snippet": False,
        }
        base.update(overrides)
        return mock.Mock(**base)

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.waiting_review_candidates")
    def test_no_candidates_message(self, review_mock, classify_mock, load_mock):
        review_mock.return_value = []
        load_mock.return_value = []
        classify_mock.return_value = []
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            from cockpit_gc.cli import cmd_review_waiting

            code = cmd_review_waiting(self._args())
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "No waiting confirmation candidates.\n")

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.waiting_review_candidates")
    def test_checklist_mode_is_read_only(self, review_mock, classify_mock, load_mock):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "claude",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-06-01T00:00:00.000Z",
            },
            Category.NEEDS_SUMMARY,
            "needs summary",
        )
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]

        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
            with mock.patch("cockpit_gc.cli.ask_multiple") as ask_mock:
                with mock.patch("sys.stdout", buffer):
                    from cockpit_gc.cli import cmd_review_waiting

                    code = cmd_review_waiting(self._args(apply=True))
        self.assertEqual(code, 0)
        complete_mock.assert_not_called()
        ask_mock.assert_not_called()
        self.assertIn("# Waiting confirmation review", buffer.getvalue())
        self.assertIn(" · abc123", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.waiting_review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    def test_ask_without_apply_shows_planned_commands(
        self, ask_mock, review_mock, classify_mock, load_mock
    ):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "claude",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-06-01T00:00:00.000Z",
            },
            Category.NEEDS_SUMMARY,
            "needs summary",
        )
        label = "task — claude / 36日前 / example-project / summary · abc123"
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = [label]

        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
            with mock.patch("sys.stdout", buffer):
                from cockpit_gc.cli import cmd_review_waiting

                code = cmd_review_waiting(self._args(ask=True))
        self.assertEqual(code, 0)
        complete_mock.assert_not_called()
        self.assertIn("Planned commands:", buffer.getvalue())
        self.assertIn("cockpit task complete abc123", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.waiting_review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    @mock.patch("cockpit_gc.cli.complete_task")
    def test_ask_with_apply_completes_selected(
        self, complete_mock, ask_mock, review_mock, classify_mock, load_mock
    ):
        from cockpit_gc.models import Category, ClassifiedTask

        item = ClassifiedTask(
            {
                "id": "abc123",
                "agentType": "claude",
                "status": "waiting_confirmation",
                "name": "task",
                "directory": "/Users/example/src/example-project",
                "lastActivityAt": "2026-06-01T00:00:00.000Z",
            },
            Category.NEEDS_SUMMARY,
            "needs summary",
        )
        label = "task — claude / 36日前 / example-project / summary · abc123"
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = [label]

        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            from cockpit_gc.cli import cmd_review_waiting

            code = cmd_review_waiting(self._args(ask=True, apply=True))
        self.assertEqual(code, 0)
        complete_mock.assert_called_once_with("abc123")
        self.assertIn("Completed tasks:", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
