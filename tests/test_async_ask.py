"""Tests for asynchronous ask persistence and resolution."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from cockpit_gc import state
from cockpit_gc.cli import cmd_resolve_ask


class AsyncAskResolutionTests(unittest.TestCase):
    def _args(self, ask_id: str, payload: object) -> Namespace:
        return Namespace(ask_id=ask_id, answers_json=json.dumps(payload))

    def _state_dir(self, tmp: str) -> Path:
        return Path(tmp) / "pending_asks"

    def test_answered_event_maps_saved_labels_and_completes_tasks(self):
        ask_id = "ask_complete"
        labels = [
            "first task — terminal / 今日 / repo · first-id",
            "second task — terminal / 今日 / repo · second-id",
        ]
        event = {
            "event": "cockpit.ask.resolved",
            "version": 1,
            "ask_id": ask_id,
            "outcome": "answered",
            "answers": [
                {
                    "type": "choices",
                    "values": [labels[1], labels[0], "not-an-offered-label"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = self._state_dir(tmp)
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                state.save_pending_ask(ask_id, "complete", labels)
                buffer = io.StringIO()
                with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
                    with mock.patch("sys.stdout", buffer):
                        code = cmd_resolve_ask(self._args(ask_id, event))

            self.assertEqual(code, 0)
            complete_mock.assert_has_calls(
                [mock.call("second-id"), mock.call("first-id")]
            )
            self.assertEqual(complete_mock.call_count, 2)
            self.assertFalse((pending_dir / f"{ask_id}.json").exists())

        output = buffer.getvalue()
        self.assertIn("Resolved ask ask_complete (complete).", output)
        self.assertIn("Succeeded: 2", output)
        self.assertIn("first-id", output)
        self.assertIn("second-id", output)
        self.assertIn("Failed: 0", output)

    def test_dismissed_event_does_not_mutate_tasks_and_cleans_state(self):
        ask_id = "ask_dismissed"
        labels = ["task — terminal / 今日 / repo · task-id"]
        event = {
            "event": "cockpit.ask.resolved",
            "ask_id": ask_id,
            "outcome": "dismissed",
        }

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = self._state_dir(tmp)
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                state.save_pending_ask(ask_id, "remove", labels)
                buffer = io.StringIO()
                with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
                    with mock.patch("cockpit_gc.cli.remove_task") as remove_mock:
                        with mock.patch("sys.stdout", buffer):
                            code = cmd_resolve_ask(self._args(ask_id, event))

            self.assertEqual(code, 0)
            complete_mock.assert_not_called()
            remove_mock.assert_not_called()
            self.assertFalse((pending_dir / f"{ask_id}.json").exists())

        self.assertIn("dismissed", buffer.getvalue())
        self.assertIn("no tasks changed", buffer.getvalue())

    def test_dismissed_event_ignores_missing_or_null_answers(self):
        ask_id = "ask_dismissed_null"
        event = {"outcome": "dismissed", "answers": None}

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = self._state_dir(tmp)
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                state.save_pending_ask(ask_id, "complete", [])
                with mock.patch("cockpit_gc.cli.complete_task") as complete_mock:
                    code = cmd_resolve_ask(self._args(ask_id, event))

            self.assertEqual(code, 0)
            complete_mock.assert_not_called()
            self.assertFalse((pending_dir / f"{ask_id}.json").exists())

    def test_answers_array_resolves_remove_action(self):
        ask_id = "ask_remove"
        labels = ["temporary task — terminal / 今日 / repo · remove-id"]
        answers = [{"type": "choices", "values": [labels[0]]}]

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = self._state_dir(tmp)
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                state.save_pending_ask(ask_id, "remove", labels)
                with mock.patch("cockpit_gc.cli.remove_task") as remove_mock:
                    code = cmd_resolve_ask(self._args(ask_id, answers))

            self.assertEqual(code, 0)
            remove_mock.assert_called_once_with("remove-id")
            self.assertFalse((pending_dir / f"{ask_id}.json").exists())

    def test_resolution_reports_failures_and_still_cleans_state(self):
        ask_id = "ask_partial"
        labels = [
            "good task — terminal / 今日 / repo · good-id",
            "bad task — terminal / 今日 / repo · bad-id",
        ]
        answers = [{"type": "choices", "values": labels}]

        def remove_side_effect(task_id: str) -> None:
            if task_id == "bad-id":
                raise RuntimeError("remove failed")

        with tempfile.TemporaryDirectory() as tmp:
            pending_dir = self._state_dir(tmp)
            with mock.patch.object(state, "PENDING_ASKS_DIR", pending_dir):
                state.save_pending_ask(ask_id, "remove", labels)
                buffer = io.StringIO()
                with mock.patch(
                    "cockpit_gc.cli.remove_task", side_effect=remove_side_effect
                ):
                    with mock.patch("sys.stdout", buffer):
                        code = cmd_resolve_ask(self._args(ask_id, answers))

            self.assertEqual(code, 1)
            self.assertFalse((pending_dir / f"{ask_id}.json").exists())

        output = buffer.getvalue()
        self.assertIn("Succeeded: 1", output)
        self.assertIn("good-id", output)
        self.assertIn("Failed: 1", output)
        self.assertIn("bad-id: remove failed", output)


if __name__ == "__main__":
    unittest.main()
