#!/usr/bin/env python3
"""Fail closed when the active task manifest and repository state disagree."""

from __future__ import annotations

import csv
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "implementation" / "CURRENT_TASK.json"
PHASE_STATUS = ROOT / "implementation" / "PHASE_STATUS.yaml"
ACTIVE_GOAL = ROOT / "implementation" / "ACTIVE_EXECUTION_GOAL.md"
NEXT_ACTION = ROOT / "implementation" / "NEXT_ACTION.md"
CONTROLLER = ROOT / "implementation" / "AUTOPILOT_CONTROLLER.md"
TRACEABILITY = ROOT / "implementation" / "REQUIREMENT_TRACEABILITY.csv"
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")
TASK_ID = re.compile(r"^[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)*$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9._*?\[\]/-]+$")
SAFE_COMMANDS = {"bash", "git", "npm", "npx", "python"}
REQUIRED_CHECK_LEVELS = {"level_1", "level_2", "runtime_preflight", "level_3"}


class CurrentTaskError(RuntimeError):
    """Raised when the active task contract is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CurrentTaskError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate manifest key: {key}")
        result[key] = value
    return result


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentTaskError(f"cannot read current task manifest: {exc}") from exc
    require(type(value) is dict, "current task manifest must be a JSON object")
    required = {
        "schema_version",
        "task_id",
        "task_kind",
        "phase",
        "status",
        "completion_gate",
        "authorized_next_task",
        "base_checkpoint",
        "predecessor_product_checkpoint",
        "requirement_ids",
        "scope",
        "non_scope",
        "frozen_invariants",
        "allowed_paths",
        "affected_checks",
        "expected_state",
        "rollback",
    }
    require(set(value) == required, "current task manifest keys drifted")
    return value


def string_list(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    require(type(value) is list, f"{label} must be a list")
    values = list(value)
    require(allow_empty or bool(values), f"{label} must not be empty")
    require(
        all(type(item) is str and item.strip() == item and item for item in values),
        f"{label} must contain non-empty trimmed strings",
    )
    require(len(set(values)) == len(values), f"{label} must not contain duplicates")
    return values


def top_level_yaml_scalars(path: Path = PHASE_STATUS) -> dict[str, str]:
    scalars: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CurrentTaskError(f"cannot read Phase status: {exc}") from exc
    for line in lines:
        if not line or line.startswith((" ", "#")) or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip().strip("'\"")
        if not value:
            continue
        require(key not in scalars, f"duplicate top-level Phase status key: {key}")
        scalars[key] = value
    return scalars


def git(*arguments: str, root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    require(
        result.returncode == 0,
        f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
    )
    return result.stdout.strip()


def validate_check_commands(value: object) -> None:
    require(type(value) is dict, "affected_checks must be an object")
    require(set(value) == REQUIRED_CHECK_LEVELS, "affected check levels drifted")
    for level, commands in value.items():
        require(type(commands) is list and commands, f"{level} checks must not be empty")
        for command in commands:
            require(
                type(command) is list and len(command) >= 2,
                f"{level} commands must be non-trivial argument arrays",
            )
            require(
                all(type(argument) is str and argument for argument in command),
                f"{level} command arguments must be non-empty strings",
            )
            require(command[0] in SAFE_COMMANDS, f"unsafe check executable: {command[0]}")
            require(
                not any(
                    argument in {";", "&&", "||", "|"}
                    or "--update-snapshots" in argument
                    for argument in command
                ),
                f"unsafe or baseline-mutating check command in {level}",
            )
            require(
                not (command[0] in {"bash", "python"} and command[1] == "-c"),
                f"inline source is not allowed in {level} check commands",
            )


def validate_requirement_ids(requirement_ids: list[str], phase: int, task_kind: str) -> None:
    if task_kind == "delivery_infrastructure":
        require(not requirement_ids, "delivery-only task must not claim product Requirements")
        return
    require(requirement_ids, "product task must freeze at least one Requirement ID")
    with TRACEABILITY.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    trace_ids = {row.get("requirement_id", "") for row in rows}
    anchor = ROOT / "implementation" / f"phase-{phase}-requirement-anchor.md"
    require(anchor.is_file(), f"Phase {phase} Requirement anchor is missing")
    anchor_text = anchor.read_text(encoding="utf-8")
    for requirement_id in requirement_ids:
        require(requirement_id in trace_ids, f"unknown Requirement ID: {requirement_id}")
        require(
            requirement_id in anchor_text,
            f"Requirement {requirement_id} is absent from the Phase {phase} anchor",
        )


def changed_paths(base_checkpoint: str) -> tuple[str, ...]:
    git("cat-file", "-e", f"{base_checkpoint}^{{commit}}")
    git("merge-base", "--is-ancestor", base_checkpoint, "HEAD")
    output = git("diff", "--name-only", "--diff-filter=ACMRTUXB", base_checkpoint, "HEAD")
    paths = tuple(line for line in output.splitlines() if line)
    require(len(set(paths)) == len(paths), "changed path list contains duplicates")
    return paths


def validate_allowed_paths(patterns: list[str], paths: Iterable[str]) -> None:
    for pattern in patterns:
        require(
            SAFE_PATH.fullmatch(pattern) is not None
            and not pattern.startswith(("/", "../"))
            and "/../" not in pattern,
            f"unsafe allowed path pattern: {pattern}",
        )
    for path in paths:
        require(
            any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns),
            f"changed path is outside the current task manifest: {path}",
        )


def validate_current_task(
    manifest_path: Path = MANIFEST,
    *,
    check_git: bool = True,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    require(manifest["schema_version"] == 1, "task manifest schema_version must be 1")
    require(
        type(manifest["task_id"]) is str
        and TASK_ID.fullmatch(manifest["task_id"]) is not None,
        "task_id is invalid",
    )
    require(
        manifest["task_kind"] in {"delivery_infrastructure", "product"},
        "task_kind is invalid",
    )
    require(
        type(manifest["phase"]) is int and 0 <= manifest["phase"] <= 9,
        "phase must be an integer from 0 through 9",
    )
    require(
        type(manifest["status"]) is str and manifest["status"].startswith("IN_PROGRESS"),
        "active task status must be IN_PROGRESS",
    )
    require(
        manifest["completion_gate"] in {"LEVEL_2", "LEVEL_3"},
        "completion_gate must be LEVEL_2 or LEVEL_3",
    )
    require(
        type(manifest["authorized_next_task"]) is str
        and TASK_ID.fullmatch(manifest["authorized_next_task"]) is not None,
        "authorized_next_task is invalid",
    )
    if manifest["task_kind"] == "delivery_infrastructure":
        require(
            manifest["completion_gate"] == "LEVEL_3",
            "delivery infrastructure changes require a complete Level 3 Gate",
        )
    for checkpoint_name in ("base_checkpoint", "predecessor_product_checkpoint"):
        require(
            type(manifest[checkpoint_name]) is str
            and HEX_SHA.fullmatch(manifest[checkpoint_name]) is not None,
            f"{checkpoint_name} must be one full lowercase Git SHA",
        )

    requirement_ids = string_list(
        manifest["requirement_ids"],
        "requirement_ids",
        allow_empty=True,
    )
    validate_requirement_ids(
        requirement_ids,
        manifest["phase"],
        manifest["task_kind"],
    )
    for label in ("scope", "non_scope", "frozen_invariants"):
        string_list(manifest[label], label)
    allowed_paths = string_list(manifest["allowed_paths"], "allowed_paths")
    validate_check_commands(manifest["affected_checks"])

    rollback = manifest["rollback"]
    require(type(rollback) is dict, "rollback must be an object")
    require(
        set(rollback) == {"before_product_resume", "after_product_resume"}
        and all(type(value) is str and value.strip() for value in rollback.values()),
        "rollback must define both non-empty recovery boundaries",
    )
    phase_state = top_level_yaml_scalars()
    expected_state = manifest["expected_state"]
    require(type(expected_state) is dict, "expected_state must be an object")
    require(
        set(expected_state)
        == {
            "phase_status_current_task",
            "phase_status_execution_hold",
            "phase_status_resumed_product_task",
            "active_goal_marker",
            "next_action_marker",
            "controller_marker",
        },
        "expected_state keys drifted",
    )
    require(
        phase_state.get("current_phase") == str(manifest["phase"]),
        "Phase status current_phase disagrees with the task manifest",
    )
    require(
        phase_state.get("current_task") == expected_state["phase_status_current_task"]
        == manifest["task_id"],
        "Phase status current_task disagrees with the task manifest",
    )
    require(
        phase_state.get("current_task_status") == manifest["status"],
        "Phase status current_task_status disagrees with the task manifest",
    )
    require(
        phase_state.get("execution_hold")
        == expected_state["phase_status_execution_hold"],
        "Phase status execution hold drifted",
    )
    require(
        phase_state.get("resumed_product_task")
        == expected_state["phase_status_resumed_product_task"],
        "resumed product task drifted",
    )
    if manifest["task_kind"] == "delivery_infrastructure":
        require(
            expected_state["phase_status_resumed_product_task"]
            == manifest["authorized_next_task"],
            "delivery task authorized_next_task drifted",
        )

    for path, marker_key in (
        (ACTIVE_GOAL, "active_goal_marker"),
        (NEXT_ACTION, "next_action_marker"),
        (CONTROLLER, "controller_marker"),
    ):
        text = path.read_text(encoding="utf-8")
        marker = expected_state[marker_key]
        require(type(marker) is str and marker in text, f"state marker missing from {path.name}")

    if check_git:
        validate_allowed_paths(
            allowed_paths,
            changed_paths(manifest["base_checkpoint"]),
        )
    return manifest


def main() -> int:
    try:
        manifest = validate_current_task()
    except (CurrentTaskError, OSError, UnicodeError, csv.Error) as exc:
        print(f"current task verification failed: {exc}", file=sys.stderr)
        return 1
    paths = changed_paths(manifest["base_checkpoint"])
    print(
        "current task verification passed: "
        f"{manifest['task_id']} with {len(paths)} committed changed paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
