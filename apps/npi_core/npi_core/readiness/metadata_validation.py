from __future__ import annotations

import re
from typing import Any, Callable, TypeVar

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    canonical_json,
    canonical_uuid,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    optional_uuid,
    require_exact_parent,
    tenant_text,
)
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.readiness.domain import instance_from_snapshot, template_from_snapshot


_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_T = TypeVar("_T")


def canonical_readiness_identity(document: Any) -> None:
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.name = document.global_id


def normalize_template_root(document: Any) -> None:
    canonical_readiness_identity(document)
    code = str(document.template_code or "").strip()
    title = str(document.title or "").strip()
    if _CODE.fullmatch(code) is None:
        frappe.throw(_("Enter a valid NPI Readiness Template code."), frappe.ValidationError)
    if not title or len(title) > 200:
        frappe.throw(_("Enter a valid NPI Readiness Template title."), frappe.ValidationError)
    if int(document.optimistic_version or 0) < 1:
        frappe.throw(_("Enter a positive optimistic version."), frappe.ValidationError)
    document.template_code = code
    document.title = title
    document.enabled = int(bool(document.enabled))


def normalize_template_version_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("template_global_id", _("NPI Readiness Template Global ID")),
            ("request_id", _("Request ID")),
        ),
    )


def validate_template_version_document(document: Any) -> None:
    supplied = json_object(document.template_snapshot, _("NPI Readiness Template Version Snapshot"))
    value = _domain_value(lambda: template_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.template_global_id),
        value.template_code,
        value.template_version,
        value.optimistic_version,
        value.title,
        value.publication_state.value,
        value.changed_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.template_global_id,
        document.template_code,
        int(document.template_version),
        int(document.optimistic_version),
        document.title,
        document.publication_state,
        document.changed_by_user_id,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("NPI Readiness Template fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    require_exact_parent(
        "NPI Readiness Template",
        str(value.template_global_id),
        {"global_id": str(value.template_global_id), "template_code": value.template_code},
        _("The NPI Readiness Template is unavailable."),
    )
    _expect_json(document.applicability_snapshot, value.applicability.snapshot_payload(), _("Readiness Applicability Snapshot"))
    _expect_array(document.category_snapshot, [item.snapshot_payload() for item in value.categories], _("Readiness Category Snapshot"))
    _expect_array(document.item_snapshot, [item.snapshot_payload() for item in value.items], _("Readiness Item Definition Snapshot"))
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("NPI Readiness Template Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("NPI Readiness Template Snapshot Hash does not match."), frappe.ValidationError)
    document.template = str(value.template_global_id)
    document.version_key_hash = value.version_key_hash
    document.changed_at = frappe_utc_datetime_text(value.changed_at, _("Changed At"))
    document.applicability_snapshot = canonical_json(value.applicability.snapshot_payload())
    document.category_snapshot = canonical_json([item.snapshot_payload() for item in value.categories])
    document.item_snapshot = canonical_json([item.snapshot_payload() for item in value.items])
    document.template_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def normalize_instance_identity(document: Any) -> None:
    _normalize_identity(
        document,
        (
            ("global_id", _("Global ID")),
            ("instance_global_id", _("NPI Readiness Instance Global ID")),
            ("project_global_id", _("Project Global ID")),
            ("template_revision_global_id", _("NPI Readiness Template Revision Global ID")),
            ("request_id", _("Request ID")),
        ),
        (("predecessor_global_id", _("Predecessor NPI Readiness Revision Global ID")),),
    )


def validate_instance_document(document: Any) -> None:
    supplied = json_object(document.instance_snapshot, _("NPI Readiness Instance Revision Snapshot"))
    value = _domain_value(lambda: instance_from_snapshot(supplied))
    expected = (
        str(value.global_id),
        str(value.instance_global_id),
        value.tenant_id,
        str(value.project.global_id),
        value.project.optimistic_version,
        value.project.snapshot_hash,
        str(value.template_revision.global_id),
        value.template_revision.version,
        value.template_revision.snapshot_hash,
        value.instance_version,
        str(value.predecessor_global_id) if value.predecessor_global_id else None,
        value.predecessor_snapshot_hash,
        value.created_by_user_id,
        str(value.request_id),
        value.trace_id,
    )
    actual = (
        document.global_id,
        document.instance_global_id,
        document.tenant_id,
        document.project_global_id,
        int(document.project_optimistic_version),
        document.project_snapshot_hash,
        document.template_revision_global_id,
        int(document.template_version),
        document.template_snapshot_hash,
        int(document.instance_version),
        document.predecessor_global_id or None,
        document.predecessor_snapshot_hash or None,
        document.created_by_user_id,
        document.request_id,
        document.trace_id,
    )
    if actual != expected:
        frappe.throw(
            _("NPI Readiness Instance fields do not match the exact snapshot."),
            frappe.ValidationError,
        )
    require_exact_parent(
        "NPI Engineering Project",
        str(value.project.global_id),
        {"global_id": str(value.project.global_id), "tenant_id": value.tenant_id},
        _("The Project is unavailable for this NPI Readiness Instance."),
    )
    require_exact_parent(
        "NPI Readiness Template Version",
        str(value.template_revision.global_id),
        {
            "global_id": str(value.template_revision.global_id),
            "template_version": value.template_revision.version,
            "snapshot_hash": value.template_revision.snapshot_hash,
            "publication_state": "published",
        },
        _("The published NPI Readiness Template version is unavailable."),
    )
    if value.predecessor_global_id is not None:
        require_exact_parent(
            "NPI Readiness Instance Revision",
            str(value.predecessor_global_id),
            {
                "global_id": str(value.predecessor_global_id),
                "instance_global_id": str(value.instance_global_id),
                "instance_version": value.instance_version - 1,
                "snapshot_hash": value.predecessor_snapshot_hash,
            },
            _("The predecessor NPI Readiness revision is unavailable."),
        )
    _expect_json(document.project_snapshot, value.project.snapshot_payload(), _("Readiness Project Snapshot"))
    _expect_array(document.category_snapshot, [item.snapshot_payload() for item in value.categories], _("Readiness Category Snapshot"))
    _expect_array(document.item_snapshot, [item.snapshot_payload() for item in value.items], _("Readiness Item Snapshot"))
    _expect_json(document.evaluation_snapshot, value.evaluation.snapshot_payload(), _("Readiness Evaluation Snapshot"))
    if document.version_key_hash not in (None, "", value.version_key_hash):
        frappe.throw(_("NPI Readiness Instance Version Key Hash does not match."), frappe.ValidationError)
    if document.snapshot_hash not in (None, "", value.snapshot_hash):
        frappe.throw(_("NPI Readiness Instance Snapshot Hash does not match."), frappe.ValidationError)
    document.project = str(value.project.global_id)
    document.template_revision = str(value.template_revision.global_id)
    document.predecessor_revision = str(value.predecessor_global_id) if value.predecessor_global_id else None
    document.version_key_hash = value.version_key_hash
    document.project_snapshot = canonical_json(value.project.snapshot_payload())
    document.category_snapshot = canonical_json([item.snapshot_payload() for item in value.categories])
    document.item_snapshot = canonical_json([item.snapshot_payload() for item in value.items])
    document.evaluation_snapshot = canonical_json(value.evaluation.snapshot_payload())
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.instance_snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = lowercase_sha256(value.snapshot_hash, _("Snapshot Hash"))


def _normalize_identity(
    document: Any,
    required: tuple[tuple[str, str], ...],
    optional: tuple[tuple[str, str], ...] = (),
) -> None:
    for fieldname, label in required:
        setattr(document, fieldname, canonical_uuid(getattr(document, fieldname), label))
    for fieldname, label in optional:
        setattr(document, fieldname, optional_uuid(getattr(document, fieldname), label))
    if hasattr(document, "tenant_id"):
        document.tenant_id = tenant_text(document.tenant_id)
    document.name = document.global_id


def _domain_value(factory: Callable[[], _T]) -> _T:
    try:
        return factory()
    except (RequestValidationFailed, ValueError, TypeError, KeyError) as error:
        message = error.title if isinstance(error, RequestValidationFailed) else _("Enter a valid immutable readiness snapshot.")
        if isinstance(error, RequestValidationFailed) and error.field_errors:
            candidate = error.field_errors[0].get("message")
            if isinstance(candidate, str) and candidate:
                message = candidate
        frappe.throw(message, frappe.ValidationError)
    raise AssertionError("Frappe validation must raise.")


def _expect_json(value: object, expected: object, label: str) -> None:
    if json_object(value, label) != expected:
        frappe.throw(_("Stored JSON does not match the exact readiness snapshot."), frappe.ValidationError)


def _expect_array(value: object, expected: list[object], label: str) -> None:
    if json_array(value, label) != expected:
        frappe.throw(_("Stored list does not match the exact readiness snapshot."), frappe.ValidationError)
