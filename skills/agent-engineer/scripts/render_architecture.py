#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from build_runner import architecture_path, extract_architecture_json


def load_architecture_text(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Missing architecture document: {path}")
    text = path.read_text(encoding="utf-8")
    return text, extract_architecture_json(text)


def cli_status() -> dict[str, str]:
    return {
        "codex": "installed" if shutil.which("codex") else "missing",
        "claude": "installed" if shutil.which("claude") else "missing",
        "opencode": "installed" if shutil.which("opencode") else "missing",
    }


def mermaid_for_architecture(architecture: dict[str, Any]) -> str:
    lines = ["flowchart TD", '  start["Approved Architecture"]']
    for step in architecture["steps"]:
        label = f"{step['id']}\\n{step['pattern']}\\n{step['engine_id']}"
        lines.append(f'  {step["id"].replace("-", "_")}["{label}"]')
        depends_on = step.get("depends_on", [])
        if depends_on:
            for dep in depends_on:
                lines.append(
                    f"  {dep.replace('-', '_')} --> {step['id'].replace('-', '_')}"
                )
        else:
            lines.append(f"  start --> {step['id'].replace('-', '_')}")
    return "\n".join(lines)


def summary_table(architecture: dict[str, Any], status: dict[str, str]) -> str:
    return "\n".join(
        [
            "| 항목 | 값 |",
            "| --- | --- |",
            f"| approval_status | `{architecture['approval_status']}` |",
            f"| composition | `{architecture['composition']}` |",
            f"| selected_patterns | {', '.join(f'`{item}`' for item in architecture['selected_patterns'])} |",
            f"| max_workers | `{architecture['parallel_policy'].get('max_workers', 1)}` |",
            f"| retry_policy | `{architecture['retry_policy'].get('mode')}` / `{architecture['retry_policy'].get('max_attempts')}` / `{architecture['retry_policy'].get('on_exhausted')}` |",
            f"| require_pass_before_done | `{architecture['validation_policy'].get('require_pass_before_done')}` |",
            f"| prefer_specialist_skill | `{architecture['delegation_policy'].get('prefer_specialist_skill')}` |",
            f"| cli_status | codex={status['codex']}, claude={status['claude']}, opencode={status['opencode']} |",
        ]
    )


def engine_table(architecture: dict[str, Any]) -> str:
    lines = [
        "| Engine | CLI | Model | Purpose |",
        "| --- | --- | --- | --- |",
    ]
    for engine in architecture["engines"]:
        lines.append(
            f"| `{engine['id']}` | `{engine['cli']}` | `{engine['model']}` | `{engine['purpose']}` |"
        )
    return "\n".join(lines)


def step_table(architecture: dict[str, Any]) -> str:
    lines = [
        "| Step | Pattern | Engine | Depends On | Writes To |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in architecture["steps"]:
        deps = ", ".join(f"`{item}`" for item in step.get("depends_on", [])) or "-"
        writes = ", ".join(f"`{item}`" for item in step.get("writes_to", [])) or "-"
        lines.append(
            f"| `{step['id']}` | `{step['pattern']}` | `{step['engine_id']}` | {deps} | {writes} |"
        )
    return "\n".join(lines)


def warnings(status: dict[str, str], architecture: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for engine in architecture["engines"]:
        if status[engine["cli"]] == "missing":
            items.append(
                f"- 경고: `{engine['cli']}`가 설치되어 있지 않다. 이 엔진은 승인안에서는 경고 대상이다."
            )
    if not items:
        items.append("- 경고 없음")
    return items


def render_document(architecture: dict[str, Any]) -> str:
    status = cli_status()
    doc = [
        "# Agent Engineer Architecture",
        "",
        "이 문서는 승인용 단일 소스 오브 트루스다. 사람은 본문을 읽고 승인하고, 실행 스크립트는 마지막 JSON 블록만 읽는다.",
        "",
        "## Approval Summary",
        "",
        summary_table(architecture, status),
        "",
        "## Engine Matrix",
        "",
        engine_table(architecture),
        "",
        "## Step Flow",
        "",
        "```mermaid",
        mermaid_for_architecture(architecture),
        "```",
        "",
        "## Step Table",
        "",
        step_table(architecture),
        "",
        "## CLI Warnings",
        "",
        *warnings(status, architecture),
        "",
        "## Machine-Readable JSON",
        "",
        "```json",
        json.dumps(architecture, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(doc)


def main() -> int:
    path = architecture_path()
    _, architecture = load_architecture_text(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_document(architecture), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
