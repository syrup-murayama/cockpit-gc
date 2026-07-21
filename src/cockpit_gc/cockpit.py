"""Cockpit runtime checks and task loading."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

COCKPIT_RUNTIME = Path.home() / ".agi-tools/data/cockpit/cli-runtime.json"


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def is_cockpit_running(runtime_path: Path = COCKPIT_RUNTIME) -> bool:
    try:
        data = json.loads(runtime_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    pid = data.get("pid")
    return isinstance(pid, int) and is_process_running(pid)


def run_cockpit(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["cockpit", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", f"cockpit {' '.join(args)} failed"))
    return payload


def load_tasks() -> list[dict[str, Any]]:
    if not is_cockpit_running():
        raise RuntimeError(
            "AGI Cockpit is not running; refusing to auto-start it via cockpit CLI"
        )

    payload = run_cockpit(["task", "list", "--all"])
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("unexpected cockpit response: data is not a list")
    return data


def fetch_task(task_id: str) -> dict[str, Any]:
    payload = run_cockpit(["task", "get", task_id])
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected cockpit response for task {task_id}")
    return data


def fetch_task_snippet(task_id: str, max_lines: int = 40) -> str:
    if not is_cockpit_running():
        raise RuntimeError(
            "AGI Cockpit is not running; refusing to auto-start it via cockpit CLI"
        )

    payload = run_cockpit(
        ["task", "get", task_id, "--turns", "1", "--max-lines", str(max_lines)]
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""

    parts: list[str] = []
    conversation = data.get("conversation")
    if isinstance(conversation, list):
        for item in conversation:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text).strip())

    terminal = data.get("terminalOutput")
    if terminal:
        parts.append(str(terminal).strip())

    return " ".join(parts).strip()


def ask_multiple(summary: str, choices: list[str]) -> str:
    if not choices:
        return ""
    if not is_cockpit_running():
        raise RuntimeError(
            "AGI Cockpit is not running; refusing to auto-start it via cockpit CLI"
        )

    args = ["ask", "--summary", summary, "--multiple"]
    for choice in choices:
        args.extend(["--choice", choice])
    payload = run_cockpit(args)
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("askId"), str):
        raise RuntimeError("unexpected cockpit ask response: missing askId")
    ask_id = data["askId"].strip()
    if not ask_id:
        raise RuntimeError("unexpected cockpit ask response: empty askId")
    return ask_id


def complete_task(task_id: str) -> None:
    if not is_cockpit_running():
        raise RuntimeError(
            "AGI Cockpit is not running; refusing to auto-start it via cockpit CLI"
        )
    run_cockpit(["task", "complete", task_id])


def remove_task(task_id: str) -> None:
    if not is_cockpit_running():
        raise RuntimeError(
            "AGI Cockpit is not running; refusing to auto-start it via cockpit CLI"
        )
    run_cockpit(["task", "remove", task_id])
