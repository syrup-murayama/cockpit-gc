"""Tests for cockpit runtime helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cockpit_gc.cockpit import (
    ask_multiple,
    complete_task,
    fetch_task_snippet,
    is_cockpit_running,
    is_process_running,
    load_tasks,
    remove_task,
)


class CockpitRuntimeTests(unittest.TestCase):
    def test_is_process_running_current_pid(self):
        self.assertTrue(is_process_running(os.getpid()))

    def test_is_process_running_missing_pid(self):
        self.assertFalse(is_process_running(999_999_999))

    def test_is_cockpit_running_false_when_file_missing(self):
        missing = Path(tempfile.gettempdir()) / "missing-cockpit-runtime.json"
        self.assertFalse(is_cockpit_running(missing))

    def test_is_cockpit_running_true_when_pid_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "cli-runtime.json"
            runtime.write_text(json.dumps({"pid": os.getpid()}))
            self.assertTrue(is_cockpit_running(runtime))

    def test_load_tasks_refuses_when_cockpit_not_running(self):
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                load_tasks()
        self.assertIn("not running", str(ctx.exception))


class CockpitMutationTests(unittest.TestCase):
    def test_ask_multiple_builds_expected_args(self):
        response = {
            "ok": True,
            "data": {"askId": "ask_abc123", "status": "scheduled"},
        }
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=True):
            with mock.patch(
                "cockpit_gc.cockpit.run_cockpit", return_value=response
            ) as run_mock:
                ask_id = ask_multiple(
                    "Pick tasks",
                    ["abc | terminal | waiting", "def | terminal | waiting"],
                )
        self.assertEqual(ask_id, "ask_abc123")
        run_mock.assert_called_once_with(
            [
                "ask",
                "--summary",
                "Pick tasks",
                "--multiple",
                "--choice",
                "abc | terminal | waiting",
                "--choice",
                "def | terminal | waiting",
            ]
        )

    def test_ask_multiple_rejects_response_without_ask_id(self):
        response = {"ok": True, "data": {"status": "scheduled"}}
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=True):
            with mock.patch(
                "cockpit_gc.cockpit.run_cockpit", return_value=response
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    ask_multiple("Pick tasks", ["choice"])
        self.assertIn("askId", str(ctx.exception))

    def test_complete_task_builds_expected_args(self):
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=True):
            with mock.patch("cockpit_gc.cockpit.run_cockpit") as run_mock:
                complete_task("abc123")
        run_mock.assert_called_once_with(["task", "complete", "abc123"])

    def test_remove_task_builds_expected_args(self):
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=True):
            with mock.patch("cockpit_gc.cockpit.run_cockpit") as run_mock:
                remove_task("abc123")
        run_mock.assert_called_once_with(["task", "remove", "abc123"])

    def test_fetch_task_snippet_builds_expected_args(self):
        response = {
            "ok": True,
            "data": {
                "conversation": [{"text": "tail output"}],
                "terminalOutput": "more output",
            },
        }
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=True):
            with mock.patch(
                "cockpit_gc.cockpit.run_cockpit", return_value=response
            ) as run_mock:
                snippet = fetch_task_snippet("abc123", max_lines=40)
        self.assertEqual(snippet, "tail output more output")
        run_mock.assert_called_once_with(
            ["task", "get", "abc123", "--turns", "1", "--max-lines", "40"]
        )

    def test_ask_multiple_refuses_when_cockpit_not_running(self):
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                ask_multiple("summary", ["choice"])
        self.assertIn("not running", str(ctx.exception))

    def test_remove_task_refuses_when_cockpit_not_running(self):
        with mock.patch("cockpit_gc.cockpit.is_cockpit_running", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                remove_task("abc123")
        self.assertIn("not running", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
