"""Tests for review-waiting helpers."""

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
    compact_waiting_label,
    is_waiting_review_candidate,
    labels_to_task_ids,
    render_checklist,
    task_id_from_label,
    waiting_review_candidates,
    waiting_summary_flag,
)


NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _task(**overrides):
    base = {
        "id": "2e901c2f",
        "name": "Portfolio site update",
        "directory": "/Users/example/src/sites/portfolio-site",
        "instruction": "",
        "status": "waiting_confirmation",
        "createdAt": "2026-06-01T00:00:00.000Z",
        "lastActivityAt": "2026-06-28T00:00:00.000Z",
        "agentType": "claude",
        "needsResume": False,
        "isPinned": False,
        "isMaster": False,
    }
    base.update(overrides)
    return base


class WaitingReviewTests(unittest.TestCase):
    def test_is_waiting_review_candidate_requires_stale_waiting(self):
        self.assertTrue(
            is_waiting_review_candidate(
                _task(),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertFalse(
            is_waiting_review_candidate(
                _task(lastActivityAt="2026-07-06T00:00:00.000Z"),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )

    def test_is_waiting_review_candidate_excludes_pinned_running_worktree_master(self):
        self.assertFalse(
            is_waiting_review_candidate(
                _task(isPinned=True),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertFalse(
            is_waiting_review_candidate(
                _task(status="running"),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertFalse(
            is_waiting_review_candidate(
                _task(directory="/Users/example/.worktrees/feature/foo"),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertFalse(
            is_waiting_review_candidate(
                _task(isMaster=True),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertTrue(
            is_waiting_review_candidate(
                _task(isMaster=True),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=True,
            )
        )

    def test_is_waiting_review_candidate_needs_resume_flag(self):
        self.assertFalse(
            is_waiting_review_candidate(
                _task(needsResume=True),
                NOW,
                stale_days=3,
                include_needs_resume=False,
                include_master=False,
            )
        )
        self.assertTrue(
            is_waiting_review_candidate(
                _task(needsResume=True),
                NOW,
                stale_days=3,
                include_needs_resume=True,
                include_master=False,
            )
        )

    def test_waiting_review_candidates_filters_and_sorts(self):
        tasks = [
            _task(id="old", lastActivityAt="2026-06-01T00:00:00.000Z"),
            _task(id="mid", lastActivityAt="2026-06-20T00:00:00.000Z"),
            _task(id="recent", lastActivityAt="2026-07-06T00:00:00.000Z"),
            _task(id="pinned", isPinned=True, lastActivityAt="2026-06-01T00:00:00.000Z"),
        ]
        classified = classify_tasks(tasks, NOW)
        candidates = waiting_review_candidates(
            tasks,
            classified,
            now=NOW,
            stale_days=3,
            limit=10,
        )
        self.assertEqual([item.task["id"] for item in candidates], ["old", "mid"])

    def test_waiting_review_candidates_respects_limit(self):
        tasks = [
            _task(
                id=f"id-{index}",
                lastActivityAt=f"2026-06-{index + 1:02d}T00:00:00.000Z",
            )
            for index in range(5)
        ]
        classified = classify_tasks(tasks, NOW)
        candidates = waiting_review_candidates(
            tasks,
            classified,
            now=NOW,
            stale_days=3,
            limit=2,
        )
        self.assertEqual(len(candidates), 2)

    def test_waiting_summary_flag(self):
        task = _task(agentType="claude")
        classified = ClassifiedTask(task, Category.NEEDS_SUMMARY, "needs summary", heavy=False)
        self.assertTrue(waiting_summary_flag(task, classified))
        self.assertTrue(waiting_summary_flag(_task(agentType="codex"), None))
        self.assertFalse(waiting_summary_flag(_task(agentType="terminal"), None))

    def test_compact_waiting_label(self):
        item = classify_tasks([_task()], NOW)[0]
        label = compact_waiting_label(item.task, classified=item, now=NOW)
        self.assertTrue(label.startswith("Portfolio site update — "))
        self.assertIn("claude / 9日前 / portfolio-site / summary", label)
        self.assertTrue(label.endswith(" · 2e901c2f"))

    def test_compact_waiting_label_flags(self):
        item = classify_tasks(
            [
                _task(
                    id="bd577e0f",
                    name="Return exactly one concise sentence",
                    agentType="cursor",
                    directory="/Users/example/src/skills-library",
                    lastActivityAt="2026-07-06T00:00:00.000Z",
                    parentTaskId="parent-1234567890",
                )
            ],
            NOW,
        )[0]
        label = compact_waiting_label(item.task, classified=item, now=NOW)
        self.assertIn("cursor / 1日前 / skills-library / child / summary", label)
        self.assertTrue(label.endswith(" · bd577e0f"))

    def test_compact_waiting_label_resume_flag(self):
        item = classify_tasks(
            [_task(needsResume=True, lastActivityAt="2026-06-01T00:00:00.000Z")],
            NOW,
        )[0]
        label = compact_waiting_label(item.task, classified=item, now=NOW)
        self.assertIn("/ resume / summary", label)

    def test_task_id_from_waiting_label(self):
        label = (
            "Phase 1: Adobe PortfolioからAstro移行... — codex / 12日前 / website / summary "
            "· 0e5ca435"
        )
        self.assertEqual(task_id_from_label(label), "0e5ca435")
        self.assertEqual(labels_to_task_ids([label]), ["0e5ca435"])

    def test_render_waiting_checklist(self):
        content = render_checklist(
            ["task — claude / 9日前 / repo / summary · abc123"],
            title="Waiting confirmation review",
        )
        self.assertIn("# Waiting confirmation review", content)
        self.assertIn("- [ ] task — claude / 9日前 / repo / summary · abc123", content)


if __name__ == "__main__":
    unittest.main()
