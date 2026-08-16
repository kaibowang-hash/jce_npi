from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

import verify_document_runtime as document_runtime
import verify_tooling_acceptance_runtime as acceptance_runtime
import verify_tooling_manufacturing_runtime as manufacturing_runtime
import verify_tooling_runtime as tooling_runtime
from verify_frappe_runtime import (
    create_disposable_user,
    delete_disposable_user,
    login,
    require,
    secret_from_environment,
    validate_disposable_user,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import bootstrap_csrf


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
TENANT_ID = document_runtime.TENANT_ID
ACTOR_USER = "Administrator"
INTERNAL_USER = f"npi-projection-{FIXTURE_RUN_ID[:16]}-internal@example.invalid"
EXTERNAL_USER = f"npi-projection-{FIXTURE_RUN_ID[:16]}-external@example.invalid"
ABSENT_PROJECT_ID = "00000000-0000-4000-8000-000000000801"
KINDS = (
    "customer_master",
    "formal_item_master",
    "formal_quality_status",
    "project_cost",
    "supplier_master",
    "tool_asset_status",
    "tooling_procurement_cost",
)
FRESHNESS_POLICY_REF = f"p8-01-runtime-policy-{FIXTURE_RUN_ID[:12]}"
SYNTHETIC_RECEIVED_AT = datetime(2026, 8, 16, 8, 1, tzinfo=UTC)
MOCK_RECEIVED_AT = datetime(2026, 8, 16, 8, 5, tzinfo=UTC)
SANDBOX_MODIFIED_AT = datetime(2026, 8, 16, 8, 10, tzinfo=UTC)
SANDBOX_RECEIVED_AT = datetime(2026, 8, 16, 8, 11, tzinfo=UTC)


def deterministic_uuid(label: str) -> UUID:
    digest = hashlib.sha256(f"p8-01:{FIXTURE_RUN_ID}:{label}".encode()).hexdigest()
    return UUID(hex=digest[:32], version=4)


def sequence_uuid_factory(label: str):
    position = 0

    def factory() -> UUID:
        nonlocal position
        position += 1
        return deterministic_uuid(f"{label}:{position}")

    return factory


def projection_path(project_id: str, *, kind: str | None = None) -> str:
    path = f"/api/npi/v1/projects/{project_id}/erp-projections"
    if kind is not None:
        path = f"{path}?{urllib.parse.urlencode({'kind': kind})}"
    return path


def projection_request(
    opener,
    base_url: str,
    path: str,
    *,
    query_key: str,
):
    headers = document_runtime.query_headers(f"p801-{query_key}")
    result = document_runtime.request(
        opener,
        base_url,
        path,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P8-01 projection request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P8-01 projection response cache control drifted",
    )
    return result


def _assert_no_secret_surface(value: object) -> None:
    forbidden_keys = {
        "credential",
        "credentials",
        "password",
        "secret",
        "secretReference",
        "token",
        "endpoint",
        "baseUrl",
        "rawError",
    }
    if isinstance(value, Mapping):
        require(
            forbidden_keys.isdisjoint(value),
            "P8-01 projection response exposed adapter or credential truth",
        )
        for nested in value.values():
            _assert_no_secret_surface(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_secret_surface(nested)


def assert_collection(
    result,
    *,
    project_id: str,
    expected_kinds: tuple[str, ...] = KINDS,
) -> dict[str, Any]:
    require(result.status == 200, "P8-01 projection collection query failed")
    value = result.body
    require(
        isinstance(value, dict)
        and set(value)
        == {"projectGlobalId", "accessState", "reasonCode", "permissions", "items"}
        and value.get("projectGlobalId") == project_id
        and value.get("accessState") == "available"
        and value.get("reasonCode") is None
        and value.get("permissions")
        == {"view": True, "edit": False, "refresh": False},
        "P8-01 projection collection authority drifted",
    )
    items = value.get("items")
    require(
        isinstance(items, list)
        and len(items) == len(expected_kinds)
        and tuple(item.get("projectionKind") for item in items) == expected_kinds,
        "P8-01 projection collection kind closure drifted",
    )
    expected_fields = {
        "observationGlobalId",
        "projectionKind",
        "scopeKind",
        "scopeGlobalId",
        "availability",
        "freshness",
        "disposition",
        "sourceSystem",
        "sourceObjectType",
        "sourceObjectId",
        "sourceVersion",
        "sourceModifiedAt",
        "receivedAt",
        "payloadHash",
        "unavailableReasonCode",
        "values",
        "currentTruth",
        "editable",
    }
    for item in items:
        expected_version = (
            "sandbox-recovery-v2"
            if item.get("projectionKind") == "customer_master"
            else "sandbox-v1"
        )
        require(
            isinstance(item, dict)
            and set(item) == expected_fields
            and item.get("availability") == "available"
            and item.get("freshness") == "fresh"
            and item.get("disposition") == "applied_current"
            and item.get("sourceSystem") == "ERPNEXT"
            and item.get("sourceVersion") == expected_version,
            "P8-01 projection item current truth drifted",
        )
        require(
            item.get("editable") is False
            and item.get("unavailableReasonCode") is None
            and isinstance(item.get("values"), dict)
            and isinstance(item.get("currentTruth"), dict)
            and item["currentTruth"].get("values") == item.get("values"),
            "P8-01 projection item read-only truth drifted",
        )
    _assert_no_secret_surface(value)
    return value


def assert_tooling_consumers(
    administrator,
    base_url: str,
    *,
    project_id: str,
    master_id: str,
    tooling_set_id: str,
) -> None:
    manufacturing = manufacturing_runtime.tooling_request(
        administrator,
        base_url,
        manufacturing_runtime.manufacturing_path(project_id, master_id),
        query_key="cost",
    )
    cost = manufacturing.body.get("erpProjection")
    require(
        manufacturing.status == 200
        and isinstance(cost, dict)
        and cost.get("state") == "available"
        and cost.get("sourceSystem") == "ERPNEXT"
        and cost.get("editableIn") == "ERPNEXT"
        and cost.get("toolingMasterGlobalId") == master_id
        and cost.get("targetVersion") == "sandbox-v1"
        and len(cost.get("rows", [])) == 1
        and cost["rows"][0].get("amount") == "1200.50",
        "P8-01 Tooling cost consumer did not use confirmed projection truth",
    )
    acceptance = acceptance_runtime.tooling_request(
        administrator,
        base_url,
        acceptance_runtime.acceptance_path(project_id, master_id),
        query_key="asset",
    )
    asset = acceptance.body.get("assetProjection")
    require(
        acceptance.status == 200
        and isinstance(asset, dict)
        and asset.get("state") == "available"
        and asset.get("sourceSystem") == "ERPNEXT"
        and asset.get("editableIn") == "ERPNEXT"
        and asset.get("toolingSetGlobalId") == tooling_set_id
        and asset.get("targetVersion") == "sandbox-v1"
        and asset.get("mappingCardinality") == "zero_or_one_per_physical_set",
        "P8-01 Tool Asset consumer did not use confirmed projection truth",
    )
    _assert_no_secret_surface(cost)
    _assert_no_secret_surface(asset)


def retained_context(administrator, base_url: str) -> dict[str, object]:
    project_id, _version = document_runtime.fixture_project(administrator, base_url)
    cockpit = tooling_runtime.tooling_request(
        administrator,
        base_url,
        f"/api/npi/v1/projects/{project_id}/cockpit",
        query_key="p801-project-reference",
    )
    references = cockpit.body.get("references")
    require(
        cockpit.status == 200 and isinstance(references, list),
        "P8-01 retained Project references are unavailable",
    )
    customer_references = [
        value
        for value in references
        if isinstance(value, dict) and value.get("type") == "customer"
    ]
    require(
        len(customer_references) == 1,
        "P8-01 retained Project customer reference cardinality drifted",
    )
    customer_reference = customer_references[0]
    require(
        customer_reference.get("sourceSystem") in {"NPI_ONE", "ERPNEXT"}
        and isinstance(customer_reference.get("sourceObjectId"), str)
        and bool(customer_reference["sourceObjectId"]),
        "P8-01 retained Project customer reference drifted",
    )
    workspace = tooling_runtime.tooling_request(
        administrator,
        base_url,
        tooling_runtime.tooling_path(project_id),
        query_key="p801-retained-context",
    )
    require(
        workspace.status == 200
        and isinstance(workspace.body.get("masters"), list)
        and isinstance(workspace.body.get("parts"), list)
        and isinstance(workspace.body.get("applicability"), list),
        "P8-01 retained Tooling workspace is unavailable",
    )
    masters = [
        value
        for value in workspace.body["masters"]
        if isinstance(value, dict)
        and value.get("title") == "Synthetic shared front housing tool"
        and value.get("originatingProjectGlobalId") == project_id
    ]
    require(
        len(masters) == 1,
        "P8-01 retained Tooling Master cardinality drifted",
    )
    master_id = str(masters[0].get("globalId"))
    require(
        str(UUID(master_id)) == master_id,
        "P8-01 retained Tooling Master identity drifted",
    )
    linked_part_ids = {
        str(value["part"]["partGlobalId"])
        for value in workspace.body["applicability"]
        if isinstance(value, dict)
        and value.get("projectGlobalId") == project_id
        and value.get("toolingMasterGlobalId") == master_id
        and isinstance(value.get("part"), dict)
        and isinstance(value["part"].get("partGlobalId"), str)
    }
    require(
        linked_part_ids,
        "P8-01 retained Tooling applicability is unavailable",
    )
    parts = [
        value
        for value in workspace.body["parts"]
        if isinstance(value, dict)
        and value.get("globalId") in linked_part_ids
        and value.get("title") == "Synthetic front housing revised"
        and isinstance(value.get("currentRevision"), dict)
        and value["currentRevision"].get("partGlobalId") == value.get("globalId")
        and value["currentRevision"].get("revisionNumber") == 2
        and value["currentRevision"].get("revisionLabel") == "B"
    ]
    require(
        len(parts) == 1,
        "P8-01 retained engineering Part cardinality drifted",
    )
    part_id = str(parts[0].get("globalId"))
    require(
        str(UUID(part_id)) == part_id,
        "P8-01 retained engineering Part identity drifted",
    )
    sets = tooling_runtime.tooling_request(
        administrator,
        base_url,
        tooling_runtime.tooling_set_path(project_id, master_id),
        query_key="sets",
    )
    require(
        sets.status == 200 and isinstance(sets.body.get("items"), list),
        "P8-01 retained Tooling Sets are unavailable",
    )
    tooling_sets = [
        value
        for value in sets.body["items"]
        if isinstance(value, dict)
        and value.get("physicalSerial") == "P6-02-PHYSICAL-001"
        and value.get("toolingMasterGlobalId") == master_id
    ]
    require(
        len(tooling_sets) == 1,
        "P8-01 retained physical Tooling Set cardinality drifted",
    )
    tooling_set_id = str(tooling_sets[0].get("globalId"))
    require(
        str(UUID(tooling_set_id)) == tooling_set_id,
        "P8-01 retained physical Tooling Set identity drifted",
    )
    return {
        "project_id": project_id,
        "master_id": master_id,
        "part_id": part_id,
        "tooling_set_id": tooling_set_id,
        "model_reference": {
            "sourceSystem": str(customer_reference["sourceSystem"]),
            "sourceObjectId": str(customer_reference["sourceObjectId"]),
        },
    }


def run_fresh(
    administrator,
    base_url: str,
    administrator_csrf: str,
    fixture_password: str,
) -> dict[str, object]:
    context = retained_context(administrator, base_url)
    seeded = run_bench_fixture(
        "seed_projection_truth",
        {"fixture_run_id": FIXTURE_RUN_ID, **context},
    )
    require(
        seeded.get("headCount") == 7
        and seeded.get("observationCount") == 25
        and seeded.get("auditCount") == 25
        and seeded.get("replayCount") == 7
        and seeded.get("consumerClosure") is True,
        "P8-01 controlled projection persistence proof drifted",
    )
    project_id = str(context["project_id"])
    master_id = str(context["master_id"])
    tooling_set_id = str(context["tooling_set_id"])
    collection = assert_collection(
        projection_request(
            administrator,
            base_url,
            projection_path(project_id),
            query_key="fresh-collection",
        ),
        project_id=project_id,
    )
    for kind in KINDS:
        assert_collection(
            projection_request(
                administrator,
                base_url,
                projection_path(project_id, kind=kind),
                query_key=f"kind-{kind}",
            ),
            project_id=project_id,
            expected_kinds=(kind,),
        )
    validate_problem(
        projection_request(
            administrator,
            base_url,
            projection_path(project_id, kind="unsupported_kind"),
            query_key="invalid-kind",
        ),
        422,
        "VALIDATION_FAILED",
    )
    validate_problem(
        projection_request(
            administrator,
            base_url,
            f"{projection_path(project_id)}?sourceObjectId=forbidden",
            query_key="unexpected-query",
        ),
        422,
        "VALIDATION_FAILED",
    )
    guest = urllib.request.build_opener()
    validate_problem(
        projection_request(
            guest,
            base_url,
            projection_path(project_id),
            query_key="guest",
        ),
        401,
        "AUTHENTICATION_REQUIRED",
    )

    document_runtime.create_internal_fixture_user(
        administrator,
        base_url,
        INTERNAL_USER,
        fixture_password,
        administrator_csrf,
    )
    external_created = False
    try:
        internal = login(base_url, INTERNAL_USER, fixture_password)
        for scoped_project, key in (
            (project_id, "internal-existing"),
            (ABSENT_PROJECT_ID, "internal-absent"),
        ):
            validate_problem(
                projection_request(
                    internal,
                    base_url,
                    projection_path(scoped_project),
                    query_key=key,
                ),
                404,
                "PROJECT_UNAVAILABLE",
            )
        created = create_disposable_user(
            administrator,
            base_url,
            EXTERNAL_USER,
            fixture_password,
            administrator_csrf,
        )
        validate_disposable_user(created, EXTERNAL_USER)
        external_created = True
        external = login(base_url, EXTERNAL_USER, fixture_password)
        redacted = projection_request(
            external,
            base_url,
            projection_path(project_id),
            query_key="external-redacted",
        )
        require(
            redacted.status == 200
            and redacted.body
            == {
                "projectGlobalId": project_id,
                "accessState": "redacted",
                "reasonCode": "projection_access_redacted",
                "permissions": {"view": False, "edit": False, "refresh": False},
                "items": [],
            },
            "P8-01 external projection response was not exactly redacted",
        )
    finally:
        if external_created:
            delete_disposable_user(
                administrator,
                base_url,
                EXTERNAL_USER,
                administrator_csrf,
            )
        delete_disposable_user(
            administrator,
            base_url,
            INTERNAL_USER,
            administrator_csrf,
        )
    assert_tooling_consumers(
        administrator,
        base_url,
        project_id=project_id,
        master_id=master_id,
        tooling_set_id=tooling_set_id,
    )
    return {
        "accessClosure": True,
        "consumerClosure": True,
        "crossProcessReplayReady": True,
        "fixtureRunId": FIXTURE_RUN_ID,
        "headCount": 7,
        "kindCount": len(collection["items"]),
        "observationCount": 25,
        "projectGlobalId": project_id,
    }


def run_replay_only(
    administrator,
    base_url: str,
) -> dict[str, object]:
    context = retained_context(administrator, base_url)
    replayed = run_bench_fixture(
        "replay_projection_truth",
        {"fixture_run_id": FIXTURE_RUN_ID, **context},
    )
    require(
        replayed.get("crossProcessReplay") is True
        and replayed.get("replayCount") == 7
        and replayed.get("headCount") == 7
        and replayed.get("observationCount") == 25,
        "P8-01 cross-process projection replay drifted",
    )
    project_id = str(context["project_id"])
    assert_collection(
        projection_request(
            administrator,
            base_url,
            projection_path(project_id),
            query_key="replay-collection",
        ),
        project_id=project_id,
    )
    assert_tooling_consumers(
        administrator,
        base_url,
        project_id=project_id,
        master_id=str(context["master_id"]),
        tooling_set_id=str(context["tooling_set_id"]),
    )
    return {
        "consumerClosure": True,
        "crossProcessReplay": True,
        "headCount": 7,
        "observationCount": 25,
        "projectGlobalId": project_id,
    }


def route_disable_probe(
    administrator,
    base_url: str,
    *,
    expected_mode: str,
) -> dict[str, object]:
    project_id = str(retained_context(administrator, base_url)["project_id"])
    result = projection_request(
        administrator,
        base_url,
        projection_path(project_id),
        query_key=f"route-{expected_mode}",
    )
    if expected_mode == "disabled":
        validate_problem(result, 503, "ERP_PROJECTION_ROUTES_DISABLED")
    else:
        assert_collection(result, project_id=project_id)
    return {"projectGlobalId": project_id, "routeMode": expected_mode}


def projection_values(kind, *, master_id: str, tooling_set_id: str) -> dict[str, object]:
    from npi_integration.projections.domain import ProjectionKind

    if kind is ProjectionKind.CUSTOMER_MASTER:
        return {
            "code": "CUSTOMER-RUNTIME-001",
            "displayName": "Controlled Runtime Customer",
            "enabled": True,
            "statusCode": "enabled",
        }
    if kind is ProjectionKind.SUPPLIER_MASTER:
        return {
            "code": "SUPPLIER-RUNTIME-001",
            "displayName": "Controlled Runtime Supplier",
            "enabled": True,
            "statusCode": "enabled",
        }
    if kind is ProjectionKind.FORMAL_ITEM_MASTER:
        return {
            "itemCode": "ITEM-RUNTIME-001",
            "stockUom": "PCS",
            "enabled": True,
            "statusCode": "enabled",
        }
    if kind is ProjectionKind.TOOLING_PROCUREMENT_COST:
        return {
            "toolingMasterGlobalId": master_id,
            "supplier": {
                "sourceObjectId": "SUPPLIER-RUNTIME-001",
                "targetVersion": "sandbox-supplier-v1",
                "supplierCode": "SUPPLIER-RUNTIME-001",
                "supplierName": "Controlled Runtime Supplier",
            },
            "rows": [
                {
                    "toolingMasterGlobalId": master_id,
                    "sourceRowId": "COST-ROW-RUNTIME-001",
                    "sourceRowVersion": "sandbox-cost-row-v1",
                    "supplierSourceObjectId": "SUPPLIER-RUNTIME-001",
                    "purchaseOrderSourceId": "PO-RUNTIME-001",
                    "purchaseReceiptSourceId": "PR-RUNTIME-001",
                    "purchaseInvoiceSourceId": "PI-RUNTIME-001",
                    "actualCostSourceId": "ACTUAL-COST-RUNTIME-001",
                    "costTypeCode": "tool_build",
                    "postingDate": "2026-08-15",
                    "currency": "CNY",
                    "amount": "1200.50",
                }
            ],
        }
    if kind is ProjectionKind.PROJECT_COST:
        return {
            "rows": [
                {
                    "rowKind": "actual_cost",
                    "sourceRowId": "PROJECT-COST-RUNTIME-001",
                    "sourceRowVersion": "sandbox-project-cost-v1",
                    "postingDate": "2026-08-15",
                    "currency": "CNY",
                    "amount": "88.25",
                    "hours": None,
                },
                {
                    "rowKind": "labor_hours",
                    "sourceRowId": "PROJECT-LABOR-RUNTIME-001",
                    "sourceRowVersion": "sandbox-project-labor-v1",
                    "postingDate": "2026-08-15",
                    "currency": None,
                    "amount": None,
                    "hours": "7.5",
                },
            ]
        }
    if kind is ProjectionKind.FORMAL_QUALITY_STATUS:
        return {
            "recordKind": "quality_inspection",
            "statusCode": "submitted",
            "resultCode": "accepted",
            "observedAt": "2026-08-16T08:10:00Z",
        }
    if kind is ProjectionKind.TOOL_ASSET_STATUS:
        return {
            "toolingSetGlobalId": tooling_set_id,
            "mappingVersion": 7,
            "formalAssetId": "ASSET-RUNTIME-001",
            "targetVersion": "sandbox-asset-v1",
            "assetState": "active",
            "currentLocation": "Controlled Runtime Tool Room",
            "shotCount": 100,
            "expectedLifeShots": 100000,
            "maintenanceDue": "2026-12-31",
            "movements": [],
            "repairs": [],
            "spares": [],
        }
    raise AssertionError(kind)


def projection_targets(
    *,
    project_id: str,
    master_id: str,
    part_id: str,
    tooling_set_id: str,
    model_reference: Mapping[str, object],
):
    from npi_integration.projections.domain import (
        ProjectionContext,
        ProjectionKind,
        ProjectionRefreshTarget,
        ProjectionScopeKind,
    )

    project_uuid = UUID(project_id)
    customer_source = (
        str(model_reference["sourceObjectId"])
        if model_reference.get("sourceSystem") == "ERPNEXT"
        else "CUSTOMER-RUNTIME-001"
    )
    identities = {
        ProjectionKind.CUSTOMER_MASTER: (
            ProjectionScopeKind.PROJECT,
            project_id,
            customer_source,
        ),
        ProjectionKind.SUPPLIER_MASTER: (
            ProjectionScopeKind.TOOLING_MASTER,
            master_id,
            "SUPPLIER-RUNTIME-001",
        ),
        ProjectionKind.FORMAL_ITEM_MASTER: (
            ProjectionScopeKind.ENGINEERING_ITEM,
            part_id,
            "ITEM-RUNTIME-001",
        ),
        ProjectionKind.TOOLING_PROCUREMENT_COST: (
            ProjectionScopeKind.TOOLING_MASTER,
            master_id,
            "TOOLING-COST-RUNTIME-001",
        ),
        ProjectionKind.PROJECT_COST: (
            ProjectionScopeKind.PROJECT,
            project_id,
            "PROJECT-COST-RUNTIME-001",
        ),
        ProjectionKind.FORMAL_QUALITY_STATUS: (
            ProjectionScopeKind.PROJECT,
            project_id,
            "QUALITY-RUNTIME-001",
        ),
        ProjectionKind.TOOL_ASSET_STATUS: (
            ProjectionScopeKind.TOOLING_SET,
            tooling_set_id,
            "ASSET-RUNTIME-001",
        ),
    }
    return tuple(
        ProjectionRefreshTarget(
            context=ProjectionContext(
                tenant_id=TENANT_ID,
                project_global_id=project_uuid,
                scope_kind=identities[kind][0],
                scope_global_id=UUID(identities[kind][1]),
            ),
            kind=kind,
            source_object_id=identities[kind][2],
        )
        for kind in ProjectionKind
    )


def projection_result(
    target,
    *,
    availability,
    mode,
    version: str | None,
    modified_at: datetime | None,
    master_id: str,
    tooling_set_id: str,
    environment: str,
    unavailable_reason: str | None = None,
):
    from npi_integration.projections.domain import ProjectionReaderResult

    return ProjectionReaderResult(
        kind=target.kind,
        adapter_mode=mode,
        source_environment=environment,
        source_object_id=target.source_object_id,
        source_version=version,
        source_modified_at=modified_at,
        availability=availability,
        values=(
            None
            if unavailable_reason is not None
            else projection_values(
                target.kind,
                master_id=master_id,
                tooling_set_id=tooling_set_id,
            )
        ),
        unavailable_reason_code=unavailable_reason,
    )


class ControlledSandboxReader:
    def __init__(self, results: Mapping[object, object]) -> None:
        self.results = dict(results)

    def _read(self, target):
        return self.results[target.kind]

    read_customer_master = _read
    read_supplier_master = _read
    read_formal_item_master = _read
    read_tooling_procurement_cost = _read
    read_project_cost = _read
    read_formal_quality_status = _read
    read_tool_asset_status = _read


def projection_repository():
    import frappe

    from npi_core.foundation.security import Principal
    from npi_integration.projections.domain import ProjectionKind
    from npi_integration.projections.frappe_repository import FrappeProjectionRepository

    principal = Principal(
        user_id=ACTOR_USER,
        roles=frozenset(frappe.get_roles(ACTOR_USER)),
        tenant_id=TENANT_ID,
        is_external=False,
    )
    require("System Manager" in principal.roles, "P8-01 runtime actor authority drifted")
    return FrappeProjectionRepository(
        principal=principal,
        request_id=str(deterministic_uuid("repository-request")),
        trace_id=f"trace-p801-runtime-{FIXTURE_RUN_ID[:12]}",
        freshness_policies={
            kind: (FRESHNESS_POLICY_REF, 86400) for kind in ProjectionKind
        },
    )


def sandbox_registry(targets, *, master_id: str, tooling_set_id: str):
    from npi_integration.projections.config import ProjectionAdapterConfiguration
    from npi_integration.projections.domain import (
        AdapterMode,
        ProjectionAvailability,
        ProjectionKind,
    )
    from npi_integration.projections.readers import ProjectionReaderRegistry

    results = {
        target.kind: projection_result(
            target,
            availability=ProjectionAvailability.AVAILABLE,
            mode=AdapterMode.SANDBOX,
            version="sandbox-v1",
            modified_at=SANDBOX_MODIFIED_AT,
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="sandbox",
        )
        for target in targets
    }
    configuration = ProjectionAdapterConfiguration(
        mode=AdapterMode.SANDBOX,
        enabled=True,
        base_url="https://erp.sandbox.example.test",
        allowed_hostnames=("erp.sandbox.example.test",),
        allowed_operations=tuple(ProjectionKind),
        secret_reference="secrets/p8-runtime-sandbox-read",
        environment_code="sandbox",
        non_production_attested=True,
        follow_redirects=False,
    )
    return ProjectionReaderRegistry(
        configuration=configuration,
        reader=ControlledSandboxReader(results),
    )


def _validate_fixture_context(
    *,
    fixture_run_id: str,
    project_id: str,
    master_id: str,
    part_id: str,
    tooling_set_id: str,
) -> None:
    import frappe

    document_runtime._validated_runtime_site()
    require(fixture_run_id == FIXTURE_RUN_ID, "P8-01 fixture namespace drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    master = frappe.get_doc("NPI Tooling Master", master_id)
    part = frappe.get_doc("NPI Engineering Part", part_id)
    tooling_set = frappe.get_doc("NPI Tooling Set", tooling_set_id)
    require(
        str(project.global_id) == project_id
        and str(project.tenant_id) == TENANT_ID
        and str(master.originating_project_global_id) == project_id
        and str(master.tenant_id) == TENANT_ID
        and str(part.originating_project_global_id) == project_id
        and str(part.tenant_id) == TENANT_ID
        and str(tooling_set.project_global_id) == project_id
        and str(tooling_set.tooling_master_global_id) == master_id
        and str(tooling_set.tenant_id) == TENANT_ID,
        "P8-01 retained Project projection scope drifted",
    )


def _structural_context(project_id: str) -> dict[str, object]:
    import frappe

    head_fields = [
        "global_id",
        "projection_kind",
        "scope_kind",
        "scope_global_id",
        "availability",
        "freshness",
        "optimistic_version",
        "head_hash",
        "current_observation",
        "last_refresh_observation",
    ]
    observation_fields = [
        "global_id",
        "event_id",
        "projection_kind",
        "availability",
        "freshness",
        "disposition",
        "payload_hash",
        "observation_hash",
    ]
    heads = [
        dict(row)
        for row in frappe.get_all(
            "NPI ERP Projection Head",
            filters={"project_global_id": project_id},
            fields=head_fields,
            order_by="projection_kind asc, global_id asc",
            limit_page_length=20,
        )
    ]
    observations = [
        dict(row)
        for row in frappe.get_all(
            "NPI ERP Projection Observation",
            filters={"project_global_id": project_id},
            fields=observation_fields,
            order_by="created_at asc, global_id asc",
            limit_page_length=100,
        )
    ]
    audit_count = frappe.db.count(
        "NPI Audit Event", {"operation": "erp_projection.observe"}
    )
    protected_counts = {
        "inbox": frappe.db.count("NPI Inbox Message"),
        "outbox": frappe.db.count("NPI Outbox Message"),
    }
    canonical = json.dumps(
        {
            "heads": heads,
            "observations": observations,
            "auditCount": audit_count,
            "protectedCounts": protected_counts,
        },
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "auditCount": audit_count,
        "digest": hashlib.sha256(canonical.encode()).hexdigest(),
        "headCount": len(heads),
        "heads": heads,
        "observationCount": len(observations),
        "observations": observations,
        "protectedCounts": protected_counts,
    }


def _assert_consumers(project_id: str, master_id: str, tooling_set_id: str) -> None:
    from npi_integration.projections.frappe_repository import (
        FrappeProjectionConsumerReader,
    )

    reader = FrappeProjectionConsumerReader()
    cost = reader.read_tooling_procurement_cost(
        project_global_id=UUID(project_id),
        tooling_master_global_id=UUID(master_id),
    )
    asset = reader.read_tool_asset_status(
        project_global_id=UUID(project_id),
        tooling_master_global_id=UUID(master_id),
    )
    require(
        isinstance(cost, dict)
        and cost.get("toolingMasterGlobalId") == master_id
        and cost.get("targetVersion") == "sandbox-v1"
        and len(cost.get("rows", [])) == 1
        and cost["rows"][0].get("amount") == "1200.50",
        "P8-01 direct Tooling cost reader closure drifted",
    )
    require(
        isinstance(asset, dict)
        and asset.get("toolingSetGlobalId") == tooling_set_id
        and asset.get("targetVersion") == "sandbox-v1"
        and asset.get("state") == "available",
        "P8-01 direct Tool Asset reader closure drifted",
    )


def seed_projection_truth(
    fixture_run_id: str,
    project_id: str,
    master_id: str,
    part_id: str,
    tooling_set_id: str,
    model_reference: Mapping[str, object],
) -> dict[str, object]:
    import frappe

    from npi_integration.projections.config import ProjectionAdapterConfiguration
    from npi_integration.projections.domain import (
        AdapterMode,
        ApplicationDisposition,
        ProjectionAvailability,
    )
    from npi_integration.projections.readers import (
        ProjectionReaderRegistry,
        SyntheticProjectionReader,
    )
    from npi_integration.projections.worker import refresh_project_projections

    _validate_fixture_context(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        master_id=master_id,
        part_id=part_id,
        tooling_set_id=tooling_set_id,
    )
    frappe.set_user(ACTOR_USER)
    repository = projection_repository()
    initial = _structural_context(project_id)
    require(
        initial["headCount"] == 0
        and initial["observationCount"] == 0
        and initial["auditCount"] == 0,
        "P8-01 fresh runtime started with retained projection truth",
    )
    protected_before = dict(initial["protectedCounts"])
    targets = projection_targets(
        project_id=project_id,
        master_id=master_id,
        part_id=part_id,
        tooling_set_id=tooling_set_id,
        model_reference=model_reference,
    )
    synthetic_results = {
        target.kind: projection_result(
            target,
            availability=ProjectionAvailability.SYNTHETIC,
            mode=AdapterMode.SYNTHETIC,
            version="synthetic-v1",
            modified_at=SYNTHETIC_RECEIVED_AT - timedelta(minutes=1),
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="disposable-test",
        )
        for target in targets
    }
    synthetic_registry = ProjectionReaderRegistry(
        configuration=ProjectionAdapterConfiguration(
            mode=AdapterMode.SYNTHETIC,
            enabled=False,
            environment_code="disposable-test",
            synthetic_test_only=True,
        ),
        reader=SyntheticProjectionReader(synthetic_results),
    )
    correlation_id = deterministic_uuid("synthetic-correlation")
    synthetic_outcomes = tuple(
        repository.apply_observation(
            project_global_id=UUID(project_id),
            target=target,
            result=synthetic_registry.read(target),
            event_id=deterministic_uuid(f"synthetic-event:{target.kind.value}"),
            received_at=SYNTHETIC_RECEIVED_AT,
            correlation_id=correlation_id,
        )
        for target in targets
    )
    require(
        all(
            outcome.disposition is ApplicationDisposition.SYNTHETIC_RETAINED
            for outcome in synthetic_outcomes
        ),
        "P8-01 synthetic proof became authoritative",
    )
    mock_batch = refresh_project_projections(
        repository=repository,
        registry=ProjectionReaderRegistry(
            configuration=ProjectionAdapterConfiguration()
        ),
        project_global_id=UUID(project_id),
        clock=lambda: MOCK_RECEIVED_AT,
        uuid_factory=sequence_uuid_factory("mock-refresh"),
    )
    require(
        len(mock_batch.outcomes) == 7
        and all(
            outcome.disposition is ApplicationDisposition.UNAVAILABLE_CURRENT
            for outcome in mock_batch.outcomes
        ),
        "P8-01 default Mock refresh did not remain unavailable",
    )
    sandbox = sandbox_registry(
        targets,
        master_id=master_id,
        tooling_set_id=tooling_set_id,
    )
    sandbox_batch = refresh_project_projections(
        repository=repository,
        registry=sandbox,
        project_global_id=UUID(project_id),
        clock=lambda: SANDBOX_RECEIVED_AT,
        uuid_factory=sequence_uuid_factory("sandbox-refresh"),
    )
    require(
        len(sandbox_batch.outcomes) == 7
        and all(
            outcome.disposition is ApplicationDisposition.APPLIED_CURRENT
            for outcome in sandbox_batch.outcomes
        ),
        "P8-01 controlled sandbox refresh did not become confirmed truth",
    )
    same_process_replay = refresh_project_projections(
        repository=repository,
        registry=sandbox,
        project_global_id=UUID(project_id),
        clock=lambda: SANDBOX_RECEIVED_AT,
        uuid_factory=sequence_uuid_factory("sandbox-refresh"),
    )
    require(
        len(same_process_replay.outcomes) == 7
        and all(outcome.replayed for outcome in same_process_replay.outcomes),
        "P8-01 same-process exact replay was not idempotent",
    )
    customer = next(
        target for target in targets if target.kind.value == "customer_master"
    )
    reorder = repository.apply_observation(
        project_global_id=UUID(project_id),
        target=customer,
        result=projection_result(
            customer,
            availability=ProjectionAvailability.AVAILABLE,
            mode=AdapterMode.SANDBOX,
            version="sandbox-reordered-v0",
            modified_at=SANDBOX_MODIFIED_AT - timedelta(minutes=1),
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="sandbox",
        ),
        event_id=deterministic_uuid("customer-reordered-event"),
        received_at=SANDBOX_RECEIVED_AT + timedelta(minutes=1),
        correlation_id=deterministic_uuid("customer-reordered-correlation"),
    )
    require(
        reorder.disposition is ApplicationDisposition.SUPERSEDED,
        "P8-01 older observation overwrote current truth",
    )
    conflict_event = deterministic_uuid("customer-conflict-event")
    unavailable = repository.apply_observation(
        project_global_id=UUID(project_id),
        target=customer,
        result=projection_result(
            customer,
            availability=ProjectionAvailability.UNAVAILABLE,
            mode=AdapterMode.MOCK,
            version=None,
            modified_at=None,
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="mock",
            unavailable_reason="controlled_transport_unavailable",
        ),
        event_id=conflict_event,
        received_at=SANDBOX_RECEIVED_AT + timedelta(minutes=2),
        correlation_id=deterministic_uuid("customer-unavailable-correlation"),
    )
    require(
        unavailable.disposition is ApplicationDisposition.UNAVAILABLE_CURRENT,
        "P8-01 unavailable observation truth drifted",
    )
    conflicted = repository.apply_observation(
        project_global_id=UUID(project_id),
        target=customer,
        result=projection_result(
            customer,
            availability=ProjectionAvailability.AVAILABLE,
            mode=AdapterMode.SANDBOX,
            version="sandbox-conflict-v2",
            modified_at=SANDBOX_MODIFIED_AT + timedelta(minutes=2),
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="sandbox",
        ),
        event_id=conflict_event,
        received_at=SANDBOX_RECEIVED_AT + timedelta(minutes=3),
        correlation_id=deterministic_uuid("customer-conflict-correlation"),
    )
    require(
        conflicted.disposition is ApplicationDisposition.CONFLICTED,
        "P8-01 conflicting event was not held unavailable",
    )
    recovery = repository.apply_observation(
        project_global_id=UUID(project_id),
        target=customer,
        result=projection_result(
            customer,
            availability=ProjectionAvailability.AVAILABLE,
            mode=AdapterMode.SANDBOX,
            version="sandbox-recovery-v2",
            modified_at=SANDBOX_MODIFIED_AT + timedelta(minutes=4),
            master_id=master_id,
            tooling_set_id=tooling_set_id,
            environment="sandbox",
        ),
        event_id=deterministic_uuid("customer-recovery-event"),
        received_at=SANDBOX_RECEIVED_AT + timedelta(minutes=5),
        correlation_id=deterministic_uuid("customer-recovery-correlation"),
    )
    require(
        recovery.disposition is ApplicationDisposition.APPLIED_CURRENT,
        "P8-01 newer confirmed truth did not recover the held stream",
    )
    final = _structural_context(project_id)
    dispositions = Counter(
        row["disposition"] for row in final["observations"]
    )
    versions = {
        row["projection_kind"]: int(row["optimistic_version"])
        for row in final["heads"]
    }
    require(
        final["headCount"] == 7
        and final["observationCount"] == 25
        and final["auditCount"] == 25
        and final["protectedCounts"] == protected_before
        and dispositions
        == Counter(
            {
                "synthetic_retained": 7,
                "unavailable_current": 8,
                "applied_current": 8,
                "superseded": 1,
                "conflicted": 1,
            }
        )
        and versions["customer_master"] == 7
        and all(
            version == 3
            for kind, version in versions.items()
            if kind != "customer_master"
        ),
        "P8-01 immutable observation/head cardinality drifted",
    )
    _assert_consumers(project_id, master_id, tooling_set_id)
    return {
        "auditCount": final["auditCount"],
        "consumerClosure": True,
        "digest": final["digest"],
        "headCount": final["headCount"],
        "observationCount": final["observationCount"],
        "replayCount": len(same_process_replay.outcomes),
    }


def replay_projection_truth(
    fixture_run_id: str,
    project_id: str,
    master_id: str,
    part_id: str,
    tooling_set_id: str,
    model_reference: Mapping[str, object],
) -> dict[str, object]:
    import frappe

    from npi_integration.projections.worker import refresh_project_projections

    _validate_fixture_context(
        fixture_run_id=fixture_run_id,
        project_id=project_id,
        master_id=master_id,
        part_id=part_id,
        tooling_set_id=tooling_set_id,
    )
    frappe.set_user(ACTOR_USER)
    before = _structural_context(project_id)
    targets = projection_targets(
        project_id=project_id,
        master_id=master_id,
        part_id=part_id,
        tooling_set_id=tooling_set_id,
        model_reference=model_reference,
    )
    batch = refresh_project_projections(
        repository=projection_repository(),
        registry=sandbox_registry(
            targets,
            master_id=master_id,
            tooling_set_id=tooling_set_id,
        ),
        project_global_id=UUID(project_id),
        clock=lambda: SANDBOX_RECEIVED_AT,
        uuid_factory=sequence_uuid_factory("sandbox-refresh"),
    )
    after = _structural_context(project_id)
    require(
        len(batch.outcomes) == 7
        and all(outcome.replayed for outcome in batch.outcomes)
        and before == after,
        "P8-01 cross-process replay changed retained projection truth",
    )
    _assert_consumers(project_id, master_id, tooling_set_id)
    return {
        "crossProcessReplay": True,
        "digest": after["digest"],
        "headCount": after["headCount"],
        "observationCount": after["observationCount"],
        "replayCount": len(batch.outcomes),
    }


def run_bench_fixture(method: str, kwargs: dict[str, object]) -> dict[str, Any]:
    environment = os.environ.copy()
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT)
        if not current_pythonpath
        else f"{ROOT}{os.pathsep}{current_pythonpath}"
    )
    completed = subprocess.run(
        [
            str(BENCH_PATH / "env" / "bin" / "python"),
            str(Path(__file__).resolve()),
            "--bench-fixture",
            method,
            "--fixture-kwargs",
            json.dumps(kwargs, separators=(",", ":"), sort_keys=True),
        ],
        cwd=BENCH_PATH / "sites",
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    require(
        completed.returncode == 0,
        f"P8-01 Bench fixture {method} failed: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P8-01 Bench fixture {method} was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P8-01 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "seed_projection_truth": seed_projection_truth,
        "replay_projection_truth": replay_projection_truth,
    }
    require(method in fixtures, "P8-01 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user(ACTOR_USER)
        result = fixtures[method](**kwargs)
        frappe.db.commit()
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url")
    parser.add_argument("--replay-only", action="store_true")
    parser.add_argument("--route-disable-probe", choices=("disabled", "recovered"))
    parser.add_argument("--bench-fixture")
    parser.add_argument("--fixture-kwargs")
    arguments = parser.parse_args()
    if arguments.bench_fixture is not None:
        require(
            arguments.base_url is None and arguments.fixture_kwargs is not None,
            "P8-01 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P8-01 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and os.environ.get(document_runtime.FIXTURE_RUN_ID_ENV) is not None
        and int(arguments.replay_only)
        + int(arguments.route_disable_probe is not None)
        <= 1,
        "P8-01 runtime invocation is incomplete",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        ACTOR_USER,
        INTERNAL_USER,
    )
    validate_local_fixture_inputs(base_url, ACTOR_USER, EXTERNAL_USER)
    require(
        FIXTURE_RUN_ID != "0" * 32
        and INTERNAL_USER.endswith("@example.invalid")
        and EXTERNAL_USER.endswith("@example.invalid"),
        "P8-01 fixture namespace drifted",
    )
    administrator = login(base_url, ACTOR_USER, administrator_password)
    if arguments.route_disable_probe is not None:
        result = route_disable_probe(
            administrator,
            base_url,
            expected_mode=arguments.route_disable_probe,
        )
    elif arguments.replay_only:
        result = run_replay_only(administrator, base_url)
    else:
        administrator_csrf = bootstrap_csrf(
            administrator,
            base_url,
            ACTOR_USER,
        )
        result = run_fresh(
            administrator,
            base_url,
            administrator_csrf,
            fixture_password,
        )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
