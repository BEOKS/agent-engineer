#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def skill_scripts() -> Path:
    return repo_root() / "skills" / "agent-engineer" / "scripts"


def run(command: list[str], cwd: Path, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if expect_ok and result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f"Failed: {' '.join(command)}")
    return result


def architecture_payload(status: str) -> dict[str, object]:
    return {
        "version": 1,
        "approval_status": status,
        "composition": "hybrid",
        "selected_patterns": [
            "task-decomposition",
            "parallel-execution",
            "state-externalization",
            "validation-loop",
        ],
        "engines": [
            {"id": "planner", "cli": "codex", "model": "gpt-5", "purpose": "decomposition"},
            {"id": "worker", "cli": "codex", "model": "gpt-5", "purpose": "worker"},
        ],
        "steps": [
            {
                "id": "step-01",
                "pattern": "task-decomposition",
                "engine_id": "planner",
                "depends_on": [],
                "writes_to": ["task_decomposition", "state_externalization"],
            },
            {
                "id": "step-02",
                "pattern": "parallel-execution",
                "engine_id": "planner",
                "depends_on": ["step-01"],
                "writes_to": ["parallel_execution", "central_orchestration"],
            },
            {
                "id": "step-03",
                "pattern": "state-externalization",
                "engine_id": "planner",
                "depends_on": ["step-02"],
                "writes_to": ["context_isolation", "state_externalization"],
            },
            {
                "id": "step-04",
                "pattern": "validation-loop",
                "engine_id": "worker",
                "depends_on": ["step-03"],
                "writes_to": [
                    "validation_loop",
                    "state_externalization",
                    "central_orchestration",
                ],
            },
        ],
        "parallel_policy": {"max_workers": 2},
        "retry_policy": {
            "mode": "until-pass-or-max-attempts",
            "max_attempts": 2,
            "on_exhausted": "blocked",
        },
        "validation_policy": {"require_pass_before_done": True},
        "delegation_policy": {"prefer_specialist_skill": True},
    }


def write_architecture(workspace: Path, status: str) -> Path:
    path = workspace / ".codex" / "agent-engineer" / "architecture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = architecture_payload(status)
    path.write_text(
        "# Draft\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    scripts = skill_scripts()
    with tempfile.TemporaryDirectory(prefix="agent-engineer-smoke-") as temp_dir:
        workspace = Path(temp_dir)
        write_architecture(workspace, "presented")

        pre_approval = run(
            ["python3", str(scripts / "build_runner.py")],
            cwd=workspace,
            expect_ok=False,
        )
        if pre_approval.returncode == 0 or "Architecture is not approved" not in (
            pre_approval.stderr + pre_approval.stdout
        ):
            raise RuntimeError("build_runner.py must fail before approval")

        write_architecture(workspace, "approved")
        run(["python3", str(scripts / "render_architecture.py")], cwd=workspace)
        run(["python3", str(scripts / "build_runner.py"), "test-run"], cwd=workspace)
        run(
            [
                "python3",
                str(scripts / "run_architecture.py"),
                "--runner-dir",
                str(workspace / ".codex" / "agent-engineer" / "runs" / "test-run"),
                "--goal",
                "Validate dry-run orchestration",
                "--dry-run",
            ],
            cwd=workspace,
        )
        run(["python3", str(scripts / "verify_store.py")], cwd=workspace)

        snapshot = json.loads(
            (workspace / ".codex" / "agent-engineer" / "store" / "snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        task_state = snapshot["state_externalization"]["tasks"]["TASK-001"]
        if task_state["status"] != "done":
            raise RuntimeError("Dry-run execution must finish TASK-001 as done")

    print("OK: smoke test passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
