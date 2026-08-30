#!/usr/bin/env python3
"""Fail-closed P8-07F production ERPNext read-only fact collector.

The collector exposes only the remote operations frozen by the P8-07F
governance transition.  Raw application names and tracked source content are
held only in a mode-0600 temporary state file; stdout contains sanitized
labels, structural metadata and checksums only.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "implementation" / "CURRENT_TASK.json"
TASK_ID = "P8-07F-FACTS"
SSH_ALIAS = "JCE-Core"
REMOTE_BENCH_ROOT = "frappe-bench"
LOCAL_TIMEZONE = ZoneInfo("Asia/Bangkok")
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")
APP_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
VERSION_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+/-]{0,127}$")
COMMIT_TOKEN = re.compile(r"^\([0-9a-f]{7,40}\)$")
REMOTE_TOKEN = re.compile(r"^[A-Za-z0-9_./:@+-]+$")
RELATIVE_PATH = re.compile(r"^[A-Za-z0-9_./+@-]+$")
SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
PUBLIC_APPS = {"frappe": "FRAPPE", "erpnext": "ERPNEXT"}
MAX_VERSION_BYTES = 64 * 1024
MAX_STATUS_BYTES = 128 * 1024
MAX_PATH_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024
MAX_DIFF_BYTES = 512 * 1024
MAX_RUNTIME_BYTES = 512 * 1024
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
RUNTIME_PAGE_SIZE = 200
RUNTIME_MAX_PAGES = 25
RUNTIME_PAGE_SIZE_OVERRIDES = {"CLIENT_SCRIPTS": 20}
SSH_OPTIONS = (
    "-T",
    "-o", "BatchMode=yes",
    "-o", "RequestTTY=no",
    "-o", "StrictHostKeyChecking=yes",
    "-o", "ForwardAgent=no",
    "-o", "ClearAllForwardings=yes",
    "-o", "ConnectionAttempts=1",
    "-o", "ConnectTimeout=10",
    "-o", "ControlMaster=no",
    "-o", "ControlPath=none",
    "-o", "PasswordAuthentication=no",
    "-o", "KbdInteractiveAuthentication=no",
    "-o", "NumberOfPasswordPrompts=0",
    "-o", "PermitLocalCommand=no",
    "-o", "LogLevel=ERROR",
)
SENSITIVE_PATH_PARTS = {
    ".env",
    "site_config.json",
    "common_site_config.json",
    "private",
    "backups",
    "logs",
    "credentials",
    "secrets",
}
SENSITIVE_CONTENT = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:password|passwd|api_secret|access_token|refresh_token|"
        r"private_key|secret_key)\s*[:=]\s*['\"][^'\"]+['\"]"
    ),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
REQUIRED_ERPNEXT_DOCTYPES = (
    "Approval Form",
    "Asset",
    "Asset Maintenance",
    "Asset Movement",
    "BOM",
    "Customer",
    "DMR",
    "Document Naming Rule",
    "Document Naming Rule Condition",
    "Engineering Change Request",
    "Injection Molding Condition",
    "Item",
    "Job Card",
    "Mold",
    "Mold Alteration",
    "Mold Management Settings",
    "Mold Outsource",
    "Mold Repair",
    "Mold Spare Part",
    "Mold Spare Part Usage",
    "Mold Trial Report",
    "Project",
    "Purchase Order",
    "Quality Inspection",
    "Quality Inspection Template",
    "Supplier",
    "System Settings",
    "Work Order",
)
RUNTIME_METADATA_SPECS: dict[str, dict[str, Any]] = {
    "CUSTOM_FIELDS": {
        "doctype": "Custom Field",
        "fields": ("name", "dt", "fieldname", "fieldtype", "options", "reqd", "read_only", "unique", "insert_after", "modified"),
        "protected_fields": ("options",),
    },
    "PROPERTY_SETTERS": {
        "doctype": "Property Setter",
        "fields": ("name", "doc_type", "field_name", "property", "property_type", "value", "modified"),
        "hashed_fields": ("value",),
    },
    "WORKFLOWS": {
        "doctype": "Workflow",
        "fields": ("name", "document_type", "is_active", "workflow_state_field", "modified"),
    },
    "WORKFLOW_STATES": {
        "doctype": "Workflow Document State",
        "fields": ("name", "parent", "state", "allow_edit", "doc_status", "is_optional_state", "modified"),
    },
    "WORKFLOW_TRANSITIONS": {
        "doctype": "Workflow Transition",
        "fields": ("name", "parent", "state", "action", "next_state", "allowed", "allow_self_approval", "condition", "modified"),
        "hashed_fields": ("condition",),
    },
    "ROLES": {
        "doctype": "Role",
        "fields": ("name", "desk_access", "is_custom", "disabled", "modified"),
    },
    "CUSTOM_DOC_PERMS": {
        "doctype": "Custom DocPerm",
        "fields": ("name", "parent", "role", "permlevel", "read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "share", "print", "email", "if_owner", "modified"),
    },
    "CLIENT_SCRIPTS": {
        "doctype": "Client Script",
        "fields": ("name", "dt", "view", "enabled", "script", "modified"),
        "hashed_fields": ("script",),
    },
    "SERVER_SCRIPTS": {
        "doctype": "Server Script",
        "fields": ("name", "script_type", "reference_doctype", "doctype_event", "event_frequency", "api_method", "disabled", "script", "modified"),
        "hashed_fields": ("script",),
    },
    "DOCTYPES": {
        "doctype": "DocType",
        "fields": ("name", "module", "custom", "istable", "issingle", "autoname", "track_changes", "is_submittable", "modified"),
        "filters": (("name", "in", REQUIRED_ERPNEXT_DOCTYPES),),
    },
    "DOCFIELDS": {
        "doctype": "DocField",
        "fields": ("name", "parent", "fieldname", "fieldtype", "options", "reqd", "read_only", "unique", "hidden", "permlevel", "idx", "modified"),
        "filters": (("parent", "in", REQUIRED_ERPNEXT_DOCTYPES),),
        "protected_fields": ("options",),
    },
    "DOCPERMS": {
        "doctype": "DocPerm",
        "fields": ("name", "parent", "role", "permlevel", "read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "share", "print", "email", "if_owner", "modified"),
        "filters": (("parent", "in", REQUIRED_ERPNEXT_DOCTYPES),),
    },
    "WEBHOOKS": {
        "doctype": "Webhook",
        "fields": ("name", "webhook_doctype", "webhook_docevent", "enabled", "request_method", "request_structure", "condition", "modified"),
        "hashed_fields": ("request_structure", "condition"),
    },
    "SCHEDULED_JOBS": {
        "doctype": "Scheduled Job Type",
        "fields": ("name", "method", "frequency", "stopped", "modified"),
    },
    "REPORTS": {
        "doctype": "Report",
        "fields": ("name", "report_name", "ref_doctype", "report_type", "is_standard", "disabled", "module", "modified"),
    },
    "PRINT_FORMATS": {
        "doctype": "Print Format",
        "fields": ("name", "doc_type", "standard", "disabled", "print_format_type", "modified"),
    },
    "NOTIFICATIONS": {
        "doctype": "Notification",
        "fields": ("name", "document_type", "event", "enabled", "channel", "modified"),
    },
    "DOCUMENT_NAMING_RULES": {
        "doctype": "Document Naming Rule",
        "fields": ("name", "document_type", "disabled", "priority", "prefix", "counter", "prefix_digits", "modified"),
        "hashed_fields": ("prefix",),
    },
    "DOCUMENT_NAMING_RULE_CONDITIONS": {
        "doctype": "Document Naming Rule Condition",
        "fields": ("name", "parent", "field", "condition", "value", "idx", "modified"),
        "hashed_fields": ("value",),
    },
}
SITE_FACT_FAMILIES = ("SYSTEM_LOCALE", "FILE_URL_SHAPES")
FILE_URL_SHAPE_FILTERS: dict[str, dict[str, Any]] = {
    "TOTAL": {},
    "LOCAL_PUBLIC": {"file_url": ["like", "/files/%"]},
    "LOCAL_PRIVATE": {"file_url": ["like", "/private/files/%"]},
    "EXTERNAL_HTTP": {"file_url": ["like", "http%"]},
}
PARENT_METADATA_FAMILIES = {
    "DOCFIELDS": ("DocType", "fields", None),
    "DOCPERMS": ("DocType", "permissions", None),
    "WORKFLOW_STATES": ("Workflow", "states", "WORKFLOWS"),
    "WORKFLOW_TRANSITIONS": ("Workflow", "transitions", "WORKFLOWS"),
    "DOCUMENT_NAMING_RULE_CONDITIONS": (
        "Document Naming Rule",
        "conditions",
        "DOCUMENT_NAMING_RULES",
    ),
}


class FactCollectionError(RuntimeError):
    """Raised when a read-only fact operation cannot be proven safe."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FactCollectionError(message)


def _timestamp() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat().replace("+00:00", "Z"),
        "local": now.astimezone(LOCAL_TIMEZONE).isoformat(),
        "timezone": "Asia/Bangkok",
    }


def _checksum(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    require(result.returncode == 0, "local Git preflight failed")
    return result.stdout.strip()


def _preflight(expected_sha: str) -> dict[str, Any]:
    require(HEX_SHA.fullmatch(expected_sha) is not None, "expected SHA is invalid")
    require(_git("rev-parse", "HEAD") == expected_sha, "local HEAD differs from expected SHA")
    for path in (
        "implementation/CURRENT_TASK.json",
        "scripts/collect_erpnext_production_facts.py",
    ):
        require(
            not _git("status", "--short", "--untracked-files=no", "--", path),
            f"governed collector path is dirty: {path}",
        )
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FactCollectionError("cannot load the current task manifest") from exc
    require(manifest.get("task_id") == TASK_ID, "P8-07F facts task is not active")
    require(
        str(manifest.get("status", "")).startswith("IN_PROGRESS"),
        "P8-07F facts task is not in progress",
    )
    return manifest


def _state_path(raw: str, *, must_exist: bool) -> Path:
    path = Path(raw)
    require(path.is_absolute(), "state path must be absolute")
    resolved_parent = path.parent.resolve()
    require(resolved_parent == Path(tempfile.gettempdir()).resolve(), "state must be in the OS temp directory")
    require(path.name.startswith("p8-07f-") and path.suffix == ".json", "state filename is invalid")
    if must_exist:
        require(path.is_file() and not path.is_symlink(), "private state is missing or unsafe")
        mode = stat.S_IMODE(path.stat().st_mode)
        require(mode == 0o600, "private state permissions drifted")
    else:
        require(not path.exists(), "private state already exists")
    return path


def _write_new_state(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_json_bytes(value))


def _replace_state(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".next")
    require(not temporary.exists(), "temporary state path already exists")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(value))
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _load_state(path: Path, expected_sha: str, ordinary_run_id: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FactCollectionError("private state is malformed") from exc
    require(type(value) is dict, "private state must be an object")
    require(value.get("schema_version") == 1, "private state schema drifted")
    require(value.get("task_id") == TASK_ID, "private state task drifted")
    require(value.get("exact_sha") == expected_sha, "private state SHA drifted")
    require(value.get("ordinary_run_id") == ordinary_run_id, "private state ordinary evidence drifted")
    require(type(value.get("apps")) is list, "private state apps are malformed")
    return value


def _validate_ordinary_run_id(value: str) -> None:
    require(value.isdigit() and int(value) > 0, "ordinary run ID is invalid")


def _remote_command(operation: str, *, site: str | None = None, root: str | None = None, path: str | None = None) -> tuple[str, ...]:
    if operation == "ERP_VERSION":
        command = ("bench", "version")
    elif operation == "INSTALLED_APPS":
        require(site is not None and APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is invalid")
        command = ("bench", "--site", site, "list-apps")
    else:
        require(root is not None and _safe_root(root), "custom app root is invalid")
        if operation == "APP_HEAD":
            command = ("git", "-C", root, "rev-parse", "HEAD")
        elif operation == "APP_STATUS":
            command = ("git", "-C", root, "status", "--short", "-uno")
        elif operation == "APP_TRACKED_PATHS":
            command = ("git", "-C", root, "ls-files", "-z")
        elif operation in {"APP_FILE_HASH", "APP_FILE_READ", "APP_FILE_MODE", "APP_HEAD_FILE_HASH", "APP_WORKTREE_DIFF"}:
            require(path is not None and _safe_relative_path(path), "tracked file path is invalid")
            if operation == "APP_FILE_HASH":
                command = ("git", "-C", root, "hash-object", "--", path)
            elif operation == "APP_FILE_READ":
                command = ("git", "-C", root, "show", f"HEAD:{path}")
            elif operation == "APP_FILE_MODE":
                command = ("git", "-C", root, "ls-files", "-s", "--", path)
            elif operation == "APP_HEAD_FILE_HASH":
                command = ("git", "-C", root, "rev-parse", f"HEAD:{path}")
            else:
                command = (
                    "git", "-C", root, "diff", "--no-ext-diff", "--no-renames",
                    "--no-color", "--unified=1000000", "HEAD", "--", path,
                )
        else:
            raise FactCollectionError("remote operation is not allowlisted")
    _validate_command_tokens(command)
    return command


def _runtime_command(family: str, site: str, start: int) -> tuple[str, ...]:
    require(family in RUNTIME_METADATA_SPECS, "runtime metadata family is not allowlisted")
    require(APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is invalid")
    page_size = RUNTIME_PAGE_SIZE_OVERRIDES.get(family, RUNTIME_PAGE_SIZE)
    require(start >= 0 and start % page_size == 0, "runtime metadata page start is invalid")
    spec = RUNTIME_METADATA_SPECS[family]
    kwargs = {
        "doctype": spec["doctype"],
        "fields": list(spec["fields"]),
        "filters": [list(row) for row in spec.get("filters", ())],
        "order_by": "name asc",
        "limit_start": start,
        "limit_page_length": page_size,
    }
    command = (
        "bench", "--site", site, "execute", "frappe.client.get_list",
        "--kwargs", json.dumps(kwargs, sort_keys=True, separators=(",", ":")),
    )
    _validate_command_tokens(command)
    return command


def _site_fact_commands(family: str, site: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    require(family in SITE_FACT_FAMILIES, "site fact family is not allowlisted")
    require(APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is invalid")
    if family == "SYSTEM_LOCALE":
        kwargs = {
            "doctype": "System Settings",
            "fieldname": ["language", "time_zone", "country"],
            "filters": {"name": "System Settings"},
        }
        commands = (
            (
                "SYSTEM_LOCALE",
                (
                    "bench", "--site", site, "execute", "frappe.client.get_value",
                    "--kwargs", json.dumps(kwargs, sort_keys=True, separators=(",", ":")),
                ),
            ),
        )
    else:
        commands = tuple(
            (
                f"FILE_URL_SHAPES_{label}",
                (
                    "bench", "--site", site, "execute", "frappe.client.get_count",
                    "--kwargs",
                    json.dumps(
                        {"doctype": "File", "filters": filters},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
            for label, filters in FILE_URL_SHAPE_FILTERS.items()
        )
    for _, command in commands:
        _validate_command_tokens(command)
    return commands


def _parent_document_command(site: str, parent_doctype: str, name: str) -> tuple[str, ...]:
    require(APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is invalid")
    require(parent_doctype in {"DocType", "Workflow", "Document Naming Rule"}, "parent metadata type is not allowlisted")
    require(type(name) is str and 0 < len(name) <= 160, "parent metadata name is invalid")
    require("@" not in name and "://" not in name, "parent metadata name may contain sensitive identity or endpoint data")
    kwargs = {"doctype": parent_doctype, "name": name}
    command = (
        "bench", "--site", site, "execute", "frappe.client.get",
        "--kwargs", json.dumps(kwargs, sort_keys=True, separators=(",", ":")),
    )
    _validate_command_tokens(command)
    return command


def _validate_command_tokens(command: Sequence[str]) -> None:
    require(bool(command), "remote command is empty")
    require(command[0] in {"bench", "git"}, "remote executable is not allowlisted")
    for token in command:
        require(type(token) is str and 0 < len(token) <= 8192, "remote command token is invalid")
        require(
            not any(character in token for character in ("\x00", "\r", "\n", ";", "&", "|", "<", ">", "`", "$")),
            "remote command token is unsafe",
        )


def _safe_root(value: str) -> bool:
    if not value.startswith("apps/") or ".." in value.split("/"):
        return False
    parts = value.split("/")
    return len(parts) == 2 and APP_TOKEN.fullmatch(parts[1]) is not None


def _safe_relative_path(value: str) -> bool:
    if not value or value.startswith("/") or RELATIVE_PATH.fullmatch(value) is None:
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _safe_inventory_path(value: str) -> bool:
    if not value or value.startswith("/") or len(value) > 1024:
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _ssh_argv(command: Sequence[str]) -> tuple[str, ...]:
    _validate_command_tokens(command)
    remote = f"cd {REMOTE_BENCH_ROOT} && exec " + shlex.join(command)
    return ("ssh", *SSH_OPTIONS, "--", SSH_ALIAS, remote)


def _run_ssh(operation: str, command: Sequence[str], max_bytes: int) -> bytes:
    environment = dict(os.environ)
    environment.pop("SSH_ASKPASS", None)
    environment["SSH_ASKPASS_REQUIRE"] = "never"
    try:
        result = subprocess.run(
            _ssh_argv(command),
            cwd=ROOT,
            check=False,
            input=b"",
            capture_output=True,
            timeout=30,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise FactCollectionError(f"{operation} exceeded the bounded timeout") from exc
    require(result.returncode == 0, f"{operation} failed without accepted output")
    require(not result.stderr, f"{operation} produced unexpected stderr")
    require(len(result.stdout) <= max_bytes, f"{operation} exceeded the bounded output limit")
    if operation != "APP_TRACKED_PATHS":
        require(b"\x00" not in result.stdout, f"{operation} returned binary output")
    return result.stdout


def _parse_app_rows(raw: bytes, label: str) -> list[dict[str, str]]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise FactCollectionError(f"{label} output is not UTF-8") from exc
    rows: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        tokens = stripped.split()
        require(1 <= len(tokens) <= 4, f"{label} row shape drifted")
        require(APP_TOKEN.fullmatch(tokens[0]) is not None, f"{label} app token is invalid")
        require(
            all(VERSION_TOKEN.fullmatch(token) is not None for token in tokens[1:3]),
            f"{label} version token is invalid",
        )
        if len(tokens) == 4:
            require(COMMIT_TOKEN.fullmatch(tokens[3]) is not None, f"{label} commit token is invalid")
        row = {"name": tokens[0]}
        if len(tokens) >= 2:
            row["version"] = tokens[1]
        if len(tokens) >= 3:
            row["branch"] = tokens[2]
        if len(tokens) == 4:
            row["commit"] = tokens[3][1:-1]
        rows.append(row)
    require(rows, f"{label} returned no app rows")
    require(len({row["name"] for row in rows}) == len(rows), f"{label} contains duplicate apps")
    return rows


def _label_apps(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    custom_index = 0
    result: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda item: item["name"].lower()):
        name = row["name"]
        public = PUBLIC_APPS.get(name.lower())
        if public is None:
            custom_index += 1
            public = f"CUSTOM_APP_{custom_index:02d}"
        result.append({**row, "label": public, "root": f"apps/{name}"})
    return result


def _public_app_row(row: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in row.items() if key in {"label", "version", "branch"}}


def _app_for_label(state: dict[str, Any], label: str) -> dict[str, str]:
    matches = [row for row in state["apps"] if row.get("label") == label]
    require(len(matches) == 1, "application label is unknown or duplicate")
    row = matches[0]
    require(type(row.get("name")) is str and APP_TOKEN.fullmatch(row["name"]) is not None, "private application name is invalid")
    require(type(row.get("root")) is str and _safe_root(row["root"]), "private application root is invalid")
    return row


def _parse_head(raw: bytes) -> str:
    value = raw.decode("ascii", errors="strict").strip()
    require(HEX_SHA.fullmatch(value) is not None, "APP_HEAD output shape drifted")
    return value


def _parse_status(raw: bytes) -> list[dict[str, str]]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise FactCollectionError("APP_STATUS output is not UTF-8") from exc
    require(len(lines) <= 500, "APP_STATUS row count exceeded")
    result: list[dict[str, str]] = []
    for line in lines:
        require(len(line) >= 4 and line[2] == " ", "APP_STATUS row shape drifted")
        status_code = line[:2]
        path = line[3:]
        require("?" not in status_code, "APP_STATUS unexpectedly returned untracked files")
        require(_safe_inventory_path(path), "APP_STATUS path shape drifted")
        result.append({"status": status_code, "path_checksum": _checksum(path.encode())})
    return result


def _parse_paths(raw: bytes) -> list[str]:
    if not raw:
        return []
    require(raw.endswith(b"\x00"), "APP_TRACKED_PATHS is not NUL terminated")
    encoded_paths = raw[:-1].split(b"\x00")
    require(encoded_paths == sorted(encoded_paths), "APP_TRACKED_PATHS is not deterministic")
    require(len(set(encoded_paths)) == len(encoded_paths), "APP_TRACKED_PATHS contains duplicates")
    try:
        paths = [value.decode("utf-8") for value in encoded_paths]
    except UnicodeDecodeError as exc:
        raise FactCollectionError("APP_TRACKED_PATHS output is not UTF-8") from exc
    require(len(paths) <= 20000, "APP_TRACKED_PATHS row count exceeded")
    require(all(_safe_inventory_path(path) for path in paths), "APP_TRACKED_PATHS contains an unsafe path")
    return paths


def _path_category(path: str) -> str:
    lowered = path.lower()
    name = Path(lowered).name
    if "/doctype/" in lowered and lowered.endswith(".json"):
        return "DOCTYPE_JSON"
    if name == "hooks.py":
        return "HOOKS"
    if name in {"modules.txt", "patches.txt"}:
        return name.removesuffix(".txt").upper()
    if "/fixtures/" in lowered or "fixture" in name:
        return "FIXTURE"
    if name == "api.py" or "/api/" in lowered or "integration" in name:
        return "API_OR_INTEGRATION_SOURCE"
    if "job" in name or "scheduler" in name:
        return "JOB_OR_SCHEDULER_SOURCE"
    suffix = Path(name).suffix.lower().lstrip(".")
    return f"TRACKED_{suffix.upper()}" if suffix else "TRACKED_NO_SUFFIX"


def _cached_path(state: dict[str, Any], label: str, path_index: int) -> str:
    cached = state["tracked_paths"].get(label)
    require(type(cached) is list and all(type(item) is str for item in cached), "cached tracked paths are malformed")
    require(0 <= path_index < len(cached), "tracked path index is outside the cached inventory")
    path = cached[path_index]
    require(_safe_inventory_path(path), "cached tracked path is unsafe")
    return path


def _path_is_sensitive(path: str) -> bool:
    lowered = path.lower().split("/")
    return any(part in SENSITIVE_PATH_PARTS for part in lowered) or any(
        part.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite", ".sql", ".bak"))
        for part in lowered
    )


def _safe_scalar(value: object) -> str | int | bool | None:
    if value is None or type(value) in {int, bool}:
        return value  # type: ignore[return-value]
    if type(value) is not str:
        return None
    require(len(value) <= 160, "metadata scalar is too long")
    require("@" not in value and "://" not in value, "metadata scalar may contain sensitive identity or endpoint data")
    require(all(ord(character) >= 32 for character in value), "metadata scalar contains control characters")
    return value


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return None


def _python_summary(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise FactCollectionError("tracked Python source cannot be parsed") from exc
    imports: set[str] = set()
    definitions: list[dict[str, Any]] = []
    assignments: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            require(SAFE_NAME.fullmatch(node.name) is not None, "Python definition name is unsafe")
            decorators = sorted(filter(None, (_decorator_name(item) for item in node.decorator_list)))
            definitions.append(
                {
                    "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                    "name": node.name,
                    "decorators": decorators,
                }
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and SAFE_NAME.fullmatch(target.id):
                    assignments.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if SAFE_NAME.fullmatch(node.target.id):
                assignments.add(node.target.id)
    return {
        "format": "python_ast",
        "imports": sorted(imports),
        "definitions": sorted(definitions, key=lambda item: (item["kind"], item["name"])),
        "module_assignments": sorted(assignments),
    }


def _json_summary(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FactCollectionError("tracked JSON cannot be parsed") from exc
    require(type(value) in {dict, list}, "tracked JSON root shape is unsupported")
    if isinstance(value, list):
        return {"format": "json", "root": "list", "row_count": len(value)}
    result: dict[str, Any] = {
        "format": "json",
        "root": "object",
        "top_level_keys": sorted(str(key) for key in value),
    }
    def protected_scalar(value: object) -> object:
        try:
            return _safe_scalar(value)
        except FactCollectionError:
            require(type(value) is str, "tracked JSON scalar shape drifted")
            encoded = value.encode("utf-8")
            return {"byte_count": len(encoded), "checksum": _checksum(encoded)}

    for key in ("doctype", "name", "module", "document_type"):
        if key in value:
            result[key] = protected_scalar(value[key])
    fields = value.get("fields")
    if isinstance(fields, list):
        safe_fields: list[dict[str, Any]] = []
        for field in fields:
            require(type(field) is dict, "DocType field row shape drifted")
            safe_fields.append(
                {
                    key: protected_scalar(field.get(key))
                    for key in ("fieldname", "fieldtype", "options", "reqd", "read_only", "unique")
                    if key in field
                }
            )
        result["fields"] = safe_fields
    permissions = value.get("permissions")
    if isinstance(permissions, list):
        safe_permissions: list[dict[str, Any]] = []
        for permission in permissions:
            require(type(permission) is dict, "DocType permission row shape drifted")
            safe_permissions.append(
                {
                    key: protected_scalar(permission.get(key))
                    for key in ("role", "permlevel", "read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "share", "print", "email")
                    if key in permission
                }
            )
        result["permissions"] = safe_permissions
    return result


def _csv_summary(text: str) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    require(rows, "tracked CSV is empty")
    headers = [_safe_scalar(value) for value in rows[0]]
    return {"format": "csv", "headers": headers, "row_count": max(0, len(rows) - 1)}


def _source_summary(path: str, raw: bytes) -> dict[str, Any]:
    require(not _path_is_sensitive(path), "tracked path is excluded as sensitive")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FactCollectionError("tracked file is not UTF-8") from exc
    suffix = Path(path).suffix.lower()
    if suffix != ".json":
        for pattern in SENSITIVE_CONTENT:
            require(pattern.search(text) is None, "tracked file may contain sensitive content")
    if suffix == ".py":
        summary = _python_summary(text)
    elif suffix == ".json":
        summary = _json_summary(text)
    elif suffix == ".csv":
        summary = _csv_summary(text)
    elif suffix in {".js", ".ts", ".tsx"}:
        names = sorted(
            set(
                re.findall(
                    r"(?:export\s+)?(?:async\s+)?(?:function|class|const|let)\s+([A-Za-z_][A-Za-z0-9_]*)",
                    text,
                )
            )
        )
        summary = {"format": "javascript_structure", "definitions": names}
    elif suffix in {".yaml", ".yml", ".toml", ".ini"}:
        keys = sorted(set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]", text)))
        summary = {"format": "declarative_keys", "keys": keys}
    else:
        summary = {"format": "opaque_tracked_text", "line_count": len(text.splitlines())}
    return {
        **summary,
        "byte_count": len(raw),
        "content_checksum": _checksum(raw),
    }


def _git_blob_sha1(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _parse_file_mode(raw: bytes, path: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FactCollectionError("APP_FILE_MODE output is not UTF-8") from exc
    lines = [line for line in text.splitlines() if line]
    require(len(lines) == 1, "APP_FILE_MODE must return one tracked entry")
    match = re.fullmatch(r"(100644|100755) ([0-9a-f]{40}) 0\t(.+)", lines[0])
    require(match is not None, "APP_FILE_MODE row shape drifted or file mode is unsafe")
    require(match.group(3) == path, "APP_FILE_MODE path drifted")
    return match.group(1)


def _trim_diff_newline(value: bytes) -> bytes:
    if value.endswith(b"\r\n"):
        return value[:-2]
    if value.endswith(b"\n"):
        return value[:-1]
    raise FactCollectionError("no-newline marker has no preceding newline")


def _reconstruct_current_file(head_raw: bytes, patch_raw: bytes, path: str) -> bytes:
    require(_safe_relative_path(path), "tracked file path is invalid")
    require(len(head_raw) <= MAX_FILE_BYTES, "HEAD file exceeded the bounded limit")
    require(len(patch_raw) <= MAX_DIFF_BYTES, "worktree diff exceeded the bounded limit")
    if not patch_raw:
        return head_raw
    require(b"\x00" not in patch_raw, "worktree diff is binary")
    try:
        patch_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FactCollectionError("worktree diff is not UTF-8") from exc
    forbidden = (
        b"GIT binary patch",
        b"Binary files ",
        b"rename from ",
        b"rename to ",
        b"copy from ",
        b"copy to ",
        b"new file mode ",
        b"deleted file mode ",
        b"old mode ",
        b"new mode ",
    )
    require(not any(marker in patch_raw for marker in forbidden), "worktree diff changes an unsafe file property")
    lines = patch_raw.splitlines(keepends=True)
    require(len(lines) >= 5, "worktree diff is truncated")
    expected_diff = f"diff --git a/{path} b/{path}".encode()
    require(lines[0].rstrip(b"\r\n") == expected_diff, "worktree diff path drifted")
    require(sum(line.startswith(b"diff --git ") for line in lines) == 1, "worktree diff contains multiple files")
    index_match = re.fullmatch(
        rb"index ([0-9a-f]{7,40})\.\.([0-9a-f]{7,40}) (100644|100755)\r?\n?",
        lines[1],
    )
    require(index_match is not None, "worktree diff index shape drifted")
    head_object = _git_blob_sha1(head_raw).encode()
    require(head_object.startswith(index_match.group(1)), "worktree diff HEAD object drifted")
    require(lines[2].rstrip(b"\r\n") == f"--- a/{path}".encode(), "worktree diff old path drifted")
    require(lines[3].rstrip(b"\r\n") == f"+++ b/{path}".encode(), "worktree diff new path drifted")

    head_lines = head_raw.splitlines(keepends=True)
    output: list[bytes] = []
    old_cursor = 0
    line_index = 4
    hunk_count = 0
    while line_index < len(lines):
        header = lines[line_index].decode("ascii", errors="strict").rstrip("\r\n")
        match = re.fullmatch(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?",
            header,
        )
        require(match is not None, "worktree diff hunk header drifted")
        hunk_count += 1
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_start = int(match.group(3))
        new_count = int(match.group(4) or "1")
        expected_old_index = 0 if old_start == 0 else old_start - 1
        require(expected_old_index >= old_cursor, "worktree diff hunks overlap or regress")
        output.extend(head_lines[old_cursor:expected_old_index])
        old_cursor = expected_old_index
        require(len(output) == (0 if new_start == 0 else new_start - 1), "worktree diff new hunk position drifted")
        line_index += 1
        entries: list[tuple[int, bytes]] = []
        while line_index < len(lines) and not lines[line_index].startswith(b"@@ "):
            line = lines[line_index]
            if line.startswith(b"\\ No newline at end of file"):
                require(entries, "no-newline marker has no content row")
                prefix, content = entries[-1]
                entries[-1] = (prefix, _trim_diff_newline(content))
            else:
                require(line[:1] in {b" ", b"-", b"+"}, "worktree diff row shape drifted")
                entries.append((line[0], line[1:]))
            line_index += 1
        observed_old = sum(prefix in {32, 45} for prefix, _ in entries)
        observed_new = sum(prefix in {32, 43} for prefix, _ in entries)
        require(observed_old == old_count and observed_new == new_count, "worktree diff hunk counts drifted")
        for prefix, content in entries:
            if prefix in {32, 45}:
                require(old_cursor < len(head_lines), "worktree diff reads beyond HEAD")
                require(head_lines[old_cursor] == content, "worktree diff context does not match HEAD")
                old_cursor += 1
            if prefix in {32, 43}:
                output.append(content)
    require(hunk_count >= 1, "worktree diff contains no hunks")
    output.extend(head_lines[old_cursor:])
    result = b"".join(output)
    require(len(result) <= MAX_FILE_BYTES, "current tracked file exceeded the bounded limit")
    require(_git_blob_sha1(result).encode().startswith(index_match.group(2)), "worktree diff result object drifted")
    return result


def _sanitize_runtime_row(row: object, family: str) -> tuple[dict[str, Any], str]:
    require(family in RUNTIME_METADATA_SPECS, "runtime metadata family is not allowlisted")
    spec = RUNTIME_METADATA_SPECS[family]
    fields = tuple(spec["fields"])
    hashed_fields = set(spec.get("hashed_fields", ()))
    protected_fields = set(spec.get("protected_fields", ()))
    require(type(row) is dict and set(row) == set(fields), "runtime metadata row shape drifted")
    name = row.get("name")
    require(type(name) is str and bool(name), "runtime metadata row name is invalid")
    require(len(name) <= 160 and all(ord(character) >= 32 for character in name), "runtime metadata row name is unsafe")
    safe_row: dict[str, Any] = {}
    for field in fields:
        field_value = row[field]
        if field in hashed_fields:
            if field_value is None:
                safe_row[field] = None
            else:
                require(type(field_value) is str, "hashed metadata field shape drifted")
                encoded = field_value.encode("utf-8")
                safe_row[field] = {
                    "byte_count": len(encoded),
                    "checksum": _checksum(encoded),
                }
        elif field in protected_fields and type(field_value) is str:
            try:
                safe_row[field] = _safe_scalar(field_value)
            except FactCollectionError:
                encoded = field_value.encode("utf-8")
                safe_row[field] = {
                    "byte_count": len(encoded),
                    "checksum": _checksum(encoded),
                }
        else:
            safe_value = _safe_scalar(field_value)
            require(field_value is None or safe_value is not None, "runtime metadata scalar shape drifted")
            safe_row[field] = safe_value
    return safe_row, name


def _parse_runtime_page(raw: bytes, family: str) -> tuple[list[dict[str, Any]], list[str]]:
    require(family in RUNTIME_METADATA_SPECS, "runtime metadata family is not allowlisted")
    require(len(raw) <= MAX_RUNTIME_BYTES, "runtime metadata output exceeded the bounded limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FactCollectionError("runtime metadata output is not exact JSON") from exc
    require(type(value) is list, "runtime metadata page must be a list")
    page_size = RUNTIME_PAGE_SIZE_OVERRIDES.get(family, RUNTIME_PAGE_SIZE)
    require(len(value) <= page_size, "runtime metadata page exceeded the fixed size")
    sanitized: list[dict[str, Any]] = []
    raw_names: list[str] = []
    for row in value:
        safe_row, name = _sanitize_runtime_row(row, family)
        sanitized.append(safe_row)
        raw_names.append(name)
    require(len(raw_names) == len(set(raw_names)), "runtime metadata page contains duplicate names")
    return sanitized, raw_names


def _parse_parent_metadata_document(
    raw: bytes,
    *,
    family: str,
    parent_doctype: str,
    parent_name: str,
    child_key: str,
) -> list[dict[str, Any]]:
    require(len(raw) <= MAX_RUNTIME_BYTES, "parent metadata output exceeded the bounded limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FactCollectionError("parent metadata output is not exact JSON") from exc
    require(type(value) is dict, "parent metadata document must be an object")
    require(value.get("doctype") == parent_doctype and value.get("name") == parent_name, "parent metadata identity drifted")
    children = value.get(child_key)
    require(type(children) is list and len(children) <= 2000, "parent metadata child shape drifted")
    fields = tuple(RUNTIME_METADATA_SPECS[family]["fields"])
    sanitized: list[dict[str, Any]] = []
    names: list[str] = []
    for child in children:
        require(type(child) is dict, "parent metadata child row drifted")
        projected = {field: child.get(field) for field in fields}
        if "parent" in projected:
            require(projected["parent"] in {None, parent_name}, "parent metadata child parent drifted")
            projected["parent"] = parent_name
        safe_row, name = _sanitize_runtime_row(projected, family)
        sanitized.append(safe_row)
        names.append(name)
    require(len(names) == len(set(names)), "parent metadata child names are duplicated")
    return sanitized


def _discover(args: argparse.Namespace, runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    path = _state_path(args.state, must_exist=False)
    version_command = _remote_command("ERP_VERSION")
    version_raw = runner("ERP_VERSION", version_command, MAX_VERSION_BYTES)
    apps = _label_apps(_parse_app_rows(version_raw, "ERP_VERSION"))
    site_status = "UNVERIFIED_RUNTIME_SITE_PARAMETER_ABSENT"
    site_raw_checksum: str | None = None
    site = os.environ.get("NPI_P8_07F_SITE")
    if site is not None:
        site_command = _remote_command("INSTALLED_APPS", site=site)
        site_raw = runner("INSTALLED_APPS", site_command, MAX_VERSION_BYTES)
        site_rows = _parse_app_rows(site_raw, "INSTALLED_APPS")
        require({row["name"] for row in site_rows}.issubset({row["name"] for row in apps}), "site app set is outside bench inventory")
        site_status = "VERIFIED"
        site_raw_checksum = _checksum(site_raw)
    state = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "exact_sha": args.expected_sha,
        "ordinary_run_id": args.ordinary_run_id,
        "created_at": _timestamp(),
        "apps": apps,
        "tracked_paths": {},
        "operation_records": [
            {
                "operation_id": "ERP_VERSION",
                "timestamp": _timestamp(),
                "source": "JCE_CORE_PRODUCTION_REDACTED",
                "checksum": _checksum(version_raw),
            }
        ],
    }
    if site_raw_checksum is not None:
        state["operation_records"].append(
            {
                "operation_id": "INSTALLED_APPS",
                "timestamp": _timestamp(),
                "source": "JCE_CORE_PRODUCTION_REDACTED",
                "checksum": site_raw_checksum,
            }
        )
    _write_new_state(path, state)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": "DISCOVER",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "apps": [_public_app_row(row) for row in apps],
            "bench_inventory_checksum": _checksum(version_raw),
            "site_inventory_status": site_status,
            "site_inventory_checksum": site_raw_checksum,
        }
    )


def _app_operation(args: argparse.Namespace, runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    path = _state_path(args.state, must_exist=True)
    state = _load_state(path, args.expected_sha, args.ordinary_run_id)
    app = _app_for_label(state, args.label)
    operation = args.operation
    if operation == "APP_TRACKED_PATHS" and args.label in state["tracked_paths"]:
        paths = state["tracked_paths"][args.label]
        require(type(paths) is list and all(type(item) is str for item in paths), "cached tracked paths are malformed")
        source_checksum = _checksum("\n".join(paths).encode())
        remote_called = False
    else:
        max_bytes = {
            "APP_HEAD": MAX_VERSION_BYTES,
            "APP_STATUS": MAX_STATUS_BYTES,
            "APP_TRACKED_PATHS": MAX_PATH_BYTES,
        }[operation]
        raw = runner(operation, _remote_command(operation, root=app["root"]), max_bytes)
        source_checksum = _checksum(raw)
        remote_called = True
        if operation == "APP_HEAD":
            result: object = {"head": _parse_head(raw)}
        elif operation == "APP_STATUS":
            statuses = _parse_status(raw)
            result = {"tracked_drift_count": len(statuses), "tracked_drift": statuses}
        else:
            paths = _parse_paths(raw)
            state["tracked_paths"][args.label] = paths
            _replace_state(path, state)
    if operation == "APP_TRACKED_PATHS":
        page_size = args.page_size
        page = args.page
        require(1 <= page_size <= MAX_PAGE_SIZE and page >= 1, "tracked path page is invalid")
        start = (page - 1) * page_size
        selected = paths[start : start + page_size]
        result = {
            "page": page,
            "page_size": page_size,
            "total": len(paths),
            "path_entries": [
                {
                    "index": start + index,
                    "path_checksum": _checksum(item.encode("utf-8")),
                    "category": _path_category(item),
                }
                for index, item in enumerate(selected)
            ],
            "remote_called": remote_called,
        }
    _emit(
        {
            "task_id": TASK_ID,
            "operation": operation,
            "timestamp": _timestamp(),
            "source": args.label,
            "source_checksum": source_checksum,
            "result": result,
        }
    )


def _file_operation(args: argparse.Namespace, runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    state_path = _state_path(args.state, must_exist=True)
    state = _load_state(state_path, args.expected_sha, args.ordinary_run_id)
    app = _app_for_label(state, args.label)
    tracked_path = _cached_path(state, args.label, args.path_index)
    require(not _path_is_sensitive(tracked_path), "tracked path is excluded as sensitive")
    hash_raw = runner(
        "APP_HEAD_FILE_HASH",
        _remote_command("APP_HEAD_FILE_HASH", root=app["root"], path=tracked_path),
        MAX_VERSION_BYTES,
    )
    git_hash = _parse_head(hash_raw)
    content_raw = runner(
        "APP_FILE_READ",
        _remote_command("APP_FILE_READ", root=app["root"], path=tracked_path),
        MAX_FILE_BYTES,
    )
    require(_git_blob_sha1(content_raw) == git_hash, "HEAD tracked content does not match its Git object")
    summary = _source_summary(tracked_path, content_raw)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": "APP_FILE_READ",
            "timestamp": _timestamp(),
            "source": args.label,
            "path_index": args.path_index,
            "path_checksum": _checksum(tracked_path.encode("utf-8")),
            "git_object": git_hash,
            "summary": summary,
        }
    )


def _current_file_operation(
    args: argparse.Namespace,
    runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh,
) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    state_path = _state_path(args.state, must_exist=True)
    state = _load_state(state_path, args.expected_sha, args.ordinary_run_id)
    app = _app_for_label(state, args.label)
    tracked_path = _cached_path(state, args.label, args.path_index)
    require(_safe_relative_path(tracked_path), "current file path is outside the strict command grammar")
    require(not _path_is_sensitive(tracked_path), "tracked path is excluded as sensitive")

    mode_raw = runner(
        "APP_FILE_MODE",
        _remote_command("APP_FILE_MODE", root=app["root"], path=tracked_path),
        MAX_VERSION_BYTES,
    )
    mode = _parse_file_mode(mode_raw, tracked_path)
    head_hash_raw = runner(
        "APP_HEAD_FILE_HASH",
        _remote_command("APP_HEAD_FILE_HASH", root=app["root"], path=tracked_path),
        MAX_VERSION_BYTES,
    )
    head_object = _parse_head(head_hash_raw)
    head_raw = runner(
        "APP_FILE_READ",
        _remote_command("APP_FILE_READ", root=app["root"], path=tracked_path),
        MAX_FILE_BYTES,
    )
    require(_git_blob_sha1(head_raw) == head_object, "HEAD tracked content does not match its Git object")
    current_hash_raw = runner(
        "APP_FILE_HASH",
        _remote_command("APP_FILE_HASH", root=app["root"], path=tracked_path),
        MAX_VERSION_BYTES,
    )
    current_object = _parse_head(current_hash_raw)
    if current_object == head_object:
        current_raw = head_raw
        worktree_state = "CLEAN"
        diff_checksum = None
    else:
        patch_raw = runner(
            "APP_WORKTREE_DIFF",
            _remote_command("APP_WORKTREE_DIFF", root=app["root"], path=tracked_path),
            MAX_DIFF_BYTES,
        )
        current_raw = _reconstruct_current_file(head_raw, patch_raw, tracked_path)
        require(_git_blob_sha1(current_raw) == current_object, "reconstructed current content does not match its Git object")
        worktree_state = "DIRTY_TRACKED"
        diff_checksum = _checksum(patch_raw)
    summary = _source_summary(tracked_path, current_raw)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": "APP_CURRENT_FILE_READ",
            "timestamp": _timestamp(),
            "source": args.label,
            "path_index": args.path_index,
            "path_checksum": _checksum(tracked_path.encode("utf-8")),
            "mode": mode,
            "head_git_object": head_object,
            "current_git_object": current_object,
            "worktree_state": worktree_state,
            "diff_checksum": diff_checksum,
            "summary": summary,
        }
    )


def _runtime_operation(
    args: argparse.Namespace,
    runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh,
) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    state_path = _state_path(args.state, must_exist=True)
    state = _load_state(state_path, args.expected_sha, args.ordinary_run_id)
    family = args.family
    require(family in RUNTIME_METADATA_SPECS, "runtime metadata family is not allowlisted")
    site = os.environ.get("NPI_P8_07F_SITE")
    require(site is not None and APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is missing or invalid")

    rows: list[dict[str, Any]] = []
    names: list[str] = []
    page_checksums: list[str] = []
    exhausted = False
    page_size = RUNTIME_PAGE_SIZE_OVERRIDES.get(family, RUNTIME_PAGE_SIZE)
    for page_index in range(RUNTIME_MAX_PAGES):
        start = page_index * page_size
        raw = runner(
            f"RUNTIME_{family}",
            _runtime_command(family, site, start),
            MAX_RUNTIME_BYTES,
        )
        page_rows, page_names = _parse_runtime_page(raw, family)
        require(not set(names).intersection(page_names), "runtime metadata pagination contains duplicate names")
        rows.extend(page_rows)
        names.extend(page_names)
        page_checksums.append(_checksum(raw))
        if len(page_rows) < page_size:
            exhausted = True
            break
    require(exhausted, "runtime metadata exceeded the fixed pagination limit")
    result_checksum = _checksum(_json_bytes(rows))
    records = state.setdefault("operation_records", [])
    require(type(records) is list, "private operation records are malformed")
    records.append(
        {
            "operation_id": f"RUNTIME_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "checksum": result_checksum,
        }
    )
    runtime_names = state.setdefault("runtime_names", {})
    require(type(runtime_names) is dict, "private runtime-name cache is malformed")
    runtime_names[family] = names
    _replace_state(state_path, state)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": f"RUNTIME_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "row_count": len(rows),
            "page_count": len(page_checksums),
            "page_checksums": page_checksums,
            "result_checksum": result_checksum,
            "rows": rows,
        }
    )


def _parent_metadata_operation(
    args: argparse.Namespace,
    runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh,
) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    state_path = _state_path(args.state, must_exist=True)
    state = _load_state(state_path, args.expected_sha, args.ordinary_run_id)
    family = args.family
    require(family in PARENT_METADATA_FAMILIES, "parent metadata family is not allowlisted")
    parent_doctype, child_key, source_family = PARENT_METADATA_FAMILIES[family]
    site = os.environ.get("NPI_P8_07F_SITE")
    require(site is not None and APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is missing or invalid")
    if parent_doctype == "DocType":
        parent_names = list(REQUIRED_ERPNEXT_DOCTYPES)
    else:
        runtime_names = state.get("runtime_names")
        require(type(runtime_names) is dict, "parent metadata requires its fixed parent family first")
        cached_names = runtime_names.get(source_family)
        require(
            type(cached_names) is list and all(type(item) is str for item in cached_names),
            "parent metadata requires its fixed parent family first",
        )
        parent_names = list(cached_names)
    require(len(parent_names) <= 500, "parent metadata parent count exceeded")

    rows: list[dict[str, Any]] = []
    document_checksums: list[str] = []
    for parent_name in parent_names:
        raw = runner(
            f"RUNTIME_{family}_PARENT",
            _parent_document_command(site, parent_doctype, parent_name),
            MAX_RUNTIME_BYTES,
        )
        rows.extend(
            _parse_parent_metadata_document(
                raw,
                family=family,
                parent_doctype=parent_doctype,
                parent_name=parent_name,
                child_key=child_key,
            )
        )
        document_checksums.append(_checksum(raw))
    result_checksum = _checksum(_json_bytes(rows))
    records = state.setdefault("operation_records", [])
    require(type(records) is list, "private operation records are malformed")
    records.append(
        {
            "operation_id": f"RUNTIME_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "checksum": result_checksum,
        }
    )
    _replace_state(state_path, state)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": f"RUNTIME_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "parent_count": len(parent_names),
            "document_checksums": document_checksums,
            "row_count": len(rows),
            "result_checksum": result_checksum,
            "rows": rows,
        }
    )


def _parse_site_fact_output(family: str, raw_outputs: dict[str, bytes]) -> dict[str, Any]:
    require(family in SITE_FACT_FAMILIES, "site fact family is not allowlisted")
    if family == "SYSTEM_LOCALE":
        require(set(raw_outputs) == {"SYSTEM_LOCALE"}, "system locale result shape drifted")
        try:
            value = json.loads(raw_outputs["SYSTEM_LOCALE"].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FactCollectionError("system locale result is not exact JSON") from exc
        expected = {"language", "time_zone", "country"}
        require(type(value) is dict and set(value) == expected, "system locale fields drifted")
        result: dict[str, Any] = {}
        for key in sorted(expected):
            item = value[key]
            require(type(item) is str and 0 < len(item) <= 128, "system locale value shape drifted")
            result[key] = _safe_scalar(item)
        return result

    expected_operations = {f"FILE_URL_SHAPES_{label}" for label in FILE_URL_SHAPE_FILTERS}
    require(set(raw_outputs) == expected_operations, "file URL shape result set drifted")
    counts: dict[str, int] = {}
    for label in FILE_URL_SHAPE_FILTERS:
        operation = f"FILE_URL_SHAPES_{label}"
        try:
            value = json.loads(raw_outputs[operation].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FactCollectionError("file URL shape count is not exact JSON") from exc
        require(type(value) is int and value >= 0, "file URL shape count drifted")
        counts[label.lower()] = value
    require(
        counts["local_public"] + counts["local_private"] + counts["external_http"] <= counts["total"],
        "file URL shape counts are inconsistent",
    )
    return counts


def _site_fact_operation(
    args: argparse.Namespace,
    runner: Callable[[str, Sequence[str], int], bytes] = _run_ssh,
) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    state_path = _state_path(args.state, must_exist=True)
    state = _load_state(state_path, args.expected_sha, args.ordinary_run_id)
    family = args.family
    require(family in SITE_FACT_FAMILIES, "site fact family is not allowlisted")
    site = os.environ.get("NPI_P8_07F_SITE")
    require(site is not None and APP_TOKEN.fullmatch(site) is not None, "runtime site parameter is missing or invalid")
    raw_outputs: dict[str, bytes] = {}
    raw_checksums: dict[str, str] = {}
    for operation, command in _site_fact_commands(family, site):
        raw = runner(operation, command, MAX_RUNTIME_BYTES)
        raw_outputs[operation] = raw
        raw_checksums[operation] = _checksum(raw)
    result = _parse_site_fact_output(family, raw_outputs)
    result_checksum = _checksum(_json_bytes(result))
    records = state.setdefault("operation_records", [])
    require(type(records) is list, "private operation records are malformed")
    records.append(
        {
            "operation_id": f"SITE_FACT_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "checksum": result_checksum,
        }
    )
    _replace_state(state_path, state)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": f"SITE_FACT_{family}",
            "timestamp": _timestamp(),
            "source": "JCE_CORE_PRODUCTION_REDACTED",
            "raw_checksums": raw_checksums,
            "result_checksum": result_checksum,
            "result": result,
        }
    )


def _cleanup(args: argparse.Namespace) -> None:
    _validate_ordinary_run_id(args.ordinary_run_id)
    _preflight(args.expected_sha)
    path = _state_path(args.state, must_exist=True)
    _load_state(path, args.expected_sha, args.ordinary_run_id)
    path.unlink()
    _emit({"task_id": TASK_ID, "operation": "CLEANUP", "state_removed": True})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-check")

    def governed(name: str) -> argparse.ArgumentParser:
        child = subparsers.add_parser(name)
        child.add_argument("--expected-sha", required=True)
        child.add_argument("--ordinary-run-id", required=True)
        child.add_argument("--state", required=True)
        return child

    governed("discover")
    app = governed("app")
    app.add_argument("--label", required=True)
    app.add_argument(
        "--operation",
        required=True,
        choices=("APP_HEAD", "APP_STATUS", "APP_TRACKED_PATHS"),
    )
    app.add_argument("--page", type=int, default=1)
    app.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    file_parser = governed("file")
    file_parser.add_argument("--label", required=True)
    file_parser.add_argument("--path-index", required=True, type=int)
    current_file_parser = governed("current-file")
    current_file_parser.add_argument("--label", required=True)
    current_file_parser.add_argument("--path-index", required=True, type=int)
    runtime_parser = governed("runtime")
    runtime_parser.add_argument("--family", required=True, choices=tuple(RUNTIME_METADATA_SPECS))
    site_facts_parser = governed("site-facts")
    site_facts_parser.add_argument("--family", required=True, choices=SITE_FACT_FAMILIES)
    governed("cleanup")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "self-check":
            _emit(
                {
                    "task_id": TASK_ID,
                    "alias": SSH_ALIAS,
                    "bench_root": REMOTE_BENCH_ROOT,
                    "allowlisted_operations": [
                        "ERP_VERSION",
                        "INSTALLED_APPS",
                        "APP_HEAD",
                        "APP_STATUS",
                        "APP_TRACKED_PATHS",
                        "APP_FILE_HASH",
                        "APP_FILE_READ",
                        "APP_FILE_MODE",
                        "APP_HEAD_FILE_HASH",
                        "APP_WORKTREE_DIFF",
                        "APP_CURRENT_FILE_READ",
                    ],
                    "runtime_metadata_families": list(RUNTIME_METADATA_SPECS),
                    "site_fact_families": list(SITE_FACT_FAMILIES),
                    "remote_contact": False,
                }
            )
        elif args.command == "discover":
            _discover(args)
        elif args.command == "app":
            _app_operation(args)
        elif args.command == "file":
            _file_operation(args)
        elif args.command == "current-file":
            _current_file_operation(args)
        elif args.command == "runtime":
            if args.family in PARENT_METADATA_FAMILIES:
                _parent_metadata_operation(args)
            else:
                _runtime_operation(args)
        elif args.command == "site-facts":
            _site_fact_operation(args)
        elif args.command == "cleanup":
            _cleanup(args)
        else:
            raise FactCollectionError("unknown collector command")
    except (FactCollectionError, OSError, ValueError) as exc:
        print(f"production fact collection stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
