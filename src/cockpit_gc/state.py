"""Persistent state for asynchronous Cockpit asks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PENDING_ASKS_DIR = Path(".cockpit_gc_state") / "pending_asks"
VALID_ACTIONS = frozenset({"complete", "remove"})


def _ask_path(ask_id: str, state_dir: Path | None = None) -> Path:
    if (
        not isinstance(ask_id, str)
        or not ask_id
        or ask_id in {".", ".."}
        or "/" in ask_id
        or "\\" in ask_id
        or "\x00" in ask_id
    ):
        raise ValueError(f"invalid ask ID: {ask_id!r}")
    return (state_dir or PENDING_ASKS_DIR) / f"{ask_id}.json"


def save_pending_ask(
    ask_id: str,
    action: str,
    labels: list[str],
    *,
    state_dir: Path | None = None,
) -> Path:
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid pending ask action: {action!r}")
    if not all(isinstance(label, str) for label in labels):
        raise ValueError("pending ask labels must be strings")

    path = _ask_path(ask_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"action": action, "labels": labels}
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return path


def load_pending_ask(
    ask_id: str,
    *,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    path = _ask_path(ask_id, state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"pending ask state not found: {ask_id}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid pending ask state: {path}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid pending ask state: {path}")
    action = payload.get("action")
    labels = payload.get("labels")
    if action not in VALID_ACTIONS or not isinstance(labels, list):
        raise RuntimeError(f"invalid pending ask state: {path}")
    if not all(isinstance(label, str) for label in labels):
        raise RuntimeError(f"invalid pending ask labels: {path}")
    return {"action": action, "labels": labels}


def delete_pending_ask(
    ask_id: str,
    *,
    state_dir: Path | None = None,
) -> None:
    _ask_path(ask_id, state_dir).unlink(missing_ok=True)
