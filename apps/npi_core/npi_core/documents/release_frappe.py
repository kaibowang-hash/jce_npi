from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.documents.release_domain import (
    DocumentReleaseFileEvidence,
    DocumentReleasePolicyState,
    DocumentReleasePolicyVersion,
    DocumentReviewEvidence,
    DocumentReviewerAssignment,
)
from npi_core.foundation.errors import RequestValidationFailed


def release_policy_value(document: Any) -> DocumentReleasePolicyVersion:
    return DocumentReleasePolicyVersion(
        global_id=_value(document, "global_id"),
        policy_global_id=_value(document, "policy_global_id"),
        tenant_id=_value(document, "tenant_id"),
        project_global_id=_value(document, "project_global_id"),
        policy_key=_value(document, "policy_key"),
        policy_version=_integer(_value(document, "policy_version")),
        title=_value(document, "title"),
        state=DocumentReleasePolicyState(
            str(_value(document, "publication_state") or "draft")
        ),
        submitter_user_ids=tuple(
            str(value) for value in _json_array(_value(document, "submitter_user_ids"))
        ),
        reviewer_assignments=tuple(
            DocumentReviewerAssignment(
                slot_key=value.get("slotKey"),
                user_id=value.get("userId"),
            )
            for value in _reviewer_rows(
                _value(document, "reviewer_assignments")
            )
        ),
        required_approval_count=_integer(
            _value(document, "required_approval_count")
        ),
        release_authority_user_ids=tuple(
            str(value)
            for value in _json_array(
                _value(document, "release_authority_user_ids")
            )
        ),
        supersede_authority_user_ids=tuple(
            str(value)
            for value in _json_array(
                _value(document, "supersede_authority_user_ids")
            )
        ),
        obsolete_authority_user_ids=tuple(
            str(value)
            for value in _json_array(
                _value(document, "obsolete_authority_user_ids")
            )
        ),
        confirmation_method=str(_value(document, "confirmation_method")),
        required_scan_state=str(_value(document, "required_scan_state")),
        require_live_private_identity=_checkbox(
            _value(document, "require_live_private_identity")
        ),
        require_sha256_match=_checkbox(
            _value(document, "require_sha256_match")
        ),
        supersede_requires_released_successor=_checkbox(
            _value(document, "supersede_requires_released_successor")
        ),
        supersede_requires_later_revision=_checkbox(
            _value(document, "supersede_requires_later_revision")
        ),
        supersede_requires_successor_effective_date=_checkbox(
            _value(document, "supersede_requires_successor_effective_date")
        ),
        snapshot_hash=str(_value(document, "snapshot_hash") or ""),
    )


def review_evidence_value(value: object) -> DocumentReviewEvidence:
    prepared = _json_object(value)
    if set(prepared) != {"revisionGlobalId", "revisionSnapshotHash", "files"}:
        raise RequestValidationFailed(
            [{"path": "reviewEvidence", "message": _("Enter valid review evidence.")}]
        )
    files = prepared.get("files")
    if not isinstance(files, list):
        raise RequestValidationFailed(
            [
                {
                    "path": "reviewEvidence.files",
                    "message": _("Enter valid file evidence."),
                }
            ]
        )
    return DocumentReviewEvidence(
        revision_global_id=prepared.get("revisionGlobalId"),
        revision_snapshot_hash=prepared.get("revisionSnapshotHash"),
        files=tuple(_release_file_evidence(item) for item in files),
    )


def protect_released_document_file(
    document: Any,
    method: str | None = None,
) -> None:
    """Prevent deletion of a binary retained by an exact released File Revision."""
    del method
    file_id = str(_value(document, "name") or "").strip()
    if not file_id:
        frappe.throw(
            _("Released document content cannot be deleted."),
            frappe.PermissionError,
        )
    retained = frappe.db.get_value(
        "NPI File Revision",
        {"frappe_file_id": file_id, "released": 1},
        "name",
    )
    if retained:
        frappe.throw(
            _("Released document content cannot be deleted."),
            frappe.PermissionError,
        )


def validate_internal_policy_users(user_ids: tuple[str, ...]) -> None:
    for user_id in user_ids:
        row = frappe.db.get_value(
            "User",
            user_id,
            ["name", "enabled", "user_type"],
            as_dict=True,
        )
        if (
            not row
            or str(_value(row, "name")).casefold() != user_id.casefold()
            or int(_value(row, "enabled") or 0) != 1
            or str(_value(row, "user_type")) != "System User"
        ):
            frappe.throw(
                _("Release policy users must be enabled internal system users."),
                frappe.ValidationError,
            )


def _release_file_evidence(value: object) -> DocumentReleaseFileEvidence:
    if not isinstance(value, dict) or set(value) != {
        "associationGlobalId",
        "associationSnapshotHash",
        "fileRevisionGlobalId",
        "fileDocumentGlobalId",
        "fileOptimisticVersion",
        "fileIdentity",
        "frappeContentHash",
        "fileName",
        "mimeType",
        "sizeBytes",
        "sha256",
        "scanState",
        "scanObservedAt",
        "uploadedByUserId",
        "uploadedAt",
    }:
        raise RequestValidationFailed(
            [
                {
                    "path": "reviewEvidence.files",
                    "message": _("Enter valid file evidence."),
                }
            ]
        )
    return DocumentReleaseFileEvidence(
        association_global_id=value.get("associationGlobalId"),
        association_snapshot_hash=value.get("associationSnapshotHash"),
        file_revision_global_id=value.get("fileRevisionGlobalId"),
        file_document_global_id=value.get("fileDocumentGlobalId"),
        file_optimistic_version=value.get("fileOptimisticVersion"),
        frappe_file_id=value.get("fileIdentity"),
        frappe_content_hash=value.get("frappeContentHash"),
        file_name=value.get("fileName"),
        mime_type=value.get("mimeType"),
        size_bytes=value.get("sizeBytes"),
        sha256=value.get("sha256"),
        scan_state=value.get("scanState"),
        scan_observed_at=_datetime(value.get("scanObservedAt")),
        uploaded_by_user_id=value.get("uploadedByUserId"),
        uploaded_at=_datetime(value.get("uploadedAt")),
    )


def _reviewer_rows(value: object) -> tuple[dict[str, object], ...]:
    prepared = _json_array(value)
    if not all(
        isinstance(item, dict) and set(item) == {"slotKey", "userId"}
        for item in prepared
    ):
        raise RequestValidationFailed(
            [
                {
                    "path": "releasePolicy.reviewerAssignments",
                    "message": _("Enter valid reviewer assignments."),
                }
            ]
        )
    return tuple(prepared)


def _json_array(value: object) -> list[object]:
    import json

    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        raise ValueError("Expected a JSON array.")
    prepared = json.loads(value)
    if not isinstance(prepared, list):
        raise ValueError("Expected a JSON array.")
    return prepared


def _json_object(value: object) -> dict[str, object]:
    import json

    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("Expected a JSON object.")
    prepared = json.loads(value)
    if not isinstance(prepared, dict):
        raise ValueError("Expected a JSON object.")
    return prepared


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _integer(value: object) -> int:
    if type(value) is bool:
        raise ValueError("Expected an integer.")
    return int(value)


def _checkbox(value: object) -> bool:
    if type(value) not in {int, bool} or int(value) not in {0, 1}:
        raise ValueError("Expected a checkbox value.")
    return int(value) == 1


def _value(document: object, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    return getter(fieldname) if callable(getter) else getattr(document, fieldname, None)
