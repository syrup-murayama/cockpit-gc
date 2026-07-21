"""Tests for the review CLI commands."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cockpit_gc import state
from cockpit_gc.cli import (
    build_parser,
    cmd_review_complete,
    cmd_review_remove,
    cmd_review_waiting,
)
from cockpit_gc.models import Category, ClassifiedTask
from cockpit_gc.review import compact_task_label


def _complete_item() -> ClassifiedTask:
    return ClassifiedTask(
        {
            "id": "abc123",
            "agentType": "terminal",
            "status": "waiting_confirmation",
            "name": "task",
            "directory": "/Users/example/src/example-project",
        },
        Category.SAFE_TO_COMPLETE,
        "autorun/terminal waiting",
    )


def _waiting_item() -> ClassifiedTask:
    return ClassifiedTask(
        {
            "id": "wait123",
            "agentType": "claude",
            "status": "waiting_confirmation",
            "name": "waiting task",
            "directory": "/Users/example/src/example-project",
        },
        Category.NEEDS_SUMMARY,
        "needs summary",
    )


def _remove_item() -> ClassifiedTask:
    return ClassifiedTask(
        {
            "id": "remove123",
            "agentType": "terminal",
            "status": "completed",
            "name": "test cleanup",
            "directory": "/Users/example/src/example-project",
        },
        Category.SAFE_TO_REMOVE,
        "test task name",
    )


class ReviewCompleteCliTests(unittest.TestCase):
    def _args(self, **overrides):
        base = {
            "limit": 10,
            "ask": False,
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
        item = _complete_item()
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]

        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
            with mock.patch("cockpit_gc.cli.ask_multiple") as ask_mock:
                with mock.patch("sys.stdout", buffer):
                    code = cmd_review_complete(self._args())
        self.assertEqual(code, 0)
        complete_mock.assert_not_called()
        ask_mock.assert_not_called()
        self.assertIn(" · abc123", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    def test_ask_schedules_and_persists_complete_state(
        self, ask_mock, review_mock, classify_mock, load_mock
    ):
        item = _complete_item()
        label = compact_task_label(item)
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "abc123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = "ask_complete"

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = Path(tmp) / "pending_asks"
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                buffer = io.StringIO()
                with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
                    with mock.patch("sys.stdout", buffer):
                        code = cmd_review_complete(self._args(ask=True))

            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(
                    (pending_dir / "ask_complete.json").read_text(encoding="utf-8")
                ),
                {"action": "complete", "labels": [label]},
            )
        ask_mock.assert_called_once_with(
            "Select safe-to-complete tasks (cockpit-gc review-complete)",
            [label],
        )
        complete_mock.assert_not_called()
        self.assertIn("ask_complete", buffer.getvalue())
        self.assertIn("cockpit.ask.resolved", buffer.getvalue())


class ReviewWaitingCliTests(unittest.TestCase):
    def _args(self, **overrides):
        base = {
            "limit": 30,
            "stale_days": 3,
            "include_needs_resume": False,
            "include_master": False,
            "ask": False,
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
            code = cmd_review_waiting(self._args())
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "No waiting confirmation candidates.\n")

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.waiting_review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    def test_ask_schedules_complete_state(
        self, ask_mock, review_mock, classify_mock, load_mock
    ):
        item = _waiting_item()
        label = "waiting task — claude / 日付不明 / example-project / summary · wait123"
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "wait123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = "ask_waiting"

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = Path(tmp) / "pending_asks"
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                buffer = io.StringIO()
                with mock.patch("sys.stdout", buffer):
                    code = cmd_review_waiting(self._args(ask=True))

            self.assertEqual(code, 0)
            payload = json.loads(
                (pending_dir / "ask_waiting.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["action"], "complete")
            self.assertEqual(payload["labels"], [label])
        self.assertIn("ask_waiting", buffer.getvalue())


class ReviewRemoveCliTests(unittest.TestCase):
    def _args(self, **overrides):
        base = {"limit": 20, "ask": False}
        base.update(overrides)
        return mock.Mock(**base)

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    def test_checklist_mode_is_read_only(self, review_mock, classify_mock, load_mock):
        item = _remove_item()
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "remove123"}]
        classify_mock.return_value = [item]
        buffer = io.StringIO()
        with mock.patch("cockpit_gc.cli.remove_task") as remove_mock:
            with mock.patch("sys.stdout", buffer):
                code = cmd_review_remove(self._args())
        self.assertEqual(code, 0)
        remove_mock.assert_not_called()
        self.assertIn("Safe-to-remove review", buffer.getvalue())
        self.assertIn(" · remove123", buffer.getvalue())

    @mock.patch("cockpit_gc.cli.load_tasks")
    @mock.patch("cockpit_gc.cli.classify_tasks")
    @mock.patch("cockpit_gc.cli.review_candidates")
    @mock.patch("cockpit_gc.cli.ask_multiple")
    def test_ask_schedules_remove_state(
        self, ask_mock, review_mock, classify_mock, load_mock
    ):
        item = _remove_item()
        label = compact_task_label(item)
        review_mock.return_value = [item]
        load_mock.return_value = [{"id": "remove123"}]
        classify_mock.return_value = [item]
        ask_mock.return_value = "ask_remove"

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = Path(tmp) / "pending_asks"
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                buffer = io.StringIO()
                with mock.patch("cockpit_gc.cli.remove_task") as remove_mock:
                    with mock.patch("sys.stdout", buffer):
                        code = cmd_review_remove(self._args(ask=True))

            self.assertEqual(code, 0)
            self.assertEqual(
                json.loads(
                    (pending_dir / "ask_remove.json").read_text(encoding="utf-8")
                ),
                {"action": "remove", "labels": [label]},
            )
        remove_mock.assert_not_called()
        self.assertIn("ask_remove", buffer.getvalue())


class ParserTests(unittest.TestCase):
    def test_review_commands_have_no_apply_flag(self):
        for command in ("review-complete", "review-waiting", "review-remove"):
            with self.subTest(command=command):
                with mock.patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit):
                        build_parser().parse_args([command, "--apply"])


if __name__ == "__main__":
    unittest.main()
