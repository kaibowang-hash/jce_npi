from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
from uuid import UUID

import frappe
from frappe import _

from npi_core.documents.baseline_domain import (
    BaselineGateDependency,
    BaselineImpactEvent,
    BaselineImpactEventType,
    DocumentBaselineMember,
    DocumentBaselinePolicyState,
    DocumentBaselinePolicyVersion,
)
from npi_core.documents.release_frappe import review_evidence_value


DOCUMENT_BASELINE_COMMAND_FLAG = "npi_document_baseline_command_write"
BASELINE_DEPENDENCY_SYSTEM_FLAG = "npi_baseline_dependency_system_write"


def require_document_baseline_command_write() -> None:
    if not getattr(frappe.flags, DOCUMENT_BASELINE_COMMAND_FLAG, False):
        frappe.throw(
            _(
                "Document baselines can only be changed through an authorized "
                "NPI baseline command."
            ),
            frappe.PermissionError,
        )


def require_baseline_dependency_system_write() -> None:
    if not getattr(frappe.flags, BASELINE_DEPENDENCY_SYSTEM_FLAG, False):
        frappe.throw(
            _(
                "Baseline dependencies can only be changed through authorized "
                "Gate and revision commands."
            ),
            frappe.PermissionError,
        )


@contextmanager
def document_baseline_command_write() -> Iterator[None]:
    with _flag_scope(DOCUMENT_BASELINE_COMMAND_FLAG):
        yield


@contextmanager
def baseline_dependency_system_write() -> Iterator[None]:
    with _flag_scope(BASELINE_DEPENDENCY_SYSTEM_FLAG):
        yield


def baseline_policy_value(document: Any) -> DocumentBaselinePolicyVersion:
    try:
        state = DocumentBaselinePolicyState(
            str(_value(document, "publication_state") or "draft")
        )
    except ValueError:
        frappe.throw(
            _("Select a supported baseline policy publication state."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    return DocumentBaselinePolicyVersion(
        global_id=_uuid(_value(document, "global_id")),
        policy_global_id=_uuid(_value(document, "policy_global_id")),
        tenant_id=_value(document, "tenant_id"),
        project_global_id=_uuid(_value(document, "project_global_id")),
        policy_key=_value(document, "policy_key"),
        policy_version=_integer(_value(document, "policy_version")),
        title=_value(document, "title"),
        state=state,
        baseline_authority_user_ids=tuple(
            str(value)
            for value in _json_array(
                _value(document, "baseline_authority_user_ids")
            )
        ),
        snapshot_hash=str(_value(document, "snapshot_hash") or ""),
    )


def baseline_member_value(document: Any) -> DocumentBaselineMember:
    return DocumentBaselineMember(
        global_id=_uuid(_value(document, "global_id")),
        sequence=_integer(_value(document, "member_sequence")),
        document_global_id=_uuid(_value(document, "document_global_id")),
        revision_global_id=_uuid(_value(document, "revision_global_id")),
        major=_integer(_value(document, "major")),
        minor=_integer(_value(document, "minor")),
        revision_snapshot_hash=_value(document, "revision_snapshot_hash"),
        lifecycle_version=_integer(_value(document, "lifecycle_version")),
        release_event_global_id=_uuid(_value(document, "release_event_global_id")),
        release_snapshot_hash=_value(document, "release_snapshot_hash"),
        release_evidence=review_evidence_value(
            _value(document, "release_evidence")
        ),
    )


def baseline_dependency_value(document: Any) -> BaselineGateDependency:
    return BaselineGateDependency(
        global_id=_uuid(_value(document, "global_id")),
        tenant_id=_value(document, "tenant_id"),
        project_global_id=_uuid(_value(document, "project_global_id")),
        baseline_global_id=_uuid(_value(document, "baseline_global_id")),
        baseline_snapshot_hash=_value(document, "baseline_snapshot_hash"),
        input_document_global_id=_uuid(_value(document, "input_document_global_id")),
        input_revision_global_id=_uuid(_value(document, "input_revision_global_id")),
        input_revision_snapshot_hash=_value(
            document,
            "input_revision_snapshot_hash",
        ),
        gate_global_id=_uuid(_value(document, "gate_global_id")),
        requirement_global_id=_uuid(_value(document, "requirement_global_id")),
        requirement_key=_value(document, "requirement_key"),
        evidence_reference_global_id=_uuid(
            _value(document, "evidence_reference_global_id")
        ),
        registered_by_user_id=_value(document, "registered_by_user_id"),
        registered_at=_datetime(_value(document, "registered_at")),
        request_id=_value(document, "request_id"),
        trace_id=_value(document, "trace_id"),
        dependency_key=str(_value(document, "dependency_key") or ""),
        snapshot_hash=str(_value(document, "snapshot_hash") or ""),
    )


def baseline_impact_value(document: Any) -> BaselineImpactEvent:
    try:
        event_type = BaselineImpactEventType(str(_value(document, "event_type")))
    except ValueError:
        frappe.throw(
            _("Select a supported baseline impact event."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    return BaselineImpactEvent(
        global_id=_uuid(_value(document, "global_id")),
        tenant_id=_value(document, "tenant_id"),
        project_global_id=_uuid(_value(document, "project_global_id")),
        dependency_global_id=_uuid(_value(document, "dependency_global_id")),
        baseline_global_id=_uuid(_value(document, "baseline_global_id")),
        baseline_snapshot_hash=_value(document, "baseline_snapshot_hash"),
        old_revision_global_id=_uuid(_value(document, "old_revision_global_id")),
        old_revision_snapshot_hash=_value(
            document,
            "old_revision_snapshot_hash",
        ),
        new_revision_global_id=_uuid(_value(document, "new_revision_global_id")),
        new_revision_snapshot_hash=_value(
            document,
            "new_revision_snapshot_hash",
        ),
        gate_global_id=_uuid(_value(document, "gate_global_id")),
        requirement_global_id=_uuid(_value(document, "requirement_global_id")),
        evidence_reference_global_id=_uuid(
            _value(document, "evidence_reference_global_id")
        ),
        initiated_by_user_id=_value(document, "initiated_by_user_id"),
        occurred_at=_datetime(_value(document, "occurred_at")),
        request_id=_value(document, "request_id"),
        trace_id=_value(document, "trace_id"),
        event_type=event_type,
        impact_key=str(_value(document, "impact_key") or ""),
        event_hash=str(_value(document, "event_hash") or ""),
    )


@contextmanager
def _flag_scope(flag_name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, flag_name, missing)
    setattr(frappe.flags, flag_name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, flag_name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, flag_name, previous)


def _value(document: Any, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    return getter(fieldname) if callable(getter) else getattr(document, fieldname, None)


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return UUID(int=0)


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    frappe.throw(
        _("Enter a valid date and time."),
        frappe.ValidationError,
    )
    raise AssertionError("Frappe validation must raise.")


def _json_array(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return parsed
    frappe.throw(
        _("Enter a valid JSON array."),
        frappe.ValidationError,
    )
    raise AssertionError("Frappe validation must raise.")
