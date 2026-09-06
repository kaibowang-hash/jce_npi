from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_document_runtime as document_runtime
from verify_frappe_runtime import require


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
TENANT_ID = document_runtime.TENANT_ID
FIXTURE_RUN_ID = os.environ.get("NPI_DOCUMENT_RUNTIME_RUN_ID", "")
RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")

HEADERS = {
    "projects.csv": (
        "source_key",
        "business_code",
        "title",
        "project_type",
        "owner_user_id",
        "target_sop",
        "template_global_id",
        "template_version",
        "template_expected_version",
    ),
    "tooling_mappings.csv": (
        "source_key",
        "project_source_key",
        "tooling_global_id",
        "target_version",
        "target_snapshot_hash",
    ),
    "file_index.csv": (
        "source_key",
        "project_source_key",
        "file_revision_global_id",
        "file_optimistic_version",
        "file_sha256",
    ),
    "npi_references.csv": (
        "source_key",
        "project_source_key",
        "reference_type",
        "source_system",
        "source_object_id",
    ),
}


def deterministic_uuid(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"p9-05:{FIXTURE_RUN_ID}:{label}")


def _csv(name: str, row: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADERS[name])
    writer.writerow(row)
    return stream.getvalue().encode()


def build_bundle(*, target_revision_id: UUID, target_version: int, target_hash: str) -> bytes:
    project_key = f"project-{FIXTURE_RUN_ID[:12]}"
    members = {
        "projects.csv": _csv(
            "projects.csv",
            [
                project_key,
                f"P905-{FIXTURE_RUN_ID[:12]}",
                "Synthetic historical migration rehearsal",
                "new_tool",
                f"p9-05-missing-{FIXTURE_RUN_ID[:12]}@example.invalid",
                "2026-12-01",
                str(deterministic_uuid("missing-template")),
                "1",
                "1",
            ],
        ),
        "tooling_mappings.csv": _csv(
            "tooling_mappings.csv",
            [
                f"tooling-{FIXTURE_RUN_ID[:12]}",
                project_key,
                str(deterministic_uuid("missing-tooling")),
                "1",
                "a" * 64,
            ],
        ),
        "file_index.csv": _csv(
            "file_index.csv",
            [
                f"file-{FIXTURE_RUN_ID[:12]}",
                project_key,
                str(target_revision_id),
                str(target_version),
                target_hash,
            ],
        ),
        "npi_references.csv": _csv(
            "npi_references.csv",
            [
                f"reference-{FIXTURE_RUN_ID[:12]}",
                project_key,
                "part",
                "NPI_ONE",
                str(deterministic_uuid("missing-part")),
            ],
        ),
    }
    manifest = {
        "schemaVersion": "historical-migration-rehearsal.v1",
        "bundleId": str(deterministic_uuid("bundle")),
        "sourceSystem": "LEGACY_NPI",
        "members": [
            {
                "name": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "rowCount": 1,
            }
            for name, content in sorted(members.items())
        ],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, separators=(",", ":"), sort_keys=True))
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def _insert_container_project() -> UUID:
    import frappe

    from npi_core.project.frappe_validation import sha256_json

    project_id = deterministic_uuid("container-project")
    template_id = deterministic_uuid("container-template")
    snapshot = {
        "templateGlobalId": str(template_id),
        "templateCode": "P905-RUNTIME",
        "templateVersion": 1,
        "applicableProjectTypes": ["new_tool"],
        "referenceRules": [],
        "gates": [],
    }
    previous = getattr(frappe.flags, "npi_project_command_write", None)
    frappe.flags.npi_project_command_write = True
    try:
        frappe.get_doc(
            {
                "doctype": "NPI Engineering Project",
                "global_id": str(project_id),
                "tenant_id": TENANT_ID,
                "business_code": f"P905-CONTAINER-{FIXTURE_RUN_ID[:12]}",
                "title": "Synthetic P9-05 runtime container",
                "project_type": "new_tool",
                "owner_user_id": f"p9-05-owner-{FIXTURE_RUN_ID[:12]}@example.invalid",
                "target_sop": "2026-12-01",
                "template_global_id": str(template_id),
                "template_code": "P905-RUNTIME",
                "template_version": 1,
                "template_snapshot_hash": sha256_json(snapshot),
                "template_snapshot": snapshot,
                "references": [],
                "creation_payload_hash": hashlib.sha256(FIXTURE_RUN_ID.encode()).hexdigest(),
            }
        ).insert()
    finally:
        if previous is None:
            delattr(frappe.flags, "npi_project_command_write")
        else:
            frappe.flags.npi_project_command_write = previous
    return project_id


def _insert_clean_file(project_id: UUID, label: str, content: bytes) -> dict[str, object]:
    import frappe
    from frappe.utils import now_datetime
    from frappe.utils.file_manager import save_file

    from npi_core.controlled_evidence_validation import (
        FILE_REVISION_COMMAND_FLAG,
        FILE_SCAN_RESULT_FLAG,
    )

    revision_id = deterministic_uuid(f"{label}-revision")
    file_document = save_file(
        f"p9-05-{label}-{FIXTURE_RUN_ID[:12]}.bin",
        content,
        "",
        "",
        is_private=1,
    )
    previous_command = getattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, None)
    setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, True)
    try:
        revision = frappe.get_doc(
            {
                "doctype": "NPI File Revision",
                "global_id": str(revision_id),
                "tenant_id": TENANT_ID,
                "project_global_id": str(project_id),
                "document_global_id": str(deterministic_uuid(f"{label}-document")),
                "revision": 1,
                "frappe_file_id": file_document.name,
                "file": file_document.file_url,
                "sha256": "0" * 64,
                "scan_state": "pending",
            }
        ).insert()
    finally:
        if previous_command is None:
            delattr(frappe.flags, FILE_REVISION_COMMAND_FLAG)
        else:
            setattr(frappe.flags, FILE_REVISION_COMMAND_FLAG, previous_command)
    previous_scan = getattr(frappe.flags, FILE_SCAN_RESULT_FLAG, None)
    setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, True)
    try:
        revision.scan_state = "clean"
        revision.scan_observed_at = now_datetime()
        revision.save()
    finally:
        if previous_scan is None:
            delattr(frappe.flags, FILE_SCAN_RESULT_FLAG)
        else:
            setattr(frappe.flags, FILE_SCAN_RESULT_FLAG, previous_scan)
    return {
        "globalId": revision_id,
        "optimisticVersion": int(revision.optimistic_version),
        "sha256": str(revision.sha256),
    }


def verify_runtime_rehearsal(fixture_run_id: str) -> dict[str, object]:
    import frappe

    from npi_core.foundation.security import Principal
    from npi_core.historical_migration.domain import HistoricalMigrationConflict
    from npi_core.historical_migration.frappe_repository import (
        FrappeHistoricalMigrationRepository,
        _execution_enabled,
        run_historical_migration_job,
    )

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and RUN_ID_PATTERN.fullmatch(fixture_run_id) is not None,
        "P9-05 runtime namespace drifted",
    )
    for doctype in (
        "NPI Historical Migration Batch",
        "NPI Historical Migration Preview",
        "NPI Historical Migration Job",
        "NPI Historical Migration Target Binding",
    ):
        require(frappe.db.table_exists(doctype), f"P9-05 runtime metadata unavailable: {doctype}")

    require(_execution_enabled() is False, "P9-05 execution must start disabled")
    project_id = _insert_container_project()
    target = _insert_clean_file(project_id, "target", b"synthetic target file\n")
    bundle = build_bundle(
        target_revision_id=target["globalId"],
        target_version=int(target["optimisticVersion"]),
        target_hash=str(target["sha256"]),
    )
    source = _insert_clean_file(project_id, "source", bundle)

    frappe.conf["npi_p9_05_routes_disabled"] = False
    frappe.conf["npi_p9_05_non_production_rehearsal"] = True
    principal = Principal(
        user_id="Administrator",
        roles=frozenset({"System Manager"}),
        tenant_id=TENANT_ID,
    )
    repository = FrappeHistoricalMigrationRepository(
        principal=principal,
        request_id=str(deterministic_uuid("request")),
        trace_id=f"trace-p905-{fixture_run_id}",
    )
    preview = repository.create_preview(
        tenant_id=TENANT_ID,
        file_revision_global_id=source["globalId"],
        file_optimistic_version=int(source["optimisticVersion"]),
        source_sha256=str(source["sha256"]),
    )
    require(
        preview.replayed is False
        and preview.response["summary"] == {"create": 0, "link": 1, "skip": 0, "blocked": 3},
        "P9-05 preview action truth drifted",
    )
    try:
        repository.queue_execution(
            preview_id=UUID(str(preview.response["globalId"])),
            expected_version=0,
            expected_snapshot_hash=str(preview.response["snapshotHash"]),
            execution_key_hash="b" * 64,
        )
    except HistoricalMigrationConflict:
        stale_rejected = True
    else:
        stale_rejected = False

    original_enqueue = frappe.enqueue
    frappe.enqueue = lambda *args, **kwargs: None
    try:
        queued = repository.queue_execution(
            preview_id=UUID(str(preview.response["globalId"])),
            expected_version=int(preview.response["version"]),
            expected_snapshot_hash=str(preview.response["snapshotHash"]),
            execution_key_hash="c" * 64,
        )
    finally:
        frappe.enqueue = original_enqueue
    replay = repository.queue_execution(
        preview_id=UUID(str(preview.response["globalId"])),
        expected_version=int(preview.response["version"]),
        expected_snapshot_hash=str(preview.response["snapshotHash"]),
        execution_key_hash="c" * 64,
    )
    job_id = UUID(str(queued.response["globalId"]))
    run_historical_migration_job(str(job_id), str(queued.response["snapshotHash"]))
    partial = repository.job(job_id)
    correction = repository.create_correction(job_id, execution_key_hash="d" * 64)
    correction_content, _file_name = repository.correction_content(job_id)
    corrected_job = repository.job(job_id)
    reconciled = repository.reconcile(
        job_id,
        expected_version=int(corrected_job["optimisticVersion"]),
        expected_snapshot_hash=str(corrected_job["snapshotHash"]),
        execution_key_hash="e" * 64,
    )
    reconciliation_replay = repository.reconcile(
        job_id,
        expected_version=int(reconciled.response["optimisticVersion"]),
        expected_snapshot_hash=str(reconciled.response["snapshotHash"]),
        execution_key_hash="e" * 64,
    )
    rolled_back = repository.rollback(
        job_id,
        expected_version=int(reconciled.response["optimisticVersion"]),
        expected_snapshot_hash=str(reconciled.response["snapshotHash"]),
        execution_key_hash="f" * 64,
    )
    rollback = rolled_back.response.get("rollback", {})
    require(
        stale_rejected
        and replay.replayed is True
        and replay.response["globalId"] == str(job_id)
        and partial["state"] == "partially_succeeded"
        and len(partial["results"]) == 4
        and sum(item["state"] == "linked" for item in partial["results"]) == 1
        and correction.response["failedRowCount"] == 3
        and correction.response["private"] is True
        and hashlib.sha256(correction_content).hexdigest() == correction.response["sha256"]
        and reconciled.response["state"] == "reconciled"
        and reconciled.response["reconciliation"]["observationCount"] == 1
        and reconciled.response["reconciliation"]["mismatchCount"] == 0
        and reconciliation_replay.replayed is True
        and rolled_back.response["state"] == "rolled_back"
        and rollback.get("decision") == "allowed"
        and rollback.get("items", [{}])[0].get("targetRetained") is True
        and frappe.db.exists("NPI File Revision", str(target["globalId"])),
        "P9-05 partial, replay, correction, reconciliation, or rollback truth drifted",
    )
    evidence = {
        "bundleSha256": str(source["sha256"]),
        "correctionSha256": str(correction.response["sha256"]),
        "exactReplay": replay.replayed,
        "failedRowCount": 3,
        "linkedRowCount": 1,
        "manifestHash": str(preview.response["manifestHash"]),
        "productionContact": False,
        "reconciliationReplay": reconciliation_replay.replayed,
        "rollbackDecision": rollback.get("decision"),
        "staleRejected": stale_rejected,
    }
    return {
        **evidence,
        "evidenceChecksum": hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest(),
    }


def run_bench_fixture() -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(ROOT) if not current_pythonpath else f"{ROOT}{os.pathsep}{current_pythonpath}"
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        completed = subprocess.run(
            [
                str(BENCH_PATH / "env" / "bin" / "python"),
                str(Path(__file__).resolve()),
                "--bench-fixture",
            ],
            cwd=BENCH_PATH / "sites",
            env=environment,
            check=False,
            stdout=output,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        require(completed.returncode == 0, "P9-05 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(bool(lines), "P9-05 Bench fixture was silent")
    result = json.loads(lines[-1])
    require(
        isinstance(result, dict)
        and result.get("exactReplay") is True
        and result.get("reconciliationReplay") is True
        and result.get("staleRejected") is True
        and result.get("linkedRowCount") == 1
        and result.get("failedRowCount") == 3
        and result.get("rollbackDecision") == "allowed"
        and result.get("productionContact") is False
        and all(re.fullmatch(r"[a-f0-9]{64}", str(result.get(key))) for key in (
            "bundleSha256", "correctionSha256", "manifestHash", "evidenceChecksum"
        )),
        "P9-05 Bench fixture output drifted",
    )
    return result


def run_local_bench_fixture() -> None:
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    original_commit = frappe.db.commit
    disabled_before = frappe.conf.get("npi_p9_05_routes_disabled")
    rehearsal_before = frappe.conf.get("npi_p9_05_non_production_rehearsal")
    try:
        frappe.set_user("Administrator")
        frappe.db.commit = lambda: None
        result = verify_runtime_rehearsal(FIXTURE_RUN_ID)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    finally:
        frappe.db.commit = original_commit
        if disabled_before is None:
            frappe.conf.pop("npi_p9_05_routes_disabled", None)
        else:
            frappe.conf["npi_p9_05_routes_disabled"] = disabled_before
        if rehearsal_before is None:
            frappe.conf.pop("npi_p9_05_non_production_rehearsal", None)
        else:
            frappe.conf["npi_p9_05_non_production_rehearsal"] = rehearsal_before
        frappe.db.rollback()
        frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-fixture", action="store_true")
    arguments = parser.parse_args()
    require(
        RUN_ID_PATTERN.fullmatch(FIXTURE_RUN_ID) is not None,
        "P9-05 runtime fixture run ID is invalid",
    )
    if arguments.bench_fixture:
        run_local_bench_fixture()
        return 0
    result = run_bench_fixture()
    print(
        json.dumps(
            {
                "environment": "disposable-local-frappe-site",
                "productionContact": False,
                "runtime": result,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
