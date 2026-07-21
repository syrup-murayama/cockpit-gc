from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .classify import classify_tasks, summarize
from .cockpit import (
    ask_multiple,
    complete_task,
    fetch_task_snippet,
    load_tasks,
    remove_task,
)
from . import state
from .models import Category
from .review import (
    compact_task_label,
    compact_waiting_label,
    labels_to_task_ids,
    render_checklist,
    review_candidates,
    waiting_review_candidates,
)
from .render import (
    plan_to_json,
    render_plan_markdown,
    render_report_markdown,
    render_scan_markdown,
    scan_to_json,
    write_json_report,
    write_markdown_report,
)
from .scan import run_scan


def cmd_report(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    summary = summarize(tasks)
    content = render_report_markdown(summary)
    if args.write:
        path = write_markdown_report(content, Path(args.output_dir), "cockpit-gc")
        print(path)
    else:
        print(content)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    result = run_scan(tasks)
    if args.json:
        payload = scan_to_json(result)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.write:
            path = write_json_report(payload, Path(args.output_dir), "cockpit-gc-scan")
            print(path)
        else:
            print(text, end="")
        return 0

    content = render_scan_markdown(result)
    if args.write:
        path = write_markdown_report(content, Path(args.output_dir), "cockpit-gc-scan")
        print(path)
    else:
        print(content)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    classified = classify_tasks(tasks)
    limit = args.limit

    if args.json:
        payload = plan_to_json(classified, limit_per_category=limit)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.write:
            path = write_json_report(payload, Path(args.output_dir), "cockpit-gc-plan")
            print(path)
        else:
            print(text, end="")
        return 0

    content = render_plan_markdown(classified, limit_per_category=limit)
    if args.write:
        path = write_markdown_report(content, Path(args.output_dir), "cockpit-gc-plan")
        print(path)
    else:
        print(content)
    return 0


def _schedule_review_ask(action: str, summary: str, labels: list[str]) -> int:
    ask_id = ask_multiple(summary, labels)
    if not ask_id:
        raise RuntimeError("cockpit ask returned no askId")
    state.save_pending_ask(ask_id, action, labels)
    print(f"Scheduled asynchronous ask: {ask_id}")
    print("Wait for the cockpit.ask.resolved event, then run:")
    print(
        "PYTHONPATH=src python3 -m cockpit_gc "
        f"resolve-ask {ask_id} --answers-json '<event JSON>'"
    )
    return 0


def cmd_review_complete(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    now = datetime.now(timezone.utc)
    classified = classify_tasks(tasks, now)
    candidates = review_candidates(classified, limit=args.limit)

    if not candidates:
        print("No safe-to-complete candidates.")
        return 0

    labels: list[str] = []
    for item in candidates:
        snippet = None
        if args.with_snippet:
            snippet = fetch_task_snippet(str(item.task.get("id", "")))
        labels.append(compact_task_label(item, snippet=snippet, now=now))

    if not args.ask:
        print(render_checklist(labels), end="")
        return 0

    return _schedule_review_ask(
        "complete",
        "Select safe-to-complete tasks (cockpit-gc review-complete)",
        labels,
    )


def cmd_review_waiting(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    now = datetime.now(timezone.utc)
    classified = classify_tasks(tasks, now)
    candidates = waiting_review_candidates(
        tasks,
        classified,
        now=now,
        stale_days=args.stale_days,
        include_needs_resume=args.include_needs_resume,
        include_master=args.include_master,
        limit=args.limit,
    )

    if not candidates:
        print("No waiting confirmation candidates.")
        return 0

    labels: list[str] = []
    for item in candidates:
        snippet = None
        if args.with_snippet:
            snippet = fetch_task_snippet(str(item.task.get("id", "")))
        labels.append(
            compact_waiting_label(
                item.task,
                classified=item,
                snippet=snippet,
                now=now,
            )
        )

    if not args.ask:
        print(
            render_checklist(labels, title="Waiting confirmation review"),
            end="",
        )
        return 0

    return _schedule_review_ask(
        "complete",
        "Select waiting_confirmation tasks (cockpit-gc review-waiting)",
        labels,
    )


def cmd_review_remove(args: argparse.Namespace) -> int:
    tasks = load_tasks()
    now = datetime.now(timezone.utc)
    classified = classify_tasks(tasks, now)
    candidates = review_candidates(
        classified,
        category=Category.SAFE_TO_REMOVE,
        limit=args.limit,
    )

    if not candidates:
        print("No safe-to-remove candidates.")
        return 0

    labels = [
        compact_task_label(item, now=now)
        for item in candidates
    ]
    if not args.ask:
        print(
            render_checklist(labels, title="Safe-to-remove review"),
            end="",
        )
        return 0

    return _schedule_review_ask(
        "remove",
        "Select safe-to-remove tasks (cockpit-gc review-remove)",
        labels,
    )


def _decode_answers_json(raw: str) -> tuple[str, str | None, list[object]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("--answers-json must contain valid JSON") from exc

    if isinstance(payload, list):
        return "answered", None, payload
    if not isinstance(payload, dict):
        raise RuntimeError("--answers-json must be an event object or answers array")

    event_ask_id = payload.get("ask_id", payload.get("askId"))
    if event_ask_id is not None and not isinstance(event_ask_id, str):
        raise RuntimeError("cockpit.ask.resolved ask_id must be a string")

    outcome = payload.get("outcome", "answered")
    if not isinstance(outcome, str):
        raise RuntimeError("cockpit.ask.resolved outcome must be a string")

    if outcome == "dismissed":
        return outcome, event_ask_id, []

    if "answers" in payload:
        answers = payload["answers"]
    elif payload.get("type") == "choices":
        answers = [payload]
    else:
        answers = []
    if not isinstance(answers, list):
        raise RuntimeError("cockpit.ask.resolved answers must be an array")
    return outcome, event_ask_id, answers


def _selected_labels(
    answers: list[object], allowed_labels: list[str]
) -> list[str]:
    if not answers or not isinstance(answers[0], dict):
        return []
    answer = answers[0]
    if answer.get("type") != "choices":
        return []
    values = answer.get("values")
    if not isinstance(values, list):
        return []
    allowed = set(allowed_labels)
    return [value for value in values if isinstance(value, str) and value in allowed]


def cmd_resolve_ask(args: argparse.Namespace) -> int:
    pending = state.load_pending_ask(args.ask_id)
    outcome, event_ask_id, answers = _decode_answers_json(args.answers_json)
    if event_ask_id is not None and event_ask_id != args.ask_id:
        raise RuntimeError(
            f"resolved event ask_id {event_ask_id} does not match {args.ask_id}"
        )

    if outcome == "dismissed":
        state.delete_pending_ask(args.ask_id)
        print(f"Ask {args.ask_id} was dismissed; no tasks changed.")
        return 0
    if outcome != "answered":
        raise RuntimeError(f"unsupported cockpit ask outcome: {outcome}")

    labels = _selected_labels(answers, pending["labels"])
    task_ids = labels_to_task_ids(labels)
    action = pending["action"]
    operation = complete_task if action == "complete" else remove_task
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    try:
        for task_id in task_ids:
            try:
                operation(task_id)
            except Exception as exc:
                failed.append((task_id, str(exc)))
            else:
                succeeded.append(task_id)
    finally:
        state.delete_pending_ask(args.ask_id)

    lines = [
        f"Resolved ask {args.ask_id} ({action}).",
        f"Succeeded: {len(succeeded)}",
    ]
    lines.extend(f"- {task_id}" for task_id in succeeded)
    lines.append(f"Failed: {len(failed)}")
    lines.extend(f"- {task_id}: {error}" for task_id, error in failed)
    print("\n".join(lines))
    return 1 if failed else 0


def cmd_apply(_args: argparse.Namespace) -> int:
    print(
        "cockpit-gc apply: not implemented by design. "
        "Use cockpit task complete/remove manually after explicit user approval.",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cockpit-gc")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="Generate a read-only task summary")
    report.add_argument("--write", action="store_true", help="Write a Markdown report file")
    report.add_argument("--output-dir", default="reports", help="Report output directory")
    report.set_defaults(func=cmd_report)

    scan = subparsers.add_parser("scan", help="Diagnose Cockpit task and process health")
    scan.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    scan.add_argument("--write", action="store_true", help="Write a report file")
    scan.add_argument("--output-dir", default="reports", help="Report output directory")
    scan.set_defaults(func=cmd_scan)

    plan = subparsers.add_parser("plan", help="List cleanup candidates by category")
    plan.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    plan.add_argument("--write", action="store_true", help="Write a report file")
    plan.add_argument("--output-dir", default="reports", help="Report output directory")
    plan.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum tasks shown per category",
    )
    plan.set_defaults(func=cmd_plan)

    apply_cmd = subparsers.add_parser(
        "apply",
        help="Reserved for future mutating operations (not implemented)",
    )
    apply_cmd.set_defaults(func=cmd_apply)

    review_complete = subparsers.add_parser(
        "review-complete",
        help="Review safe-to-complete tasks with an optional interactive checklist",
    )
    review_complete.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum safe-to-complete candidates to show",
    )
    review_complete.add_argument(
        "--ask",
        action="store_true",
        help="Schedule cockpit ask --multiple and persist its pending state",
    )
    review_complete.add_argument(
        "--with-snippet",
        action="store_true",
        help="Fetch a short task tail via cockpit task get before showing labels",
    )
    review_complete.set_defaults(func=cmd_review_complete)

    review_waiting = subparsers.add_parser(
        "review-waiting",
        help="Review stale waiting_confirmation tasks with an optional interactive checklist",
    )
    review_waiting.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum waiting_confirmation candidates to show",
    )
    review_waiting.add_argument(
        "--stale-days",
        type=int,
        default=3,
        help="Only include tasks whose last activity is at least N days ago",
    )
    review_waiting.add_argument(
        "--include-needs-resume",
        action="store_true",
        help="Include tasks that need resume",
    )
    review_waiting.add_argument(
        "--include-master",
        action="store_true",
        help="Include master tasks",
    )
    review_waiting.add_argument(
        "--ask",
        action="store_true",
        help="Schedule cockpit ask --multiple and persist its pending state",
    )
    review_waiting.add_argument(
        "--with-snippet",
        action="store_true",
        help="Fetch a short task tail via cockpit task get before showing labels",
    )
    review_waiting.set_defaults(func=cmd_review_waiting)

    review_remove = subparsers.add_parser(
        "review-remove",
        help="Review safe-to-remove tasks with an optional interactive checklist",
    )
    review_remove.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum safe-to-remove candidates to show",
    )
    review_remove.add_argument(
        "--ask",
        action="store_true",
        help="Schedule cockpit ask --multiple and persist its pending state",
    )
    review_remove.set_defaults(func=cmd_review_remove)

    resolve_ask = subparsers.add_parser(
        "resolve-ask",
        help="Apply a resolved cockpit.ask.resolved event to a pending review",
    )
    resolve_ask.add_argument("ask_id", help="askId printed by a review --ask command")
    resolve_ask.add_argument(
        "--answers-json",
        required=True,
        help="Resolved event JSON or its answers array",
    )
    resolve_ask.set_defaults(func=cmd_resolve_ask)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"cockpit-gc: {exc}", file=sys.stderr)
        return 1
