from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .classify import classify_tasks, summarize
from .cockpit import ask_multiple, complete_task, fetch_task_snippet, load_tasks
from .review import (
    compact_task_label,
    compact_waiting_label,
    format_planned_completes,
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

    selected_labels = ask_multiple(
        "Select safe-to-complete tasks (cockpit-gc review-complete)",
        labels,
    )
    task_ids = labels_to_task_ids(selected_labels)

    if not args.apply:
        print(format_planned_completes(task_ids), end="")
        return 0

    for task_id in task_ids:
        complete_task(task_id)

    lines = ["Completed tasks:"]
    if task_ids:
        for task_id in task_ids:
            lines.append(f"- {task_id}")
    else:
        lines.append("- (none)")
    lines.append("")
    print("\n".join(lines), end="")
    return 0


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

    selected_labels = ask_multiple(
        "Select waiting_confirmation tasks (cockpit-gc review-waiting)",
        labels,
    )
    task_ids = labels_to_task_ids(selected_labels)

    if not args.apply:
        print(format_planned_completes(task_ids), end="")
        return 0

    for task_id in task_ids:
        complete_task(task_id)

    lines = ["Completed tasks:"]
    if task_ids:
        for task_id in task_ids:
            lines.append(f"- {task_id}")
    else:
        lines.append("- (none)")
    lines.append("")
    print("\n".join(lines), end="")
    return 0


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
        help="Use cockpit ask --multiple for checkbox selection",
    )
    review_complete.add_argument(
        "--apply",
        action="store_true",
        help="Complete selected tasks (requires --ask)",
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
        help="Use cockpit ask --multiple for checkbox selection",
    )
    review_waiting.add_argument(
        "--apply",
        action="store_true",
        help="Complete selected tasks (requires --ask)",
    )
    review_waiting.add_argument(
        "--with-snippet",
        action="store_true",
        help="Fetch a short task tail via cockpit task get before showing labels",
    )
    review_waiting.set_defaults(func=cmd_review_waiting)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"cockpit-gc: {exc}", file=sys.stderr)
        return 1
