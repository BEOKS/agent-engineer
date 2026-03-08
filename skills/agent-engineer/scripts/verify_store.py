#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_state import (
    PACKET_STATUSES,
    REPORT_RESULTS,
    TASK_STATUSES,
    VALIDATION_RESULTS,
    WORKER_STATUSES,
    app_root,
    architecture_path,
    canonical_json,
    compute_event_hash,
    events_path,
    load_events,
    load_snapshot,
    replay_events,
    snapshot_path,
)


def extract_architecture_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    marker = "```json"
    start = text.rfind(marker)
    if start == -1:
        return None
    body = text[start + len(marker) :]
    end = body.find("```")
    if end == -1:
        return None
    return json.loads(body[:end].strip())


def task_ids(snapshot: dict[str, Any]) -> set[str]:
    return {task["id"] for task in snapshot["task_decomposition"]["tasks"]}


def validate_hash_chain(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    previous = None
    for index, event in enumerate(events, start=1):
        expected_hash = compute_event_hash(event)
        if event.get("prev_hash") != previous:
            errors.append(f"Event {index} has invalid prev_hash")
        if event.get("hash") != expected_hash:
            errors.append(f"Event {index} hash mismatch")
        previous = event.get("hash")
    return errors


def validate_snapshot_replay(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    expected = replay_events(events)
    if canonical_json(snapshot) != canonical_json(expected):
        return ["snapshot.json does not match replayed events.jsonl"]
    return []


def validate_schema(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids = set()
    for task in snapshot["task_decomposition"]["tasks"]:
        if task["status"] not in TASK_STATUSES:
            errors.append(f"Task {task['id']} has invalid status")
        if task["id"] in ids:
            errors.append(f"Duplicate task id: {task['id']}")
        ids.add(task["id"])
    for packet in snapshot["context_isolation"]["context_packets"]:
        if packet["status"] not in PACKET_STATUSES:
            errors.append(f"Context packet {packet['task_id']} has invalid status")
    for item in snapshot["state_externalization"]["tasks"].values():
        if item["status"] not in TASK_STATUSES:
            errors.append("state_externalization.tasks contains invalid status")
    for item in snapshot["state_externalization"]["validations"]:
        if item["result"] not in {"pass", "fail"}:
            errors.append(f"Validation {item['task_id']} has invalid result")
    for item in snapshot["validation_loop"]["task_validations"]:
        for validation in item["validation"]:
            if validation["result"] not in VALIDATION_RESULTS:
                errors.append(f"Validation loop entry {item['task_id']} has invalid result")
    for item in snapshot["central_orchestration"]["workers"]:
        if item["status"] not in WORKER_STATUSES:
            errors.append(f"Worker {item['name']} has invalid status")
    for item in snapshot["central_orchestration"]["reports"]:
        if item["result"] not in REPORT_RESULTS:
            errors.append(f"Report {item['task_id']} has invalid result")
    return errors


def validate_references(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ids = task_ids(snapshot)
    parallel_ids = {item["id"] for item in snapshot["parallel_execution"]["parallel_tasks"]}
    known = ids | parallel_ids
    for task in snapshot["task_decomposition"]["tasks"]:
        for dep in task["depends_on"]:
            if dep not in ids:
                errors.append(f"Task {task['id']} depends on unknown task {dep}")
    for packet in snapshot["context_isolation"]["context_packets"]:
        if packet["task_id"] not in ids:
            errors.append(f"Context packet references unknown task {packet['task_id']}")
        expected_ref = f"snapshot.json#/state_externalization/tasks/{packet['task_id']}"
        if packet["state_ref"] != expected_ref:
            errors.append(f"Context packet {packet['task_id']} has invalid state_ref")
    for item in snapshot["validation_loop"]["task_validations"]:
        if item["task_id"] not in ids:
            errors.append(f"Validation loop references unknown task {item['task_id']}")
    for item in snapshot["state_externalization"]["validations"]:
        if item["task_id"] not in ids:
            errors.append(f"Validation references unknown task {item['task_id']}")
    for item in snapshot["central_orchestration"]["backlog"]:
        if item["id"] not in ids:
            errors.append(f"Backlog references unknown task {item['id']}")
    for item in snapshot["central_orchestration"]["reports"]:
        if item["task_id"] not in ids:
            errors.append(f"Report references unknown task {item['task_id']}")
    for item in snapshot["parallel_execution"]["parallel_tasks"]:
        for dep in item["depends_on"]:
            if dep not in known:
                errors.append(f"Parallel task {item['id']} depends on unknown task {dep}")
    return errors


def validate_done_transitions(snapshot: dict[str, Any]) -> list[str]:
    passing = {
        item["task_id"]
        for item in snapshot["state_externalization"]["validations"]
        if item["result"] == "pass"
    }
    for item in snapshot["validation_loop"]["task_validations"]:
        for validation in item["validation"]:
            if validation["result"] == "pass":
                passing.add(item["task_id"])
    errors: list[str] = []
    for task in snapshot["task_decomposition"]["tasks"]:
        if task["status"] == "done" and task["id"] not in passing:
            errors.append(f"Task {task['id']} is done without a passing validation")
    return errors


def validate_parallel_scopes(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    owners: dict[str, str] = {}
    for item in snapshot["parallel_execution"]["parallel_tasks"]:
        for scope in item["scope"]:
            previous = owners.get(scope)
            if previous and previous != item["id"]:
                errors.append(f"Parallel scope conflict: {scope} used by {previous} and {item['id']}")
            owners[scope] = item["id"]
    return errors


def validate_role_paths(snapshot: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    owners: dict[str, str] = {}
    for role in snapshot["role_decomposition"]["roles"]:
        for path in role["owned_paths"]:
            previous = owners.get(path)
            if previous and previous != role["name"]:
                errors.append(f"Owned path conflict: {path} assigned to {previous} and {role['name']}")
            owners[path] = role["name"]
    return errors


def has_execution_data(snapshot: dict[str, Any]) -> bool:
    return any(
        [
            snapshot["task_decomposition"]["tasks"],
            snapshot["state_externalization"]["tasks"],
            snapshot["state_externalization"]["validations"],
            snapshot["parallel_execution"]["parallel_tasks"],
            snapshot["central_orchestration"]["backlog"],
            snapshot["central_orchestration"]["reports"],
        ]
    )


def validate_approval_gate(snapshot: dict[str, Any], architecture: dict[str, Any] | None) -> list[str]:
    if not has_execution_data(snapshot):
        return []
    if architecture is None:
        return ["Execution data exists but architecture.md is missing or unreadable"]
    if architecture.get("approval_status") != "approved":
        return ["Execution data exists before architecture approval"]
    return []


def main() -> int:
    if not events_path().exists() or not snapshot_path().exists():
        print("Store is not initialized", file=sys.stderr)
        return 1

    snapshot = load_snapshot()
    events = load_events()
    architecture = extract_architecture_json(architecture_path())

    errors: list[str] = []
    errors.extend(validate_hash_chain(events))
    errors.extend(validate_snapshot_replay(snapshot, events))
    errors.extend(validate_schema(snapshot))
    errors.extend(validate_references(snapshot))
    errors.extend(validate_done_transitions(snapshot))
    errors.extend(validate_parallel_scopes(snapshot))
    errors.extend(validate_role_paths(snapshot))
    errors.extend(validate_approval_gate(snapshot, architecture))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"OK: {app_root()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
