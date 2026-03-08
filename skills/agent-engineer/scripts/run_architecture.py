#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def run_python(script_name: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(script_dir() / script_name), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def run_checked(script_name: str, args: list[str], cwd: Path) -> None:
    result = run_python(script_name, args, cwd)
    if result.returncode != 0:
        message = result.stderr or result.stdout or f"{script_name} failed"
        raise RuntimeError(message.strip())


def load_runner(runner_dir: Path) -> dict[str, Any]:
    runner_file = runner_dir / "runner.json"
    if not runner_file.exists():
        raise ValueError(f"Missing runner.json in {runner_dir}")
    return json.loads(runner_file.read_text(encoding="utf-8"))


def ensure_store(cwd: Path) -> None:
    store = cwd / ".codex" / "agent-engineer" / "store" / "snapshot.json"
    if not store.exists():
        run_checked("agent_state.py", ["init-store"], cwd)


def extract_json_payload(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```json"):
        candidate = candidate[len("```json") :]
        candidate = candidate[: candidate.rfind("```")].strip()
    return json.loads(candidate)


def invoke_engine(cwd: Path, engine_id: str, prompt: str, output_file: Path, dry_run: bool) -> str:
    args = ["--engine-id", engine_id, "--prompt", prompt, "--output-file", str(output_file)]
    if dry_run:
        args.append("--dry-run")
    result = run_python("invoke_agent.py", args, cwd)
    if result.returncode != 0:
        message = result.stderr or result.stdout or "invoke_agent.py failed"
        raise RuntimeError(message.strip())
    return result.stdout


def current_snapshot(cwd: Path) -> dict[str, Any]:
    path = cwd / ".codex" / "agent-engineer" / "store" / "snapshot.json"
    return json.loads(path.read_text(encoding="utf-8"))


def add_task(cwd: Path, task: dict[str, Any], goal: str) -> None:
    args = [
        "add-task",
        "--id",
        task["id"],
        "--title",
        task["title"],
        "--goal",
        goal,
        "--status",
        task.get("status", "todo"),
    ]
    for flag, items in (
        ("--input", task.get("input", [])),
        ("--output", task.get("output", [])),
        ("--done-when", task.get("done_when", [])),
        ("--depends-on", task.get("depends_on", [])),
    ):
        if items:
            args.extend([flag, *items])
    run_checked("agent_state.py", args, cwd)


def handle_task_decomposition(
    step: dict[str, Any],
    runner: dict[str, Any],
    cwd: Path,
    goal: str,
    dry_run: bool,
) -> None:
    output_file = Path(runner["runner_dir"]) / "artifacts" / f"{step['id']}-task-decomposition.json"
    prompt = (
        "Return JSON only with keys goal and tasks. "
        "Each task must include id, title, input, output, done_when, depends_on, status. "
        f"Goal: {goal}"
    )
    if dry_run:
        payload = {
            "goal": goal,
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Execute approved objective",
                    "input": [goal],
                    "output": ["completed deliverable"],
                    "done_when": ["Validation passes"],
                    "depends_on": [],
                    "status": "todo",
                }
            ],
        }
        output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        response = json.dumps(payload)
    else:
        response = invoke_engine(cwd, step["engine_id"], prompt, output_file, dry_run=False)
    payload = extract_json_payload(response)
    for task in payload["tasks"]:
        add_task(cwd, task, payload["goal"])


def handle_parallel_execution(step: dict[str, Any], runner: dict[str, Any], cwd: Path) -> None:
    snapshot = current_snapshot(cwd)
    task_list = snapshot["task_decomposition"]["tasks"]
    max_workers = runner["architecture"]["parallel_policy"].get("max_workers", 1)
    join_point = snapshot["parallel_execution"]["join_point"] or "integration-review"
    run_checked("agent_state.py", ["set-join-point", "--join-point", join_point], cwd)
    for index, task in enumerate(task_list[:max_workers], start=1):
        args = [
            "assign-worker",
            "--task-id",
            task["id"],
            "--owner",
            f"worker-{index:02d}",
            "--priority",
            str(index),
            "--status",
            task["status"],
            "--role",
            "implementer",
            "--worker-status",
            "idle",
            "--scope",
            task["id"],
        ]
        if task.get("depends_on"):
            args.extend(["--depends-on", *task["depends_on"]])
        run_checked("agent_state.py", args, cwd)


def handle_state_externalization(cwd: Path) -> None:
    snapshot = current_snapshot(cwd)
    for task in snapshot["task_decomposition"]["tasks"]:
        args = [
            "add-context-packet",
            "--task-id",
            task["id"],
            "--goal",
            task["title"],
            "--status",
            "ready",
            "--verification",
            "Run validation before marking done",
        ]
        if task.get("input"):
            args.extend(["--files", *task["input"]])
        run_checked("agent_state.py", args, cwd)


def handle_central_orchestration(runner: dict[str, Any], cwd: Path) -> None:
    engines = runner["architecture"]["engines"]
    lead = engines[0]["id"]
    args = ["register-team", "--lead", lead]
    for engine in engines[1:]:
        args.extend(["--teammate", f"{engine['id']}:{engine['purpose']}:approved-architecture"])
    run_checked("agent_state.py", args, cwd)


def load_validation_map(path: Path | None) -> dict[str, list[dict[str, str]]]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def worker_engine_id(runner: dict[str, Any], fallback_step: dict[str, Any]) -> str:
    for engine in runner["architecture"]["engines"]:
        if engine["purpose"] == "worker":
            return engine["id"]
    return fallback_step["engine_id"]


def run_validation_command(command: str, cwd: Path, dry_run: bool) -> tuple[str, str]:
    if dry_run:
        return "pass", "dry-run"
    result = subprocess.run(command, cwd=cwd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "pass", result.stdout.strip()
    reason = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
    return "fail", reason


def handle_validation_loop(
    step: dict[str, Any],
    runner: dict[str, Any],
    cwd: Path,
    goal: str,
    validation_map: dict[str, list[dict[str, str]]],
    dry_run: bool,
) -> None:
    snapshot = current_snapshot(cwd)
    max_attempts = runner["architecture"]["retry_policy"]["max_attempts"]
    engine_id = worker_engine_id(runner, step)
    for task in snapshot["task_decomposition"]["tasks"]:
        commands = validation_map.get(task["id"], [])
        if not commands:
            if dry_run:
                commands = [{"name": "dry-run-check", "command": "true"}]
            else:
                raise RuntimeError(f"No validation commands for task {task['id']}")
        for attempt in range(1, max_attempts + 1):
            run_checked(
                "agent_state.py",
                ["update-task-status", "--task-id", task["id"], "--status", "doing", "--owner", engine_id],
                cwd,
            )
            output_file = Path(runner["runner_dir"]) / "artifacts" / f"{task['id']}-attempt-{attempt}.txt"
            prompt = f"Work on task {task['id']}: {task['title']}. Goal: {goal}"
            invoke_engine(cwd, engine_id, prompt, output_file, dry_run=dry_run)
            all_passed = True
            for item in commands:
                result, reason = run_validation_command(item["command"], cwd, dry_run)
                run_checked(
                    "agent_state.py",
                    [
                        "record-validation",
                        "--task-id",
                        task["id"],
                        "--name",
                        item["name"],
                        "--validation-command",
                        item["command"],
                        "--result",
                        result,
                        "--reason",
                        reason,
                    ],
                    cwd,
                )
                if result != "pass":
                    all_passed = False
            if all_passed:
                run_checked(
                    "agent_state.py",
                    ["update-task-status", "--task-id", task["id"], "--status", "done", "--owner", engine_id],
                    cwd,
                )
                run_checked(
                    "agent_state.py",
                    ["record-report", "--task-id", task["id"], "--result", "done", "--next-action", "review"],
                    cwd,
                )
                break
            if attempt == max_attempts:
                run_checked(
                    "agent_state.py",
                    ["update-task-status", "--task-id", task["id"], "--status", "blocked", "--owner", engine_id],
                    cwd,
                )
                run_checked(
                    "agent_state.py",
                    [
                        "record-report",
                        "--task-id",
                        task["id"],
                        "--result",
                        "blocked",
                        "--next-action",
                        "user-intervention",
                    ],
                    cwd,
                )
                raise RuntimeError(f"Task {task['id']} exceeded max_attempts={max_attempts}")
            run_checked(
                "agent_state.py",
                [
                    "record-report",
                    "--task-id",
                    task["id"],
                    "--result",
                    "needs-review",
                    "--next-action",
                    f"retry-{attempt + 1}",
                ],
                cwd,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an approved agent-engineer runner")
    parser.add_argument("--runner-dir", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--validation-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    runner_dir = Path(args.runner_dir).resolve()
    runner = load_runner(runner_dir)
    runner["runner_dir"] = str(runner_dir)
    cwd = Path(runner["workspace"]).resolve()
    ensure_store(cwd)
    validation_map = load_validation_map(Path(args.validation_file) if args.validation_file else None)

    for step in runner["ordered_steps"]:
        run_checked("verify_store.py", [], cwd)
        pattern = step["pattern"]
        if pattern == "task-decomposition":
            handle_task_decomposition(step, runner, cwd, args.goal, args.dry_run)
        elif pattern == "parallel-execution":
            handle_parallel_execution(step, runner, cwd)
        elif pattern == "state-externalization":
            handle_state_externalization(cwd)
        elif pattern == "central-orchestration":
            handle_central_orchestration(runner, cwd)
        elif pattern == "validation-loop":
            handle_validation_loop(step, runner, cwd, args.goal, validation_map, args.dry_run)
        else:
            output_file = runner_dir / "artifacts" / f"{step['id']}.txt"
            prompt = f"Execute step {step['id']} with pattern {pattern}. Goal: {args.goal}"
            invoke_engine(cwd, step["engine_id"], prompt, output_file, dry_run=args.dry_run)
        run_checked("verify_store.py", [], cwd)

    print(runner_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
