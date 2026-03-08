#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


TASK_STATUSES = {"todo", "doing", "done", "blocked"}
PACKET_STATUSES = {"draft", "ready", "used", "expired"}
WORKER_STATUSES = {"idle", "busy", "blocked"}
REPORT_RESULTS = {"done", "blocked", "needs-review"}
VALIDATION_RESULTS = {"pass", "fail", "pending"}


def app_root(base_dir: Path | None = None) -> Path:
    base = (base_dir or Path.cwd()).resolve()
    return base / ".codex" / "agent-engineer"


def store_dir(base_dir: Path | None = None) -> Path:
    return app_root(base_dir) / "store"


def snapshot_path(base_dir: Path | None = None) -> Path:
    return store_dir(base_dir) / "snapshot.json"


def events_path(base_dir: Path | None = None) -> Path:
    return store_dir(base_dir) / "events.jsonl"


def architecture_path(base_dir: Path | None = None) -> Path:
    return app_root(base_dir) / "architecture.md"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def empty_snapshot() -> dict[str, Any]:
    return {
        "task_decomposition": {"goal": "", "tasks": []},
        "role_decomposition": {"roles": [], "handoff_contracts": []},
        "context_isolation": {"context_packets": []},
        "state_externalization": {
            "goal": "",
            "tasks": {},
            "decisions": [],
            "validations": [],
        },
        "validation_loop": {"task_validations": []},
        "parallel_execution": {"parallel_tasks": [], "join_point": ""},
        "central_orchestration": {"backlog": [], "workers": [], "reports": []},
        "compositions": {
            "ralph": {
                "prd_ref": "task_decomposition",
                "progress_ref": "state_externalization",
                "validation_ref": "validation_loop",
            },
            "agent_team": {
                "team": {"lead": "", "teammates": []},
                "shared_board": [],
            },
        },
    }


def load_snapshot(base_dir: Path | None = None) -> dict[str, Any]:
    path = snapshot_path(base_dir)
    if not path.exists():
        return empty_snapshot()
    return json.loads(path.read_text(encoding="utf-8"))


def write_snapshot(snapshot: dict[str, Any], base_dir: Path | None = None) -> None:
    path = snapshot_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(snapshot) + "\n", encoding="utf-8")


def load_events(base_dir: Path | None = None) -> list[dict[str, Any]]:
    path = events_path(base_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def compute_event_hash(event: dict[str, Any]) -> str:
    payload = {
        "ts": event["ts"],
        "command": event["command"],
        "payload": event["payload"],
        "prev_hash": event["prev_hash"],
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def append_event(base_dir: Path | None, command: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = events_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = load_events(base_dir)
    event = {
        "ts": now_iso(),
        "command": command,
        "payload": payload,
        "prev_hash": events[-1]["hash"] if events else None,
    }
    event["hash"] = compute_event_hash(event)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def rewrite_events(events: list[dict[str, Any]], base_dir: Path | None = None) -> None:
    path = events_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def ensure_store_exists(base_dir: Path | None = None) -> None:
    if not events_path(base_dir).exists() or not snapshot_path(base_dir).exists():
        raise SystemExit("Store is not initialized. Run `agent_state.py init-store` first.")


def find_task(snapshot: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in snapshot["task_decomposition"]["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def has_passing_validation(snapshot: dict[str, Any], task_id: str) -> bool:
    for item in snapshot["state_externalization"]["validations"]:
        if item["task_id"] == task_id and item["result"] == "pass":
            return True
    for item in snapshot["validation_loop"]["task_validations"]:
        if item["task_id"] != task_id:
            continue
        for validation in item["validation"]:
            if validation["result"] == "pass":
                return True
    return False


def upsert_by_key(items: list[dict[str, Any]], key: str, value: str, payload: dict[str, Any]) -> None:
    for index, item in enumerate(items):
        if item.get(key) == value:
            items[index] = payload
            return
    items.append(payload)


def apply_event(snapshot: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    new_snapshot = copy.deepcopy(snapshot)
    command = event["command"]
    payload = event["payload"]

    if command == "init-store":
        return empty_snapshot()

    if command == "add-task":
        task_id = payload["id"]
        if find_task(new_snapshot, task_id):
            raise ValueError(f"Task already exists: {task_id}")
        task = {
            "id": task_id,
            "title": payload["title"],
            "input": payload.get("input", []),
            "output": payload.get("output", []),
            "done_when": payload.get("done_when", []),
            "depends_on": payload.get("depends_on", []),
            "status": payload.get("status", "todo"),
        }
        if task["status"] not in TASK_STATUSES:
            raise ValueError(f"Invalid task status: {task['status']}")
        if payload.get("goal"):
            new_snapshot["task_decomposition"]["goal"] = payload["goal"]
            new_snapshot["state_externalization"]["goal"] = payload["goal"]
        new_snapshot["task_decomposition"]["tasks"].append(task)
        new_snapshot["state_externalization"]["tasks"][task_id] = {
            "status": task["status"],
            "owner": payload.get("owner", ""),
            "updated_at": payload.get("updated_at", event["ts"]),
        }
        return new_snapshot

    if command == "update-task-status":
        task_id = payload["task_id"]
        task = find_task(new_snapshot, task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        status = payload["status"]
        if status not in TASK_STATUSES:
            raise ValueError(f"Invalid task status: {status}")
        if status == "done" and not has_passing_validation(new_snapshot, task_id):
            raise ValueError(f"Cannot mark {task_id} done without a passing validation")
        task["status"] = status
        state = new_snapshot["state_externalization"]["tasks"].setdefault(task_id, {})
        state["status"] = status
        state["owner"] = payload.get("owner", state.get("owner", ""))
        state["updated_at"] = payload.get("updated_at", event["ts"])
        for backlog in new_snapshot["central_orchestration"]["backlog"]:
            if backlog["id"] == task_id:
                backlog["status"] = status
                backlog["owner"] = payload.get("owner", backlog.get("owner", ""))
        return new_snapshot

    if command == "add-role":
        role = {
            "name": payload["name"],
            "responsibility": payload.get("responsibility", []),
            "input": payload.get("input", []),
            "output": payload.get("output", []),
            "owned_paths": payload.get("owned_paths", []),
        }
        upsert_by_key(new_snapshot["role_decomposition"]["roles"], "name", role["name"], role)
        return new_snapshot

    if command == "add-context-packet":
        task_id = payload["task_id"]
        packet = {
            "task_id": task_id,
            "goal": payload["goal"],
            "constraints": payload.get("constraints", []),
            "files": payload.get("files", []),
            "state_ref": payload.get("state_ref")
            or f"snapshot.json#/state_externalization/tasks/{task_id}",
            "verification": payload.get("verification", []),
            "status": payload.get("status", "draft"),
        }
        if packet["status"] not in PACKET_STATUSES:
            raise ValueError(f"Invalid packet status: {packet['status']}")
        upsert_by_key(
            new_snapshot["context_isolation"]["context_packets"], "task_id", task_id, packet
        )
        return new_snapshot

    if command == "record-decision":
        decision = {
            "id": payload["id"],
            "summary": payload["summary"],
            "reason": payload["reason"],
        }
        upsert_by_key(new_snapshot["state_externalization"]["decisions"], "id", decision["id"], decision)
        return new_snapshot

    if command == "record-validation":
        task_id = payload["task_id"]
        if payload["result"] not in VALIDATION_RESULTS:
            raise ValueError(f"Invalid validation result: {payload['result']}")
        state_validation = {
            "task_id": task_id,
            "command": payload["command"],
            "result": payload["result"],
        }
        new_snapshot["state_externalization"]["validations"].append(state_validation)
        validation = {
            "name": payload.get("name", "validation"),
            "command": payload["command"],
            "result": payload["result"],
            "reason": payload.get("reason", ""),
        }
        entries = new_snapshot["validation_loop"]["task_validations"]
        for item in entries:
            if item["task_id"] == task_id:
                item["validation"].append(validation)
                break
        else:
            entries.append({"task_id": task_id, "validation": [validation]})
        return new_snapshot

    if command == "assign-worker":
        task_id = payload["task_id"]
        owner = payload["owner"]
        if payload.get("worker_status", "idle") not in WORKER_STATUSES:
            raise ValueError(f"Invalid worker status: {payload.get('worker_status')}")
        backlog = {
            "id": task_id,
            "priority": payload.get("priority", 1),
            "status": payload.get("status", "todo"),
            "owner": owner,
        }
        worker = {
            "name": owner,
            "role": payload.get("role", "implementer"),
            "status": payload.get("worker_status", "idle"),
        }
        upsert_by_key(new_snapshot["central_orchestration"]["backlog"], "id", task_id, backlog)
        upsert_by_key(new_snapshot["central_orchestration"]["workers"], "name", owner, worker)
        if payload.get("scope"):
            parallel = {
                "id": task_id,
                "owner": owner,
                "scope": payload.get("scope", []),
                "depends_on": payload.get("depends_on", []),
            }
            upsert_by_key(new_snapshot["parallel_execution"]["parallel_tasks"], "id", task_id, parallel)
        return new_snapshot

    if command == "record-report":
        result = payload["result"]
        if result not in REPORT_RESULTS:
            raise ValueError(f"Invalid report result: {result}")
        report = {
            "task_id": payload["task_id"],
            "result": result,
            "next_action": payload["next_action"],
        }
        upsert_by_key(
            new_snapshot["central_orchestration"]["reports"], "task_id", report["task_id"], report
        )
        return new_snapshot

    if command == "set-join-point":
        new_snapshot["parallel_execution"]["join_point"] = payload["join_point"]
        return new_snapshot

    if command == "register-team":
        team = {
            "lead": payload["lead"],
            "teammates": payload.get("teammates", []),
        }
        new_snapshot["compositions"]["agent_team"]["team"] = team
        if payload.get("shared_board") is not None:
            new_snapshot["compositions"]["agent_team"]["shared_board"] = payload["shared_board"]
        elif new_snapshot["central_orchestration"]["backlog"]:
            new_snapshot["compositions"]["agent_team"]["shared_board"] = [
                {
                    "task_id": item["id"],
                    "owner": item["owner"],
                    "status": item["status"],
                }
                for item in new_snapshot["central_orchestration"]["backlog"]
            ]
        return new_snapshot

    raise ValueError(f"Unsupported command: {command}")


def replay_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = empty_snapshot()
    for event in events:
        snapshot = apply_event(snapshot, event)
    return snapshot


def refresh_snapshot_from_events(base_dir: Path | None = None) -> dict[str, Any]:
    events = load_events(base_dir)
    snapshot = replay_events(events)
    write_snapshot(snapshot, base_dir)
    return snapshot


def write_fresh_store(base_dir: Path | None = None) -> None:
    root = store_dir(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": now_iso(),
        "command": "init-store",
        "payload": {},
        "prev_hash": None,
    }
    event["hash"] = compute_event_hash(event)
    rewrite_events([event], base_dir)
    write_snapshot(empty_snapshot(), base_dir)


def load_json_arg(value: str) -> Any:
    return json.loads(value)


def parse_teammate(value: str) -> dict[str, Any]:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "Teammate must use `name:role:input1|input2` format"
        )
    name, role, raw_inputs = parts
    return {
        "name": name,
        "role": role,
        "input": [item for item in raw_inputs.split("|") if item],
    }


def get_path_value(snapshot: dict[str, Any], dotted_path: str) -> Any:
    value: Any = snapshot
    for segment in dotted_path.split("."):
        if isinstance(value, dict):
            value = value[segment]
        else:
            raise KeyError(dotted_path)
    return value


def handle_init_store(args: argparse.Namespace) -> int:
    if store_dir().exists() and not args.force:
        raise SystemExit("Store already exists. Use `--force` to recreate it.")
    write_fresh_store()
    print(store_dir())
    return 0


def handle_show(args: argparse.Namespace) -> int:
    ensure_store_exists()
    snapshot = load_snapshot()
    if args.path:
        print(pretty_json(get_path_value(snapshot, args.path)))
    else:
        print(pretty_json(snapshot))
    return 0


def handle_snapshot(args: argparse.Namespace) -> int:
    ensure_store_exists()
    snapshot = refresh_snapshot_from_events()
    if args.path:
        print(pretty_json(get_path_value(snapshot, args.path)))
    else:
        print(pretty_json(snapshot))
    return 0


def handle_mutation(command: str, payload: dict[str, Any]) -> int:
    ensure_store_exists()
    snapshot = replay_events(load_events())
    event = {
        "ts": now_iso(),
        "command": command,
        "payload": payload,
        "prev_hash": load_events()[-1]["hash"],
    }
    event["hash"] = compute_event_hash(event)
    new_snapshot = apply_event(snapshot, event)
    append_event(None, command, payload)
    write_snapshot(new_snapshot)
    print(snapshot_path())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="State store CRUD for agent-engineer")
    subparsers = parser.add_subparsers(dest="action", required=True)

    init_store = subparsers.add_parser("init-store")
    init_store.add_argument("--force", action="store_true")

    show = subparsers.add_parser("show")
    show.add_argument("--path")

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--path")

    add_task = subparsers.add_parser("add-task")
    add_task.add_argument("--id", required=True)
    add_task.add_argument("--title", required=True)
    add_task.add_argument("--goal")
    add_task.add_argument("--input", nargs="*", default=[])
    add_task.add_argument("--output", nargs="*", default=[])
    add_task.add_argument("--done-when", nargs="*", default=[])
    add_task.add_argument("--depends-on", nargs="*", default=[])
    add_task.add_argument("--status", default="todo")
    add_task.add_argument("--owner", default="")

    update = subparsers.add_parser("update-task-status")
    update.add_argument("--task-id", required=True)
    update.add_argument("--status", required=True)
    update.add_argument("--owner", default="")

    add_role = subparsers.add_parser("add-role")
    add_role.add_argument("--name", required=True)
    add_role.add_argument("--responsibility", nargs="*", default=[])
    add_role.add_argument("--input", nargs="*", default=[])
    add_role.add_argument("--output", nargs="*", default=[])
    add_role.add_argument("--owned-paths", nargs="*", default=[])

    add_packet = subparsers.add_parser("add-context-packet")
    add_packet.add_argument("--task-id", required=True)
    add_packet.add_argument("--goal", required=True)
    add_packet.add_argument("--constraints", nargs="*", default=[])
    add_packet.add_argument("--files", nargs="*", default=[])
    add_packet.add_argument("--state-ref")
    add_packet.add_argument("--verification", nargs="*", default=[])
    add_packet.add_argument("--status", default="draft")

    decision = subparsers.add_parser("record-decision")
    decision.add_argument("--id", required=True)
    decision.add_argument("--summary", required=True)
    decision.add_argument("--reason", required=True)

    validation = subparsers.add_parser("record-validation")
    validation.add_argument("--task-id", required=True)
    validation.add_argument("--name", default="validation")
    validation.add_argument("--validation-command", required=True)
    validation.add_argument("--result", required=True)
    validation.add_argument("--reason", default="")

    assign = subparsers.add_parser("assign-worker")
    assign.add_argument("--task-id", required=True)
    assign.add_argument("--owner", required=True)
    assign.add_argument("--priority", type=int, default=1)
    assign.add_argument("--status", default="todo")
    assign.add_argument("--role", default="implementer")
    assign.add_argument("--worker-status", default="idle")
    assign.add_argument("--scope", nargs="*", default=[])
    assign.add_argument("--depends-on", nargs="*", default=[])

    report = subparsers.add_parser("record-report")
    report.add_argument("--task-id", required=True)
    report.add_argument("--result", required=True)
    report.add_argument("--next-action", required=True)

    join = subparsers.add_parser("set-join-point")
    join.add_argument("--join-point", required=True)

    team = subparsers.add_parser("register-team")
    team.add_argument("--lead", required=True)
    team.add_argument("--teammate", action="append", type=parse_teammate, default=[])
    team.add_argument("--shared-board-json")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.action == "init-store":
        return handle_init_store(args)
    if args.action == "show":
        return handle_show(args)
    if args.action == "snapshot":
        return handle_snapshot(args)
    if args.action == "add-task":
        return handle_mutation(
            "add-task",
            {
                "id": args.id,
                "title": args.title,
                "goal": args.goal,
                "input": args.input,
                "output": args.output,
                "done_when": args.done_when,
                "depends_on": args.depends_on,
                "status": args.status,
                "owner": args.owner,
                "updated_at": now_iso(),
            },
        )
    if args.action == "update-task-status":
        return handle_mutation(
            "update-task-status",
            {
                "task_id": args.task_id,
                "status": args.status,
                "owner": args.owner,
                "updated_at": now_iso(),
            },
        )
    if args.action == "add-role":
        return handle_mutation(
            "add-role",
            {
                "name": args.name,
                "responsibility": args.responsibility,
                "input": args.input,
                "output": args.output,
                "owned_paths": args.owned_paths,
            },
        )
    if args.action == "add-context-packet":
        return handle_mutation(
            "add-context-packet",
            {
                "task_id": args.task_id,
                "goal": args.goal,
                "constraints": args.constraints,
                "files": args.files,
                "state_ref": args.state_ref,
                "verification": args.verification,
                "status": args.status,
            },
        )
    if args.action == "record-decision":
        return handle_mutation(
            "record-decision",
            {"id": args.id, "summary": args.summary, "reason": args.reason},
        )
    if args.action == "record-validation":
        return handle_mutation(
            "record-validation",
            {
                "task_id": args.task_id,
                "name": args.name,
                "command": args.validation_command,
                "result": args.result,
                "reason": args.reason,
            },
        )
    if args.action == "assign-worker":
        return handle_mutation(
            "assign-worker",
            {
                "task_id": args.task_id,
                "owner": args.owner,
                "priority": args.priority,
                "status": args.status,
                "role": args.role,
                "worker_status": args.worker_status,
                "scope": args.scope,
                "depends_on": args.depends_on,
            },
        )
    if args.action == "record-report":
        return handle_mutation(
            "record-report",
            {
                "task_id": args.task_id,
                "result": args.result,
                "next_action": args.next_action,
            },
        )
    if args.action == "set-join-point":
        return handle_mutation("set-join-point", {"join_point": args.join_point})
    if args.action == "register-team":
        shared_board = (
            load_json_arg(args.shared_board_json) if args.shared_board_json else None
        )
        return handle_mutation(
            "register-team",
            {
                "lead": args.lead,
                "teammates": args.teammate,
                "shared_board": shared_board,
            },
        )
    raise SystemExit(f"Unsupported command: {args.action}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
