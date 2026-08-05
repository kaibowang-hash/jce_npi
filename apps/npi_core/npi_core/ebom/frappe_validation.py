from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator
from uuid import UUID

import frappe
from frappe import _

from npi_core.documents.frappe_validation import (
    canonical_json,
    json_array,
    json_object,
)
from npi_core.ebom.domain import (
    EngineeringBomLine,
    EngineeringBomPolicyState,
    EngineeringBomPolicyVersion,
)
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.tracing import resolve_trace_id


EBOM_POLICY_WRITE_FLAG = "npi_ebom_policy_write"
EBOM_COMMAND_WRITE_FLAG = "npi_ebom_command_write"
EBOM_LIFECYCLE_WRITE_FLAG = "npi_ebom_lifecycle_command_write"


def require_ebom_policy_write() -> None:
    if not getattr(frappe.flags, EBOM_POLICY_WRITE_FLAG, False):
        frappe.throw(
            _("EBOM policy versions can only be changed through authorized administration."),
            frappe.PermissionError,
        )


def require_ebom_command_write() -> None:
    if not getattr(frappe.flags, EBOM_COMMAND_WRITE_FLAG, False):
        frappe.throw(
            _("EBOM revisions can only be changed through an authorized NPI command."),
            frappe.PermissionError,
        )


def require_ebom_lifecycle_write() -> None:
    if not getattr(frappe.flags, EBOM_LIFECYCLE_WRITE_FLAG, False):
        frappe.throw(
            _("EBOM review and release history can only be changed through an authorized NPI command."),
            frappe.PermissionError,
        )


@contextmanager
def ebom_policy_write() -> Iterator[None]:
    with _flag_scope(EBOM_POLICY_WRITE_FLAG):
        yield


@contextmanager
def ebom_command_write() -> Iterator[None]:
    with _flag_scope(EBOM_COMMAND_WRITE_FLAG):
        yield


@contextmanager
def ebom_lifecycle_write() -> Iterator[None]:
    with _flag_scope(EBOM_LIFECYCLE_WRITE_FLAG):
        yield


@contextmanager
def ebom_domain_validation() -> Iterator[None]:
    try:
        yield
    except RequestValidationFailed as error:
        message = error.title
        if error.field_errors:
            candidate = error.field_errors[0].get("message")
            if isinstance(candidate, str) and candidate:
                message = candidate
        frappe.throw(message, frappe.ValidationError)


def ebom_domain_value(factory: Any) -> Any:
    with ebom_domain_validation():
        return factory()
    raise AssertionError("Frappe validation must raise.")


def ebom_policy_value(document: Any) -> EngineeringBomPolicyVersion:
    try:
        state = EngineeringBomPolicyState(
            str(_value(document, "publication_state") or "draft")
        )
    except ValueError:
        frappe.throw(
            _("Select a supported EBOM policy publication state."),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    return EngineeringBomPolicyVersion(
        global_id=_uuid(_value(document, "global_id")),
        policy_global_id=_uuid(_value(document, "policy_global_id")),
        tenant_id=_value(document, "tenant_id"),
        project_global_id=_uuid(_value(document, "project_global_id")),
        policy_key=_value(document, "policy_key"),
        policy_version=_integer(_value(document, "policy_version")),
        title=_value(document, "title"),
        state=state,
        synthetic_namespace=_value(document, "synthetic_namespace"),
        quantity_scale=_integer(_value(document, "quantity_scale")),
        maximum_nodes=_integer(_value(document, "maximum_nodes")),
        engineering_uoms=tuple(
            str(value)
            for value in json_array(
                _value(document, "engineering_uoms"),
                _("Engineering UOM Allowlist"),
            )
        ),
        attribute_keys=tuple(
            str(value)
            for value in json_array(
                _value(document, "attribute_keys"),
                _("Controlled Attribute Keys"),
            )
        ),
        creator_user_ids=_user_ids(document, "creator_user_ids", _("Creator User IDs")),
        review_submitter_user_ids=_user_ids(
            document,
            "review_submitter_user_ids",
            _("Review Submitter User IDs"),
        ),
        reviewer_user_ids=_user_ids(document, "reviewer_user_ids", _("Reviewer User IDs")),
        release_authority_user_ids=_user_ids(
            document,
            "release_authority_user_ids",
            _("Release Authority User IDs"),
        ),
        line_identity_mode=str(_value(document, "line_identity_mode") or ""),
        require_acyclic_graph=_checkbox(_value(document, "require_acyclic_graph")),
        require_closed_alternates=_checkbox(
            _value(document, "require_closed_alternates")
        ),
        require_effectivity_order=_checkbox(
            _value(document, "require_effectivity_order")
        ),
        snapshot_hash=str(_value(document, "snapshot_hash") or ""),
    )


def ebom_line_value(value: object) -> EngineeringBomLine:
    item = json_object(value, _("Canonical EBOM Line Snapshot"))
    expected = {
        "globalId",
        "lineKey",
        "parentLineKey",
        "engineeringItemId",
        "description",
        "quantity",
        "engineeringUom",
        "alternateForLineKey",
        "alternateGroupKey",
        "effectivityStart",
        "effectivityEnd",
        "attributes",
    }
    if set(item) != expected:
        frappe.throw(
            _("Canonical EBOM Line Snapshot contains unsupported fields."),
            frappe.ValidationError,
        )
    attributes = json_object(item.get("attributes"), _("Controlled Attributes"))
    return EngineeringBomLine(
        global_id=_uuid(item.get("globalId")),
        line_key=item.get("lineKey"),
        parent_line_key=item.get("parentLineKey"),
        engineering_item_id=item.get("engineeringItemId"),
        description=item.get("description"),
        quantity=_decimal(item.get("quantity")),
        engineering_uom=item.get("engineeringUom"),
        alternate_for_line_key=item.get("alternateForLineKey"),
        alternate_group_key=item.get("alternateGroupKey"),
        effectivity_start=_date(item.get("effectivityStart")),
        effectivity_end=_date(item.get("effectivityEnd")),
        attributes=tuple((str(key), str(item)) for key, item in attributes.items()),
    )


def canonical_line_snapshot(line: EngineeringBomLine, quantity_scale: int) -> str:
    return canonical_json(line.canonical_dict(quantity_scale))


def deny_ebom_history_update() -> None:
    frappe.throw(_("EBOM history cannot be changed."), frappe.PermissionError)


def validate_internal_ebom_policy_users(user_ids: tuple[str, ...]) -> None:
    for user_id in user_ids:
        row = frappe.db.get_value(
            "User",
            user_id,
            ["name", "enabled", "user_type"],
            as_dict=True,
        )
        try:
            enabled = int(_value(row, "enabled") or 0) if row else 0
        except (TypeError, ValueError):
            enabled = 0
        if (
            not row
            or str(_value(row, "name")).casefold() != user_id.casefold()
            or enabled != 1
            or str(_value(row, "user_type")) != "System User"
        ):
            frappe.throw(
                _("EBOM policy users must be enabled internal system users."),
                frappe.ValidationError,
            )


def deny_ebom_history_delete(
    document: object | None = None,
    *,
    target_global_id: object | None = None,
    target_version: object = 1,
) -> None:
    if document is not None:
        _queue_ebom_history_delete_attempt(
            document,
            target_global_id=target_global_id,
            target_version=target_version,
        )
    frappe.throw(_("EBOM history cannot be deleted."), frappe.PermissionError)


def _queue_ebom_history_delete_attempt(
    document: object,
    *,
    target_global_id: object | None,
    target_version: object,
) -> None:
    doctype = str(_value(document, "doctype") or "").strip()
    global_id = (
        _audit_uuid(target_global_id)
        or _audit_uuid(_value(document, "global_id"))
        or _audit_uuid(_value(document, "name"))
    )
    try:
        object_version = 0 if isinstance(target_version, bool) else int(target_version)
    except (TypeError, ValueError):
        object_version = 0
    if not doctype or global_id is None or object_version < 1:
        return
    actor = str(getattr(getattr(frappe, "session", None), "user", None) or "Guest")
    trace_id = resolve_trace_id(_trace_header())
    event = create_audit_event(
        actor=actor,
        trace_id=trace_id,
        operation="ebom.history.delete_attempt",
        global_id=global_id,
        object_version=object_version,
        result="denied",
        input_summary={"doctype": doctype},
    )
    values: dict[str, object] = {
        "doctype": "NPI Audit Event",
        "event_id": str(event.event_id),
        "global_id": str(event.global_id),
        "object_version": event.object_version,
        "actor": event.actor,
        "trace_id": event.trace_id,
        "operation": event.operation,
        "result": event.result,
        "input_summary": dict(event.input_summary),
    }

    def persist_after_rollback() -> None:
        missing = object()
        previous = getattr(frappe.flags, "npi_audit_append", missing)
        frappe.flags.npi_audit_append = True
        try:
            frappe.get_doc(dict(values)).insert()
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            raise
        finally:
            if previous is missing:
                try:
                    delattr(frappe.flags, "npi_audit_append")
                except AttributeError:
                    pass
            else:
                frappe.flags.npi_audit_append = previous

    frappe.db.after_rollback.add(persist_after_rollback)


def _trace_header() -> str | None:
    getter = getattr(frappe, "get_request_header", None)
    if not callable(getter):
        return None
    try:
        value = getter("X-Trace-ID")
    except (AttributeError, RuntimeError):
        return None
    return value if isinstance(value, str) else None


def _audit_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


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


def _user_ids(document: Any, fieldname: str, label: str) -> tuple[str, ...]:
    return tuple(
        str(value) for value in json_array(_value(document, fieldname), label)
    )


def _checkbox(value: object) -> bool:
    return type(value) in {int, bool} and int(value) == 1


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


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("NaN")


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        frappe.throw(_("Enter a valid effectivity date."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise.")


def _value(document: Any, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    return getter(fieldname) if callable(getter) else getattr(document, fieldname, None)
