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
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
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
            command = ("git", "-C", root, "status", "--short", "--untracked-files=no")
        elif operation == "APP_TRACKED_PATHS":
            command = ("git", "-C", root, "ls-files")
        elif operation in {"APP_FILE_HASH", "APP_FILE_READ"}:
            require(path is not None and _safe_relative_path(path), "tracked file path is invalid")
            if operation == "APP_FILE_HASH":
                command = ("git", "-C", root, "hash-object", "--", path)
            else:
                command = ("git", "-C", root, "show", f"HEAD:{path}")
        else:
            raise FactCollectionError("remote operation is not allowlisted")
    require(
        all(REMOTE_TOKEN.fullmatch(token) is not None for token in command),
        "remote command token is unsafe",
    )
    return command


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


def _ssh_argv(command: Sequence[str]) -> tuple[str, ...]:
    require(bool(command), "remote command is empty")
    require(all(REMOTE_TOKEN.fullmatch(token) is not None for token in command), "remote command token is unsafe")
    remote = f"cd {REMOTE_BENCH_ROOT} && exec " + " ".join(command)
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
        require(_safe_relative_path(path), "APP_STATUS path shape drifted")
        result.append({"status": status_code, "path_checksum": _checksum(path.encode())})
    return result


def _parse_paths(raw: bytes) -> list[str]:
    try:
        paths = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise FactCollectionError("APP_TRACKED_PATHS output is not UTF-8") from exc
    require(len(paths) <= 20000, "APP_TRACKED_PATHS row count exceeded")
    require(paths == sorted(paths), "APP_TRACKED_PATHS is not deterministic")
    require(len(set(paths)) == len(paths), "APP_TRACKED_PATHS contains duplicates")
    require(all(_safe_relative_path(path) for path in paths), "APP_TRACKED_PATHS contains an unsafe path")
    return paths


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
    for key in ("doctype", "name", "module", "document_type"):
        if key in value:
            result[key] = _safe_scalar(value[key])
    fields = value.get("fields")
    if isinstance(fields, list):
        safe_fields: list[dict[str, Any]] = []
        for field in fields:
            require(type(field) is dict, "DocType field row shape drifted")
            safe_fields.append(
                {
                    key: _safe_scalar(field.get(key))
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
                    key: _safe_scalar(permission.get(key))
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
    for pattern in SENSITIVE_CONTENT:
        require(pattern.search(raw.decode("utf-8", errors="ignore")) is None, "tracked file may contain sensitive content")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FactCollectionError("tracked file is not UTF-8") from exc
    suffix = Path(path).suffix.lower()
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
            "paths": selected,
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
    cached = state["tracked_paths"].get(args.label)
    require(type(cached) is list and args.path in cached, "file read requires a cached exact tracked path")
    require(not _path_is_sensitive(args.path), "tracked path is excluded as sensitive")
    hash_raw = runner(
        "APP_FILE_HASH",
        _remote_command("APP_FILE_HASH", root=app["root"], path=args.path),
        MAX_VERSION_BYTES,
    )
    git_hash = _parse_head(hash_raw)
    content_raw = runner(
        "APP_FILE_READ",
        _remote_command("APP_FILE_READ", root=app["root"], path=args.path),
        MAX_FILE_BYTES,
    )
    summary = _source_summary(args.path, content_raw)
    _emit(
        {
            "task_id": TASK_ID,
            "operation": "APP_FILE_READ",
            "timestamp": _timestamp(),
            "source": args.label,
            "path": args.path,
            "git_object": git_hash,
            "summary": summary,
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
    file_parser.add_argument("--path", required=True)
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
                    ],
                    "remote_contact": False,
                }
            )
        elif args.command == "discover":
            _discover(args)
        elif args.command == "app":
            _app_operation(args)
        elif args.command == "file":
            _file_operation(args)
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
