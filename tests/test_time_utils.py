"""Tests for time helpers."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import unittest
from datetime import datetime, timezone

from cockpit_gc.time_utils import age_days, parse_time


class TimeUtilsTests(unittest.TestCase):
    def test_parse_time_zulu(self):
        dt = parse_time("2026-07-01T12:00:00.000Z")
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertEqual(dt.year, 2026)

    def test_parse_time_invalid(self):
        self.assertIsNone(parse_time("not-a-date"))

    def test_age_days_from_last_activity(self):
        now = datetime(2026, 7, 7, tzinfo=timezone.utc)
        task = {"lastActivityAt": "2026-07-01T00:00:00.000Z"}
        self.assertEqual(age_days(task, now), 6)


if __name__ == "__main__":
    unittest.main()
