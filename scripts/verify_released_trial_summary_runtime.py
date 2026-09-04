from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import verify_controlled_print_runtime as controlled_print_runtime
import verify_document_runtime as document_runtime
import verify_production_transition_runtime as production_transition_runtime
import verify_readiness_runtime as readiness_runtime
import verify_trial_runtime as trial_runtime
from verify_frappe_runtime import (
    HttpResult,
    login,
    require,
    secret_from_environment,
    validate_local_fixture_inputs,
    validate_problem,
)
from verify_project_runtime import (
    bootstrap_csrf,
    delete_resource,
    get_resource,
    update_resource,
)


ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / "tmp" / "frappe-bench"
SITE_NAME = document_runtime.SITE_NAME
RUNTIME_MARKER = document_runtime.RUNTIME_MARKER
FIXTURE_RUN_ID = document_runtime.FIXTURE_RUN_ID
ACTOR_USER = trial_runtime.REVIEW_USER
NO_WRITE_USER = document_runtime.BASELINE_USER
UNRELATED_USER = trial_runtime.UNRELATED_USER
SOURCE_KIND = "released_trial_summary"

RETAIN_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-retain"
REVISE_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-revise"
STALE_REVISE_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-stale-revise"
NOOP_REVISE_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-noop-revise"
NO_WRITE_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-no-write"
SUBMIT_APPROVED_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-submit-approved"
DECIDE_APPROVED_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-decide-approved"
REOPEN_REJECTED_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-reopen-rejected"
SUBMIT_REJECTED_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-submit-rejected"
DECIDE_REJECTED_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-decide-rejected"
PRINT_KEY = f"p7-07-runtime-{FIXTURE_RUN_ID}-controlled-print"

RETAIN_REASON = "P707-RETAIN-APPROVED-SUMMARY"
REVISE_REASON = "P707-RETAIN-REJECTED-SUMMARY"
PRINT_TITLE = "P707 disposable released summary output"
WATERMARK_SOURCE = "P707-DISPOSABLE-CONTROLLED-OUTPUT"
ABSENT_ID = "00000000-0000-4000-8000-000000000707"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SUMMARY_KEYS = {
    "projectGlobalId",
    "trialRound",
    "summaryRevisions",
    "currentSummaryRevisionGlobalId",
    "currentDecidedConclusion",
    "permissions",
    "controlledOutput",
    "holds",
}
_SNAPSHOT_KEYS = controlled_print_runtime._SNAPSHOT_KEYS
_FORBIDDEN_KEY_PARTS = (
    "authorization",
    "credential",
    "cookie",
    "filecontent",
    "fileurl",
    "hostname",
    "password",
    "privatepath",
    "privateurl",
    "providerpayload",
    "secret",
    "token",
)
_FORBIDDEN_VALUE_MARKERS = (
    "/private/files/",
    "authorization:",
    "bearer ",
    "cookie=",
    "file://",
    "http://",
    "https://",
    production_transition_runtime.POLICY_SENTINEL.casefold(),
    production_transition_runtime.HANDOVER_SENTINEL.casefold(),
    production_transition_runtime.OBSERVATION_SENTINEL.casefold(),
)


def fixture_uuid4(scope: str) -> str:
    digest = bytearray(
        hashlib.sha256(
            (
                "https://npi-one.example.invalid/runtime/p7-07/"
                f"{FIXTURE_RUN_ID}/{scope}"
            ).encode()
        ).digest()[:16]
    )
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


REGISTRY_ID = fixture_uuid4("registry")
MAPPING_ID = fixture_uuid4("mapping-approved-en")
P8_08_REQUEST_ID = fixture_uuid4("p8-08-projection-request")
P8_08_TRACE_ID = f"p8-08-runtime-{FIXTURE_RUN_ID}"
PRINT_FORMAT_NAME = f"P707 Runtime {FIXTURE_RUN_ID[:12]}"


def summary_path(
    project_id: str,
    round_id: str,
    summary_id: str | None = None,
) -> str:
    base = (
        f"/api/npi/v1/projects/{project_id}/trial-rounds/{round_id}"
        "/released-trial-summaries"
    )
    return base if summary_id is None else f"{base}/{summary_id}:revise"


def summary_stream_path(
    project_id: str,
    round_id: str,
    revision: Mapping[str, object],
) -> str:
    return summary_path(project_id, round_id, str(revision["summaryGlobalId"]))


def capability_path(project_id: str, summary: Mapping[str, object]) -> str:
    query = urllib.parse.urlencode(
        {
            "sourceKind": SOURCE_KIND,
            "sourceGlobalId": summary["globalId"],
            "sourceVersion": summary["summaryVersion"],
            "language": "en",
        }
    )
    return f"/api/npi/v1/projects/{project_id}/controlled-print/capability?{query}"


def controlled_print_payload(summary: Mapping[str, object]) -> dict[str, object]:
    return {
        "sourceKind": SOURCE_KIND,
        "sourceGlobalId": summary["globalId"],
        "sourceVersion": summary["summaryVersion"],
        "language": "en",
    }


def summary_request(
    opener,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf_token: str | None = None,
    idempotency_key: str | None = None,
    query_key: str = "query",
) -> HttpResult:
    headers = (
        document_runtime.command_headers(csrf_token, idempotency_key)
        if idempotency_key is not None
        else document_runtime.query_headers(f"p707-{query_key}")
    )
    result = document_runtime.request(
        opener,
        base_url,
        path,
        method=method,
        payload=payload,
        request_headers=headers,
    )
    require(
        result.headers.get("X-Request-ID") == headers["X-Request-ID"],
        "P7-07 request identity was not echoed",
    )
    require(
        result.headers.get("Cache-Control") == "private, no-store",
        "P7-07 private no-store boundary drifted",
    )
    return HttpResult(
        result.status,
        result.headers,
        result.body,
        request_id=headers["X-Request-ID"],
        trace_id=headers["X-Trace-ID"],
    )


def summary_command(
    opener,
    base_url: str,
    csrf_token: str,
    path: str,
    payload: dict[str, object],
    key: str,
    *,
    replayed: bool = False,
) -> HttpResult:
    result = summary_request(
        opener,
        base_url,
        path,
        method="POST",
        payload=payload,
        csrf_token=csrf_token,
        idempotency_key=key,
    )
    require(
        result.status == 201
        and result.headers.get("Idempotency-Replayed")
        == ("true" if replayed else "false"),
        f"P7-07 command returned HTTP {result.status}",
    )
    require_safe_payload(result.body, "P7-07 command response")
    return result


def require_safe_payload(value: object, label: str) -> None:
    def walk(candidate: object, path: str) -> None:
        if isinstance(candidate, Mapping):
            for key, item in candidate.items():
                folded_key = str(key).replace("_", "").replace("-", "").casefold()
                require(
                    not any(part in folded_key for part in _FORBIDDEN_KEY_PARTS),
                    f"{label} exposed a sensitive key at {path}",
                )
                walk(item, f"{path}.{key}")
        elif isinstance(candidate, Sequence) and not isinstance(
            candidate, (str, bytes, bytearray)
        ):
            for index, item in enumerate(candidate):
                walk(item, f"{path}[{index}]")
        elif isinstance(candidate, str):
            folded = candidate.casefold()
            require(
                not any(marker in folded for marker in _FORBIDDEN_VALUE_MARKERS),
                f"{label} exposed a sensitive value at {path}",
            )

    walk(value, "$")


def assert_summary_workspace(
    result: HttpResult,
    project_id: str,
    round_id: str,
    *,
    round_state: str,
    round_version: int,
    revision_count: int,
    conclusion_state: str,
) -> dict[str, Any]:
    require(result.status in {200, 201}, "P7-07 summary workspace failed")
    require(
        isinstance(result.body, dict) and set(result.body) == _SUMMARY_KEYS,
        "P7-07 summary workspace contract drifted",
    )
    trial_round = result.body.get("trialRound")
    conclusion = result.body.get("currentDecidedConclusion")
    revisions = result.body.get("summaryRevisions")
    require(
        isinstance(trial_round, dict)
        and trial_round.get("globalId") == round_id
        and trial_round.get("currentState") == round_state
        and trial_round.get("optimisticVersion") == round_version
        and _SHA256.fullmatch(str(trial_round.get("snapshotHash"))) is not None
        and result.body.get("projectGlobalId") == project_id,
        "P7-07 exact Round identity drifted",
    )
    require(
        isinstance(conclusion, dict)
        and conclusion.get("state") == conclusion_state
        and _SHA256.fullmatch(str(conclusion.get("snapshotHash"))) is not None,
        "P7-07 current decided conclusion drifted",
    )
    require(
        isinstance(revisions, list)
        and len(revisions) == revision_count
        and [value.get("summaryVersion") for value in revisions]
        == list(range(1, revision_count + 1)),
        "P7-07 immutable summary history drifted",
    )
    if revisions:
        require(
            result.body.get("currentSummaryRevisionGlobalId")
            == revisions[-1].get("globalId")
            and result.body.get("controlledOutput")
            == {
                "sourceObjectType": SOURCE_KIND,
                "sourceGlobalId": revisions[-1].get("globalId"),
                "sourceVersion": revisions[-1].get("summaryVersion"),
                "mapping": "unavailable",
            },
            "P7-07 current summary or held mapping truth drifted",
        )
    else:
        require(
            result.body.get("currentSummaryRevisionGlobalId") is None,
            "P7-07 empty summary history exposed a tip",
        )
    require(
        set(result.body.get("holds", {}).values()) == {"unavailable"}
        and result.body.get("permissions", {}).get("requiresExactRound") is True
        and result.body.get("permissions", {}).get("requiresExactConclusion") is True
        and result.body.get("permissions", {}).get("requiresExactPredecessor") is True,
        "P7-07 authority holds or exactness permissions drifted",
    )
    for value in revisions:
        require(
            _SHA256.fullmatch(str(value.get("snapshotHash"))) is not None
            and value.get("projectGlobalId") == project_id
            and value.get("trialRoundGlobalId") == round_id,
            "P7-07 retained summary identity drifted",
        )
        require_safe_payload(value, "P7-07 retained summary")
    require_safe_payload(result.body, "P7-07 summary workspace")
    return result.body


def retain_payload(
    trial_round: Mapping[str, object],
    conclusion: Mapping[str, object],
    *,
    reason: str,
) -> dict[str, object]:
    return {
        "expectedRoundOptimisticVersion": trial_round["optimisticVersion"],
        "expectedRoundSnapshotHash": trial_round["snapshotHash"],
        "conclusionRevisionGlobalId": conclusion["globalId"],
        "expectedConclusionVersion": conclusion["conclusionVersion"],
        "expectedConclusionSnapshotHash": conclusion["snapshotHash"],
        "reason": reason,
    }


def revise_payload(
    trial_round: Mapping[str, object],
    conclusion: Mapping[str, object],
    predecessor: Mapping[str, object],
    *,
    reason: str,
) -> dict[str, object]:
    return {
        **retain_payload(trial_round, conclusion, reason=reason),
        "predecessorRevisionGlobalId": predecessor["globalId"],
        "expectedPredecessorVersion": predecessor["summaryVersion"],
        "expectedPredecessorSnapshotHash": predecessor["snapshotHash"],
    }


def _exact_snapshots(
    values: Sequence[Mapping[str, Any]],
    frozen: Sequence[Mapping[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for expected in frozen:
        matches = [
            value
            for value in values
            if value.get("globalId") == expected.get("globalId")
            and value.get("snapshotHash") == expected.get("snapshotHash")
        ]
        result.append(trial_runtime.exact_single(matches, label))
    return result


def _submission_sources(
    workspace: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_reference = readiness_runtime.current_controlled_reference(workspace)
    if current_reference is not None:
        comparison_snapshot = current_reference.get("comparisonSnapshot")
        frozen_references: Sequence[Mapping[str, Any]] = [current_reference]
    else:
        predecessor = workspace["conclusionRevisions"][-1]
        comparison_snapshot = predecessor.get("comparisonSnapshot")
        frozen_references = predecessor.get("reviewReferences") or []
    require(
        isinstance(comparison_snapshot, Mapping) and bool(frozen_references),
        "P7-07 exact submission sources are unavailable",
    )
    comparison = _exact_snapshots(
        workspace["comparisonSnapshots"],
        [comparison_snapshot],
        "P7-07 exact submission comparison",
    )[0]
    references = _exact_snapshots(
        workspace["reviewReferenceRevisions"],
        frozen_references,
        "P7-07 exact submission reference",
    )
    require(
        all(
            value.get("comparisonSnapshot")
            == {
                "globalId": comparison["globalId"],
                "snapshotHash": comparison["snapshotHash"],
            }
            for value in references
        ),
        "P7-07 submission references do not match the exact comparison",
    )
    return comparison, references


def _review_context(
    reviewer,
    base_url: str,
    project_id: str,
    round_id: str,
    *,
    state: str,
    round_version: int,
    conclusions: int,
) -> dict[str, Any]:
    return trial_runtime.assert_review_workspace(
        trial_runtime.trial_request(
            reviewer,
            base_url,
            trial_runtime.review_path(project_id, round_id),
            query_key=f"p707-{state}-{round_version}",
        ),
        project_id,
        round_id,
        state=state,
        round_version=round_version,
        policies=1,
        comparisons=2,
        references=4,
        conclusions=conclusions,
    )


def _reopen(
    reviewer,
    base_url: str,
    csrf_token: str,
    project_id: str,
    round_id: str,
    workspace: Mapping[str, Any],
    key: str,
    reason: str,
) -> dict[str, Any]:
    policy = trial_runtime.exact_single(workspace["policyVersions"], "P7-07 policy")
    conclusion = workspace["conclusionRevisions"][-1]
    result = trial_runtime.command(
        reviewer,
        base_url,
        csrf_token,
        trial_runtime.execution_path(project_id, round_id, ":reopen"),
        {
            **trial_runtime.review_policy_context(policy, workspace["trialRound"]),
            "conclusionGlobalId": conclusion["conclusionGlobalId"],
            "expectedConclusionRevisionGlobalId": conclusion["globalId"],
            "expectedConclusionRevisionSnapshotHash": conclusion["snapshotHash"],
            "expectedConclusionVersion": conclusion["conclusionVersion"],
            "reason": reason,
        },
        key,
    )
    return result.body


def _submit(
    reviewer,
    base_url: str,
    csrf_token: str,
    project_id: str,
    round_id: str,
    workspace: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    policy = trial_runtime.exact_single(workspace["policyVersions"], "P7-07 policy")
    comparison, references = _submission_sources(workspace)
    predecessor = workspace["conclusionRevisions"][-1]
    result = trial_runtime.command(
        reviewer,
        base_url,
        csrf_token,
        trial_runtime.review_path(project_id, round_id, "/conclusions"),
        trial_runtime.conclusion_payload(
            policy,
            workspace["trialRound"],
            comparison,
            references,
            predecessor=predecessor,
        ),
        key,
    )
    return result.body


def _decide(
    reviewer,
    base_url: str,
    csrf_token: str,
    project_id: str,
    round_id: str,
    workspace: Mapping[str, Any],
    key: str,
    decision: str,
) -> dict[str, Any]:
    policy = trial_runtime.exact_single(workspace["policyVersions"], "P7-07 policy")
    conclusion = workspace["conclusionRevisions"][-1]
    result = trial_runtime.command(
        reviewer,
        base_url,
        csrf_token,
        trial_runtime.review_path(
            project_id,
            round_id,
            f"/conclusions/{conclusion['conclusionGlobalId']}:decide",
        ),
        {
            **trial_runtime.review_policy_context(policy, workspace["trialRound"]),
            "expectedConclusionRevisionGlobalId": conclusion["globalId"],
            "expectedConclusionRevisionSnapshotHash": conclusion["snapshotHash"],
            "expectedConclusionVersion": conclusion["conclusionVersion"],
            "decision": decision,
            "reason": f"P707 decide exact technical conclusion as {decision}.",
        },
        key,
    )
    return result.body


def _site_marker() -> object:
    import frappe

    configuration = getattr(frappe, "conf", None)
    return (
        configuration.get("npi_runtime_disposable_marker")
        if hasattr(configuration, "get")
        else None
    )


def _require_disposable_site() -> None:
    require(
        _site_marker() == RUNTIME_MARKER,
        "P7-07 fixtures require the exact disposable runtime Site marker",
    )


def verify_released_summary_schema(**_kwargs: object) -> dict[str, object]:
    import frappe
    from npi_core.controlled_print.source_registry import (
        default_controlled_print_source_registry,
    )

    _require_disposable_site()
    require(
        frappe.db.table_exists("NPI Released Trial Summary Revision"),
        "P7-07 released-summary schema is unavailable",
    )
    registry = default_controlled_print_source_registry()
    require(
        registry.source_object_types
        == (controlled_print_runtime.SOURCE_KIND, SOURCE_KIND),
        "P7-07 disposable source registry drifted",
    )
    return {
        "runtimeMarker": RUNTIME_MARKER,
        "sourceKinds": list(registry.source_object_types),
        "summaryTable": True,
    }


def provision_released_summary_mapping(
    *, project_id: str, actor_user_id: str
) -> dict[str, object]:
    import frappe
    from npi_core.controlled_print.domain import (
        ControlledPrintRegistryVersion,
        PrintCopyState,
        PrintDeliveryMode,
        PrintRegistryState,
    )
    from npi_core.controlled_print.frappe_validation import (
        controlled_print_registry_write,
    )

    _require_disposable_site()
    require(actor_user_id == ACTOR_USER, "P7-07 mapping actor drifted")
    project = frappe.get_doc("NPI Engineering Project", project_id)
    template = (
        "<h1>Released Trial Summary</h1>"
        "<p>{{ doc.summaryRevision.summaryGlobalId }}</p>"
        "<p>{{ doc.presentationProjection.conclusionState }}</p>"
        "<p>{{ doc.presentationProjection.conclusionCode }}</p>"
        "<p>{{ controlledPrint.snapshotHash }}</p>"
    )
    now = datetime.now(UTC)
    mapping = ControlledPrintRegistryVersion(
        global_id=UUID(MAPPING_ID),
        registry_global_id=UUID(REGISTRY_ID),
        tenant_id=str(project.tenant_id),
        mapping_key=f"p7_07_runtime_{FIXTURE_RUN_ID}",
        mapping_version=1,
        title=PRINT_TITLE,
        state=PrintRegistryState.PUBLISHED,
        source_object_type=SOURCE_KIND,
        project_type_key=str(project.project_type),
        gate_key=None,
        source_state="approved",
        language="en",
        delivery_mode=PrintDeliveryMode.CONTROLLED_PDF,
        copy_state=PrintCopyState.NOT_NUMBERED,
        print_format_name=PRINT_FORMAT_NAME,
        template_content=template,
        template_sha256=hashlib.sha256(template.encode()).hexdigest(),
        watermark_source=WATERMARK_SOURCE,
        printer_user_ids=(actor_user_id,),
        effective_from=now - timedelta(days=1),
        published_at=now - timedelta(days=1),
    )
    require(
        not frappe.db.exists("Print Format", PRINT_FORMAT_NAME)
        and not frappe.db.exists("NPI Controlled Print Registry", REGISTRY_ID)
        and not frappe.db.exists("NPI Controlled Print Registry Version", MAPPING_ID),
        "P7-07 disposable mapping already exists",
    )
    frappe.get_doc(
        {
            "doctype": "Print Format",
            "name": PRINT_FORMAT_NAME,
            "doc_type": "NPI Released Trial Summary Revision",
            "module": "NPI Core",
            "standard": "No",
            "custom_format": 1,
            "disabled": 0,
            "print_format_type": "Jinja",
            "raw_printing": 0,
            "html": template,
        }
    ).insert(ignore_permissions=True)
    with controlled_print_registry_write():
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Registry",
                "global_id": REGISTRY_ID,
                "tenant_id": str(project.tenant_id),
                "registry_key": f"p7_07_runtime_{FIXTURE_RUN_ID}",
                "title": PRINT_TITLE,
                "enabled": 1,
                "optimistic_version": 1,
            }
        ).insert()
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Registry Version",
                "global_id": MAPPING_ID,
                "print_registry": REGISTRY_ID,
                "tenant_id": str(project.tenant_id),
                "registry_global_id": REGISTRY_ID,
                "mapping_key": mapping.mapping_key,
                "mapping_version": 1,
                "title": mapping.title,
                "publication_state": "published",
                "source_object_type": SOURCE_KIND,
                "project_type_key": str(project.project_type),
                "source_state": "approved",
                "language": "en",
                "delivery_mode": "controlled_pdf",
                "copy_state": "not_numbered",
                "print_format_name": PRINT_FORMAT_NAME,
                "template_content": template,
                "template_sha256": mapping.template_sha256,
                "watermark_source": mapping.watermark_source,
                "printer_user_ids": json.dumps([actor_user_id]),
                "effective_from": mapping.effective_from.isoformat(),
                "mapping_snapshot": json.dumps(mapping.snapshot_payload()),
                "snapshot_hash": mapping.snapshot_hash,
                "published_at": mapping.published_at.isoformat(),
                "optimistic_version": 1,
            }
        ).insert()
    frappe.db.commit()
    return {
        "mappingGlobalId": MAPPING_ID,
        "registryGlobalId": REGISTRY_ID,
        "sourceState": "approved",
        "templateSha256": mapping.template_sha256,
    }


def _canonical_row_digest(
    frappe, doctype: str, filters: Mapping[str, object]
) -> str:
    rows = frappe.get_all(
        doctype,
        filters=dict(filters),
        fields=["*"],
        order_by="name asc",
        limit_page_length=2_001,
    )
    require(len(rows) <= 2_000, f"P7-07 {doctype} digest collection is unsafe")
    encoded = json.dumps(
        rows,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def protected_source_context(
    *, fixture_run_id: str, project_id: str
) -> dict[str, object]:
    _require_disposable_site()
    context = readiness_runtime.readiness_persistence_context(
        fixture_run_id, project_id=project_id
    )
    excluded = "trial:NPI Trial Command Idempotency"
    return {
        "counts": {
            key: value
            for key, value in context["downstreamCounts"].items()
            if key != excluded
        },
        "digests": {
            key: value
            for key, value in context["downstreamDigests"].items()
            if key != excluded
        },
        "projectOptimisticVersion": context["projectOptimisticVersion"],
        "sourcePreparationAuditCounts": context["sourcePreparationAuditCounts"],
        "sourcePreparationAuditDigests": context["sourcePreparationAuditDigests"],
    }


def cumulative_protected_context(
    *, fixture_run_id: str, project_id: str
) -> dict[str, object]:
    _require_disposable_site()
    context = production_transition_runtime.production_transition_persistence_context(
        fixture_run_id, project_id=project_id
    )
    changing = {
        "trial:NPI Trial Round",
        "trial:NPI Trial Round Lifecycle Event",
        "trial:NPI Trial Command Idempotency",
        "trial:NPI Trial Conclusion Revision",
        "audit:non-p706",
    }
    return {
        "downstreamSnapshot": {
            key: value
            for key, value in context["downstreamSnapshot"].items()
            if key not in changing
        },
        "transitionGlobalSnapshot": context["transitionGlobalSnapshot"],
        "transitionSnapshot": context["transitionSnapshot"],
    }


def target_persistence_context(*, project_id: str) -> dict[str, object]:
    import frappe

    _require_disposable_site()
    summary_filters = {"project_global_id": project_id}
    summary_receipt_filters = {
        "project_global_id": project_id,
        "operation": [
            "in",
            ["released_trial_summary.retain", "released_trial_summary.revise"],
        ],
    }
    print_filters = {
        "project_global_id": project_id,
        "source_object_type": SOURCE_KIND,
    }
    result: dict[str, object] = {}
    for key, doctype, filters in (
        ("summaries", "NPI Released Trial Summary Revision", summary_filters),
        ("summaryReceipts", "NPI Trial Command Idempotency", summary_receipt_filters),
        ("printSnapshots", "NPI Controlled Print Snapshot", print_filters),
        (
            "printOutputs",
            "NPI Controlled Print Output",
            {"project_global_id": project_id},
        ),
        (
            "printReceipts",
            "NPI Controlled Print Command Idempotency",
            {"project_global_id": project_id, "actor_user_id": ACTOR_USER},
        ),
        (
            "printAccessEvents",
            "NPI Controlled Print Access Event",
            {"project_global_id": project_id, "actor_user_id": ACTOR_USER},
        ),
    ):
        result[key] = {
            "count": int(frappe.db.count(doctype, filters)),
            "digest": _canonical_row_digest(frappe, doctype, filters),
        }
    for operation in ("released_trial_summary.retain", "released_trial_summary.revise"):
        filters = {"operation": operation, "actor": ACTOR_USER}
        result[f"audit:{operation}"] = {
            "count": int(frappe.db.count("NPI Audit Event", filters)),
            "digest": _canonical_row_digest(frappe, "NPI Audit Event", filters),
        }
    return result


def released_summary_projection_truth(
    *,
    project_id: str,
    current_summary: Mapping[str, object],
) -> dict[str, str | None]:
    from npi_core.foundation.security import Principal
    from npi_core.trial.released_summary_repository import (
        FrappeReleasedTrialSummaryRepository,
    )
    from npi_integration.released_summary_projection.readers import (
        ContractHeldReleasedSummaryProjectionAdapter,
    )
    from npi_integration.released_summary_projection.source import (
        ProjectFirstReleasedSummarySourceReader,
    )

    _require_disposable_site()
    require(
        isinstance(current_summary, dict)
        and current_summary.get("projectGlobalId") == project_id
        and current_summary.get("tenantId") == trial_runtime.TENANT_ID,
        "P8-08 retained source scope drifted",
    )
    before = target_persistence_context(project_id=project_id)
    repository = FrappeReleasedTrialSummaryRepository(
        principal=Principal(
            user_id=ACTOR_USER,
            roles=frozenset({"System Manager"}),
            tenant_id=trial_runtime.TENANT_ID,
        ),
        request_id=P8_08_REQUEST_ID,
        trace_id=P8_08_TRACE_ID,
    )
    descriptor = ProjectFirstReleasedSummarySourceReader(
        repository
    ).read_current_source(
        project_global_id=UUID(project_id),
        trial_round_global_id=UUID(str(current_summary.get("trialRoundGlobalId"))),
        summary_revision_global_id=UUID(str(current_summary.get("globalId"))),
    )
    require(descriptor is not None, "P8-08 exact retained source is unavailable")
    require(
        {
            "projectGlobalId": str(descriptor.project_global_id),
            "trialRoundGlobalId": str(descriptor.trial_round_global_id),
            "summaryRevisionGlobalId": str(descriptor.summary_revision_global_id),
            "summaryGlobalId": str(descriptor.summary_global_id),
            "summaryVersion": descriptor.summary_version,
            "snapshotHash": descriptor.snapshot_hash,
            "sourceManifestHash": descriptor.source_manifest_hash,
            "presentationProjectionHash": descriptor.presentation_projection_hash,
            "redactionManifestHash": descriptor.redaction_manifest_hash,
        }
        == {
            "projectGlobalId": current_summary.get("projectGlobalId"),
            "trialRoundGlobalId": current_summary.get("trialRoundGlobalId"),
            "summaryRevisionGlobalId": current_summary.get("globalId"),
            "summaryGlobalId": current_summary.get("summaryGlobalId"),
            "summaryVersion": current_summary.get("summaryVersion"),
            "snapshotHash": current_summary.get("snapshotHash"),
            "sourceManifestHash": current_summary.get("sourceManifestHash"),
            "presentationProjectionHash": current_summary.get(
                "presentationProjectionHash"
            ),
            "redactionManifestHash": current_summary.get("redactionManifestHash"),
        },
        "P8-08 exact retained source identity drifted",
    )
    status = ContractHeldReleasedSummaryProjectionAdapter().project(
        descriptor,
        trace_id=P8_08_TRACE_ID,
    ).safe_status()
    require(
        status
        == {
            "sourceState": "current",
            "sourceFingerprint": descriptor.fingerprint,
            "externalProjection": "unavailable",
            "unavailableReasonCode": "external_contract_held",
            "traceId": P8_08_TRACE_ID,
        },
        "P8-08 unavailable projection truth drifted",
    )
    after = target_persistence_context(project_id=project_id)
    require(after == before, "P8-08 read-only projection changed retained truth")
    return status


def retained_truth(*, project_id: str) -> dict[str, object]:
    import frappe

    _require_disposable_site()
    trial_counts = {
        doctype: int(frappe.db.count(doctype, {"project_global_id": project_id}))
        for doctype in (
            "NPI Trial Round",
            "NPI Trial Round Lifecycle Event",
            "NPI Trial Command Idempotency",
            "NPI Trial Conclusion Revision",
        )
    }
    # P7-04 seals 12/39/5 lifecycle/command/conclusion rows, P7-05 adds
    # 1/3/1, and this flow adds five review transitions plus two summary commands.
    require(
        trial_counts
        == {
            "NPI Trial Round": 2,
            "NPI Trial Round Lifecycle Event": 18,
            "NPI Trial Command Idempotency": 49,
            "NPI Trial Conclusion Revision": 11,
        },
        "P7-07 cumulative Trial cardinality drifted",
    )
    summaries = frappe.get_all(
        "NPI Released Trial Summary Revision",
        filters={"project_global_id": project_id},
        fields=["global_id", "summary_version", "summary_snapshot", "snapshot_hash"],
        order_by="summary_version asc",
        limit_page_length=3,
    )
    require(len(summaries) == 2, "P7-07 retained summary cardinality drifted")
    parsed_summaries: list[dict[str, Any]] = []
    for row in summaries:
        payload = row.summary_snapshot
        if isinstance(payload, str):
            payload = json.loads(payload)
        require(
            isinstance(payload, dict)
            and payload.get("globalId") == str(row.global_id)
            and payload.get("summaryVersion") == int(row.summary_version)
            and payload.get("snapshotHash") == str(row.snapshot_hash),
            "P7-07 persisted summary snapshot drifted",
        )
        require_safe_payload(payload, "P7-07 persisted summary snapshot")
        parsed_summaries.append(payload)
    receipts = frappe.get_all(
        "NPI Trial Command Idempotency",
        filters={
            "project_global_id": project_id,
            "actor_user_id": ACTOR_USER,
            "operation": [
                "in",
                ["released_trial_summary.retain", "released_trial_summary.revise"],
            ],
            "sealed": 1,
        },
        fields=["operation", "response_payload", "response_hash"],
        order_by="creation asc",
        limit_page_length=3,
    )
    require(len(receipts) == 2, "P7-07 sealed receipt cardinality drifted")
    receipt_responses: dict[str, dict[str, Any]] = {}
    for row in receipts:
        payload = row.response_payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        require(isinstance(payload, dict), "P7-07 sealed response is invalid")
        require_safe_payload(payload, "P7-07 sealed summary response")
        receipt_responses[str(row.operation)] = payload
    audits = frappe.get_all(
        "NPI Audit Event",
        filters={
            "actor": ACTOR_USER,
            "operation": [
                "in",
                ["released_trial_summary.retain", "released_trial_summary.revise"],
            ],
        },
        fields=["input_summary"],
        limit_page_length=3,
    )
    require(len(audits) == 2, "P7-07 audit cardinality drifted")
    for row in audits:
        payload = row.input_summary
        if isinstance(payload, str):
            payload = json.loads(payload)
        require_safe_payload(payload, "P7-07 persisted audit summary")
    print_rows = frappe.get_all(
        "NPI Controlled Print Snapshot",
        filters={
            "project_global_id": project_id,
            "source_object_type": SOURCE_KIND,
        },
        fields=["global_id", "source_global_id", "source_version", "source_snapshot"],
        limit_page_length=2,
    )
    require(len(print_rows) == 1, "P7-07 controlled snapshot cardinality drifted")
    print_row = print_rows[0]
    source_snapshot = print_row.source_snapshot
    if isinstance(source_snapshot, str):
        source_snapshot = json.loads(source_snapshot)
    require_safe_payload(source_snapshot, "P7-07 controlled-print source snapshot")
    require(
        isinstance(source_snapshot, dict)
        and str(print_row.source_global_id) == parsed_summaries[0]["globalId"]
        and int(print_row.source_version) == 1
        and source_snapshot.get("summaryRevision", {}).get("snapshotHash")
        == parsed_summaries[0]["snapshotHash"],
        "P7-07 controlled source did not retain exact summary v1",
    )
    output = frappe.db.get_value(
        "NPI Controlled Print Output",
        {"snapshot_global_id": str(print_row.global_id)},
        ["sha256", "size_bytes", "frappe_file_id"],
        as_dict=True,
    )
    require(output is not None, "P7-07 controlled output is unavailable")
    file_document = frappe.get_doc("File", str(output.frappe_file_id))
    content = file_document.get_content()
    if isinstance(content, str):
        content = content.encode()
    require(
        isinstance(content, bytes)
        and hashlib.sha256(content).hexdigest() == str(output.sha256)
        and len(content) == int(output.size_bytes),
        "P7-07 controlled PDF integrity drifted",
    )
    projection_source = released_summary_projection_truth(
        project_id=project_id,
        current_summary=parsed_summaries[-1],
    )
    return {
        "printResponse": _controlled_print_response(frappe, str(print_row.global_id)),
        "projectionSource": projection_source,
        "retainedOutputHash": str(output.sha256),
        "retainedOutputSize": int(output.size_bytes),
        "summaryResponses": receipt_responses,
        "summarySnapshots": parsed_summaries,
        "trialCounts": trial_counts,
    }


def _controlled_print_response(frappe, snapshot_id: str) -> dict[str, Any]:
    rows = frappe.get_all(
        "NPI Controlled Print Command Idempotency",
        filters={
            "actor_user_id": ACTOR_USER,
            "snapshot_global_id": snapshot_id,
            "sealed": 1,
        },
        fields=["response_payload"],
        limit_page_length=2,
    )
    require(len(rows) == 1, "P7-07 controlled receipt cardinality drifted")
    payload = rows[0].response_payload
    if isinstance(payload, str):
        payload = json.loads(payload)
    require(isinstance(payload, dict), "P7-07 controlled response is invalid")
    require_safe_payload(payload, "P7-07 sealed controlled response")
    return payload


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
        f"P7-07 Bench fixture {method} failed: {completed.stderr[-2000:]}",
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), f"P7-07 Bench fixture {method} was silent")
    result = json.loads(lines[-1])
    require(isinstance(result, dict), "P7-07 Bench fixture result is invalid")
    return result


def run_local_bench_fixture(method: str, kwargs: dict[str, object]) -> None:
    import frappe

    fixtures = {
        "verify_released_summary_schema": verify_released_summary_schema,
        "provision_released_summary_mapping": provision_released_summary_mapping,
        "protected_source_context": protected_source_context,
        "cumulative_protected_context": cumulative_protected_context,
        "target_persistence_context": target_persistence_context,
        "retained_truth": retained_truth,
    }
    require(method in fixtures, "P7-07 Bench fixture is unavailable")
    frappe.init(site=SITE_NAME, sites_path=str(BENCH_PATH / "sites"))
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        result = fixtures[method](**kwargs)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def _protected_sources(project_id: str) -> dict[str, Any]:
    return run_bench_fixture(
        "protected_source_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )


def _target_context(project_id: str) -> dict[str, Any]:
    return run_bench_fixture("target_persistence_context", {"project_id": project_id})


def _assert_print_snapshot(
    value: object, project_id: str, summary: Mapping[str, object]
) -> dict[str, Any]:
    require(
        isinstance(value, dict) and set(value) == _SNAPSHOT_KEYS,
        "P7-07 controlled snapshot shape drifted",
    )
    source = value.get("source")
    output = value.get("output")
    require(
        isinstance(source, dict)
        and source.get("sourceKind") == SOURCE_KIND
        and source.get("sourceGlobalId") == summary["globalId"]
        and source.get("sourceVersion") == summary["summaryVersion"]
        and isinstance(output, dict)
        and output.get("mimeType") == "application/pdf"
        and int(output.get("sizeBytes", 0)) > 0
        and _SHA256.fullmatch(str(output.get("sha256"))) is not None
        and value.get("actorUserId") == ACTOR_USER
        and value.get("language") == "en"
        and value.get("deliveryMode") == "controlled_pdf"
        and value.get("copyState") == "not_numbered"
        and value.get("watermarkSource") == WATERMARK_SOURCE,
        "P7-07 exact controlled snapshot truth drifted",
    )
    require_safe_payload(value, "P7-07 controlled snapshot response")
    return value


def _verify_idor_and_no_write(
    administrator,
    base_url: str,
    administrator_csrf: str,
    reviewer,
    reviewer_csrf: str,
    fixture_password: str,
    project_id: str,
    round_id: str,
    current: Mapping[str, Any],
) -> None:
    before = _target_context(project_id)
    cross_project = summary_request(
        administrator,
        base_url,
        summary_path(trial_runtime.second_project_id(administrator, base_url), round_id),
        query_key="cross-project",
    )
    absent = summary_request(
        administrator,
        base_url,
        summary_path(project_id, ABSENT_ID),
        query_key="absent-round",
    )
    validate_problem(cross_project, 404, "RELEASED_TRIAL_SUMMARY_UNAVAILABLE")
    validate_problem(absent, 404, "RELEASED_TRIAL_SUMMARY_UNAVAILABLE")
    require(
        {
            key: cross_project.body.get(key)
            for key in ("type", "title", "status", "code", "retryable")
        }
        == {
            key: absent.body.get(key)
            for key in ("type", "title", "status", "code", "retryable")
        },
        "P7-07 cross-Project and absent identities are distinguishable",
    )
    missing_summary = summary_request(
        reviewer,
        base_url,
        summary_path(project_id, round_id, ABSENT_ID),
        method="POST",
        payload=revise_payload(
            current["trialRound"],
            current["currentDecidedConclusion"],
            current["summaryRevisions"][-1],
            reason="P707 absent summary scope probe",
        ),
        csrf_token=reviewer_csrf,
        idempotency_key=f"{STALE_REVISE_KEY}-absent",
    )
    validate_problem(
        missing_summary, 404, "RELEASED_TRIAL_SUMMARY_UNAVAILABLE"
    )
    no_write = login(base_url, NO_WRITE_USER, fixture_password)
    no_write_csrf = bootstrap_csrf(no_write, base_url, NO_WRITE_USER)
    denied = summary_request(
        no_write,
        base_url,
        summary_stream_path(project_id, round_id, current["summaryRevisions"][-1]),
        method="POST",
        payload=revise_payload(
            current["trialRound"],
            current["currentDecidedConclusion"],
            current["summaryRevisions"][-1],
            reason="P707 no-write authority probe",
        ),
        csrf_token=no_write_csrf,
        idempotency_key=NO_WRITE_KEY,
    )
    validate_problem(denied, 403, "PERMISSION_DENIED")
    require(_target_context(project_id) == before, "P7-07 IDOR/no-write probe wrote data")


def run_fresh(
    administrator,
    base_url: str,
    administrator_csrf: str,
    fixture_password: str,
) -> dict[str, object]:
    schema = run_bench_fixture("verify_released_summary_schema", {})
    project_id, _plan_id, detail = trial_runtime.retained_detail(administrator, base_url)
    round_id = trial_runtime.require_uuid(
        next(
            value["globalId"]
            for value in detail["rounds"]
            if value.get("displayLabel") == "T1"
        ),
        "P7-07 review Round",
    )
    cumulative_before = run_bench_fixture(
        "cumulative_protected_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    reviewer = login(base_url, ACTOR_USER, fixture_password)
    reviewer_csrf = bootstrap_csrf(reviewer, base_url, ACTOR_USER)
    initial = _review_context(
        reviewer,
        base_url,
        project_id,
        round_id,
        state="analysis",
        round_version=10,
        conclusions=6,
    )
    submitted_approved = _submit(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id,
        round_id,
        initial,
        SUBMIT_APPROVED_KEY,
    )
    approved = _decide(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id,
        round_id,
        submitted_approved,
        DECIDE_APPROVED_KEY,
        "approved",
    )
    approved_review = trial_runtime.assert_review_workspace(
        HttpResult(201, {}, approved),
        project_id,
        round_id,
        state="approved",
        round_version=12,
        policies=1,
        comparisons=2,
        references=4,
        conclusions=8,
    )
    empty = assert_summary_workspace(
        summary_request(
            reviewer,
            base_url,
            summary_path(project_id, round_id),
            query_key="empty-approved",
        ),
        project_id,
        round_id,
        round_state="approved",
        round_version=12,
        revision_count=0,
        conclusion_state="approved",
    )
    before_retain_sources = _protected_sources(project_id)
    retain_request = retain_payload(
        empty["trialRound"], empty["currentDecidedConclusion"], reason=RETAIN_REASON
    )
    retained = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_path(project_id, round_id),
        retain_request,
        RETAIN_KEY,
    )
    retained_body = assert_summary_workspace(
        retained,
        project_id,
        round_id,
        round_state="approved",
        round_version=12,
        revision_count=1,
        conclusion_state="approved",
    )
    summary_v1 = retained_body["summaryRevisions"][0]
    require(
        summary_v1.get("conclusionState") == "approved"
        and summary_v1.get("conclusionRevisionGlobalId")
        == approved_review["conclusionRevisions"][-1]["globalId"],
        "P7-07 approved summary did not freeze exact conclusion v8",
    )
    replay = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_path(project_id, round_id),
        retain_request,
        RETAIN_KEY,
        replayed=True,
    )
    require(replay.body == retained.body, "P7-07 same-process retain replay drifted")
    conflict_payload = dict(retain_request)
    conflict_payload["reason"] = f"{RETAIN_REASON}-CONFLICT"
    conflict = summary_request(
        reviewer,
        base_url,
        summary_path(project_id, round_id),
        method="POST",
        payload=conflict_payload,
        csrf_token=reviewer_csrf,
        idempotency_key=RETAIN_KEY,
    )
    validate_problem(conflict, 409, "TRIAL_IDEMPOTENCY_CONFLICT")
    require(
        _protected_sources(project_id) == before_retain_sources,
        "P7-07 retain/replay mutated an upstream source",
    )

    mapping = run_bench_fixture(
        "provision_released_summary_mapping",
        {"project_id": project_id, "actor_user_id": ACTOR_USER},
    )
    capability = controlled_print_runtime.api_request(
        reviewer,
        base_url,
        capability_path(project_id, summary_v1),
        correlation_label="p707-capability",
    )
    require(
        capability.status == 200
        and capability.body.get("available") is True
        and capability.body.get("sourceKind") == SOURCE_KIND
        and capability.body.get("sourceGlobalId") == summary_v1["globalId"]
        and capability.body.get("sourceVersion") == 1
        and capability.body.get("registry", {}).get("globalId") == MAPPING_ID,
        "P7-07 exact controlled-print capability drifted",
    )
    before_print_sources = _protected_sources(project_id)
    printed = controlled_print_runtime.api_request(
        reviewer,
        base_url,
        controlled_print_runtime.controlled_print_path(project_id),
        method="POST",
        payload=controlled_print_payload(summary_v1),
        csrf_token=reviewer_csrf,
        idempotency_key=PRINT_KEY,
        correlation_label="p707-print",
    )
    require(
        printed.status == 201
        and printed.headers.get("Idempotency-Replayed") == "false",
        "P7-07 controlled print create failed",
    )
    printed_body = _assert_print_snapshot(printed.body, project_id, summary_v1)
    print_replay = controlled_print_runtime.api_request(
        reviewer,
        base_url,
        controlled_print_runtime.controlled_print_path(project_id),
        method="POST",
        payload=controlled_print_payload(summary_v1),
        csrf_token=reviewer_csrf,
        idempotency_key=PRINT_KEY,
        correlation_label="p707-print-replay",
    )
    require(
        print_replay.status == 201
        and print_replay.headers.get("Idempotency-Replayed") == "true"
        and print_replay.body == printed.body,
        "P7-07 same-process controlled-print replay drifted",
    )
    snapshot_id = str(printed_body["globalId"])
    content_path = (
        f"{controlled_print_runtime.controlled_print_path(project_id, snapshot_id)}/content"
    )
    first_pdf = controlled_print_runtime.download_request(
        reviewer, base_url, content_path, correlation_label="p707-download-v1"
    )
    output = printed_body["output"]
    require(
        first_pdf.status == 200
        and first_pdf.content.startswith(b"%PDF-")
        and hashlib.sha256(first_pdf.content).hexdigest() == output["sha256"]
        and len(first_pdf.content) == output["sizeBytes"]
        and first_pdf.headers.get("X-NPI-Snapshot-Hash")
        == printed_body["snapshotHash"]
        and first_pdf.headers.get("X-NPI-Output-Hash") == output["sha256"],
        "P7-07 exact controlled PDF response drifted",
    )
    require(
        _protected_sources(project_id) == before_print_sources,
        "P7-07 controlled print mutated an upstream source",
    )

    reopened_rejected = _reopen(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id,
        round_id,
        approved,
        REOPEN_REJECTED_KEY,
        "P707 reopen approved conclusion for rejected technical successor.",
    )
    submitted_rejected = _submit(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id,
        round_id,
        reopened_rejected,
        SUBMIT_REJECTED_KEY,
    )
    rejected = _decide(
        reviewer,
        base_url,
        reviewer_csrf,
        project_id,
        round_id,
        submitted_rejected,
        DECIDE_REJECTED_KEY,
        "rejected",
    )
    trial_runtime.assert_review_workspace(
        HttpResult(201, {}, rejected),
        project_id,
        round_id,
        state="rejected",
        round_version=15,
        policies=1,
        comparisons=2,
        references=4,
        conclusions=11,
    )
    current = assert_summary_workspace(
        summary_request(
            reviewer,
            base_url,
            summary_path(project_id, round_id),
            query_key="current-rejected",
        ),
        project_id,
        round_id,
        round_state="rejected",
        round_version=15,
        revision_count=1,
        conclusion_state="rejected",
    )
    before_revise_sources = _protected_sources(project_id)
    revise_request = revise_payload(
        current["trialRound"],
        current["currentDecidedConclusion"],
        summary_v1,
        reason=REVISE_REASON,
    )
    revised = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_stream_path(project_id, round_id, summary_v1),
        revise_request,
        REVISE_KEY,
    )
    revised_body = assert_summary_workspace(
        revised,
        project_id,
        round_id,
        round_state="rejected",
        round_version=15,
        revision_count=2,
        conclusion_state="rejected",
    )
    first, second = revised_body["summaryRevisions"]
    require(
        first == summary_v1
        and second.get("predecessorGlobalId") == first["globalId"]
        and second.get("predecessorSnapshotHash") == first["snapshotHash"]
        and second.get("conclusionState") == "rejected",
        "P7-07 rejected technical successor lineage drifted",
    )
    revised_replay = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_stream_path(project_id, round_id, summary_v1),
        revise_request,
        REVISE_KEY,
        replayed=True,
    )
    require(revised_replay.body == revised.body, "P7-07 revise replay drifted")
    before_failures = _target_context(project_id)
    stale = summary_request(
        reviewer,
        base_url,
        summary_stream_path(project_id, round_id, summary_v1),
        method="POST",
        payload=revise_request,
        csrf_token=reviewer_csrf,
        idempotency_key=STALE_REVISE_KEY,
    )
    validate_problem(stale, 409, "RELEASED_TRIAL_SUMMARY_CONFLICT")
    noop = summary_request(
        reviewer,
        base_url,
        summary_stream_path(project_id, round_id, second),
        method="POST",
        payload=revise_payload(
            revised_body["trialRound"],
            revised_body["currentDecidedConclusion"],
            second,
            reason="P707 reject a no-op summary successor",
        ),
        csrf_token=reviewer_csrf,
        idempotency_key=NOOP_REVISE_KEY,
    )
    validate_problem(noop, 409, "RELEASED_TRIAL_SUMMARY_CONFLICT")
    require(
        _target_context(project_id) == before_failures,
        "P7-07 stale/no-op failure did not roll back",
    )
    require(
        _protected_sources(project_id) == before_revise_sources,
        "P7-07 revise/replay mutated an upstream source",
    )
    post_revision_pdf = controlled_print_runtime.download_request(
        reviewer,
        base_url,
        content_path,
        correlation_label="p707-download-after-v2",
    )
    require(
        post_revision_pdf.status == 200
        and post_revision_pdf.content == first_pdf.content,
        "P7-07 retained summary v1 output followed summary v2",
    )
    detail_result = controlled_print_runtime.api_request(
        reviewer,
        base_url,
        controlled_print_runtime.controlled_print_path(project_id, snapshot_id),
        correlation_label="p707-print-detail-after-v2",
    )
    require(
        detail_result.status == 200 and detail_result.body == printed.body,
        "P7-07 retained controlled snapshot followed summary v2",
    )
    _verify_idor_and_no_write(
        administrator,
        base_url,
        administrator_csrf,
        reviewer,
        reviewer_csrf,
        fixture_password,
        project_id,
        round_id,
        revised_body,
    )
    before_generic = get_resource(
        administrator,
        base_url,
        "NPI Released Trial Summary Revision",
        second["globalId"],
    )
    update = update_resource(
        administrator,
        base_url,
        "NPI Released Trial Summary Revision",
        second["globalId"],
        {"snapshot_hash": "0" * 64},
        administrator_csrf,
    )
    delete = delete_resource(
        administrator,
        base_url,
        "NPI Released Trial Summary Revision",
        second["globalId"],
        administrator_csrf,
    )
    after_generic = get_resource(
        administrator,
        base_url,
        "NPI Released Trial Summary Revision",
        second["globalId"],
    )
    require(
        before_generic.status == after_generic.status == 200
        and update.status in {403, 417}
        and delete.status in {403, 417}
        and before_generic.body == after_generic.body,
        "P7-07 immutable summary accepted generic mutation",
    )
    retained = run_bench_fixture("retained_truth", {"project_id": project_id})
    cumulative_after = run_bench_fixture(
        "cumulative_protected_context",
        {"fixture_run_id": FIXTURE_RUN_ID, "project_id": project_id},
    )
    require(
        cumulative_after == cumulative_before,
        "P7-07 changed Gate/Project/Work/Tooling/Trial-source/integration truth",
    )
    return {
        "crossProcessReplayReady": True,
        "firstSummaryGlobalId": first["globalId"],
        "fixtureRunId": FIXTURE_RUN_ID,
        "mapping": mapping,
        "outputHash": retained["retainedOutputHash"],
        "outputSize": retained["retainedOutputSize"],
        "projectionSource": retained["projectionSource"],
        "projectGlobalId": project_id,
        "rejectedTechnicalSummaryRetained": True,
        "roundGlobalId": round_id,
        "snapshotGlobalId": snapshot_id,
        "summaryCount": 2,
    }


def route_disable_probe(
    reviewer,
    base_url: str,
    *,
    expected_mode: str,
) -> dict[str, object]:
    project_id, _plan_id, detail = trial_runtime.retained_detail(reviewer, base_url)
    round_id = next(
        value["globalId"]
        for value in detail["rounds"]
        if value.get("displayLabel") == "T1"
    )
    result = summary_request(
        reviewer,
        base_url,
        summary_path(project_id, round_id),
        query_key=f"route-{expected_mode}",
    )
    review = trial_runtime.trial_request(
        reviewer,
        base_url,
        trial_runtime.review_path(project_id, round_id),
        query_key=f"p707-predecessor-{expected_mode}",
    )
    trial_runtime.assert_review_workspace(
        review,
        project_id,
        round_id,
        state="rejected",
        round_version=15,
        policies=1,
        comparisons=2,
        references=4,
        conclusions=11,
    )
    if expected_mode == "disabled":
        validate_problem(result, 503, "RELEASED_TRIAL_SUMMARY_ROUTES_DISABLED")
    else:
        assert_summary_workspace(
            result,
            project_id,
            round_id,
            round_state="rejected",
            round_version=15,
            revision_count=2,
            conclusion_state="rejected",
        )
    return {"predecessorRouteRetained": True, "routeMode": expected_mode}


def run_replay_only(
    administrator,
    base_url: str,
    fixture_password: str,
) -> dict[str, object]:
    project_id, _plan_id, detail = trial_runtime.retained_detail(administrator, base_url)
    round_id = next(
        value["globalId"]
        for value in detail["rounds"]
        if value.get("displayLabel") == "T1"
    )
    retained = run_bench_fixture("retained_truth", {"project_id": project_id})
    summary_v1, summary_v2 = retained["summarySnapshots"]
    reviewer = login(base_url, ACTOR_USER, fixture_password)
    reviewer_csrf = bootstrap_csrf(reviewer, base_url, ACTOR_USER)
    retain_replay = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_path(project_id, round_id),
        retain_payload(
            {
                "optimisticVersion": summary_v1["trialRoundOptimisticVersion"],
                "snapshotHash": summary_v1["trialRoundSnapshotHash"],
            },
            {
                "globalId": summary_v1["conclusionRevisionGlobalId"],
                "conclusionVersion": summary_v1["conclusionVersion"],
                "snapshotHash": summary_v1["conclusionSnapshotHash"],
            },
            reason=summary_v1["reason"],
        ),
        RETAIN_KEY,
        replayed=True,
    )
    revise_replay = summary_command(
        reviewer,
        base_url,
        reviewer_csrf,
        summary_path(project_id, round_id, summary_v1["globalId"]),
        revise_payload(
            {
                "optimisticVersion": summary_v2["trialRoundOptimisticVersion"],
                "snapshotHash": summary_v2["trialRoundSnapshotHash"],
            },
            {
                "globalId": summary_v2["conclusionRevisionGlobalId"],
                "conclusionVersion": summary_v2["conclusionVersion"],
                "snapshotHash": summary_v2["conclusionSnapshotHash"],
            },
            summary_v1,
            reason=summary_v2["reason"],
        ),
        REVISE_KEY,
        replayed=True,
    )
    require(
        retain_replay.body
        == retained["summaryResponses"]["released_trial_summary.retain"]
        and revise_replay.body
        == retained["summaryResponses"]["released_trial_summary.revise"],
        "P7-07 cross-process summary replay drifted",
    )
    print_replay = controlled_print_runtime.api_request(
        reviewer,
        base_url,
        controlled_print_runtime.controlled_print_path(project_id),
        method="POST",
        payload=controlled_print_payload(summary_v1),
        csrf_token=reviewer_csrf,
        idempotency_key=PRINT_KEY,
        correlation_label="p707-cross-process-print",
    )
    require(
        print_replay.status == 201
        and print_replay.headers.get("Idempotency-Replayed") == "true"
        and print_replay.body == retained["printResponse"],
        "P7-07 cross-process controlled-print replay drifted",
    )
    snapshot_id = str(print_replay.body["globalId"])
    content = controlled_print_runtime.download_request(
        reviewer,
        base_url,
        (
            f"{controlled_print_runtime.controlled_print_path(project_id, snapshot_id)}"
            "/content"
        ),
        correlation_label="p707-cross-process-content",
    )
    require(
        content.status == 200
        and hashlib.sha256(content.content).hexdigest()
        == retained["retainedOutputHash"]
        and len(content.content) == retained["retainedOutputSize"],
        "P7-07 cross-process retained PDF drifted",
    )
    return {
        "crossProcessReplay": True,
        "projectGlobalId": project_id,
        "projectionSource": retained["projectionSource"],
        "retainedOutputHash": retained["retainedOutputHash"],
        "summaryCount": 2,
    }


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
            "P7-07 fixture invocation drifted",
        )
        kwargs = json.loads(arguments.fixture_kwargs)
        require(isinstance(kwargs, dict), "P7-07 fixture arguments are invalid")
        run_local_bench_fixture(arguments.bench_fixture, kwargs)
        return
    require(
        arguments.base_url is not None
        and os.environ.get(document_runtime.FIXTURE_RUN_ID_ENV) is not None
        and int(arguments.replay_only)
        + int(arguments.route_disable_probe is not None)
        <= 1,
        "P7-07 runtime invocation is incomplete",
    )
    administrator_password = secret_from_environment(
        "NPI_RUNTIME_ADMINISTRATOR_PASSWORD"
    )
    fixture_password = secret_from_environment("NPI_RUNTIME_FIXTURE_PASSWORD")
    base_url = validate_local_fixture_inputs(
        arguments.base_url,
        "Administrator",
        ACTOR_USER,
    )
    validate_local_fixture_inputs(
        base_url,
        "Administrator",
        UNRELATED_USER,
    )
    require(
        FIXTURE_RUN_ID != "0" * 32
        and ACTOR_USER.endswith("@example.invalid")
        and UNRELATED_USER.endswith("@example.invalid"),
        "P7-07 fixture namespace drifted",
    )
    administrator = login(base_url, "Administrator", administrator_password)
    if arguments.route_disable_probe is not None:
        reviewer = login(base_url, ACTOR_USER, fixture_password)
        result = route_disable_probe(
            reviewer,
            base_url,
            expected_mode=arguments.route_disable_probe,
        )
    elif arguments.replay_only:
        result = run_replay_only(administrator, base_url, fixture_password)
    else:
        administrator_csrf = bootstrap_csrf(
            administrator, base_url, "Administrator"
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
