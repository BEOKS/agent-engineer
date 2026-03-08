#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_runner import load_architecture, validate_architecture


def build_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise ValueError("Use either --prompt or --prompt-file")
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise ValueError("A prompt is required")


def engine_for_id(architecture: dict[str, Any], engine_id: str) -> dict[str, Any]:
    for engine in architecture["engines"]:
        if engine["id"] == engine_id:
            return engine
    raise ValueError(f"Unknown engine id: {engine_id}")


def command_for_engine(engine: dict[str, Any], prompt: str, cwd: Path) -> list[str]:
    cli = engine["cli"]
    model = engine["model"]
    if cli == "codex":
        return [cli, "exec", "--skip-git-repo-check", "-C", str(cwd), "-m", model, prompt]
    if cli == "claude":
        return [cli, "-p", "--model", model, prompt]
    if cli == "opencode":
        return [cli, "run", "--model", model, prompt]
    raise ValueError(f"Unsupported CLI: {cli}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Invoke approved agent engine")
    parser.add_argument("--engine-id", required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--output-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    _, architecture = load_architecture()
    validate_architecture(architecture, require_approved=True)
    engine = engine_for_id(architecture, args.engine_id)
    prompt = build_prompt(args)
    command = command_for_engine(engine, prompt, Path.cwd())

    if args.dry_run:
        payload = {
            "engine_id": args.engine_id,
            "cli": engine["cli"],
            "model": engine["model"],
            "command": command,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output_file:
            Path(args.output_file).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0

    result = subprocess.run(
        command,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    if args.output_file:
        Path(args.output_file).write_text(result.stdout, encoding="utf-8")
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
