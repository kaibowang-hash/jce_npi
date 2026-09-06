from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import BinaryPayload, frappe_binary_call, frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.historical_migration.domain import HistoricalMigrationRoutesDisabled
from npi_core.historical_migration.frappe_repository import (
    FrappeHistoricalMigrationRepository,
)
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
_PREVIEW_FIELDS = frozenset(
    {
        "tenantId",
        "fileRevisionGlobalId",
        "fileOptimisticVersion",
        "sha256",
    }
)
_VERSION_FIELDS = frozenset({"expectedVersion", "expectedSnapshotHash"})
_NO_FIELDS = frozenset()
_repository_factory = FrappeHistoricalMigrationRepository


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_historical_migration_workspace(
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _query(
        _NO_FIELDS,
        request_fields,
        lambda repository: repository.workspace(),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_historical_migration_preview(
    tenantId: Any = None,
    fileRevisionGlobalId: Any = None,
    fileOptimisticVersion: Any = None,
    sha256: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _PREVIEW_FIELDS,
        request_fields,
        lambda repository, _execution_key: repository.create_preview(
            tenant_id=_text(tenantId, "tenantId", 128),
            file_revision_global_id=_uuid(fileRevisionGlobalId, "fileRevisionGlobalId"),
            file_optimistic_version=_positive(
                fileOptimisticVersion, "fileOptimisticVersion"
            ),
            source_sha256=_hash(sha256, "sha256"),
        ),
        success_status=201,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def execute_historical_migration_preview(
    expectedVersion: Any = None,
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _VERSION_FIELDS,
        request_fields,
        lambda repository, execution_key: repository.queue_execution(
            preview_id=_route_uuid("preview_id"),
            expected_version=_positive(expectedVersion, "expectedVersion"),
            expected_snapshot_hash=_hash(
                expectedSnapshotHash, "expectedSnapshotHash"
            ),
            execution_key_hash=execution_key,
        ),
        success_status=202,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_historical_migration_job(**request_fields: Any) -> dict[str, Any] | None:
    return _query(
        _NO_FIELDS,
        request_fields,
        lambda repository: repository.job(_route_uuid("job_id")),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_historical_migration_correction(
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _command(
        _NO_FIELDS,
        request_fields,
        lambda repository, execution_key: repository.create_correction(
            _route_uuid("job_id"), execution_key_hash=execution_key
        ),
        success_status=201,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reconcile_historical_migration_job(
    expectedVersion: Any = None,
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _versioned_job_command(
        expectedVersion,
        expectedSnapshotHash,
        request_fields,
        lambda repository, execution_key, expected_version, expected_snapshot_hash: repository.reconcile(
            _route_uuid("job_id"),
            expected_version=expected_version,
            expected_snapshot_hash=expected_snapshot_hash,
            execution_key_hash=execution_key,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def rollback_historical_migration_job(
    expectedVersion: Any = None,
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _versioned_job_command(
        expectedVersion,
        expectedSnapshotHash,
        request_fields,
        lambda repository, execution_key, expected_version, expected_snapshot_hash: repository.rollback(
            _route_uuid("job_id"),
            expected_version=expected_version,
            expected_snapshot_hash=expected_snapshot_hash,
            execution_key_hash=execution_key,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def download_historical_migration_correction(
    expectedSnapshotHash: Any = None,
    **request_fields: Any,
) -> None:
    allowed = frozenset({"expectedSnapshotHash"})
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle() -> BinaryPayload:
        actor, repository, request_id = _authorized_repository(require_csrf=True)
        reject_unexpected_request_fields(allowed, request_fields)
        require_request_fields(allowed, request_fields)
        actor_idempotency_key_hash(
            actor, frappe.get_request_header("Idempotency-Key")
        )
        job_id = _route_uuid("job_id")
        job = repository.job(job_id)
        if job.get("snapshotHash") != _hash(
            expectedSnapshotHash, "expectedSnapshotHash"
        ):
            from npi_core.historical_migration.domain import HistoricalMigrationConflict

            raise HistoricalMigrationConflict()
        content, file_name = repository.correction_content(job_id)
        headers["X-Request-ID"] = request_id
        return BinaryPayload(
            content=content,
            file_name=file_name,
            mime_type="text/csv",
            disposition="attachment",
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    frappe_binary_call(handle, response_headers=headers)


def _versioned_job_command(expected_version, expected_hash, request_fields, operation):
    def execute(repository, execution_key):
        return operation(
            repository,
            execution_key,
            _positive(expected_version, "expectedVersion"),
            _hash(expected_hash, "expectedSnapshotHash"),
        )

    return _command(_VERSION_FIELDS, request_fields, execute)


def _query(allowed, request_fields, operation):
    headers = {"X-Request-ID": response_request_id()}

    def handle():
        _actor, repository, request_id = _authorized_repository(require_csrf=False)
        reject_unexpected_request_fields(allowed, request_fields)
        response = operation(repository)
        if not isinstance(response, dict):
            raise RuntimeError("Historical migration response is invalid.")
        headers["X-Request-ID"] = request_id
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=headers,
    )


def _command(allowed, request_fields, operation, *, success_status=200):
    headers = {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }

    def handle():
        actor, repository, request_id = _authorized_repository(require_csrf=True)
        reject_unexpected_request_fields(allowed, request_fields)
        require_request_fields(allowed, request_fields)
        execution_key = actor_idempotency_key_hash(
            actor, frappe.get_request_header("Idempotency-Key")
        )
        outcome = operation(repository, execution_key)
        headers["X-Request-ID"] = request_id
        headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return outcome.response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=success_status,
        response_headers=headers,
    )


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
        raise RuntimeError("Historical migration command has no trace identity.")
    return (
        actor,
        _repository_factory(
            principal=principal, request_id=request_id, trace_id=trace_id
        ),
        request_id,
    )


def _require_routes_enabled() -> None:
    configuration = getattr(frappe, "conf", None)
    enabled = bool(
        hasattr(configuration, "get")
        and configuration.get("npi_p9_05_routes_disabled") is False
    )
    if not enabled:
        raise HistoricalMigrationRoutesDisabled()


def _route_uuid(name: str) -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get(name) if hasattr(route_params, "get") else None
    return _uuid(value, name)


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a canonical global ID."))
    try:
        parsed = UUID(value)
    except ValueError:
        raise _field_problem(path, _("Enter a canonical global ID.")) from None
    if str(parsed) != value.casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a lowercase SHA-256 hash."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _field_problem(path, _("Enter a valid value."))
    return value.strip()


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
