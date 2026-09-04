from __future__ import annotations

import json
import re
from datetime import date
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import BinaryPayload, frappe_binary_call, frappe_domain_call
from npi_core.data_exchange.domain import (
    ArchiveSourceKind,
    DataExchangeRoutesDisabled,
    DatasetId,
    ExportLanguage,
    RedactionProfile,
    RetentionCategory,
    RetentionScope,
)
from npi_core.data_exchange.frappe_repository import FrappeDataExchangeRepository
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_request_fields,
    response_request_id,
)


_HASH = re.compile(r"^[a-f0-9]{64}$")
_NO_FIELDS = frozenset()
_PROFILE_FIELDS = frozenset({"globalId", "version", "datasetId", "columns", "language", "redactionProfile", "query", "maxRows", "maxBytes"})
_EXPORT_FIELDS = frozenset({"profileId", "profileVersion", "profileHash"})
_DOWNLOAD_FIELDS = frozenset({"expectedPackageHash"})
_POLICY_FIELDS = frozenset({"globalId", "version", "scope", "scopeReference", "effectiveFrom", "effectiveUntil", "retentionYears"})
_ARCHIVE_FIELDS = frozenset({"globalId", "sourceKind", "sourceId", "sourceVersion", "sourceHash", "policyId", "policyVersion", "policyHash", "scope", "scopeReference"})
_repository_factory = FrappeDataExchangeRepository


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_data_exchange_workspace(**request_fields: Any) -> dict[str, Any] | None:
    return _query(_NO_FIELDS, request_fields, lambda repository: repository.workspace())


@frappe.whitelist(allow_guest=True, methods=["POST"])
def publish_data_exchange_profile(
    globalId: Any = None, version: Any = None, datasetId: Any = None,
    columns: Any = None, language: Any = None, redactionProfile: Any = None,
    query: Any = None, maxRows: Any = None, maxBytes: Any = None, **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _PROFILE_FIELDS,
        request_fields,
        lambda repository, _key: repository.publish_profile(
            global_id=_uuid(globalId, "globalId"), version=_positive(version, "version"),
            dataset_id=_enum(DatasetId, datasetId, "datasetId"), columns=_text_tuple(columns, "columns"),
            language=_enum(ExportLanguage, language, "language"), redaction_profile=_enum(RedactionProfile, redactionProfile, "redactionProfile"),
            query=tuple(_object(query, "query").items()), max_rows=_positive(maxRows, "maxRows"), max_bytes=_positive(maxBytes, "maxBytes"),
        ),
        success_status=201,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_data_exchange_export(
    profileId: Any = None, profileVersion: Any = None, profileHash: Any = None, **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _EXPORT_FIELDS,
        request_fields,
        lambda repository, key: repository.create_export(
            profile_id=_uuid(profileId, "profileId"), profile_version=_positive(profileVersion, "profileVersion"),
            profile_hash=_hash(profileHash, "profileHash"), execution_key_hash=key,
        ),
        success_status=201,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def download_data_exchange_export(expectedPackageHash: Any = None, **request_fields: Any) -> None:
    headers = {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}

    def handle() -> BinaryPayload:
        actor, repository, request_id = _authorized_repository(require_csrf=True)
        reject_unexpected_request_fields(_DOWNLOAD_FIELDS, request_fields)
        require_request_fields(_DOWNLOAD_FIELDS, request_fields)
        actor_idempotency_key_hash(actor, frappe.get_request_header("Idempotency-Key"))
        content, file_name, mime_type = repository.export_content(_route_uuid("export_id"), _hash(expectedPackageHash, "expectedPackageHash"))
        headers["X-Request-ID"] = request_id
        return BinaryPayload(
            content=content, file_name=file_name, mime_type=mime_type, disposition="attachment",
            headers={"Content-Disposition": f'attachment; filename="{file_name}"', "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'", "Referrer-Policy": "no-referrer"},
        )

    frappe_binary_call(handle, response_headers=headers)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def publish_retention_policy(
    globalId: Any = None, version: Any = None, scope: Any = None, scopeReference: Any = None,
    effectiveFrom: Any = None, effectiveUntil: Any = None, retentionYears: Any = None, **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _POLICY_FIELDS,
        request_fields,
        lambda repository, _key: repository.publish_policy(
            global_id=_uuid(globalId, "globalId"), version=_positive(version, "version"),
            scope=_enum(RetentionScope, scope, "scope"), scope_reference=_optional_text(scopeReference),
            effective_from=_date(effectiveFrom, "effectiveFrom"), effective_until=_optional_date(effectiveUntil, "effectiveUntil"),
            retention_years=_retention_years(retentionYears),
        ),
        success_status=201,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_retention_archive(
    globalId: Any = None, sourceKind: Any = None, sourceId: Any = None, sourceVersion: Any = None,
    sourceHash: Any = None, policyId: Any = None, policyVersion: Any = None, policyHash: Any = None,
    scope: Any = None, scopeReference: Any = None, **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _ARCHIVE_FIELDS,
        request_fields,
        lambda repository, key: repository.create_archive(
            global_id=_uuid(globalId, "globalId"), source_kind=_enum(ArchiveSourceKind, sourceKind, "sourceKind"),
            source_id=_uuid(sourceId, "sourceId"), source_version=_positive(sourceVersion, "sourceVersion"), source_hash=_hash(sourceHash, "sourceHash"),
            policy_id=_uuid(policyId, "policyId"), policy_version=_positive(policyVersion, "policyVersion"), policy_hash=_hash(policyHash, "policyHash"),
            scope=_enum(RetentionScope, scope, "scope"), scope_reference=_optional_text(scopeReference), execution_key_hash=key,
        ),
        success_status=201,
    )


def _query(allowed, request_fields, operation):
    headers = {"X-Request-ID": response_request_id()}

    def handle():
        _actor, repository, request_id = _authorized_repository(require_csrf=False)
        reject_unexpected_request_fields(allowed, request_fields)
        response = operation(repository)
        if not isinstance(response, dict):
            raise RuntimeError("Data Exchange response is invalid.")
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(handle, cache_control="private, no-store", response_headers=headers)


def _command(allowed, request_fields, operation, *, success_status=200):
    headers = {"X-Request-ID": response_request_id(), "Idempotency-Replayed": "false"}

    def handle():
        actor, repository, request_id = _authorized_repository(require_csrf=True)
        reject_unexpected_request_fields(allowed, request_fields)
        require_request_fields(allowed, request_fields)
        key = actor_idempotency_key_hash(actor, frappe.get_request_header("Idempotency-Key"))
        outcome = operation(repository, key)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(handle, cache_control="private, no-store", success_status=success_status, response_headers=headers)


def _authorized_repository(*, require_csrf: bool):
    _require_routes_enabled()
    actor = authenticated_user()
    if require_csrf:
        require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    request_id = str(_uuid(frappe.get_request_header("X-Request-ID"), "requestId"))
    from npi_core.foundation.tracing import current_trace_id
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("Data Exchange command has no trace identity.")
    return actor, _repository_factory(principal=principal, request_id=request_id, trace_id=trace_id), request_id


def _require_routes_enabled() -> None:
    configuration = getattr(frappe, "conf", None)
    if not (hasattr(configuration, "get") and configuration.get("npi_p9_06_routes_disabled") is False):
        raise DataExchangeRoutesDisabled()


def _route_uuid(name: str) -> UUID:
    params = getattr(frappe.flags, "npi_route_params", None)
    return _uuid(params.get(name) if hasattr(params, "get") else None, name)


def _uuid(value, path):
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a canonical global ID."))
    try:
        parsed = UUID(value)
    except ValueError:
        raise _field_problem(path, _("Enter a canonical global ID.")) from None
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive(value, path):
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _hash(value, path):
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _enum(enum_type, value, path):
    try:
        return enum_type(value)
    except (ValueError, TypeError):
        raise _field_problem(path, _("Select a supported value.")) from None


def _object(value, path):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = None
    if not isinstance(value, dict):
        raise _field_problem(path, _("Enter a valid object."))
    return value


def _text_tuple(value, path):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = None
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise _field_problem(path, _("Select at least one supported column."))
    return tuple(value)


def _retention_years(value):
    values = _object(value, "retentionYears")
    try:
        return tuple((category, values[category.value]) for category in RetentionCategory)
    except KeyError:
        raise _field_problem("retentionYears", _("Enter retention years for every controlled category.")) from None


def _date(value, path):
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid date."))
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _field_problem(path, _("Enter a valid date.")) from None


def _optional_date(value, path):
    return None if value in (None, "") else _date(value, path)


def _optional_text(value):
    return None if value in (None, "") else str(value)


def _field_problem(path, message):
    return RequestValidationFailed([{"path": path, "message": message}])
