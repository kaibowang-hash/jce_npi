from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import date
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


def deterministic_uuid(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"p9-06:{FIXTURE_RUN_ID}:{label}")


def verify_runtime_data_exchange(fixture_run_id: str) -> dict[str, object]:
    import frappe

    from npi_core.data_exchange.domain import (
        ArchiveSourceKind,
        DataExchangeConflict,
        DatasetId,
        ExportLanguage,
        RedactionProfile,
        RetentionCategory,
        RetentionScope,
    )
    from npi_core.data_exchange.frappe_repository import (
        FrappeDataExchangeRepository,
        _routes_enabled,
    )
    from npi_core.foundation.security import Principal

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and RUN_ID_PATTERN.fullmatch(fixture_run_id) is not None,
        "P9-06 runtime namespace drifted",
    )
    for doctype in (
        "NPI Data Exchange Profile",
        "NPI Data Exchange Export",
        "NPI Retention Policy Version",
        "NPI Retention Archive Record",
    ):
        require(
            frappe.db.table_exists(doctype),
            f"P9-06 runtime metadata unavailable: {doctype}",
        )
    require(_routes_enabled() is False, "P9-06 routes must start disabled")
    frappe.conf["npi_p9_06_routes_disabled"] = False
    principal = Principal(
        user_id="Administrator",
        roles=frozenset({"System Manager"}),
        tenant_id=TENANT_ID,
    )
    repository = FrappeDataExchangeRepository(
        principal=principal,
        request_id=str(deterministic_uuid("request")),
        trace_id=f"trace-p906-{fixture_run_id}",
    )
    profile_id = deterministic_uuid("profile")
    profile = repository.publish_profile(
        global_id=profile_id,
        version=1,
        dataset_id=DatasetId.PROJECT_PORTFOLIO,
        columns=(
            "projectCode",
            "title",
            "projectType",
            "lifecycleState",
            "targetSop",
            "currentHealthStatus",
            "openWorkCount",
            "currentGate",
            "erpAvailability",
        ),
        language=ExportLanguage.ENGLISH,
        redaction_profile=RedactionProfile.MINIMUM_DISCLOSURE,
        query=(),
        max_rows=5_000,
        max_bytes=8_000_000,
    )
    profile_replay = repository.publish_profile(
        global_id=profile_id,
        version=1,
        dataset_id=DatasetId.PROJECT_PORTFOLIO,
        columns=(
            "projectCode",
            "title",
            "projectType",
            "lifecycleState",
            "targetSop",
            "currentHealthStatus",
            "openWorkCount",
            "currentGate",
            "erpAvailability",
        ),
        language=ExportLanguage.ENGLISH,
        redaction_profile=RedactionProfile.MINIMUM_DISCLOSURE,
        query=(),
        max_rows=5_000,
        max_bytes=8_000_000,
    )
    export = repository.create_export(
        profile_id=profile_id,
        profile_version=1,
        profile_hash=str(profile.response["definitionHash"]),
        execution_key_hash="a" * 64,
    )
    export_replay = repository.create_export(
        profile_id=profile_id,
        profile_version=1,
        profile_hash=str(profile.response["definitionHash"]),
        execution_key_hash="a" * 64,
    )
    export_id = UUID(str(export.response["globalId"]))
    package_hash = str(export.response["artifact"]["sha256"])
    content, file_name, mime_type = repository.export_content(export_id, package_hash)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = tuple(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    require(
        members
        == (
            "manifest.json",
            "report.csv",
            "report.xlsx",
            "report.pdf",
            "README.txt",
        )
        and manifest.get("profileHash") == profile.response["definitionHash"]
        and manifest.get("dataSha256") == export.response["dataHash"]
        and hashlib.sha256(content).hexdigest() == package_hash
        and file_name.endswith(".zip")
        and mime_type == "application/zip",
        "P9-06 deterministic private package truth drifted",
    )
    years = tuple((category, 7) for category in RetentionCategory)
    policy_id = deterministic_uuid("policy")
    policy = repository.publish_policy(
        global_id=policy_id,
        version=1,
        scope=RetentionScope.TENANT,
        scope_reference=None,
        effective_from=date(2020, 1, 1),
        effective_until=None,
        retention_years=years,
    )
    policy_replay = repository.publish_policy(
        global_id=policy_id,
        version=1,
        scope=RetentionScope.TENANT,
        scope_reference=None,
        effective_from=date(2020, 1, 1),
        effective_until=None,
        retention_years=years,
    )
    archive_id = deterministic_uuid("archive")
    try:
        repository.create_archive(
            global_id=archive_id,
            source_kind=ArchiveSourceKind.DATA_EXCHANGE_EXPORT,
            source_id=export_id,
            source_version=1,
            source_hash="0" * 64,
            policy_id=policy_id,
            policy_version=1,
            policy_hash=str(policy.response["definitionHash"]),
            scope=RetentionScope.TENANT,
            scope_reference=None,
            execution_key_hash="b" * 64,
        )
    except DataExchangeConflict:
        source_drift_rejected = True
    else:
        source_drift_rejected = False
    archived = repository.create_archive(
        global_id=archive_id,
        source_kind=ArchiveSourceKind.DATA_EXCHANGE_EXPORT,
        source_id=export_id,
        source_version=1,
        source_hash=package_hash,
        policy_id=policy_id,
        policy_version=1,
        policy_hash=str(policy.response["definitionHash"]),
        scope=RetentionScope.TENANT,
        scope_reference=None,
        execution_key_hash="c" * 64,
    )
    archive_replay = repository.create_archive(
        global_id=archive_id,
        source_kind=ArchiveSourceKind.DATA_EXCHANGE_EXPORT,
        source_id=export_id,
        source_version=1,
        source_hash=package_hash,
        policy_id=policy_id,
        policy_version=1,
        policy_hash=str(policy.response["definitionHash"]),
        scope=RetentionScope.TENANT,
        scope_reference=None,
        execution_key_hash="c" * 64,
    )
    require(
        profile_replay.replayed
        and export_replay.replayed
        and policy_replay.replayed
        and archive_replay.replayed
        and source_drift_rejected
        and archived.response["sourceHash"] == package_hash
        and archived.response["policyHash"] == policy.response["definitionHash"],
        "P9-06 exact replay, conflict or archive binding truth drifted",
    )
    evidence = {
        "archiveRecordHash": str(archived.response["recordHash"]),
        "exactArchiveReplay": archive_replay.replayed,
        "exactExportReplay": export_replay.replayed,
        "exactPolicyReplay": policy_replay.replayed,
        "exactProfileReplay": profile_replay.replayed,
        "packageSha256": package_hash,
        "productionContact": False,
        "sourceDriftRejected": source_drift_rejected,
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
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
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
        require(completed.returncode == 0, "P9-06 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(bool(lines), "P9-06 Bench fixture was silent")
    result = json.loads(lines[-1])
    require(
        isinstance(result, dict)
        and result.get("exactArchiveReplay") is True
        and result.get("exactExportReplay") is True
        and result.get("exactPolicyReplay") is True
        and result.get("exactProfileReplay") is True
        and result.get("sourceDriftRejected") is True
        and result.get("productionContact") is False
        and all(
            re.fullmatch(r"[a-f0-9]{64}", str(result.get(key)))
            for key in ("archiveRecordHash", "packageSha256", "evidenceChecksum")
        ),
        "P9-06 Bench fixture output drifted",
    )
    return result


def run_local_bench_fixture() -> None:
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    original_commit = frappe.db.commit
    disabled_before = frappe.conf.get("npi_p9_06_routes_disabled")
    try:
        frappe.set_user("Administrator")
        frappe.db.commit = lambda: None
        result = verify_runtime_data_exchange(FIXTURE_RUN_ID)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    finally:
        frappe.db.commit = original_commit
        if disabled_before is None:
            frappe.conf.pop("npi_p9_06_routes_disabled", None)
        else:
            frappe.conf["npi_p9_06_routes_disabled"] = disabled_before
        frappe.db.rollback()
        frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-fixture", action="store_true")
    arguments = parser.parse_args()
    require(
        RUN_ID_PATTERN.fullmatch(FIXTURE_RUN_ID) is not None,
        "P9-06 runtime fixture run ID is invalid",
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
