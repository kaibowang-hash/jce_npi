from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

import frappe
from frappe import _

from npi_core.controlled_print.domain import (
    CONTROLLED_PRINT_OPERATION,
    ControlledPrintAccessEvent,
    ControlledPrintOutput,
    ControlledPrintRegistryReference,
    ControlledPrintRegistryVersion,
    ControlledPrintSnapshot,
    ControlledPrintSourceReference,
    PrintAccessEventType,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    sha256_json,
)
from npi_core.documents.frappe_validation import (
    actor_text,
    assert_immutable_fields,
    canonical_json,
    canonical_uuid,
    deny_document_history_delete,
    document_domain_value,
    frappe_utc_datetime_text,
    json_array,
    json_object,
    lowercase_sha256,
    positive_integer,
    required_text,
    require_exact_parent,
    tenant_text,
    utc_datetime_text,
)


REGISTRY_WRITE_FLAG = "npi_controlled_print_registry_write"
COMMAND_WRITE_FLAG = "npi_controlled_print_command_write"


@contextmanager
def controlled_print_registry_write() -> Iterator[None]:
    with _flag(REGISTRY_WRITE_FLAG):
        yield


@contextmanager
def controlled_print_command_write() -> Iterator[None]:
    with _flag(COMMAND_WRITE_FLAG):
        yield


def require_controlled_print_registry_write() -> None:
    if not getattr(frappe.flags, REGISTRY_WRITE_FLAG, False):
        frappe.throw(
            _("Controlled print mappings require an authorized administrative command."),
            frappe.PermissionError,
        )


def require_controlled_print_command_write() -> None:
    if not getattr(frappe.flags, COMMAND_WRITE_FLAG, False):
        frappe.throw(
            _("Controlled print history requires an authorized NPI command."),
            frappe.PermissionError,
        )


def deny_controlled_print_history_delete(document: Any) -> None:
    deny_document_history_delete(
        document,
        target_global_id=_value(document, "global_id"),
        target_version=_value(document, "mapping_version")
        or _value(document, "version")
        or 1,
    )


def validate_registry_root(document: Any) -> None:
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.tenant_id = tenant_text(document.tenant_id)
    document.registry_key = required_text(
        document.registry_key,
        _("Registry Key"),
        128,
    )
    expected_key_hash = hashlib.sha256(document.registry_key.encode("utf-8")).hexdigest()
    if document.registry_key_hash and document.registry_key_hash != expected_key_hash:
        frappe.throw(
            _("Registry Key Hash does not match Registry Key."),
            frappe.ValidationError,
        )
    document.registry_key_hash = expected_key_hash
    document.title = required_text(document.title, _("Title"), 140)
    document.enabled = 1 if bool(document.enabled) else 0
    document.optimistic_version = positive_integer(
        document.optimistic_version,
        _("Optimistic Version"),
    )


def validate_registry_version(document: Any) -> None:
    supplied_mapping_snapshot = json_object(
        document.mapping_snapshot,
        _("Mapping Snapshot"),
    )
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.registry_global_id = canonical_uuid(
        document.registry_global_id,
        _("Registry Global ID"),
    )
    document.print_registry = canonical_uuid(
        document.print_registry,
        _("Controlled Print Registry"),
    )
    users = tuple(
        str(value)
        for value in json_array(document.printer_user_ids, _("Printer User IDs"))
    )
    effective_to = _optional_datetime(document.effective_to, _("Effective To"))
    published_at = _optional_datetime(document.published_at, _("Published At"))
    mapping = document_domain_value(
        lambda: ControlledPrintRegistryVersion(
            global_id=UUID(document.global_id),
            registry_global_id=UUID(document.registry_global_id),
            tenant_id=document.tenant_id,
            mapping_key=document.mapping_key,
            mapping_version=document.mapping_version,
            title=document.title,
            state=_supported_choice(PrintRegistryState, document.publication_state),
            source_object_type=document.source_object_type,
            project_type_key=document.project_type_key,
            gate_key=str(document.gate_key) if document.gate_key else None,
            source_state=document.source_state,
            language=document.language,
            delivery_mode=_supported_choice(PrintDeliveryMode, document.delivery_mode),
            copy_state=_supported_choice(PrintCopyState, document.copy_state),
            print_format_name=document.print_format_name,
            template_content=document.template_content,
            template_sha256=document.template_sha256,
            watermark_source=document.watermark_source,
            printer_user_ids=users,
            effective_from=_datetime(document.effective_from, _("Effective From")),
            effective_to=effective_to,
            published_at=published_at,
            snapshot_hash=str(document.snapshot_hash or ""),
        )
    )
    document.tenant_id = tenant_text(mapping.tenant_id)
    document.mapping_key = mapping.mapping_key
    document.mapping_version = mapping.mapping_version
    document.version_key = f"{mapping.registry_global_id}:{mapping.mapping_version}"
    document.title = mapping.title
    document.publication_state = mapping.state.value
    document.source_object_type = mapping.source_object_type
    document.project_type_key = mapping.project_type_key
    document.gate_key = mapping.gate_key
    document.source_state = mapping.source_state
    document.language = mapping.language
    document.delivery_mode = mapping.delivery_mode.value
    document.copy_state = mapping.copy_state.value
    document.print_format_name = mapping.print_format_name
    document.template_content = mapping.template_content
    document.template_sha256 = mapping.template_sha256
    document.watermark_source = mapping.watermark_source
    document.printer_user_ids = canonical_json(list(mapping.printer_user_ids))
    document.effective_from = frappe_utc_datetime_text(
        mapping.effective_from,
        _("Effective From"),
    )
    document.effective_to = (
        None
        if mapping.effective_to is None
        else frappe_utc_datetime_text(mapping.effective_to, _("Effective To"))
    )
    document.mapping_snapshot = canonical_json(mapping.snapshot_payload())
    document.snapshot_hash = mapping.snapshot_hash
    document.published_at = (
        None
        if mapping.published_at is None
        else frappe_utc_datetime_text(mapping.published_at, _("Published At"))
    )
    document.optimistic_version = positive_integer(
        document.optimistic_version,
        _("Optimistic Version"),
    )
    if document.print_registry != document.registry_global_id:
        frappe.throw(
            _("The controlled print mapping does not match its registry."),
            frappe.ValidationError,
        )
    require_exact_parent(
        "NPI Controlled Print Registry",
        document.print_registry,
        {
            "global_id": document.registry_global_id,
            "tenant_id": document.tenant_id,
        },
        _("The controlled print mapping does not match its registry."),
    )
    if supplied_mapping_snapshot != mapping.snapshot_payload():
        frappe.throw(
            _("Mapping Snapshot does not match the exact registry version."),
            frappe.ValidationError,
        )


def validate_snapshot(document: Any) -> None:
    snapshot_value = json_object(document.source_snapshot, _("Source Snapshot"))
    supplied_snapshot = json_object(document.snapshot, _("Snapshot"))

    def build_snapshot() -> ControlledPrintSnapshot:
        source = ControlledPrintSourceReference(
            document.source_object_type,
            UUID(canonical_uuid(document.source_global_id, _("Source Global ID"))),
            document.source_version,
            document.source_state,
            document.source_snapshot_hash,
        )
        registry = ControlledPrintRegistryReference(
            UUID(canonical_uuid(document.mapping_global_id, _("Mapping Global ID"))),
            UUID(canonical_uuid(document.registry_global_id, _("Registry Global ID"))),
            document.mapping_version,
            document.mapping_snapshot_hash,
            document.template_sha256,
        )
        return ControlledPrintSnapshot(
            global_id=UUID(canonical_uuid(document.global_id, _("Global ID"))),
            tenant_id=document.tenant_id,
            project_global_id=UUID(
                canonical_uuid(document.project_global_id, _("Project Global ID"))
            ),
            project_type_key=document.project_type_key,
            gate_key=str(document.gate_key) if document.gate_key else None,
            source=source,
            registry=registry,
            language=document.language,
            delivery_mode=_supported_choice(PrintDeliveryMode, document.delivery_mode),
            copy_state=_supported_choice(PrintCopyState, document.copy_state),
            watermark_source=document.watermark_source,
            source_snapshot=snapshot_value,
            actor_user_id=document.actor_user_id,
            printed_at=_datetime(document.printed_at, _("Printed At")),
            request_id=UUID(canonical_uuid(document.request_id, _("Request ID"))),
            trace_id=document.trace_id,
            version=document.snapshot_version,
            snapshot_hash=str(document.snapshot_hash or ""),
            verification_payload=str(document.verification_payload or ""),
        )

    value = document_domain_value(build_snapshot)
    document.global_id = str(value.global_id)
    document.tenant_id = tenant_text(value.tenant_id)
    document.project_global_id = str(value.project_global_id)
    document.project_type_key = value.project_type_key
    document.gate_key = value.gate_key
    document.source_object_type = value.source.source_object_type
    document.source_global_id = str(value.source.source_global_id)
    document.source_version = value.source.source_version
    document.source_state = value.source.source_state
    document.source_snapshot = canonical_json(
        value.snapshot_payload()["sourceSnapshot"]
    )
    document.source_snapshot_hash = value.source.source_snapshot_hash
    document.mapping_global_id = str(value.registry.mapping_global_id)
    document.registry_global_id = str(value.registry.registry_global_id)
    document.mapping_version = value.registry.version
    document.mapping_snapshot_hash = value.registry.snapshot_hash
    document.template_sha256 = value.registry.template_sha256
    document.language = value.language
    document.delivery_mode = value.delivery_mode.value
    document.copy_state = value.copy_state.value
    document.watermark_source = value.watermark_source
    document.actor_user_id = actor_text(value.actor_user_id, _("Actor User ID"))
    document.printed_at = frappe_utc_datetime_text(value.printed_at, _("Printed At"))
    document.request_id = str(value.request_id)
    document.trace_id = required_text(value.trace_id, _("Trace ID"), 128)
    document.snapshot_version = value.version
    document.snapshot = canonical_json(value.snapshot_payload())
    document.snapshot_hash = value.snapshot_hash
    document.verification_payload = value.verification_payload
    _require_project(document.tenant_id, document.project_global_id)
    require_exact_parent(
        "NPI Controlled Print Registry",
        document.registry_global_id,
        {
            "global_id": document.registry_global_id,
            "tenant_id": document.tenant_id,
            "enabled": 1,
        },
        _("The controlled print snapshot does not match an enabled registry."),
    )
    mapping_row = require_exact_parent(
        "NPI Controlled Print Registry Version",
        document.mapping_global_id,
        {
            "global_id": document.mapping_global_id,
            "print_registry": document.registry_global_id,
            "registry_global_id": document.registry_global_id,
            "tenant_id": document.tenant_id,
            "mapping_version": document.mapping_version,
            "publication_state": PrintRegistryState.PUBLISHED.value,
            "source_object_type": document.source_object_type,
            "project_type_key": document.project_type_key,
            "gate_key": document.gate_key,
            "source_state": document.source_state,
            "language": document.language,
            "delivery_mode": document.delivery_mode,
            "copy_state": document.copy_state,
            "watermark_source": document.watermark_source,
            "snapshot_hash": document.mapping_snapshot_hash,
            "template_sha256": document.template_sha256,
        },
        _("The controlled print snapshot does not match its exact mapping."),
        extra_fields=("effective_from", "effective_to"),
    )
    effective_from = _datetime(
        _value(mapping_row, "effective_from"),
        _("Effective From"),
    )
    effective_to = _optional_datetime(
        _value(mapping_row, "effective_to"),
        _("Effective To"),
    )
    if value.printed_at < effective_from or (
        effective_to is not None and value.printed_at >= effective_to
    ):
        frappe.throw(
            _("The controlled print mapping is not effective at the print time."),
            frappe.ValidationError,
        )
    if supplied_snapshot != value.snapshot_payload():
        frappe.throw(
            _("Snapshot does not match the exact controlled print source."),
            frappe.ValidationError,
        )


def validate_output(document: Any) -> None:
    controlled_print_snapshot = canonical_uuid(
        document.controlled_print_snapshot,
        _("Controlled Print Snapshot"),
    )
    supplied_output_snapshot = json_object(
        document.output_snapshot,
        _("Output Snapshot"),
    )
    value = document_domain_value(
        lambda: ControlledPrintOutput(
            global_id=UUID(canonical_uuid(document.global_id, _("Global ID"))),
            tenant_id=document.tenant_id,
            project_global_id=UUID(
                canonical_uuid(document.project_global_id, _("Project Global ID"))
            ),
            snapshot_global_id=UUID(
                canonical_uuid(document.snapshot_global_id, _("Snapshot Global ID"))
            ),
            frappe_file_id=document.frappe_file_id,
            file_name=document.file_name,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            frappe_content_hash=document.frappe_content_hash,
            sha256=document.sha256,
            created_by_user_id=document.created_by_user_id,
            created_at=_datetime(document.created_at, _("Created At")),
            record_hash=str(document.record_hash or ""),
        )
    )
    document.global_id = str(value.global_id)
    document.tenant_id = tenant_text(value.tenant_id)
    document.project_global_id = str(value.project_global_id)
    document.snapshot_global_id = str(value.snapshot_global_id)
    document.frappe_file_id = value.frappe_file_id
    document.file_name = value.file_name
    document.mime_type = value.mime_type
    document.size_bytes = value.size_bytes
    document.frappe_content_hash = value.frappe_content_hash
    document.sha256 = value.sha256
    document.created_by_user_id = actor_text(
        value.created_by_user_id,
        _("Created By User ID"),
    )
    document.created_at = frappe_utc_datetime_text(value.created_at, _("Created At"))
    document.output_snapshot = canonical_json(value.record_payload())
    document.record_hash = value.record_hash
    document.controlled_print_snapshot = controlled_print_snapshot
    if controlled_print_snapshot != document.snapshot_global_id:
        frappe.throw(
            _("The controlled print output does not match its snapshot."),
            frappe.ValidationError,
        )
    _require_project(document.tenant_id, document.project_global_id)
    require_exact_parent(
        "NPI Controlled Print Snapshot",
        controlled_print_snapshot,
        {
            "global_id": document.snapshot_global_id,
            "tenant_id": document.tenant_id,
            "project_global_id": document.project_global_id,
        },
        _("The controlled print output does not match its snapshot."),
    )
    file_row = require_exact_parent(
        "File",
        document.frappe_file_id,
        {
            "name": document.frappe_file_id,
            "is_private": 1,
            "file_name": document.file_name,
            "file_size": document.size_bytes,
            "content_hash": document.frappe_content_hash,
        },
        _("The controlled print output does not match its exact private file."),
        extra_fields=("file_url",),
    )
    file_url = str(_value(file_row, "file_url") or "")
    file_path = PurePosixPath(file_url)
    if (
        not file_url.startswith("/private/files/")
        or len(file_path.parts) != 4
        or file_path.parts[:3] != ("/", "private", "files")
        or file_path.name != document.file_name
    ):
        frappe.throw(
            _("The controlled print output does not match its exact private file."),
            frappe.ValidationError,
        )
    if supplied_output_snapshot != value.record_payload():
        frappe.throw(
            _("Output Snapshot does not match the exact private output."),
            frappe.ValidationError,
        )


def validate_access_event(document: Any) -> None:
    controlled_print_snapshot = canonical_uuid(
        document.controlled_print_snapshot,
        _("Controlled Print Snapshot"),
    )
    controlled_print_output = canonical_uuid(
        document.controlled_print_output,
        _("Controlled Print Output"),
    )
    supplied_event_snapshot = json_object(
        document.event_snapshot,
        _("Event Snapshot"),
    )
    value = document_domain_value(
        lambda: ControlledPrintAccessEvent(
            global_id=UUID(canonical_uuid(document.global_id, _("Global ID"))),
            tenant_id=document.tenant_id,
            project_global_id=UUID(
                canonical_uuid(document.project_global_id, _("Project Global ID"))
            ),
            snapshot_global_id=UUID(
                canonical_uuid(document.snapshot_global_id, _("Snapshot Global ID"))
            ),
            output_global_id=UUID(
                canonical_uuid(document.output_global_id, _("Output Global ID"))
            ),
            event_type=_supported_choice(PrintAccessEventType, document.event_type),
            actor_user_id=document.actor_user_id,
            occurred_at=_datetime(document.occurred_at, _("Occurred At")),
            trace_id=document.trace_id,
            event_hash=str(document.event_hash or ""),
        )
    )
    document.global_id = str(value.global_id)
    document.tenant_id = tenant_text(value.tenant_id)
    document.project_global_id = str(value.project_global_id)
    document.snapshot_global_id = str(value.snapshot_global_id)
    document.output_global_id = str(value.output_global_id)
    document.event_type = value.event_type.value
    document.actor_user_id = actor_text(value.actor_user_id, _("Actor User ID"))
    document.occurred_at = frappe_utc_datetime_text(value.occurred_at, _("Occurred At"))
    document.trace_id = required_text(value.trace_id, _("Trace ID"), 128)
    document.event_snapshot = canonical_json(value.event_payload())
    document.event_hash = value.event_hash
    document.controlled_print_snapshot = controlled_print_snapshot
    document.controlled_print_output = controlled_print_output
    if controlled_print_snapshot != document.snapshot_global_id:
        frappe.throw(
            _("The controlled print access event does not match its snapshot."),
            frappe.ValidationError,
        )
    if controlled_print_output != document.output_global_id:
        frappe.throw(
            _("The controlled print access event does not match its output."),
            frappe.ValidationError,
        )
    _require_project(document.tenant_id, document.project_global_id)
    require_exact_parent(
        "NPI Controlled Print Snapshot",
        controlled_print_snapshot,
        {
            "global_id": document.snapshot_global_id,
            "tenant_id": document.tenant_id,
            "project_global_id": document.project_global_id,
        },
        _("The controlled print access event does not match its snapshot."),
    )
    require_exact_parent(
        "NPI Controlled Print Output",
        controlled_print_output,
        {
            "global_id": document.output_global_id,
            "tenant_id": document.tenant_id,
            "project_global_id": document.project_global_id,
            "snapshot_global_id": document.snapshot_global_id,
            "controlled_print_snapshot": document.snapshot_global_id,
        },
        _("The controlled print access event does not match its output."),
    )
    if supplied_event_snapshot != value.event_payload():
        frappe.throw(
            _("Event Snapshot does not match the exact access event."),
            frappe.ValidationError,
        )


def validate_command_receipt(document: Any) -> None:
    document.global_id = canonical_uuid(document.global_id, _("Global ID"))
    document.tenant_id = tenant_text(document.tenant_id)
    document.project_global_id = canonical_uuid(
        document.project_global_id,
        _("Project Global ID"),
    )
    document.actor_user_id = actor_text(document.actor_user_id, _("Actor User ID"))
    if document.operation != CONTROLLED_PRINT_OPERATION:
        frappe.throw(_("Select a supported operation."), frappe.ValidationError)
    document.idempotency_key_hash = lowercase_sha256(
        document.idempotency_key_hash,
        _("Idempotency Key Hash"),
    )
    document.payload_hash = lowercase_sha256(
        document.payload_hash,
        _("Payload Hash"),
    )
    document.receipt_key = hashlib.sha256(
        (
            f"{document.tenant_id}\0{document.project_global_id}\0"
            f"{document.actor_user_id}\0{document.operation}\0"
            f"{document.idempotency_key_hash}"
        ).encode("utf-8")
    ).hexdigest()
    document.snapshot_global_id = (
        canonical_uuid(document.snapshot_global_id, _("Snapshot Global ID"))
        if document.snapshot_global_id
        else None
    )
    document.sealed = 1 if bool(document.sealed) else 0
    response = json_object(document.response_payload or {}, _("Response Payload"))
    if document.sealed:
        if not document.snapshot_global_id or not response:
            frappe.throw(
                _("A sealed controlled print receipt requires an exact response."),
                frappe.ValidationError,
            )
        expected_response_hash = sha256_json(response)
        if document.response_hash and document.response_hash != expected_response_hash:
            frappe.throw(
                _("Response Hash does not match Response Payload."),
                frappe.ValidationError,
            )
        document.response_hash = expected_response_hash
    elif document.snapshot_global_id or response or document.response_hash:
        frappe.throw(
            _("An unsealed controlled print receipt cannot contain a response."),
            frappe.ValidationError,
        )
    document.response_payload = canonical_json(response)
    document.created_at = frappe_utc_datetime_text(
        _datetime(document.created_at, _("Created At")),
        _("Created At"),
    )
    document.updated_at = frappe_utc_datetime_text(
        _datetime(document.updated_at, _("Updated At")),
        _("Updated At"),
    )
    _require_project(document.tenant_id, document.project_global_id)
    if document.sealed:
        require_exact_parent(
            "NPI Controlled Print Snapshot",
            document.snapshot_global_id,
            {
                "global_id": document.snapshot_global_id,
                "tenant_id": document.tenant_id,
                "project_global_id": document.project_global_id,
            },
            _("The controlled print receipt does not match its snapshot."),
        )


def require_immutable_or_receipt_seal(document: Any, fields: tuple[str, ...]) -> None:
    previous = document.get_doc_before_save()
    if previous is None:
        return
    assert_immutable_fields(document, previous, fields)
    previous_sealed = bool(_value(previous, "sealed"))
    current_sealed = bool(_value(document, "sealed"))
    if previous_sealed or not current_sealed:
        frappe.throw(
            _("Controlled print command receipts can only be sealed once."),
            frappe.PermissionError,
        )


def _datetime(value: object, label: str) -> datetime:
    text = utc_datetime_text(value, label)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _optional_datetime(value: object, label: str) -> datetime | None:
    return None if value in (None, "") else _datetime(value, label)


def _supported_choice(enum_type: Any, value: object) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        frappe.throw(_("Select a supported value."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise.")


def _require_project(tenant_id: str, project_global_id: str) -> None:
    require_exact_parent(
        "NPI Engineering Project",
        project_global_id,
        {
            "global_id": project_global_id,
            "tenant_id": tenant_id,
        },
        _("The controlled print record does not match its Project and tenant."),
    )


@contextmanager
def _flag(name: str) -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, name, missing)
    setattr(frappe.flags, name, True)
    try:
        yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, name)
            except AttributeError:
                pass
        else:
            setattr(frappe.flags, name, previous)


def _value(document: object, fieldname: str) -> object:
    getter = getattr(document, "get", None)
    return getter(fieldname) if callable(getter) else getattr(document, fieldname, None)
