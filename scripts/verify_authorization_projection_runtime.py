from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import verify_document_runtime as document_runtime
from verify_frappe_runtime import require


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
TENANT_ID = document_runtime.TENANT_ID
FIXTURE_RUN_ID = os.environ.get("NPI_DOCUMENT_RUNTIME_RUN_ID", "")
RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def deterministic_uuid(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"p9-04:{FIXTURE_RUN_ID}:{label}")


def event_mapping(
    *,
    source_version: int,
    enabled: bool,
    event_label: str,
    service_user: str,
    target_user: str,
    now: datetime,
) -> dict[str, object]:
    from npi_integration.authorization_projection.domain import canonical_hash

    roles = ["NPI API User"] if enabled else []
    projects = (
        [
            {
                "projectId": str(deterministic_uuid("project")),
                "access": "contribute",
            }
        ]
        if enabled
        else []
    )
    organizations = (
        [{"kind": "Company", "referenceKey": "runtime-company-reference"}]
        if enabled
        else []
    )
    payload: dict[str, object] = {
        "sourceSubjectId": f"runtime-subject-{FIXTURE_RUN_ID}",
        "targetUserId": target_user,
        "sourceVersion": source_version,
        "enabled": enabled,
        "roles": roles,
        "projectAccess": projects,
        "organizationScopes": organizations,
        "issuedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiresAt": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return {
        "schemaVersion": 1,
        "operation": "replace_user_authorization",
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "objectType": "UserAuthorizationProjection",
        "eventId": str(deterministic_uuid(event_label)),
        **payload,
        "traceId": f"trace-p904-{FIXTURE_RUN_ID}",
        "payloadHash": canonical_hash(payload),
    }


def ensure_service_user(user_id: str) -> None:
    import frappe

    require(not frappe.db.exists("User", user_id), "P9-04 runtime user already exists")
    frappe.get_doc(
        {
            "doctype": "User",
            "email": user_id,
            "enabled": 1,
            "first_name": "P9 Authorization",
            "last_name": "Runtime Fixture",
            "language": "en",
            "roles": [
                {"role": "Desk User"},
                {"role": "NPI API User"},
            ],
            "send_welcome_email": 0,
            "user_type": "System User",
        }
    ).insert()


def verify_runtime_projection(fixture_run_id: str) -> dict[str, object]:
    import frappe

    from npi_core.foundation.errors import AuthenticationRequired, VersionConflict
    from npi_core.request_security import authenticated_principal
    from npi_integration.authorization_projection.domain import (
        AuthorizationProjectionEvent,
    )
    from npi_integration.authorization_projection.frappe_repository import (
        FrappeAuthorizationProjectionRepository,
        resolve_authorization_projection,
    )

    document_runtime._validated_runtime_site()
    require(
        fixture_run_id == FIXTURE_RUN_ID
        and RUN_ID_PATTERN.fullmatch(fixture_run_id) is not None,
        "P9-04 runtime namespace drifted",
    )
    service_user = f"p9-04-service-{fixture_run_id}@example.invalid"
    target_user = f"p9-04-member-{fixture_run_id}@example.invalid"
    ensure_service_user(service_user)
    require(
        not frappe.db.exists("User", target_user),
        "P9-04 target User must be absent before governed provisioning",
    )
    now = datetime.now(UTC).replace(microsecond=0)
    frappe.conf["npi_p9_04_authorization_role_allowlist"] = ["NPI API User"]
    frappe.conf["npi_p9_04_authorization_max_ttl_seconds"] = 7200
    frappe.conf["npi_p9_04_authorization_projection_enforced"] = True
    frappe.set_user(service_user)
    repository = FrappeAuthorizationProjectionRepository(
        actor=service_user,
        tenant_id=TENANT_ID,
        request_id=deterministic_uuid("request"),
        now=now,
    )
    first_event = AuthorizationProjectionEvent.from_mapping(
        event_mapping(
            source_version=1,
            enabled=True,
            event_label="enabled",
            service_user=service_user,
            target_user=target_user,
            now=now,
        )
    )
    first = repository.apply(first_event)
    replay = repository.apply(first_event)
    local_user = frappe.db.get_value(
        "User",
        target_user,
        ["enabled", "user_type", "send_welcome_email"],
        as_dict=True,
    )
    local_roles = set(frappe.get_roles(target_user) or ())
    resolved = resolve_authorization_projection(target_user, TENANT_ID, now)
    require(
        first.state == "enabled"
        and first.local_user_state == "enabled"
        and first.local_user_disposition == "created"
        and replay.exact_replay is True
        and replay.local_user_disposition == "exact_replay"
        and local_user
        and int(local_user.get("enabled") or 0) == 1
        and local_user.get("user_type") == "System User"
        and int(local_user.get("send_welcome_email") or 0) == 0
        and "Desk User" in local_roles
        and "System Manager" not in local_roles
        and isinstance(resolved, dict)
        and resolved.get("roles") == ("NPI API User",)
        and resolved.get("project_access")
        == {str(deterministic_uuid("project")): "contribute"}
        and resolved.get("organization_scopes")
        == {
            "Company": ("runtime-company-reference",),
            "Customer": (),
            "Supplier": (),
        },
        "P9-04 current projection truth drifted",
    )
    frappe.set_user(target_user)
    principal = authenticated_principal()
    require(
        principal.user_id == target_user
        and principal.roles == frozenset({"NPI API User"})
        and principal.tenant_id == TENANT_ID
        and principal.is_external is False,
        "P9-04 projected principal drifted",
    )
    frappe.set_user(service_user)
    try:
        repository.apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    source_version=1,
                    enabled=True,
                    event_label="stale",
                    service_user=service_user,
                    target_user=target_user,
                    now=now,
                )
            )
        )
    except VersionConflict:
        stale_rejected = True
    else:
        stale_rejected = False
    disabled = repository.apply(
        AuthorizationProjectionEvent.from_mapping(
            event_mapping(
                source_version=2,
                enabled=False,
                event_label="disabled",
                service_user=service_user,
                target_user=target_user,
                now=now,
            )
        )
    )
    disabled_user = frappe.db.get_value(
        "User",
        target_user,
        ["enabled", "user_type"],
        as_dict=True,
    )
    frappe.set_user(target_user)
    try:
        authenticated_principal()
    except AuthenticationRequired:
        disabled_rejected = True
    else:
        disabled_rejected = False
    projection_count = frappe.db.count(
        "NPI Authorization Projection",
        {"global_id": str(first.projection_id)},
    )
    audit_count = frappe.db.count(
        "NPI Audit Event",
        {"global_id": str(first.projection_id)},
    )
    require(
        stale_rejected
        and disabled.state == "disabled"
        and disabled.local_user_state == "disabled"
        and disabled.local_user_disposition == "disabled"
        and disabled_user
        and int(disabled_user.get("enabled") or 0) == 0
        and disabled_user.get("user_type") == "System User"
        and disabled_rejected
        and projection_count == 1
        and audit_count == 2,
        "P9-04 replay, stale, revocation, or audit truth drifted",
    )
    evidence = {
        "auditCount": audit_count,
        "disabledFailsClosed": disabled_rejected,
        "exactReplay": replay.exact_replay,
        "localUserCreated": first.local_user_disposition == "created",
        "localUserDisabled": int(disabled_user.get("enabled") or 0) == 0,
        "projectionCount": projection_count,
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
        require(completed.returncode == 0, "P9-04 Bench fixture failed")
        output.seek(0)
        lines = [line for line in output if line.strip()]
    require(bool(lines), "P9-04 Bench fixture was silent")
    result = json.loads(lines[-1])
    require(
        isinstance(result, dict)
        and set(result)
        == {
            "auditCount",
            "disabledFailsClosed",
            "evidenceChecksum",
            "exactReplay",
            "localUserCreated",
            "localUserDisabled",
            "projectionCount",
            "staleRejected",
        }
        and result.get("auditCount") == 2
        and result.get("disabledFailsClosed") is True
        and result.get("exactReplay") is True
        and result.get("localUserCreated") is True
        and result.get("localUserDisabled") is True
        and result.get("projectionCount") == 1
        and result.get("staleRejected") is True
        and re.fullmatch(r"[a-f0-9]{64}", str(result.get("evidenceChecksum"))),
        "P9-04 Bench fixture output drifted",
    )
    return result


def run_local_bench_fixture() -> None:
    import frappe

    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = verify_runtime_projection(FIXTURE_RUN_ID)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    finally:
        frappe.db.rollback()
        frappe.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-fixture", action="store_true")
    arguments = parser.parse_args()
    require(
        RUN_ID_PATTERN.fullmatch(FIXTURE_RUN_ID) is not None,
        "P9-04 runtime fixture run ID is invalid",
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
