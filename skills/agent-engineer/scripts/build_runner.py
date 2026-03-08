#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any


def app_root(base_dir: Path | None = None) -> Path:
    base = (base_dir or Path.cwd()).resolve()
    return base / ".codex" / "agent-engineer"


def architecture_path(base_dir: Path | None = None) -> Path:
    return app_root(base_dir) / "architecture.md"


def runs_dir(base_dir: Path | None = None) -> Path:
    return app_root(base_dir) / "runs"


def extract_architecture_json(text: str) -> dict[str, Any]:
    matches = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not matches:
        raise ValueError("architecture.md must contain a JSON code fence")
    return json.loads(matches[-1])


def load_architecture(base_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = architecture_path(base_dir)
    if not path.exists():
        raise ValueError(f"Missing architecture document: {path}")
    architecture = extract_architecture_json(path.read_text(encoding="utf-8"))
    return path, architecture


def cli_status() -> dict[str, str | None]:
    return {name: shutil.which(name) for name in ("codex", "claude", "opencode")}


def allow_missing_cli() -> bool:
    return os.getenv("AGENT_ENGINEER_ALLOW_MISSING_CLI") == "1"


def topological_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {step["id"]: step for step in steps}
    if len(by_id) != len(steps):
        raise ValueError("Step ids must be unique")
    incoming = {step["id"]: set(step.get("depends_on", [])) for step in steps}
    for step_id, deps in incoming.items():
        missing = deps - by_id.keys()
        if missing:
            raise ValueError(f"Step {step_id} depends on unknown step(s): {sorted(missing)}")
    ordered: list[dict[str, Any]] = []
    ready = sorted(step_id for step_id, deps in incoming.items() if not deps)
    while ready:
        step_id = ready.pop(0)
        ordered.append(by_id[step_id])
        for candidate, deps in incoming.items():
            if step_id in deps:
                deps.remove(step_id)
                if not deps and by_id[candidate] not in ordered and candidate not in ready:
                    ready.append(candidate)
        ready.sort()
    if len(ordered) != len(steps):
        raise ValueError("Step dependency graph contains a cycle")
    return ordered


def validate_architecture(architecture: dict[str, Any], require_approved: bool = True) -> list[dict[str, Any]]:
    required = {
        "version",
        "approval_status",
        "composition",
        "selected_patterns",
        "engines",
        "steps",
        "parallel_policy",
        "retry_policy",
        "validation_policy",
        "delegation_policy",
    }
    missing = required - architecture.keys()
    if missing:
        raise ValueError(f"Architecture JSON missing keys: {sorted(missing)}")
    if require_approved and architecture["approval_status"] != "approved":
        raise ValueError("Architecture is not approved")
    engines = architecture["engines"]
    if not engines:
        raise ValueError("Architecture must define at least one engine")
    engine_ids = set()
    installed = cli_status()
    skip_cli_check = allow_missing_cli()
    for engine in engines:
        for key in ("id", "cli", "model", "purpose"):
            if not engine.get(key):
                raise ValueError(f"Engine is missing `{key}`")
        if engine["id"] in engine_ids:
            raise ValueError(f"Duplicate engine id: {engine['id']}")
        engine_ids.add(engine["id"])
        if engine["cli"] not in installed:
            raise ValueError(f"Unsupported CLI: {engine['cli']}")
        if installed[engine["cli"]] is None and not skip_cli_check:
            raise ValueError(f"Selected CLI is not installed: {engine['cli']}")
    ordered = topological_steps(architecture["steps"])
    for step in ordered:
        for key in ("id", "pattern", "engine_id", "writes_to"):
            if key not in step:
                raise ValueError(f"Step {step.get('id', '<unknown>')} missing `{key}`")
        if step["engine_id"] not in engine_ids:
            raise ValueError(f"Step {step['id']} references unknown engine {step['engine_id']}")
    retry_policy = architecture["retry_policy"]
    if retry_policy.get("mode") != "until-pass-or-max-attempts":
        raise ValueError("retry_policy.mode must be `until-pass-or-max-attempts`")
    if int(retry_policy.get("max_attempts", 0)) < 1:
        raise ValueError("retry_policy.max_attempts must be >= 1")
    if retry_policy.get("on_exhausted") != "blocked":
        raise ValueError("retry_policy.on_exhausted must be `blocked`")
    if architecture["validation_policy"].get("require_pass_before_done") is not True:
        raise ValueError("validation_policy.require_pass_before_done must be true")
    return ordered


def default_run_id() -> str:
    return dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def write_runner(run_dir: Path, payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "artifacts").mkdir()
    runner_json = run_dir / "runner.json"
    runner_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_arch_path = Path(__file__).resolve().parent / "run_architecture.py"
    run_sh = run_dir / "run.sh"
    run_sh.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'python3 "{run_arch_path}" --runner-dir "$(cd "$(dirname "$0")" && pwd)" "$@"\n',
        encoding="utf-8",
    )
    run_sh.chmod(run_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    run_id = sys.argv[1] if len(sys.argv) > 1 else default_run_id()
    _, architecture = load_architecture()
    ordered = validate_architecture(architecture, require_approved=True)
    run_dir = runs_dir() / run_id
    if run_dir.exists():
        raise ValueError(f"Run directory already exists: {run_dir}")
    payload = {
        "run_id": run_id,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace": str(Path.cwd().resolve()),
        "architecture_path": str(architecture_path()),
        "architecture": architecture,
        "ordered_steps": ordered,
        "cli_status": cli_status(),
    }
    write_runner(run_dir, payload)
    print(run_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
