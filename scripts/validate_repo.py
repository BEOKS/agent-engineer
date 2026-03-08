#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SKILL_FILES = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/pattern-catalog.md",
    "references/architecture-selection.md",
    "references/domain-routing.md",
    "references/source-index.md",
    "scripts/agent_state.py",
    "scripts/verify_store.py",
    "scripts/render_architecture.py",
    "scripts/build_runner.py",
    "scripts/run_architecture.py",
    "scripts/invoke_agent.py",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path} is missing YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def assert_exists(base: Path, relative: str) -> None:
    path = base / relative
    if not path.exists():
        raise ValueError(f"Missing required file: {path}")


def validate_skill(skill_dir: Path) -> None:
    for relative in REQUIRED_SKILL_FILES:
        assert_exists(skill_dir, relative)

    frontmatter = parse_frontmatter(skill_dir / "SKILL.md")
    if frontmatter.get("name") != "agent-engineer":
        raise ValueError("SKILL.md name must be `agent-engineer`")
    description = frontmatter.get("description", "")
    required_phrases = [
        "task decomposition",
        "role decomposition",
        "context isolation",
        "state externalization",
        "validation loops",
        "parallel execution",
        "central orchestration",
    ]
    lowered = description.lower()
    for phrase in required_phrases:
        if phrase not in lowered:
            raise ValueError(f"SKILL.md description must mention `{phrase}`")

    openai_yaml = (skill_dir / "agents" / "openai.yaml").read_text(encoding="utf-8")
    if "$agent-engineer" not in openai_yaml:
        raise ValueError("agents/openai.yaml must mention `$agent-engineer` in default_prompt")


def main() -> int:
    root = repo_root()
    skill_dir = root / "skills" / "agent-engineer"
    validate_skill(skill_dir)
    print(f"OK: {skill_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
