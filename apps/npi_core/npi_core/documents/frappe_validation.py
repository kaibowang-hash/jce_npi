from __future__ import annotations

import json
import re
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Callable, Iterator, Mapping, TypeVar
from uuid import UUID

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.foundation.tracing import resolve_trace_id


DOCUMENT_COMMAND_FLAG = "npi_document_command_write"
DOCUMENT_POLICY_FLAG = "npi_document_policy_write"
DOCUMENT_RELEASE_COMMAND_FLAG = "npi_document_release_command_write"
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_DIAGNOSTIC_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_PROJECTION_VALIDATION_DIAGNOSTIC_FLAG = (
    "npi_document_projection_validation_diagnostic"
)
PROJECTION_VALIDATION_DIAGNOSTIC_CODES = frozenset(
    {
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_INPUT",
        "DOCUMENT_CHECKOUT_PROJECTION_IMMUTABLE_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_POLICY_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_DOMAIN_RECONSTRUCTION",
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_IDENTITY",
        "DOCUMENT_CHECKOUT_PROJECTION_VERSION",
        "DOCUMENT_CHECKOUT_PROJECTION_REVISION",
        "DOCUMENT_CHECKOUT_PROJECTION_LOCK",
        "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_PROJECTION",
        "DOCUMENT_CHECKOUT_PROJECTION_COMMAND_GUARD",
        "DOCUMENT_CHECKOUT_PROJECTION_FRAPPE_STANDARD_VALIDATION",
        "DOCUMENT_CHECKOUT_PROJECTION_POST_SAVE_HOOK",
        "DOCUMENT_CHECKOUT_PROJECTION_SAVE_LIFECYCLE",
    }
)
_T = TypeVar("_T")


def require_document_command_write() -> None:
    if not getattr(frappe.flags, DOCUMENT_COMMAND_FLAG, False):
        frappe.throw(
            _("Controlled documents can only be changed through an authorized NPI document command."),
            frappe.PermissionError,
        )


def require_document_policy_write() -> None:
    if not getattr(frappe.flags, DOCUMENT_POLICY_FLAG, False):
        frappe.throw(
            _("Document policy versions can only be changed through authorized administration."),
            frappe.PermissionError,
        )


def require_document_release_command_write() -> None:
    if not getattr(frappe.flags, DOCUMENT_RELEASE_COMMAND_FLAG, False):
        frappe.throw(
            _("Document review and release history can only be changed through an authorized NPI release command."),
            frappe.PermissionError,
        )


@contextmanager
def document_command_write() -> Iterator[None]:
    with _flag_scope(DOCUMENT_COMMAND_FLAG):
        yield


@contextmanager
def document_policy_write() -> Iterator[None]:
    with _flag_scope(DOCUMENT_POLICY_FLAG):
        yield


@contextmanager
def document_release_command_write() -> Iterator[None]:
    with _flag_scope(DOCUMENT_RELEASE_COMMAND_FLAG):
        yield


@contextmanager
def document_projection_validation_diagnostics(trace_id: str) -> Iterator[None]:
    """Enable one exact, sanitized checkout projection diagnostic scope."""

    enabled = _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
    state = {
        "trace_id": trace_id,
        "substage": None,
        "recorded": False,
    }
    flags = frappe.flags
    missing = object()
    previous = getattr(flags, _PROJECTION_VALIDATION_DIAGNOSTIC_FLAG, missing)
    setattr(
        flags,
        _PROJECTION_VALIDATION_DIAGNOSTIC_FLAG,
        state if enabled else None,
    )
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(flags, _PROJECTION_VALIDATION_DIAGNOSTIC_FLAG)
            except AttributeError:
                pass
        else:
            setattr(
                flags,
                _PROJECTION_VALIDATION_DIAGNOSTIC_FLAG,
                previous,
            )


def mark_projection_validation_substage(code: str) -> None:
    """Mark one closed validation substage without changing save behavior."""

    state = _projection_validation_diagnostic_state()
    if state is not None and code in PROJECTION_VALIDATION_DIAGNOSTIC_CODES:
        state["substage"] = code


def record_projection_validation_fallback(error: Exception) -> None:
    """Classify failures outside custom hooks without changing save behavior."""

    state = _projection_validation_diagnostic_state()
    if state is None or state.get("recorded") is True:
        return
    candidate = state.get("substage")
    code = (
        str(candidate)
        if candidate in PROJECTION_VALIDATION_DIAGNOSTIC_CODES
        else "DOCUMENT_CHECKOUT_PROJECTION_SAVE_LIFECYCLE"
    )
    _record_projection_validation_failure(code, error, state)


def _projection_validation_diagnostic_state() -> dict[str, object] | None:
    state = getattr(
        frappe.flags,
        _PROJECTION_VALIDATION_DIAGNOSTIC_FLAG,
        None,
    )
    if (
        not isinstance(state, dict)
        or set(state) != {"trace_id", "substage", "recorded"}
        or not isinstance(state.get("trace_id"), str)
        or _DIAGNOSTIC_TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
    ):
        return None
    return state


def _record_projection_validation_failure(
    code: str,
    error: Exception,
    state: dict[str, object],
) -> None:
    if (
        code not in PROJECTION_VALIDATION_DIAGNOSTIC_CODES
        or state.get("recorded") is True
    ):
        return
    exception_type = type(error).__name__
    if _DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None:
        return
    state["recorded"] = True
    try:
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI Document projection validation failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics must never replace the original validation failure.
        pass


@contextmanager
def document_domain_validation() -> Iterator[None]:
    """Translate pure-domain field failures into a normal Frappe validation."""

    try:
        yield
    except RequestValidationFailed as error:
        message = error.title
        if error.field_errors:
            candidate = error.field_errors[0].get("message")
            if isinstance(candidate, str) and candidate:
                message = candidate
        frappe.throw(message, frappe.ValidationError)


def document_domain_value(factory: Callable[[], _T]) -> _T:
    with document_domain_validation():
        return factory()
    raise AssertionError("Frappe validation must raise.")


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


def canonical_uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError) as error:
        frappe.throw(
            _("{field} must be a valid global ID.").format(field=label),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.") from error


def optional_uuid(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    return canonical_uuid(value, label)


def required_text(
    value: object,
    label: str,
    maximum: int,
    *,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        frappe.throw(
            _("{field} is required.").format(field=label),
            frappe.ValidationError,
        )
    normalized = value.strip()
    if len(normalized) > maximum or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        frappe.throw(
            _("{field} is invalid.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def key_text(value: object, label: str) -> str:
    return required_text(value, label, 64, pattern=_KEY_PATTERN)


def tenant_text(value: object) -> str:
    return required_text(value, _("Tenant ID"), 128, pattern=_TENANT_PATTERN)


def actor_text(value: object, label: str) -> str:
    return required_text(value, label, 254, pattern=_ACTOR_PATTERN)


def lowercase_sha256(value: object, label: str) -> str:
    normalized = required_text(value, label, 64)
    if _HASH_PATTERN.fullmatch(normalized) is None:
        frappe.throw(
            _("{field} must be a valid SHA-256 value.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be a positive whole number.").format(field=label),
            frappe.ValidationError,
        )
    return value


def nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        frappe.throw(
            _("{field} must be zero or a positive whole number.").format(field=label),
            frappe.ValidationError,
        )
    return value


def optional_date_text(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        frappe.throw(
            _("{field} must be a valid date.").format(field=label),
            frappe.ValidationError,
        )
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            frappe.throw(
                _("{field} must be a valid date.").format(field=label),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
    frappe.throw(
        _("{field} must be a valid date.").format(field=label),
        frappe.ValidationError,
    )
    raise AssertionError("Frappe validation must raise.")


def utc_datetime_text(value: object, label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            frappe.throw(
                _("{field} must be a valid date and time.").format(field=label),
                frappe.ValidationError,
            )
            raise AssertionError("Frappe validation must raise.") from error
    else:
        frappe.throw(
            _("{field} must be a valid date and time.").format(field=label),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def frappe_utc_datetime_text(value: object, label: str) -> str:
    """Return a UTC value in Frappe's database Datetime text format."""

    canonical = utc_datetime_text(value, label)
    parsed = datetime.fromisoformat(canonical.replace("Z", "+00:00"))
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def json_object(value: object, label: str) -> dict[str, object]:
    prepared = _json_value(value, label)
    if not isinstance(prepared, dict):
        frappe.throw(
            _("{field} must be a JSON object.").format(field=label),
            frappe.ValidationError,
        )
    return prepared


def json_array(value: object, label: str) -> list[object]:
    prepared = _json_value(value, label)
    if not isinstance(prepared, list):
        frappe.throw(
            _("{field} must be a JSON array.").format(field=label),
            frappe.ValidationError,
        )
    return prepared


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_value(value: object, label: str) -> object:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        frappe.throw(
            _("{field} must contain valid JSON.").format(field=label),
            frappe.ValidationError,
        )
    try:
        return json.loads(value, parse_constant=_reject_json_constant)
    except (TypeError, ValueError) as error:
        frappe.throw(
            _("{field} must contain valid JSON.").format(field=label),
            frappe.ValidationError,
        )
        raise AssertionError("Frappe validation must raise.") from error


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Unsupported JSON constant: {value}")


def assert_immutable_fields(
    document: object,
    previous: object,
    fields: Iterable[str],
) -> None:
    for fieldname in fields:
        current_value = _value(document, fieldname)
        previous_value = _value(previous, fieldname)
        if fieldname.endswith("_at"):
            current_value = _comparable_datetime(current_value)
            previous_value = _comparable_datetime(previous_value)
        if current_value != previous_value:
            frappe.throw(
                _("Controlled document history cannot be changed."),
                frappe.PermissionError,
            )


def deny_document_history_update() -> None:
    frappe.throw(
        _("Controlled document history cannot be changed."),
        frappe.PermissionError,
    )


def require_exact_parent(
    doctype: str,
    name: object,
    expected: Mapping[str, object],
    message: str,
    *,
    extra_fields: Iterable[str] = (),
) -> Mapping[str, object]:
    fields = list(dict.fromkeys([*expected, *extra_fields]))
    row = frappe.db.get_value(
        doctype,
        name,
        fields,
        as_dict=True,
    )
    if not row:
        frappe.throw(message, frappe.ValidationError)
    for fieldname, expected_value in expected.items():
        actual = _value(row, fieldname)
        if type(expected_value) is int:
            try:
                matches = type(actual) is not bool and int(actual) == expected_value
            except (TypeError, ValueError):
                matches = False
        elif expected_value is None:
            matches = actual in (None, "")
        elif fieldname.endswith("_at"):
            matches = _comparable_datetime(actual) == _comparable_datetime(
                expected_value
            )
        else:
            matches = str(actual) == str(expected_value)
        if not matches:
            frappe.throw(message, frappe.ValidationError)
    return row


def deny_document_history_delete(
    document: object,
    *,
    target_global_id: object | None = None,
    target_version: object = 1,
) -> None:
    _queue_delete_attempt_audit(
        document,
        target_global_id=target_global_id,
        target_version=target_version,
    )
    frappe.throw(
        _("Controlled document history cannot be deleted."),
        frappe.PermissionError,
    )


def _queue_delete_attempt_audit(
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
        operation="document.history.delete_attempt",
        global_id=global_id,
        object_version=object_version,
        result="denied",
        input_summary={"doctype": doctype},
    )
    values: Mapping[str, object] = {
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


def _value(document: object, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    return getter(fieldname) if callable(getter) else getattr(document, fieldname, None)


def _comparable_datetime(value: object) -> object:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return object()
    except ValueError:
        return object()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
