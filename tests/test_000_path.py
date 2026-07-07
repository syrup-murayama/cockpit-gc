"""Run first (alphabetically) to add src/ to sys.path for unittest discover."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_path_helper = Path(__file__).resolve().parent / "_path.py"
_spec = importlib.util.spec_from_file_location("cockpit_gc_tests_path", _path_helper)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load path helper: {_path_helper}")
_path_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_path_module)

import unittest


class PathSetupTests(unittest.TestCase):
    def test_src_on_sys_path(self):
        src = Path(__file__).resolve().parents[1] / "src"
        import sys

        self.assertIn(str(src), sys.path)
