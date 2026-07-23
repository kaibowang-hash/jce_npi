from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from uuid import uuid4

from verify_frappe_runtime import (
    HttpResult,
    create_disposable_user,
    delete_disposable_user,
    login,
    request,
    require,
    user_resource_path,
    validate_disposable_user,
    validate_problem,
)


TEMPLATE_GLOBAL_ID = "54be6b80-1534-54b9-97e6-9314cb8d69af"
TEMPLATE_VERSION = 1
TEMPLATE_VERSION_KEY = f"{TEMPLATE_GLOBAL_ID}:{TEMPLATE_VERSION}"
TEMPLATE_CODE = "P4-RUNTIME-SYNTHETIC"
TENANT_ID = "runtime-tenant"
BUSINESS_CODE = "P4-RUNTIME-001"
IDEMPOTENCY_KEY = "p4-runtime-project-create-v1"
CONFLICT_KEY = "p4-runtime-business-conflict-v1"
VERSION_KEY = "p4-runtime-version-conflict-v1"


def resource_path(doctype: str, name: str | None = None) -> str:
    encoded_doctype = urllib.parse.quote(doctype, safe="")
    if name is None:
        return f"/api/resource/{encoded_doctype}"
    return f"/api/resource/{encoded_doctype}/{urllib.parse.quote(name, safe='')}"


def get_resource(opener, base_url: str, doctype: str, name: str) -> HttpResult:
    return request(opener, base_url, resource_path(doctype, name))


def create_resource(
    opener,
    base_url: str,
    doctype: str,
    payload: dict[str, object],
    csrf_token: str,
) -> HttpResult:
    return request(
        opener,
        base_url,
        resource_path(doctype),
        method="POST",
        payload=payload,
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
    )


def update_resource(
    opener,
    base_url: str,
    doctype: str,
    name: str,
    payload: dict[str, object],
    csrf_token: str,
) -> HttpResult:
    return request(
        opener,
        base_url,
        resource_path(doctype, name),
        method="PUT",
        payload=payload,
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
    )


def set_user_enabled(
    opener,
    base_url: str,
    user_id: str,
    enabled: bool,
    csrf_token: str,
) -> None:
    result = update_resource(
        opener,
        base_url,
        "User",
        user_id,
        {"enabled": 1 if enabled else 0},
        csrf_token,
    )
    require(
        result.status == 200,
        f"Disposable Project owner update returned HTTP {result.status}",
    )


def set_template_enabled(
    opener,
    base_url: str,
    enabled: bool,
    csrf_token: str,
) -> None:
    result = update_resource(
        opener,
        base_url,
        "NPI Project Template",
        TEMPLATE_GLOBAL_ID,
        {"enabled": 1 if enabled else 0},
        csrf_token,
    )
    require(
        result.status == 200,
        f"Synthetic Project Template update returned HTTP {result.status}",
    )


def delete_resource(
    opener,
    base_url: str,
    doctype: str,
    name: str,
    csrf_token: str,
) -> HttpResult:
    return request(
        opener,
        base_url,
        resource_path(doctype, name),
        method="DELETE",
        request_headers={"X-Frappe-CSRF-Token": csrf_token},
    )


def list_resources(
    opener,
    base_url: str,
    doctype: str,
    *,
    filters: list[list[object]],
    fields: list[str],
) -> list[dict[str, object]]:
    query = urllib.parse.urlencode(
        {
            "fields": json.dumps(fields, separators=(",", ":")),
            "filters": json.dumps(filters, separators=(",", ":")),
            "limit_page_length": "100",
        }
    )
    result = request(
        opener,
        base_url,
        f"{resource_path(doctype)}?{query}",
    )
    require(result.status == 200, f"{doctype} query returned HTTP {result.status}")
    rows = result.body.get("data")
    require(isinstance(rows, list), f"{doctype} query did not return a data list")
    return rows


def bootstrap_csrf(opener, base_url: str, expected_user: str) -> str:
    result = request(opener, base_url, "/api/npi/v1/session/bootstrap")
    require(result.status == 200, f"Bootstrap returned HTTP {result.status}")
    require(result.body.get("userId") == expected_user, "Bootstrap user drifted")
    token = result.body.get("csrfToken")
    require(isinstance(token, str) and len(token) >= 32, "CSRF token is unavailable")
    return token


def ensure_synthetic_template(opener, base_url: str, csrf_token: str) -> None:
    template = get_resource(
        opener,
        base_url,
        "NPI Project Template",
        TEMPLATE_GLOBAL_ID,
    )
    if template.status == 404:
        template = create_resource(
            opener,
            base_url,
            "NPI Project Template",
            {
                "global_id": TEMPLATE_GLOBAL_ID,
                "template_code": TEMPLATE_CODE,
                "title": "Synthetic P4 runtime template",
                "enabled": 1,
            },
            csrf_token,
        )
    require(
        template.status in {200, 201},
        f"Synthetic Project Template returned HTTP {template.status}",
    )
    template_data = template.body.get("data", {})
    require(template_data.get("name") == TEMPLATE_GLOBAL_ID, "Template name is not its UUID")
    require(template_data.get("global_id") == TEMPLATE_GLOBAL_ID, "Template UUID drifted")
    require(template_data.get("template_code") == TEMPLATE_CODE, "Template code drifted")

    version = get_resource(
        opener,
        base_url,
        "NPI Project Template Version",
        TEMPLATE_VERSION_KEY,
    )
    if version.status == 404:
        version = create_resource(
            opener,
            base_url,
            "NPI Project Template Version",
            {
                "project_template": TEMPLATE_GLOBAL_ID,
                "template_version": TEMPLATE_VERSION,
                "title": "Synthetic P4 runtime template version",
                "publication_state": "published",
                "applicable_project_types": ["new_tool"],
                "reference_rules": [
                    {
                        "reference_type": "customer",
                        "required": 1,
                        "allow_multiple": 0,
                    }
                ],
                "gates": [
                    {"gate_key": "G0", "title": "Synthetic intake", "sequence": 1},
                    {"gate_key": "G1", "title": "Synthetic initiation", "sequence": 2},
                ],
            },
            csrf_token,
        )
    require(
        version.status in {200, 201},
        f"Synthetic Template Version returned HTTP {version.status}",
    )
    version_data = version.body.get("data", {})
    require(version_data.get("name") == TEMPLATE_VERSION_KEY, "Template version key drifted")
    require(version_data.get("publication_state") == "published", "Template is not published")
    require(version_data.get("optimistic_version") == 1, "Template optimistic version drifted")
    snapshot_hash = version_data.get("snapshot_hash")
    require(
        isinstance(snapshot_hash, str) and len(snapshot_hash) == 64,
        "Template snapshot hash is unavailable",
    )


def project_payload(owner: str) -> dict[str, object]:
    return {
        "tenantId": TENANT_ID,
        "businessCode": BUSINESS_CODE,
        "title": "Synthetic runtime project",
        "projectType": "new_tool",
        "ownerUserId": owner,
        "targetSop": "2026-12-31",
        "templateGlobalId": TEMPLATE_GLOBAL_ID,
        "templateVersion": TEMPLATE_VERSION,
        "expectedVersion": 1,
        "references": [
            {
                "type": "customer",
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": "RUNTIME-CUSTOMER",
            }
        ],
    }


def post_project(
    opener,
    base_url: str,
    payload: dict[str, object],
    *,
    csrf_token: str | None,
    idempotency_key: str,
    request_id: str | None = None,
) -> HttpResult:
    headers = {
        "Idempotency-Key": idempotency_key,
        "X-Request-ID": request_id or str(uuid4()),
        "X-Trace-ID": f"trace-{uuid4().hex}",
    }
    if csrf_token is not None:
        headers["X-Frappe-CSRF-Token"] = csrf_token
    return request(
        opener,
        base_url,
        "/api/npi/v1/projects",
        method="POST",
        payload=payload,
        request_headers=headers,
    )


def get_cockpit(opener, base_url: str, project_id: str) -> HttpResult:
    request_id = str(uuid4())
    result = request(
        opener,
        base_url,
        f"/api/npi/v1/projects/{project_id}/cockpit",
        request_headers={
            "X-Request-ID": request_id,
            "X-Trace-ID": f"trace-{uuid4().hex}",
        },
    )
    require(result.headers.get("X-Request-ID") == request_id, "Request ID was not echoed")
    return result


def validate_cockpit(result: HttpResult, *, administrator: bool) -> str:
    require(result.status in {200, 201}, f"Cockpit returned HTTP {result.status}")
    require(
        set(result.body) == {"project", "templateRef", "references", "gates", "permissions"},
        "Cockpit top-level keys drifted",
    )
    project = result.body["project"]
    require(project["businessCode"] == BUSINESS_CODE, "Project business code drifted")
    require(project["state"] == "draft" and project["version"] == 1, "Project state drifted")
    require(project["tenantId"] == TENANT_ID, "Project tenant drifted")
    require(project["source"] == {
        "sourceSystem": "NPI_ONE",
        "editableIn": "NPI_ONE",
        "syncState": "local",
    }, "Project source truth drifted")
    require(result.body["templateRef"]["globalId"] == TEMPLATE_GLOBAL_ID, "Template identity drifted")
    require(result.body["templateRef"]["version"] == TEMPLATE_VERSION, "Template version drifted")
    require(
        [(gate["key"], gate["sequence"], gate["state"]) for gate in result.body["gates"]]
        == [("G0", 1, "not_started"), ("G1", 2, "not_started")],
        "Gate shells are incomplete or unordered",
    )
    reference = result.body["references"][0]
    require("globalId" not in reference, "Absent reference globalId was serialized as null")
    require(reference["sourceSystem"] == "ERPNEXT", "Reference provenance drifted")
    permissions = result.body["permissions"]
    require(permissions["canView"] is True, "View permission drifted")
    require(
        permissions["canContribute"] is administrator
        and permissions["canAdminister"] is administrator,
        "Project permission projection drifted",
    )
    require(result.headers.get("Cache-Control") == "private, no-store", "Project caching is unsafe")
    return str(project["globalId"])


def actor_key_hash(actor: str, key: str) -> str:
    return hashlib.sha256(f"{actor.casefold()}\x1f{key}".encode()).hexdigest()


def verify_persistence(
    opener,
    base_url: str,
    project_id: str,
    owner: str,
) -> None:
    projects = list_resources(
        opener,
        base_url,
        "NPI Engineering Project",
        filters=[["global_id", "=", project_id]],
        fields=["global_id", "owner_user_id", "template_snapshot_hash"],
    )
    require(len(projects) == 1 and projects[0]["owner_user_id"] == owner, "Project persistence drifted")
    gates = list_resources(
        opener,
        base_url,
        "NPI Gate Shell",
        filters=[["project_global_id", "=", project_id]],
        fields=["global_id", "gate_key", "sequence", "state"],
    )
    require(len(gates) == 2, "Gate persistence is not atomic")
    records = list_resources(
        opener,
        base_url,
        "NPI Project Idempotency",
        filters=[["project_global_id", "=", project_id]],
        fields=["actor", "actor_key_hash", "payload_hash", "project_global_id"],
    )
    require(len(records) == 1, "Idempotency replay record count drifted")
    require("idempotency_key" not in records[0], "Raw idempotency key was persisted")
    reservations = list_resources(
        opener,
        base_url,
        "NPI Project Business Code",
        filters=[["project_global_id", "=", project_id]],
        fields=["tenant_id", "business_code", "project_global_id"],
    )
    require(len(reservations) == 1, "Business code reservation count drifted")
    audits = list_resources(
        opener,
        base_url,
        "NPI Audit Event",
        filters=[["global_id", "=", project_id], ["operation", "=", "project.create"]],
        fields=["event_id", "actor", "operation", "result", "trace_id"],
    )
    require(len(audits) == 1 and audits[0]["result"] == "created", "Project audit count drifted")


def verify_no_idempotency_record(opener, base_url: str, actor: str, key: str) -> None:
    rows = list_resources(
        opener,
        base_url,
        "NPI Project Idempotency",
        filters=[["actor_key_hash", "=", actor_key_hash(actor, key)]],
        fields=["actor_key_hash", "project_global_id"],
    )
    require(rows == [], "Rejected command retained an idempotency record")


def verify_generic_mutation_denied(
    opener,
    base_url: str,
    project_id: str,
    csrf_token: str,
) -> None:
    project_update = update_resource(
        opener,
        base_url,
        "NPI Engineering Project",
        project_id,
        {"lifecycle_state": "active", "optimistic_version": 2},
        csrf_token,
    )
    require(
        project_update.status == 403,
        f"Generic Project update returned HTTP {project_update.status}",
    )

    gates = list_resources(
        opener,
        base_url,
        "NPI Gate Shell",
        filters=[["project_global_id", "=", project_id]],
        fields=["global_id", "state", "optimistic_version"],
    )
    require(len(gates) == 2, "Gate shells were unavailable for mutation testing")
    gate_id = str(gates[0]["global_id"])
    gate_update = update_resource(
        opener,
        base_url,
        "NPI Gate Shell",
        gate_id,
        {"state": "not_started", "optimistic_version": 2},
        csrf_token,
    )
    require(
        gate_update.status == 403,
        f"Generic Gate update returned HTTP {gate_update.status}",
    )

    project = get_resource(opener, base_url, "NPI Engineering Project", project_id)
    require(project.status == 200, "Project disappeared after rejected mutation")
    project_data = project.body.get("data", {})
    require(
        project_data.get("lifecycle_state") == "draft"
        and project_data.get("optimistic_version") == 1,
        "Rejected generic Project mutation changed persisted state",
    )
    gate = get_resource(opener, base_url, "NPI Gate Shell", gate_id)
    require(gate.status == 200, "Gate disappeared after rejected mutation")
    gate_data = gate.body.get("data", {})
    require(
        gate_data.get("state") == "not_started"
        and gate_data.get("optimistic_version") == 1,
        "Rejected generic Gate mutation changed persisted state",
    )

    audits = list_resources(
        opener,
        base_url,
        "NPI Audit Event",
        filters=[["global_id", "=", project_id], ["operation", "=", "project.create"]],
        fields=["name", "result"],
    )
    require(len(audits) == 1, "Project audit was unavailable for mutation testing")
    audit_name = str(audits[0]["name"])
    audit_update = update_resource(
        opener,
        base_url,
        "NPI Audit Event",
        audit_name,
        {"result": "tampered"},
        csrf_token,
    )
    require(
        audit_update.status == 403,
        f"Generic Audit update returned HTTP {audit_update.status}",
    )
    audit = get_resource(opener, base_url, "NPI Audit Event", audit_name)
    require(audit.status == 200, "Audit disappeared after rejected mutation")
    require(
        audit.body.get("data", {}).get("result") == "created",
        "Rejected generic Audit mutation changed persisted history",
    )

    template_update = update_resource(
        opener,
        base_url,
        "NPI Project Template",
        TEMPLATE_GLOBAL_ID,
        {"template_code": "MUST-NOT-CHANGE"},
        csrf_token,
    )
    require(
        template_update.status in {403, 417},
        f"Template code update returned HTTP {template_update.status}",
    )
    template = get_resource(
        opener,
        base_url,
        "NPI Project Template",
        TEMPLATE_GLOBAL_ID,
    )
    require(template.status == 200, "Template disappeared after rejected mutation")
    require(
        template.body.get("data", {}).get("template_code") == TEMPLATE_CODE,
        "Rejected Template code mutation changed the version family",
    )


def verify_standalone_child_mutation_denied(
    opener,
    base_url: str,
    project_id: str,
    csrf_token: str,
) -> None:
    parent_specs = (
        {
            "doctype": "NPI Project Reference",
            "parent_doctype": "NPI Engineering Project",
            "parent_name": project_id,
            "parent_field": "references",
            "create": {
                "reference_type": "product",
                "source_system": "NPI_ONE",
                "source_object_id": "SYN-PRODUCT-STANDALONE",
            },
            "update": {"source_object_id": "MUST-NOT-CHANGE"},
        },
        {
            "doctype": "NPI Template Gate Definition",
            "parent_doctype": "NPI Project Template Version",
            "parent_name": TEMPLATE_VERSION_KEY,
            "parent_field": "gates",
            "create": {
                "gate_key": "G9",
                "title": "Standalone Gate must be rejected",
                "sequence": 99,
            },
            "update": {"title": "MUST-NOT-CHANGE"},
        },
        {
            "doctype": "NPI Template Reference Rule",
            "parent_doctype": "NPI Project Template Version",
            "parent_name": TEMPLATE_VERSION_KEY,
            "parent_field": "reference_rules",
            "create": {
                "reference_type": "product",
                "required": 0,
                "allow_multiple": 0,
            },
            "update": {"allow_multiple": 1},
        },
    )
    parent_snapshots: dict[tuple[str, str, str], list[object]] = {}
    for spec in parent_specs:
        parent = get_resource(
            opener,
            base_url,
            str(spec["parent_doctype"]),
            str(spec["parent_name"]),
        )
        require(
            parent.status == 200,
            f"{spec['parent_doctype']} was unavailable for child mutation testing",
        )
        rows = parent.body.get("data", {}).get(str(spec["parent_field"]))
        require(
            isinstance(rows, list) and rows,
            f"{spec['doctype']} had no retained child row",
        )
        key = (
            str(spec["parent_doctype"]),
            str(spec["parent_name"]),
            str(spec["parent_field"]),
        )
        parent_snapshots[key] = rows

        create_payload = {
            "parent": spec["parent_name"],
            "parenttype": spec["parent_doctype"],
            "parentfield": spec["parent_field"],
            **spec["create"],
        }
        create = create_resource(
            opener,
            base_url,
            str(spec["doctype"]),
            create_payload,
            csrf_token,
        )
        require(
            create.status in {403, 417},
            f"Standalone {spec['doctype']} create returned HTTP {create.status}",
        )

        child_name = str(rows[0].get("name"))
        require(child_name and child_name != "None", "Child row identity is unavailable")
        update = update_resource(
            opener,
            base_url,
            str(spec["doctype"]),
            child_name,
            dict(spec["update"]),
            csrf_token,
        )
        require(
            update.status in {403, 417},
            f"Standalone {spec['doctype']} update returned HTTP {update.status}",
        )
        delete = delete_resource(
            opener,
            base_url,
            str(spec["doctype"]),
            child_name,
            csrf_token,
        )
        require(
            delete.status in {403, 417},
            f"Standalone {spec['doctype']} deletion returned HTTP {delete.status}",
        )

    for (parent_doctype, parent_name, parent_field), snapshot in parent_snapshots.items():
        retained = get_resource(opener, base_url, parent_doctype, parent_name)
        require(retained.status == 200, f"{parent_doctype} disappeared after child attack")
        require(
            retained.body.get("data", {}).get(parent_field) == snapshot,
            f"Rejected standalone child mutation changed {parent_doctype}.{parent_field}",
        )


def verify_history_deletion_denied(
    opener,
    base_url: str,
    project_id: str,
    csrf_token: str,
) -> None:
    queries = (
        ("NPI Gate Shell", [["project_global_id", "=", project_id]], ["name"]),
        (
            "NPI Project Idempotency",
            [["project_global_id", "=", project_id]],
            ["name"],
        ),
        (
            "NPI Project Business Code",
            [["project_global_id", "=", project_id]],
            ["name"],
        ),
        (
            "NPI Audit Event",
            [["global_id", "=", project_id], ["operation", "=", "project.create"]],
            ["name"],
        ),
    )
    targets = [
        ("NPI Engineering Project", project_id),
        ("NPI Project Template Version", TEMPLATE_VERSION_KEY),
    ]
    for doctype, filters, fields in queries:
        rows = list_resources(
            opener,
            base_url,
            doctype,
            filters=filters,
            fields=fields,
        )
        expected_count = 2 if doctype == "NPI Gate Shell" else 1
        require(
            len(rows) == expected_count,
            f"{doctype} history target is unavailable",
        )
        targets.extend((doctype, str(row["name"])) for row in rows)

    for doctype, name in targets:
        rejected = delete_resource(
            opener,
            base_url,
            doctype,
            name,
            csrf_token,
        )
        require(
            rejected.status in {403, 417},
            f"{doctype} history deletion returned HTTP {rejected.status}",
        )
        retained = get_resource(opener, base_url, doctype, name)
        require(retained.status == 200, f"{doctype} history was physically deleted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--administrator-user", default="Administrator")
    parser.add_argument("--administrator-password", required=True)
    parser.add_argument(
        "--owner-user",
        default="npi-project-runtime-owner@example.invalid",
    )
    parser.add_argument(
        "--unrelated-user",
        default="npi-project-runtime-unrelated@example.invalid",
    )
    parser.add_argument("--fixture-password", default="DevOnly_Project_Runtime_2026!")
    arguments = parser.parse_args()
    base_url = arguments.base_url.rstrip("/")
    require(
        urllib.parse.urlparse(base_url).hostname in {"127.0.0.1", "localhost", "::1"},
        "Project runtime verification is restricted to a local Site",
    )
    require(arguments.administrator_user == "Administrator", "Local Administrator is required")
    users = (arguments.owner_user, arguments.unrelated_user)
    require(
        all(user.endswith("@example.invalid") for user in users),
        "Runtime Project users must use reserved example.invalid identities",
    )

    administrator = login(
        base_url,
        arguments.administrator_user,
        arguments.administrator_password,
    )
    administrator_csrf = bootstrap_csrf(
        administrator,
        base_url,
        arguments.administrator_user,
    )
    ensure_synthetic_template(administrator, base_url, administrator_csrf)

    for user in users:
        require(
            request(administrator, base_url, user_resource_path(user)).status == 404,
            f"Disposable Project user already exists: {user}",
        )
    created_users: list[str] = []
    try:
        for user in users:
            created = create_disposable_user(
                administrator,
                base_url,
                user,
                arguments.fixture_password,
                administrator_csrf,
            )
            validate_disposable_user(created, user)
            created_users.append(user)

        owner = login(base_url, arguments.owner_user, arguments.fixture_password)
        unrelated = login(base_url, arguments.unrelated_user, arguments.fixture_password)
        owner_csrf = bootstrap_csrf(owner, base_url, arguments.owner_user)
        bootstrap_csrf(unrelated, base_url, arguments.unrelated_user)

        payload = project_payload(arguments.owner_user)
        set_template_enabled(
            administrator,
            base_url,
            False,
            administrator_csrf,
        )
        try:
            disabled_template = post_project(
                administrator,
                base_url,
                payload,
                csrf_token=administrator_csrf,
                idempotency_key="p4-runtime-disabled-template-v1",
            )
            validate_problem(
                disabled_template,
                422,
                "PROJECT_TEMPLATE_UNAVAILABLE",
            )
            verify_no_idempotency_record(
                administrator,
                base_url,
                arguments.administrator_user,
                "p4-runtime-disabled-template-v1",
            )
        finally:
            set_template_enabled(
                administrator,
                base_url,
                True,
                administrator_csrf,
            )

        tenant_mismatch_payload = dict(payload)
        tenant_mismatch_payload["tenantId"] = "other-runtime-tenant"
        tenant_mismatch = post_project(
            administrator,
            base_url,
            tenant_mismatch_payload,
            csrf_token=administrator_csrf,
            idempotency_key="p4-runtime-tenant-mismatch-v1",
        )
        validate_problem(tenant_mismatch, 403, "PERMISSION_DENIED")
        verify_no_idempotency_record(
            administrator,
            base_url,
            arguments.administrator_user,
            "p4-runtime-tenant-mismatch-v1",
        )

        request_id = str(uuid4())
        created = post_project(
            administrator,
            base_url,
            payload,
            csrf_token=administrator_csrf,
            idempotency_key=IDEMPOTENCY_KEY,
            request_id=request_id,
        )
        project_id = validate_cockpit(created, administrator=True)
        require(created.status == 201, "Project command did not return HTTP 201")
        require(created.headers.get("X-Request-ID") == request_id, "Create request ID drifted")
        require(created.headers.get("Idempotency-Replayed") in {"true", "false"}, "Replay header is invalid")

        replay = post_project(
            administrator,
            base_url,
            payload,
            csrf_token=administrator_csrf,
            idempotency_key=IDEMPOTENCY_KEY,
        )
        require(replay.status == 201, "Idempotent replay did not return HTTP 201")
        require(replay.headers.get("Idempotency-Replayed") == "true", "Replay was not declared")
        require(validate_cockpit(replay, administrator=True) == project_id, "Replay identity drifted")

        changed = dict(payload)
        changed["title"] = "Changed payload must conflict"
        payload_conflict = post_project(
            administrator,
            base_url,
            changed,
            csrf_token=administrator_csrf,
            idempotency_key=IDEMPOTENCY_KEY,
        )
        validate_problem(payload_conflict, 409, "IDEMPOTENCY_KEY_CONFLICT")

        business_conflict = post_project(
            administrator,
            base_url,
            payload,
            csrf_token=administrator_csrf,
            idempotency_key=CONFLICT_KEY,
        )
        validate_problem(business_conflict, 409, "PROJECT_BUSINESS_CODE_CONFLICT")
        verify_no_idempotency_record(
            administrator,
            base_url,
            arguments.administrator_user,
            CONFLICT_KEY,
        )

        version_payload = dict(payload)
        version_payload["businessCode"] = "P4-RUNTIME-VERSION-CONFLICT"
        version_payload["expectedVersion"] = 999
        version_conflict = post_project(
            administrator,
            base_url,
            version_payload,
            csrf_token=administrator_csrf,
            idempotency_key=VERSION_KEY,
        )
        validate_problem(version_conflict, 409, "VERSION_CONFLICT")
        verify_no_idempotency_record(
            administrator,
            base_url,
            arguments.administrator_user,
            VERSION_KEY,
        )

        no_csrf = post_project(
            administrator,
            base_url,
            payload,
            csrf_token=None,
            idempotency_key="p4-runtime-csrf-check-v1",
        )
        validate_problem(no_csrf, 403, "CSRF_TOKEN_INVALID")
        require(bool(no_csrf.headers.get("X-Request-ID")), "CSRF error lost request ID")

        owner_create = post_project(
            owner,
            base_url,
            payload,
            csrf_token=owner_csrf,
            idempotency_key="p4-runtime-owner-denied-v1",
        )
        validate_problem(owner_create, 403, "PERMISSION_DENIED")

        owner_cockpit = get_cockpit(owner, base_url, project_id)
        require(validate_cockpit(owner_cockpit, administrator=False) == project_id, "Owner view drifted")
        administrator_cockpit = get_cockpit(administrator, base_url, project_id)
        validate_cockpit(administrator_cockpit, administrator=True)
        set_user_enabled(
            administrator,
            base_url,
            arguments.owner_user,
            False,
            administrator_csrf,
        )
        try:
            disabled_owner_replay = post_project(
                administrator,
                base_url,
                payload,
                csrf_token=administrator_csrf,
                idempotency_key=IDEMPOTENCY_KEY,
            )
            require(
                disabled_owner_replay.status == 201
                and disabled_owner_replay.headers.get("Idempotency-Replayed") == "true",
                "Disabled owner prevented a valid idempotent replay",
            )
            validate_cockpit(disabled_owner_replay, administrator=True)
        finally:
            set_user_enabled(
                administrator,
                base_url,
                arguments.owner_user,
                True,
                administrator_csrf,
            )
        verify_generic_mutation_denied(
            administrator,
            base_url,
            project_id,
            administrator_csrf,
        )
        verify_standalone_child_mutation_denied(
            administrator,
            base_url,
            project_id,
            administrator_csrf,
        )
        verify_history_deletion_denied(
            administrator,
            base_url,
            project_id,
            administrator_csrf,
        )

        unrelated_problem = get_cockpit(unrelated, base_url, project_id)
        absent_problem = get_cockpit(unrelated, base_url, str(uuid4()))
        validate_problem(unrelated_problem, 404, "PROJECT_UNAVAILABLE")
        validate_problem(absent_problem, 404, "PROJECT_UNAVAILABLE")
        for field in ("type", "title", "status", "code", "retryable"):
            require(
                unrelated_problem.body.get(field) == absent_problem.body.get(field),
                "IDOR-safe absent and unauthorized problems differ",
            )

        guest = get_cockpit(
            urllib.request.build_opener(),
            base_url,
            project_id,
        )
        validate_problem(guest, 401, "AUTHENTICATION_REQUIRED")
        invalid_id = get_cockpit(administrator, base_url, "not-a-uuid")
        validate_problem(invalid_id, 422, "VALIDATION_FAILED")

        verify_persistence(
            administrator,
            base_url,
            project_id,
            arguments.owner_user,
        )
    finally:
        cleanup = login(
            base_url,
            arguments.administrator_user,
            arguments.administrator_password,
        )
        cleanup_csrf = bootstrap_csrf(
            cleanup,
            base_url,
            arguments.administrator_user,
        )
        for user in reversed(created_users):
            delete_disposable_user(cleanup, base_url, user, cleanup_csrf)

    print(
        json.dumps(
            {
                "auditEvents": 1,
                "businessCodeConflict": 409,
                "disabledOwnerReplay": True,
                "disabledTemplate": 422,
                "gateShells": 2,
                "genericCrudDenied": True,
                "historyDeleteDenied": 7,
                "standaloneChildMutationsDenied": 9,
                "idor": 404,
                "idempotentReplay": True,
                "ownerReadOnly": True,
                "projectId": project_id,
                "templateGlobalId": TEMPLATE_GLOBAL_ID,
                "templateInstalledByMigration": False,
                "tenantMismatch": 403,
                "versionConflict": 409,
            },
            sort_keys=True,
        )
    )
    print("local Frappe Project runtime verification passed")


if __name__ == "__main__":
    main()
