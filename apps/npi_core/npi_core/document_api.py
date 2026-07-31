from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID

import frappe
from frappe import _

from npi_core.api import BinaryPayload, frappe_binary_call, frappe_domain_call
from npi_core.documents.domain import (
    DocumentRelationshipKind,
    DocumentUnavailable,
    MAX_FILE_BYTES,
)
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.foundation.tracing import current_trace_id
from npi_core.project.domain import actor_idempotency_key_hash
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
    require_document_routes_enabled,
    require_request_fields,
    response_request_id,
)


_LIST_FIELDS = frozenset(
    {
        "limit",
        "cursor",
        "relationshipKind",
        "targetIdentity",
        "targetVersion",
        "projectReferenceType",
        "targetSourceSystem",
        "targetReferenceGlobalId",
    }
)
_CREATE_FIELDS = frozenset(
    {
        "policyGlobalId",
        "policyVersion",
        "policySnapshotHash",
        "documentTypeKey",
        "title",
        "confidentialityKey",
        "objectLinks",
    }
)
_CHECK_OUT_FIELDS = frozenset({"expectedDocumentVersion"})
_CHECK_IN_FIELDS = frozenset({"expectedDocumentVersion", "expectedLockVersion"})
_RECOVER_FIELDS = frozenset(
    {"expectedDocumentVersion", "expectedLockVersion", "reason"}
)
_REVISION_FIELDS = frozenset({"metadata"})
_REVISION_METADATA_FIELDS = frozenset(
    {
        "expectedDocumentVersion",
        "expectedLockVersion",
        "major",
        "minor",
        "reason",
        "effectiveDate",
        "predecessorRevisionId",
    }
)
_CONTENT_FIELDS = frozenset(
    {"expectedDocumentVersion", "expectedFileVersion", "disposition"}
)
_RELATIONSHIP_KINDS = frozenset(value.value for value in DocumentRelationshipKind)
_PROJECT_REFERENCE_TYPES = frozenset(
    {"customer", "product", "part", "tooling", "order"}
)
_SOURCE_SYSTEMS = frozenset({"NPI_ONE", "ERPNEXT"})
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class _CommandOutcomeLike(Protocol):
    response: dict[str, Any]
    replayed: bool


class _ContentOutcomeLike(Protocol):
    content: bytes
    file_name: str
    mime_type: str
    disposition: str
    replayed: bool


class _RepositoryLike(Protocol):
    def authorize_scope(
        self,
        project_id: UUID,
        document_id: UUID | None = None,
        *,
        administer: bool,
    ) -> bool: ...

    def list_documents(
        self, project_id: UUID, **kwargs: Any
    ) -> dict[str, Any] | None: ...

    def document_detail(
        self, project_id: UUID, document_id: UUID
    ) -> dict[str, Any] | None: ...

    def create_document(
        self, project_id: UUID, **kwargs: Any
    ) -> _CommandOutcomeLike | None: ...

    def check_out(
        self, project_id: UUID, document_id: UUID, **kwargs: Any
    ) -> _CommandOutcomeLike | None: ...

    def check_in(
        self, project_id: UUID, document_id: UUID, **kwargs: Any
    ) -> _CommandOutcomeLike | None: ...

    def recover_lock(
        self, project_id: UUID, document_id: UUID, **kwargs: Any
    ) -> _CommandOutcomeLike | None: ...

    def create_revision(
        self, project_id: UUID, document_id: UUID, **kwargs: Any
    ) -> _CommandOutcomeLike | None: ...

    def file_capability(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        file_revision_id: UUID,
    ) -> dict[str, Any] | None: ...

    def content(
        self,
        project_id: UUID,
        document_id: UUID,
        revision_id: UUID,
        file_revision_id: UUID,
        **kwargs: Any,
    ) -> _ContentOutcomeLike | None: ...


def _repository_factory(
    *,
    principal: Principal,
    request_id: str,
    trace_id: str,
) -> _RepositoryLike:
    from npi_core.documents.frappe_repository import FrappeDocumentRepository

    return FrappeDocumentRepository(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_documents(
    limit: Any = None,
    cursor: Any = None,
    relationshipKind: Any = None,
    targetIdentity: Any = None,
    targetVersion: Any = None,
    projectReferenceType: Any = None,
    targetSourceSystem: Any = None,
    targetReferenceGlobalId: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, _document_id = _query_context(
            _LIST_FIELDS,
            request_fields,
        )
        relationship_filter = _relationship_filter(
            relationshipKind,
            targetIdentity,
            targetVersion,
            projectReferenceType,
            targetSourceSystem,
            targetReferenceGlobalId,
        )
        response = repository.list_documents(
            project_id,
            limit=_bounded_limit(limit),
            cursor=_optional_cursor(cursor),
            **relationship_filter,
        )
        if response is None:
            raise DocumentUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_document(
    policyGlobalId: Any = None,
    policyVersion: Any = None,
    policySnapshotHash: Any = None,
    documentTypeKey: Any = None,
    title: Any = None,
    confidentialityKey: Any = None,
    objectLinks: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = _command_headers()

    def handle() -> dict[str, Any]:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            _document_id,
        ) = _command_context(
            _CREATE_FIELDS,
            _CREATE_FIELDS,
            request_fields,
        )
        outcome = repository.create_document(
            project_id,
            idempotency_key=idempotency_key,
            policy_global_id=_uuid_value(policyGlobalId, "policyGlobalId"),
            policy_version=_positive_integer(policyVersion, "policyVersion"),
            policy_snapshot_hash=_hash_value(
                policySnapshotHash,
                "policySnapshotHash",
            ),
            document_type_key=_key_value(
                documentTypeKey,
                "documentTypeKey",
            ),
            title=_text_value(title, "title", 280),
            confidentiality_key=_key_value(
                confidentialityKey,
                "confidentialityKey",
            ),
            object_links=_object_links(objectLinks),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_document(**request_fields: Any) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, document_id = _query_context(
            frozenset(),
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        response = repository.document_detail(
            project_id,
            document_id,
        )
        if response is None:
            raise DocumentUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def check_out_document(
    expectedDocumentVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = _command_headers()

    def handle() -> dict[str, Any]:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            document_id,
        ) = _command_context(
            _CHECK_OUT_FIELDS,
            _CHECK_OUT_FIELDS,
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        outcome = repository.check_out(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=_positive_integer(
                expectedDocumentVersion,
                "expectedDocumentVersion",
            ),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def check_in_document(
    expectedDocumentVersion: Any = None,
    expectedLockVersion: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = _command_headers()

    def handle() -> dict[str, Any]:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            document_id,
        ) = _command_context(
            _CHECK_IN_FIELDS,
            _CHECK_IN_FIELDS,
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        outcome = repository.check_in(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=_positive_integer(
                expectedDocumentVersion,
                "expectedDocumentVersion",
            ),
            expected_lock_version=_positive_integer(
                expectedLockVersion,
                "expectedLockVersion",
            ),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def recover_document_lock(
    expectedDocumentVersion: Any = None,
    expectedLockVersion: Any = None,
    reason: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = _command_headers()

    def handle() -> dict[str, Any]:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            document_id,
        ) = _command_context(
            _RECOVER_FIELDS,
            _RECOVER_FIELDS,
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        outcome = repository.recover_lock(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=_positive_integer(
                expectedDocumentVersion,
                "expectedDocumentVersion",
            ),
            expected_lock_version=_positive_integer(
                expectedLockVersion,
                "expectedLockVersion",
            ),
            reason=_text_value(reason, "reason", 1_000),
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_document_revision(
    metadata: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    success_headers = _command_headers()

    def handle() -> dict[str, Any]:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            document_id,
        ) = _command_context(
            _REVISION_FIELDS,
            _REVISION_FIELDS,
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        revision = _revision_metadata(metadata)
        file_name, content = _uploaded_file()
        outcome = repository.create_revision(
            project_id,
            document_id,
            idempotency_key=idempotency_key,
            expected_document_version=revision["expectedDocumentVersion"],
            expected_lock_version=revision["expectedLockVersion"],
            major=revision["major"],
            minor=revision["minor"],
            reason=revision["reason"],
            effective_date=revision["effectiveDate"],
            predecessor_revision_id=revision["predecessorRevisionId"],
            file_name=file_name,
            content=content,
        )
        return _command_response(
            outcome,
            request_id=request_id,
            success_headers=success_headers,
        )

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        success_status=201,
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_file_capabilities(**request_fields: Any) -> dict[str, Any] | None:
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        request_id, repository, project_id, document_id = _query_context(
            frozenset(),
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        response = repository.file_capability(
            project_id,
            document_id,
            _route_uuid("revision_id", "revisionId"),
            _route_uuid("file_revision_id", "fileRevisionId"),
        )
        if response is None:
            raise DocumentUnavailable()
        success_headers["X-Request-ID"] = request_id
        return _response_dict(response)

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_file_content(
    expectedDocumentVersion: Any = None,
    expectedFileVersion: Any = None,
    disposition: Any = None,
    **request_fields: Any,
) -> None:
    success_headers = _command_headers()

    def handle() -> BinaryPayload:
        (
            request_id,
            idempotency_key,
            repository,
            project_id,
            document_id,
        ) = _command_context(
            _CONTENT_FIELDS,
            _CONTENT_FIELDS,
            request_fields,
            require_document=True,
        )
        assert document_id is not None
        requested_disposition = _enum_value(
            disposition,
            "disposition",
            frozenset({"inline", "attachment"}),
        )
        outcome = repository.content(
            project_id,
            document_id,
            _route_uuid("revision_id", "revisionId"),
            _route_uuid("file_revision_id", "fileRevisionId"),
            idempotency_key=idempotency_key,
            expected_document_version=_positive_integer(
                expectedDocumentVersion,
                "expectedDocumentVersion",
            ),
            expected_file_version=_positive_integer(
                expectedFileVersion,
                "expectedFileVersion",
            ),
            disposition=requested_disposition,
        )
        if outcome is None:
            raise DocumentUnavailable()
        if type(outcome.replayed) is not bool:
            raise RuntimeError("The Document content replay result is invalid.")
        success_headers["X-Request-ID"] = request_id
        success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
        return BinaryPayload(
            content=outcome.content,
            file_name=outcome.file_name,
            mime_type=outcome.mime_type,
            disposition=outcome.disposition,
            headers={
                "Content-Disposition": _content_disposition(
                    outcome.disposition,
                    outcome.file_name,
                ),
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "Referrer-Policy": "no-referrer",
            },
        )

    frappe_binary_call(handle, response_headers=success_headers)


def _query_context(
    allowed_fields: frozenset[str],
    request_fields: dict[str, Any],
    *,
    require_document: bool = False,
) -> tuple[str, _RepositoryLike, UUID, UUID | None]:
    require_document_routes_enabled()
    actor = authenticated_user()
    principal = authenticated_principal(actor)
    provisional_request_id = response_request_id()
    repository = _repository(principal, provisional_request_id)
    project_id, document_id = _authorized_route_scope(
        repository,
        administer=False,
        require_document=require_document,
    )
    reject_unexpected_request_fields(allowed_fields, request_fields)
    request_id = _request_id()
    return request_id, repository, project_id, document_id


def _command_context(
    allowed_fields: frozenset[str],
    required_fields: frozenset[str],
    request_fields: dict[str, Any],
    *,
    require_document: bool = False,
) -> tuple[str, str, _RepositoryLike, UUID, UUID | None]:
    require_document_routes_enabled()
    actor = authenticated_user()
    require_csrf_token()
    principal = authenticated_principal(actor)
    if principal.is_external or "System Manager" not in principal.roles:
        raise PermissionDenied()
    provisional_request_id = response_request_id()
    repository = _repository(principal, provisional_request_id)
    project_id, document_id = _authorized_route_scope(
        repository,
        administer=True,
        require_document=require_document,
    )
    reject_unexpected_request_fields(allowed_fields, request_fields)
    require_request_fields(required_fields, request_fields)
    request_id = _request_id()
    idempotency_key = actor_idempotency_key_hash(
        actor,
        frappe.get_request_header("Idempotency-Key"),
    )
    return (
        request_id,
        idempotency_key,
        repository,
        project_id,
        document_id,
    )


def _authorized_route_scope(
    repository: _RepositoryLike,
    *,
    administer: bool,
    require_document: bool,
) -> tuple[UUID, UUID | None]:
    project_id = _opaque_route_uuid("project_id")
    if not repository.authorize_scope(
        project_id,
        administer=administer,
    ):
        raise DocumentUnavailable()
    if not require_document:
        return project_id, None
    document_id = _opaque_route_uuid("document_id")
    if not repository.authorize_scope(
        project_id,
        document_id,
        administer=administer,
    ):
        raise DocumentUnavailable()
    return project_id, document_id


def _repository(principal: Principal, request_id: str) -> _RepositoryLike:
    trace_id = current_trace_id.get()
    if trace_id is None:
        raise RuntimeError("The Document request has no active trace identity.")
    return _repository_factory(
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )


def _command_headers() -> dict[str, str]:
    return {
        "X-Request-ID": response_request_id(),
        "Idempotency-Replayed": "false",
    }


def _command_response(
    outcome: _CommandOutcomeLike | None,
    *,
    request_id: str,
    success_headers: dict[str, str],
) -> dict[str, Any]:
    if outcome is None:
        raise DocumentUnavailable()
    if type(outcome.replayed) is not bool:
        raise RuntimeError("The Document command replay result is invalid.")
    success_headers["X-Request-ID"] = request_id
    success_headers["Idempotency-Replayed"] = str(outcome.replayed).lower()
    return _response_dict(outcome.response)


def _response_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("The Document response is invalid.")
    return value


def _route_uuid(key: str, path: str) -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get(key) if hasattr(route_params, "get") else None
    return _uuid_value(value, path)


def _opaque_route_uuid(key: str) -> UUID:
    route_params = getattr(frappe.flags, "npi_route_params", None)
    value = route_params.get(key) if hasattr(route_params, "get") else None
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise DocumentUnavailable() from error
    if str(parsed) != str(value).casefold():
        raise DocumentUnavailable()
    return parsed


def _request_id() -> str:
    return str(
        _uuid_value(
            frappe.get_request_header("X-Request-ID"),
            "requestId",
        )
    )


def _uuid_value(value: object, path: str) -> UUID:
    try:
        parsed = UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid global ID.")) from error
    if str(parsed) != str(value).casefold():
        raise _field_problem(path, _("Enter a canonical global ID."))
    return parsed


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value in (None, "") else _uuid_value(value, path)


def _positive_integer(value: object, path: str, *, maximum: int = 2_147_483_647) -> int:
    if type(value) is not int or value < 1 or value > maximum:
        raise _field_problem(path, _("Enter a positive whole number."))
    return value


def _positive_query_integer(
    value: object,
    path: str,
    *,
    maximum: int = 2_147_483_647,
) -> int:
    if type(value) is int:
        return _positive_integer(value, path, maximum=maximum)
    if (
        isinstance(value, str)
        and len(value) <= 10
        and value.isascii()
        and value.isdigit()
    ):
        parsed = int(value)
        if str(parsed) == value and parsed <= maximum:
            return parsed
    raise _field_problem(path, _("Enter a positive whole number."))


def _nonnegative_integer(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _field_problem(path, _("Enter zero or a positive whole number."))
    return value


def _hash_value(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid SHA-256 value."))
    return value


def _key_value(value: object, path: str) -> str:
    normalized = _text_value(value, path, 64)
    if _KEY_PATTERN.fullmatch(normalized) is None:
        raise _field_problem(path, _("Enter a valid controlled key."))
    return normalized


def _text_value(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _field_problem(path, _("Enter a shorter value."))
    return normalized


def _enum_value(
    value: object,
    path: str,
    choices: frozenset[str],
) -> str:
    if not isinstance(value, str) or value not in choices:
        raise _field_problem(path, _("Select a supported value."))
    return value


def _optional_cursor(value: object) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 500:
        raise _field_problem("cursor", _("Enter a valid cursor."))
    return value


def _bounded_limit(value: object) -> int:
    if value in (None, ""):
        return 50
    return _positive_integer(value, "limit", maximum=100)


def _object_links(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) > 64:
        raise _field_problem(
            "objectLinks",
            _("Enter no more than 64 related objects."),
        )
    result = []
    fingerprints = set()
    for index, item in enumerate(value):
        path = f"objectLinks[{index}]"
        if not isinstance(item, dict):
            raise _field_problem(path, _("Enter a valid related object."))
        kind = _enum_value(
            item.get("kind"),
            f"{path}.kind",
            _RELATIONSHIP_KINDS,
        )
        expected_fields = {"kind", "targetIdentity", "targetVersion"}
        if kind == DocumentRelationshipKind.PROJECT_REFERENCE.value:
            expected_fields.update(
                {
                    "projectReferenceType",
                    "targetSourceSystem",
                    "targetReferenceGlobalId",
                }
            )
        if set(item) != expected_fields:
            raise _field_problem(
                path,
                _("The related object contains unsupported fields."),
            )
        normalized: dict[str, object] = {
            "kind": kind,
            "targetIdentity": _text_value(
                item.get("targetIdentity"),
                f"{path}.targetIdentity",
                512,
            ),
            "targetVersion": _positive_integer(
                item.get("targetVersion"),
                f"{path}.targetVersion",
            ),
        }
        if kind == DocumentRelationshipKind.PROJECT_REFERENCE.value:
            normalized.update(
                {
                    "projectReferenceType": _enum_value(
                        item.get("projectReferenceType"),
                        f"{path}.projectReferenceType",
                        _PROJECT_REFERENCE_TYPES,
                    ),
                    "targetSourceSystem": _enum_value(
                        item.get("targetSourceSystem"),
                        f"{path}.targetSourceSystem",
                        _SOURCE_SYSTEMS,
                    ),
                    "targetReferenceGlobalId": (
                        str(parsed)
                        if (
                            parsed := _optional_uuid(
                                item.get("targetReferenceGlobalId"),
                                f"{path}.targetReferenceGlobalId",
                            )
                        )
                        else None
                    ),
                }
            )
        fingerprint = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if fingerprint in fingerprints:
            raise _field_problem(
                path,
                _("Attach each related object once."),
            )
        fingerprints.add(fingerprint)
        result.append(normalized)
    return tuple(result)


def _relationship_filter(
    relationship_kind: object,
    target_identity: object,
    target_version: object,
    project_reference_type: object,
    target_source_system: object,
    target_reference_global_id: object,
) -> dict[str, object]:
    values = (
        relationship_kind,
        target_identity,
        target_version,
        project_reference_type,
        target_source_system,
        target_reference_global_id,
    )
    if all(value in (None, "") for value in values):
        return {
            "relationship_kind": None,
            "target_identity": None,
            "target_version": None,
            "project_reference_type": None,
            "target_source_system": None,
            "target_reference_global_id": None,
        }
    kind = _enum_value(
        relationship_kind,
        "relationshipKind",
        _RELATIONSHIP_KINDS,
    )
    identity = _text_value(target_identity, "targetIdentity", 512)
    version = _positive_query_integer(target_version, "targetVersion")
    if kind == DocumentRelationshipKind.PROJECT_REFERENCE.value:
        subtype = _enum_value(
            project_reference_type,
            "projectReferenceType",
            _PROJECT_REFERENCE_TYPES,
        )
        source = _enum_value(
            target_source_system,
            "targetSourceSystem",
            _SOURCE_SYSTEMS,
        )
        reference_id = _optional_uuid(
            target_reference_global_id,
            "targetReferenceGlobalId",
        )
    else:
        if any(
            value not in (None, "")
            for value in (
                project_reference_type,
                target_source_system,
                target_reference_global_id,
            )
        ):
            raise _field_problem(
                "relationshipKind",
                _("Only a Project reference can use typed reference filters."),
            )
        subtype = None
        source = None
        reference_id = None
    return {
        "relationship_kind": kind,
        "target_identity": identity,
        "target_version": version,
        "project_reference_type": subtype,
        "target_source_system": source,
        "target_reference_global_id": reference_id,
    }


def _revision_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, str) or len(value) > 16_384:
        raise _field_problem("metadata", _("Enter valid revision metadata."))
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except (TypeError, ValueError) as error:
        raise _field_problem(
            "metadata",
            _("Enter valid revision metadata."),
        ) from error
    if not isinstance(parsed, dict) or set(parsed) != _REVISION_METADATA_FIELDS:
        raise _field_problem(
            "metadata",
            _("Revision metadata contains unsupported fields."),
        )
    effective_date = _optional_date(
        parsed.get("effectiveDate"),
        "metadata.effectiveDate",
    )
    predecessor = _optional_uuid(
        parsed.get("predecessorRevisionId"),
        "metadata.predecessorRevisionId",
    )
    return {
        "expectedDocumentVersion": _positive_integer(
            parsed.get("expectedDocumentVersion"),
            "metadata.expectedDocumentVersion",
        ),
        "expectedLockVersion": _positive_integer(
            parsed.get("expectedLockVersion"),
            "metadata.expectedLockVersion",
        ),
        "major": _nonnegative_integer(parsed.get("major"), "metadata.major"),
        "minor": _nonnegative_integer(parsed.get("minor"), "metadata.minor"),
        "reason": _text_value(parsed.get("reason"), "metadata.reason", 2_000),
        "effectiveDate": effective_date,
        "predecessorRevisionId": predecessor,
    }


def _optional_date(value: object, path: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _field_problem(path, _("Enter a valid date."))
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _field_problem(path, _("Enter a valid date.")) from error


def _uploaded_file() -> tuple[str, bytes]:
    request = getattr(frappe, "request", None)
    files = getattr(request, "files", None)
    if files is None or not hasattr(files, "keys"):
        raise _field_problem("file", _("Select one file."))
    if set(files.keys()) != {"file"}:
        raise _field_problem("file", _("Select exactly one file."))
    values = files.getlist("file") if hasattr(files, "getlist") else [files.get("file")]
    if len(values) != 1 or values[0] is None:
        raise _field_problem("file", _("Select exactly one file."))
    uploaded = values[0]
    file_name = getattr(uploaded, "filename", None)
    stream = getattr(uploaded, "stream", uploaded)
    read = getattr(stream, "read", None)
    if not callable(read):
        raise _field_problem("file", _("Select one file."))
    content = read(MAX_FILE_BYTES + 1)
    if not isinstance(content, bytes):
        raise _field_problem("file", _("Select one binary file."))
    if len(content) > MAX_FILE_BYTES:
        raise _field_problem(
            "file",
            _("The file exceeds the supported infrastructure limit."),
        )
    return _text_value(file_name, "fileName", 255), content


def _content_disposition(disposition: str, file_name: str) -> str:
    normalized = unicodedata.normalize("NFC", file_name)
    if (
        "\r" in normalized
        or "\n" in normalized
        or "/" in normalized
        or "\\" in normalized
    ):
        raise ValueError("The content filename is unsafe.")
    ascii_name = (
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    fallback = re.sub(r"[^A-Za-z0-9._-]", "_", ascii_name).strip("._")
    if not fallback:
        fallback = "document"
    encoded = quote(normalized, safe="")
    return f'{disposition}; filename="{fallback}"; ' f"filename*=UTF-8''{encoded}"


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Unsupported JSON constant: {value}")


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
