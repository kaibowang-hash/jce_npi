#!/usr/bin/env python3
"""Fixed disposable-Site evidence helpers for the P9-07 recovery rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Iterable

import verify_document_runtime as document_runtime
from verify_frappe_runtime import require
from verify_local_frappe_site import load_controlled_database


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = "npi.localhost"
DATABASE_NAME = "npi_one_runtime"
RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
REHEARSAL_SCHEMA = "go-live-rehearsal-manifest.v1"
RESULT_SCHEMA = "go-live-recovery-result.v1"
RUN_ID = os.environ.get("NPI_DOCUMENT_RUNTIME_RUN_ID", "")
RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
DIRECTORY_PATTERN = re.compile(r"^npi-p9-07-rehearsal\.[A-Za-z0-9]{6}$")
BACKUP_MEMBERS = {
    "config": "site-config.json",
    "database": "database.sql.gz",
    "privateFiles": "private-files.tgz",
    "publicFiles": "public-files.tgz",
}
MAX_TREE_FILES = 10_000
MAX_TREE_BYTES = 512 * 1024 * 1024


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _run_git(*arguments: str, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    require(completed.returncode == 0, "P9-07 exact source identity is unavailable")
    value = completed.stdout.strip()
    require(bool(value), "P9-07 exact source identity is empty")
    return value


def _git_tree_sha256(path: str) -> str:
    tree_id = _run_git("rev-parse", f"HEAD:{path}")
    require(re.fullmatch(r"[a-f0-9]{40,64}", tree_id) is not None, "P9-07 Git tree identity drifted")
    return hashlib.sha256(tree_id.encode("ascii")).hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"P9-07 {label} is unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError(f"P9-07 {label} is invalid") from None
    require(isinstance(value, dict), f"P9-07 {label} must be an object")
    return value


def validated_rehearsal_directory(raw: str) -> Path:
    root_raw = os.environ.get("NPI_P9_07_REHEARSAL_ROOT", "")
    require(bool(root_raw), "P9-07 rehearsal root is unavailable")
    root = Path(root_raw)
    candidate = Path(raw)
    require(
        root.is_dir()
        and not root.is_symlink()
        and candidate.is_dir()
        and not candidate.is_symlink(),
        "P9-07 rehearsal directory must be physical",
    )
    root = root.resolve(strict=True)
    candidate = candidate.resolve(strict=True)
    require(
        candidate.parent == root and DIRECTORY_PATTERN.fullmatch(candidate.name) is not None,
        "P9-07 rehearsal directory escaped the fixed temporary root",
    )
    require(
        stat.S_IMODE(candidate.stat().st_mode) & 0o077 == 0,
        "P9-07 rehearsal directory permissions are too broad",
    )
    return candidate


def release_manifest() -> dict[str, object]:
    load_controlled_database(require_runtime_config=True)
    git_sha = _run_git("rev-parse", "HEAD")
    frappe_sha = _run_git("rev-parse", "HEAD", cwd=BENCH_PATH / "apps" / "frappe")
    require(re.fullmatch(r"[a-f0-9]{40}", git_sha) is not None, "P9-07 Git SHA drifted")
    require(re.fullmatch(r"[a-f0-9]{40}", frappe_sha) is not None, "P9-07 Frappe SHA drifted")
    app_names = sorted(
        line.strip()
        for line in (BENCH_PATH / "sites" / "apps.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    require(
        app_names == ["frappe", "npi_core", "npi_integration"],
        "P9-07 installed application boundary drifted",
    )
    site_config = _read_json_object(
        BENCH_PATH / "sites" / SITE_NAME / "site_config.json",
        "Site configuration",
    )
    manifest = {
        "appNames": app_names,
        "appTreeSha256": {
            "npi_core": _git_tree_sha256("apps/npi_core"),
            "npi_integration": _git_tree_sha256("apps/npi_integration"),
        },
        "configKeyCount": len(site_config),
        "configKeySha256": canonical_sha256(sorted(site_config)),
        "database": DATABASE_NAME,
        "environment": "disposable-local-frappe-site",
        "frappeSha": frappe_sha,
        "gitSha": git_sha,
        "productionContact": False,
        "runtimeMarker": RUNTIME_MARKER,
        "schemaTreeSha256": _git_tree_sha256(
            "apps/npi_core/npi_core/npi_core/doctype"
        ),
        "schemaVersion": REHEARSAL_SCHEMA,
        "site": SITE_NAME,
    }
    validate_release_manifest(manifest)
    return manifest


def validate_release_manifest(value: object) -> None:
    require(isinstance(value, dict), "P9-07 release manifest must be an object")
    require(
        set(value)
        == {
            "appNames",
            "appTreeSha256",
            "configKeyCount",
            "configKeySha256",
            "database",
            "environment",
            "frappeSha",
            "gitSha",
            "productionContact",
            "runtimeMarker",
            "schemaTreeSha256",
            "schemaVersion",
            "site",
        },
        "P9-07 release manifest shape drifted",
    )
    require(
        value.get("schemaVersion") == REHEARSAL_SCHEMA
        and value.get("environment") == "disposable-local-frappe-site"
        and value.get("site") == SITE_NAME
        and value.get("database") == DATABASE_NAME
        and value.get("runtimeMarker") == RUNTIME_MARKER
        and value.get("productionContact") is False,
        "P9-07 release manifest target drifted",
    )
    require(
        value.get("appNames") == ["frappe", "npi_core", "npi_integration"],
        "P9-07 release manifest applications drifted",
    )
    app_hashes = value.get("appTreeSha256")
    require(
        isinstance(app_hashes, dict) and set(app_hashes) == {"npi_core", "npi_integration"},
        "P9-07 release manifest application fingerprints drifted",
    )
    hashes = [
        value.get("configKeySha256"),
        value.get("schemaTreeSha256"),
        *app_hashes.values(),
    ]
    require(
        len(hashes) == 4
        and all(re.fullmatch(r"[a-f0-9]{64}", str(item)) for item in hashes),
        "P9-07 release manifest fingerprints drifted",
    )


def _canary_description(stage: str) -> str:
    require(stage in {"pre", "post"}, "P9-07 canary stage drifted")
    return f"P9-07 synthetic {stage}-backup canary {RUN_ID}"


def _canary_paths(stage: str) -> tuple[Path, Path]:
    file_name = f"npi-p9-07-{stage}-{RUN_ID}.txt"
    site = BENCH_PATH / "sites" / SITE_NAME
    return site / "public" / "files" / file_name, site / "private" / "files" / file_name


def _canary_content(stage: str, visibility: str) -> bytes:
    return f"p9-07:{RUN_ID}:{stage}:{visibility}\n".encode("ascii")


def _todo_names(frappe: Any, stage: str) -> tuple[str, ...]:
    return tuple(
        frappe.get_all(
            "ToDo",
            filters={"description": _canary_description(stage)},
            pluck="name",
            limit_page_length=2,
        )
    )


def _write_canary_files(stage: str) -> None:
    for path, visibility in zip(_canary_paths(stage), ("public", "private"), strict=True):
        require(path.parent.is_dir() and not path.parent.is_symlink(), "P9-07 file root drifted")
        with path.open("xb") as stream:
            stream.write(_canary_content(stage, visibility))
        path.chmod(0o600)


def _remove_canary_files(stages: Iterable[str]) -> None:
    for stage in stages:
        for path in _canary_paths(stage):
            require(path.parent.is_dir() and not path.parent.is_symlink(), "P9-07 file root drifted")
            path.unlink(missing_ok=True)


def _verify_canary_files(stage: str, *, present: bool) -> None:
    for path, visibility in zip(_canary_paths(stage), ("public", "private"), strict=True):
        if present:
            require(path.is_file() and not path.is_symlink(), "P9-07 restored file canary is missing")
            require(
                path.read_bytes() == _canary_content(stage, visibility),
                "P9-07 restored file canary content drifted",
            )
        else:
            require(not path.exists(), "P9-07 post-backup file canary survived restore")


def run_frappe_phase(phase: str) -> dict[str, object]:
    import frappe

    require(RUN_ID_PATTERN.fullmatch(RUN_ID) is not None, "P9-07 runtime namespace drifted")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        document_runtime._validated_runtime_site()
        pre_names = _todo_names(frappe, "pre")
        post_names = _todo_names(frappe, "post")
        if phase == "prepare":
            require(not pre_names and not post_names, "P9-07 database canary is not clean")
            _remove_canary_files(("pre", "post"))
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": _canary_description("pre"),
                    "priority": "Low",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            _write_canary_files("pre")
            frappe.db.commit()
        elif phase == "post-backup":
            require(len(pre_names) == 1 and not post_names, "P9-07 pre-backup database canary drifted")
            _verify_canary_files("pre", present=True)
            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "description": _canary_description("post"),
                    "priority": "Low",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            _write_canary_files("post")
            frappe.db.commit()
        elif phase in {"verify-restore", "finalize"}:
            require(len(pre_names) == 1, "P9-07 pre-backup database canary was not restored")
            require(not post_names, "P9-07 post-backup database canary survived restore")
            _verify_canary_files("pre", present=True)
            _verify_canary_files("post", present=False)
            if phase == "finalize":
                frappe.delete_doc("ToDo", pre_names[0], ignore_permissions=True, force=True)
                _remove_canary_files(("pre",))
                frappe.db.commit()
        elif phase == "cleanup":
            for name in (*pre_names, *post_names):
                frappe.delete_doc("ToDo", name, ignore_permissions=True, force=True)
            _remove_canary_files(("pre", "post"))
            frappe.db.commit()
        else:
            raise RuntimeError("P9-07 fixture phase is not allowlisted")
        result = {
            "phase": phase,
            "productionContact": False,
            "runIdHash": hashlib.sha256(RUN_ID.encode("ascii")).hexdigest(),
            "schemaVersion": RESULT_SCHEMA,
        }
        return {**result, "evidenceChecksum": canonical_sha256(result)}
    finally:
        frappe.destroy()


def tree_inventory() -> dict[str, object]:
    load_controlled_database(require_runtime_config=True)
    site = BENCH_PATH / "sites" / SITE_NAME
    records: list[tuple[str, int, str]] = []
    total_bytes = 0
    for visibility in ("public", "private"):
        root = site / visibility / "files"
        require(root.is_dir() and not root.is_symlink(), "P9-07 file tree root drifted")
        for path in sorted(root.rglob("*")):
            require(not path.is_symlink(), "P9-07 file tree contains a symbolic link")
            if not path.is_file():
                continue
            size = path.stat().st_size
            total_bytes += size
            require(
                len(records) < MAX_TREE_FILES and total_bytes <= MAX_TREE_BYTES,
                "P9-07 file tree exceeds the fixed evidence bound",
            )
            records.append(
                (
                    f"{visibility}/{path.relative_to(root).as_posix()}",
                    size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
    evidence = {"fileCount": len(records), "totalBytes": total_bytes, "treeSha256": canonical_sha256(records)}
    return {**evidence, "evidenceChecksum": canonical_sha256(evidence)}


def backup_inventory(directory: Path) -> dict[str, object]:
    records: dict[str, dict[str, object]] = {}
    for label, name in sorted(BACKUP_MEMBERS.items()):
        path = directory / name
        require(path.is_file() and not path.is_symlink(), f"P9-07 {label} backup is unavailable")
        size = path.stat().st_size
        require(size > 0, f"P9-07 {label} backup is empty")
        records[label] = {"bytes": size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    evidence = {"members": records, "productionContact": False, "schemaVersion": RESULT_SCHEMA}
    return {**evidence, "evidenceChecksum": canonical_sha256(evidence)}


def validate_tree_replay(expected_path: Path) -> dict[str, object]:
    expected = _read_json_object(expected_path, "pre-backup file inventory")
    actual = tree_inventory()
    require(actual == expected, "P9-07 restored file tree does not match the backup source")
    return actual


def validate_forward_fix(manifest_path: Path) -> dict[str, object]:
    expected = _read_json_object(manifest_path, "release manifest")
    validate_release_manifest(expected)
    actual = release_manifest()
    require(actual == expected, "P9-07 post-restore release identity drifted")
    evidence = {
        "manifestSha256": canonical_sha256(actual),
        "productionContact": False,
        "schemaVersion": RESULT_SCHEMA,
    }
    return {**evidence, "evidenceChecksum": canonical_sha256(evidence)}


def build_result(directory: Path) -> dict[str, object]:
    manifest = _read_json_object(directory / "release-manifest.json", "release manifest")
    backup = _read_json_object(directory / "backup-inventory.json", "backup inventory")
    source_tree = _read_json_object(directory / "pre-backup-files.json", "file inventory")
    validate_release_manifest(manifest)
    require(
        backup == backup_inventory(directory),
        "P9-07 recorded backup inventory drifted",
    )
    require(
        source_tree == tree_inventory(),
        "P9-07 final restored file inventory drifted before canary cleanup",
    )
    durations: dict[str, int] = {}
    for key, environment_name in (
        ("backupSeconds", "NPI_P9_07_BACKUP_SECONDS"),
        ("restoreSeconds", "NPI_P9_07_RESTORE_SECONDS"),
        ("forwardFixSeconds", "NPI_P9_07_FORWARD_FIX_SECONDS"),
    ):
        raw = os.environ.get(environment_name, "")
        require(raw.isdigit(), f"P9-07 {key} is invalid")
        duration = int(raw)
        require(0 <= duration <= 2_700, f"P9-07 {key} exceeds the controlled bound")
        durations[key] = duration
    evidence = {
        **durations,
        "backupInventorySha256": canonical_sha256(backup),
        "fileTreeSha256": source_tree.get("treeSha256"),
        "forwardFixVerified": True,
        "productionContact": False,
        "releaseManifestSha256": canonical_sha256(manifest),
        "restoreVerified": True,
        "schemaVersion": RESULT_SCHEMA,
    }
    return {**evidence, "evidenceChecksum": canonical_sha256(evidence)}


def emit(value: object) -> None:
    print(json.dumps(value, separators=(",", ":"), sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "backup-inventory",
            "capture-tree",
            "forward-fix",
            "manifest",
            "prepare",
            "post-backup",
            "verify-restore",
            "verify-tree",
            "finalize",
            "cleanup",
            "result",
        ),
    )
    parser.add_argument("--rehearsal-dir")
    arguments = parser.parse_args()
    require(RUN_ID_PATTERN.fullmatch(RUN_ID) is not None, "P9-07 runtime fixture run ID is invalid")
    directory = (
        validated_rehearsal_directory(arguments.rehearsal_dir)
        if arguments.rehearsal_dir
        else None
    )
    if arguments.mode == "manifest":
        emit(release_manifest())
    elif arguments.mode == "capture-tree":
        emit(tree_inventory())
    elif arguments.mode == "backup-inventory":
        require(directory is not None, "P9-07 backup inventory directory is required")
        emit(backup_inventory(directory))
    elif arguments.mode == "verify-tree":
        require(directory is not None, "P9-07 tree inventory directory is required")
        emit(validate_tree_replay(directory / "pre-backup-files.json"))
    elif arguments.mode == "forward-fix":
        require(directory is not None, "P9-07 release manifest directory is required")
        emit(validate_forward_fix(directory / "release-manifest.json"))
    elif arguments.mode == "result":
        require(directory is not None, "P9-07 result directory is required")
        emit(build_result(directory))
    else:
        emit(run_frappe_phase(arguments.mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
