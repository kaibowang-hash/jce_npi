from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4

import frappe

from npi_core.controlled_print.domain import (
    CONTROLLED_PRINT_OPERATION,
    ControlledPrintAccessEvent,
    ControlledPrintAuthorityUnavailable,
    ControlledPrintContext,
    ControlledPrintIdempotencyConflict,
    ControlledPrintMappingUnavailable,
    ControlledPrintOutput,
    ControlledPrintRegistryReference,
    ControlledPrintRegistryVersion,
    ControlledPrintSnapshot,
    ControlledPrintSourceReference,
    PrintAccessEventType,
    PrintCopyState,
    PrintDeliveryMode,
    PrintRegistryState,
    controlled_print_command_payload_hash,
    controlled_print_receipt_key,
    resolve_controlled_print_mapping,
    sha256_json,
)
from npi_core.controlled_print.frappe_validation import (
    controlled_print_command_write,
)
from npi_core.controlled_print.rendering import (
    RenderedControlledPrintPdf,
    frappe_convert_pdf,
    frappe_render_template,
    frappe_translate,
    render_controlled_print_pdf,
)
from npi_core.controlled_print.service import AuthorizedControlledPrintProject
from npi_core.controlled_print.source_registry import (
    ControlledPrintSourceRegistry,
    default_controlled_print_source_registry,
)
from npi_core.documents.frappe_repository import FrappeDocumentRepository
from npi_core.foundation.audit import create_audit_event


_MAX_MAPPING_CANDIDATES = 64


@dataclass(frozen=True, slots=True)
class ControlledPrintCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ControlledPrintContentOutcome:
    content: bytes
    file_name: str
    mime_type: str
    snapshot_hash: str
    output_hash: str


class FrappeControlledPrintRepository(FrappeDocumentRepository):
    """Frappe repository for exact controlled-print resolution and retained bytes."""

    def __init__(
        self,
        *,
        source_registry: ControlledPrintSourceRegistry | None = None,
        render_template=frappe_render_template,
        convert_pdf=frappe_convert_pdf,
        translate=frappe_translate,
        clock=None,
        uuid_factory=uuid4,
        **values: object,
    ) -> None:
        super().__init__(**values)
        self._source_registry = (
            source_registry
            if source_registry is not None
            else default_controlled_print_source_registry()
        )
        self._render_template = render_template
        self._convert_pdf = convert_pdf
        self._translate = translate
        self._clock = clock or (lambda: datetime.now(UTC))
        self._uuid_factory = uuid_factory

    def authorize_project(
        self,
        project_global_id: UUID,
    ) -> AuthorizedControlledPrintProject | None:
        project = self._authorized_project(project_global_id)
        if project is None:
            return None
        return AuthorizedControlledPrintProject(
            global_id=UUID(str(project.global_id)),
            tenant_id=str(project.tenant_id),
            project_type_key=str(project.project_type),
        )

    def published_mapping_candidates(
        self,
        context: ControlledPrintContext,
        *,
        at: datetime,
    ) -> Sequence[ControlledPrintRegistryVersion]:
        del at  # Domain matching owns the exact half-open effectivity rule.
        names = frappe.get_all(
            "NPI Controlled Print Registry Version",
            filters={
                "tenant_id": context.tenant_id,
                "publication_state": PrintRegistryState.PUBLISHED.value,
                "source_object_type": context.source_object_type,
                "project_type_key": context.project_type_key,
                "source_state": context.source_state,
                "language": context.language,
                "delivery_mode": context.delivery_mode.value,
                "copy_state": context.copy_state.value,
            },
            pluck="name",
            order_by="effective_from asc, mapping_version asc, global_id asc",
            limit_page_length=_MAX_MAPPING_CANDIDATES + 1,
        )
        if len(names) > _MAX_MAPPING_CANDIDATES:
            raise RuntimeError(
                "Controlled print mapping candidates exceed their safe bound."
            )
        mappings: list[ControlledPrintRegistryVersion] = []
        for name in names:
            document = frappe.get_doc(
                "NPI Controlled Print Registry Version",
                str(name),
            )
            mapping = _mapping_value(document)
            if mapping.gate_key != context.gate_key:
                continue
            _require_enabled_registry(document, mapping)
            mappings.append(mapping)
        return tuple(mappings)

    def create_snapshot(
        self,
        project_global_id: UUID,
        *,
        source_object_type: str,
        source_global_id: UUID,
        expected_source_version: int,
        language: str,
        idempotency_key_hash: str,
    ) -> ControlledPrintCommandOutcome | None:
        project = self._locked_view_authorized_project(project_global_id)
        if project is None:
            return None
        tenant_id = str(project.tenant_id)
        project_type_key = str(project.project_type)
        payload_hash = controlled_print_command_payload_hash(
            actor_user_id=self.actor,
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            source_object_type=source_object_type,
            source_global_id=source_global_id,
            source_version=expected_source_version,
            language=language,
        )
        receipt_key = controlled_print_receipt_key(
            actor_user_id=self.actor,
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            idempotency_key_hash=idempotency_key_hash,
        )
        replay = self._receipt_replay(
            receipt_key=receipt_key,
            payload_hash=payload_hash,
            project=project,
            idempotency_key_hash=idempotency_key_hash,
        )
        if replay is not None:
            return ControlledPrintCommandOutcome(replay, replayed=True)

        source = self._source_registry.resolve_exact(
            project_global_id=project_global_id,
            source_object_type=source_object_type,
            source_global_id=source_global_id,
            expected_source_version=expected_source_version,
        )
        if source.project_type_key != project_type_key:
            raise RuntimeError(
                "Controlled print source Project type does not match its Project."
            )
        context = source.context(tenant_id=tenant_id, language=language)
        now = self._now()
        mapping = resolve_controlled_print_mapping(
            self.published_mapping_candidates(context, at=now),
            context,
            at=now,
        )
        if not mapping.authorizes(self.actor):
            raise ControlledPrintAuthorityUnavailable()
        snapshot = ControlledPrintSnapshot(
            global_id=self._new_uuid(),
            tenant_id=tenant_id,
            project_global_id=project_global_id,
            project_type_key=project_type_key,
            gate_key=source.gate_key,
            source=source.reference,
            registry=ControlledPrintRegistryReference.from_mapping(mapping),
            language=language,
            delivery_mode=context.delivery_mode,
            copy_state=context.copy_state,
            watermark_source=mapping.watermark_source,
            source_snapshot=source.snapshot,
            actor_user_id=self.actor,
            printed_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        rendered = render_controlled_print_pdf(
            snapshot=snapshot,
            mapping=mapping,
            render_template=self._render_template,
            convert_pdf=self._convert_pdf,
            translate=self._translate,
        )
        with _controlled_print_write_scope():
            receipt = self._insert_receipt(
                receipt_key=receipt_key,
                payload_hash=payload_hash,
                project=project,
                idempotency_key_hash=idempotency_key_hash,
                now=now,
            )
            self._insert_snapshot(snapshot)
            file_document = self._save_private_file(snapshot, rendered)
            output = self._insert_output(
                snapshot=snapshot,
                rendered=rendered,
                file_document=file_document,
            )
            event = self._insert_access_event(
                snapshot=snapshot,
                output=output,
                event_type=PrintAccessEventType.CREATED,
                occurred_at=now,
            )
            self._append_audit(
                operation="controlled_print.snapshot.create",
                snapshot=snapshot,
                output=output,
                event=event,
            )
            response = snapshot.public_dict(output=output)
            self._seal_receipt(receipt, snapshot=snapshot, response=response, now=now)
        return ControlledPrintCommandOutcome(response)

    def snapshot_detail(
        self,
        project_global_id: UUID,
        snapshot_global_id: UUID,
    ) -> dict[str, Any] | None:
        bundle = self._authorized_snapshot_bundle(
            project_global_id,
            snapshot_global_id,
        )
        if bundle is None:
            return None
        _project, snapshot, output = bundle
        return snapshot.public_dict(output=output)

    def content(
        self,
        project_global_id: UUID,
        snapshot_global_id: UUID,
    ) -> ControlledPrintContentOutcome | None:
        bundle = self._authorized_snapshot_bundle(
            project_global_id,
            snapshot_global_id,
        )
        if bundle is None:
            return None
        _project, snapshot, output = bundle
        file_document = _optional_doc("File", output.frappe_file_id)
        if file_document is None or not _file_identity_matches(file_document, output):
            raise RuntimeError("Controlled print private File identity drifted.")
        content = file_document.get_content()
        if isinstance(content, str):
            content = content.encode("utf-8")
        if (
            not isinstance(content, bytes)
            or len(content) != output.size_bytes
            or hashlib.sha256(content).hexdigest() != output.sha256
        ):
            raise RuntimeError("Controlled print retained PDF integrity drifted.")
        occurred_at = self._now()
        with _controlled_print_write_scope():
            event = self._insert_access_event(
                snapshot=snapshot,
                output=output,
                event_type=PrintAccessEventType.DOWNLOADED,
                occurred_at=occurred_at,
            )
            self._append_audit(
                operation="controlled_print.output.download",
                snapshot=snapshot,
                output=output,
                event=event,
            )
        return ControlledPrintContentOutcome(
            content=content,
            file_name=output.file_name,
            mime_type=output.mime_type,
            snapshot_hash=snapshot.snapshot_hash,
            output_hash=output.sha256,
        )

    def _locked_view_authorized_project(self, project_global_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_global_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return (
            project
            if self._can_view_project(project, project_global_id)
            else None
        )

    def _receipt_replay(
        self,
        *,
        receipt_key: str,
        payload_hash: str,
        project: object,
        idempotency_key_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Controlled Print Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "snapshot_global_id",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        expected = {
            "tenant_id": str(_value(project, "tenant_id")),
            "project_global_id": str(_value(project, "global_id")),
            "actor_user_id": self.actor,
            "operation": CONTROLLED_PRINT_OPERATION,
            "idempotency_key_hash": idempotency_key_hash,
        }
        if any(str(_value(row, key)) != value for key, value in expected.items()):
            raise ControlledPrintIdempotencyConflict()
        if str(_value(row, "payload_hash")) != payload_hash:
            raise ControlledPrintIdempotencyConflict()
        if int(_value(row, "sealed") or 0) != 1:
            raise RuntimeError("Controlled print idempotency receipt is unsealed.")
        response = _json_object(_value(row, "response_payload"))
        if (
            str(_value(row, "snapshot_global_id")) != str(response.get("globalId"))
            or str(_value(row, "response_hash")) != sha256_json(response)
        ):
            raise RuntimeError("Controlled print idempotency receipt integrity drifted.")
        return response

    def _insert_receipt(
        self,
        *,
        receipt_key: str,
        payload_hash: str,
        project: object,
        idempotency_key_hash: str,
        now: datetime,
    ):
        return frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Command Idempotency",
                "global_id": str(self._new_uuid()),
                "receipt_key": receipt_key,
                "tenant_id": str(_value(project, "tenant_id")),
                "project_global_id": str(_value(project, "global_id")),
                "actor_user_id": self.actor,
                "operation": CONTROLLED_PRINT_OPERATION,
                "idempotency_key_hash": idempotency_key_hash,
                "payload_hash": payload_hash,
                "snapshot_global_id": None,
                "response_payload": _canonical_json({}),
                "response_hash": None,
                "sealed": 0,
                "created_at": _database_datetime(now),
                "updated_at": _database_datetime(now),
            }
        ).insert()

    @staticmethod
    def _insert_snapshot(snapshot: ControlledPrintSnapshot) -> object:
        return frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Snapshot",
                "global_id": str(snapshot.global_id),
                "tenant_id": snapshot.tenant_id,
                "project_global_id": str(snapshot.project_global_id),
                "project_type_key": snapshot.project_type_key,
                "gate_key": snapshot.gate_key,
                "source_object_type": snapshot.source.source_object_type,
                "source_global_id": str(snapshot.source.source_global_id),
                "source_version": snapshot.source.source_version,
                "source_state": snapshot.source.source_state,
                "source_snapshot": _canonical_json(
                    snapshot.snapshot_payload()["sourceSnapshot"]
                ),
                "source_snapshot_hash": snapshot.source.source_snapshot_hash,
                "mapping_global_id": str(snapshot.registry.mapping_global_id),
                "registry_global_id": str(snapshot.registry.registry_global_id),
                "mapping_version": snapshot.registry.version,
                "mapping_snapshot_hash": snapshot.registry.snapshot_hash,
                "template_sha256": snapshot.registry.template_sha256,
                "language": snapshot.language,
                "delivery_mode": snapshot.delivery_mode.value,
                "copy_state": snapshot.copy_state.value,
                "watermark_source": snapshot.watermark_source,
                "actor_user_id": snapshot.actor_user_id,
                "printed_at": _database_datetime(snapshot.printed_at),
                "request_id": str(snapshot.request_id),
                "trace_id": snapshot.trace_id,
                "snapshot_version": snapshot.version,
                "snapshot": _canonical_json(snapshot.snapshot_payload()),
                "snapshot_hash": snapshot.snapshot_hash,
                "verification_payload": snapshot.verification_payload,
            }
        ).insert()

    def _save_private_file(
        self,
        snapshot: ControlledPrintSnapshot,
        rendered: RenderedControlledPrintPdf,
    ) -> object:
        from frappe.utils.file_manager import save_file

        file_document = save_file(
            rendered.file_name,
            rendered.content,
            "NPI Controlled Print Snapshot",
            str(snapshot.global_id),
            is_private=1,
        )
        _register_orphan_cleanup(file_document)
        if not _saved_file_matches(file_document, snapshot, rendered):
            raise RuntimeError("New controlled print private File identity drifted.")
        return file_document

    def _insert_output(
        self,
        *,
        snapshot: ControlledPrintSnapshot,
        rendered: RenderedControlledPrintPdf,
        file_document: object,
    ) -> ControlledPrintOutput:
        output = ControlledPrintOutput(
            global_id=self._new_uuid(),
            tenant_id=snapshot.tenant_id,
            project_global_id=snapshot.project_global_id,
            snapshot_global_id=snapshot.global_id,
            frappe_file_id=str(_value(file_document, "name")),
            file_name=rendered.file_name,
            mime_type=rendered.mime_type,
            size_bytes=rendered.size_bytes,
            frappe_content_hash=str(_value(file_document, "content_hash")),
            sha256=rendered.sha256,
            created_by_user_id=self.actor,
            created_at=snapshot.printed_at,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Output",
                "global_id": str(output.global_id),
                "tenant_id": output.tenant_id,
                "project_global_id": str(output.project_global_id),
                "controlled_print_snapshot": str(output.snapshot_global_id),
                "snapshot_global_id": str(output.snapshot_global_id),
                "frappe_file_id": output.frappe_file_id,
                "file_name": output.file_name,
                "mime_type": output.mime_type,
                "size_bytes": output.size_bytes,
                "frappe_content_hash": output.frappe_content_hash,
                "sha256": output.sha256,
                "created_by_user_id": output.created_by_user_id,
                "created_at": _database_datetime(output.created_at),
                "output_snapshot": _canonical_json(output.record_payload()),
                "record_hash": output.record_hash,
            }
        ).insert()
        return output

    def _insert_access_event(
        self,
        *,
        snapshot: ControlledPrintSnapshot,
        output: ControlledPrintOutput,
        event_type: PrintAccessEventType,
        occurred_at: datetime,
    ) -> ControlledPrintAccessEvent:
        event = ControlledPrintAccessEvent(
            global_id=self._new_uuid(),
            tenant_id=snapshot.tenant_id,
            project_global_id=snapshot.project_global_id,
            snapshot_global_id=snapshot.global_id,
            output_global_id=output.global_id,
            event_type=event_type,
            actor_user_id=self.actor,
            occurred_at=occurred_at,
            trace_id=self.trace_id,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Controlled Print Access Event",
                "global_id": str(event.global_id),
                "tenant_id": event.tenant_id,
                "project_global_id": str(event.project_global_id),
                "controlled_print_snapshot": str(event.snapshot_global_id),
                "snapshot_global_id": str(event.snapshot_global_id),
                "controlled_print_output": str(event.output_global_id),
                "output_global_id": str(event.output_global_id),
                "event_type": event.event_type.value,
                "actor_user_id": event.actor_user_id,
                "occurred_at": _database_datetime(event.occurred_at),
                "trace_id": event.trace_id,
                "event_snapshot": _canonical_json(event.event_payload()),
                "event_hash": event.event_hash,
            }
        ).insert()
        return event

    def _append_audit(
        self,
        *,
        operation: str,
        snapshot: ControlledPrintSnapshot,
        output: ControlledPrintOutput,
        event: ControlledPrintAccessEvent,
    ) -> None:
        audit = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=snapshot.global_id,
            object_version=snapshot.version,
            result="created" if event.event_type is PrintAccessEventType.CREATED else "downloaded",
            input_summary={
                "eventId": str(event.global_id),
                "outputId": str(output.global_id),
                "outputSha256": output.sha256,
                "projectId": str(snapshot.project_global_id),
                "requestId": self.request_id,
                "snapshotHash": snapshot.snapshot_hash,
            },
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(audit.event_id),
                "global_id": str(audit.global_id),
                "object_version": audit.object_version,
                "actor": audit.actor,
                "trace_id": audit.trace_id,
                "operation": audit.operation,
                "result": audit.result,
                "input_summary": dict(audit.input_summary),
            }
        ).insert()

    @staticmethod
    def _seal_receipt(
        receipt: object,
        *,
        snapshot: ControlledPrintSnapshot,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.snapshot_global_id = str(snapshot.global_id)
        receipt.response_payload = _canonical_json(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    def _authorized_snapshot_bundle(
        self,
        project_global_id: UUID,
        snapshot_global_id: UUID,
    ) -> tuple[object, ControlledPrintSnapshot, ControlledPrintOutput] | None:
        project = self._authorized_project(project_global_id)
        if project is None:
            return None
        snapshot_document = _optional_doc(
            "NPI Controlled Print Snapshot",
            str(snapshot_global_id),
        )
        if snapshot_document is None:
            return None
        snapshot = _snapshot_value(snapshot_document)
        if (
            snapshot.global_id != snapshot_global_id
            or snapshot.project_global_id != project_global_id
            or snapshot.tenant_id != str(project.tenant_id)
            or snapshot.project_type_key != str(project.project_type)
        ):
            return None
        mapping_document = _optional_doc(
            "NPI Controlled Print Registry Version",
            str(snapshot.registry.mapping_global_id),
        )
        if mapping_document is None:
            raise RuntimeError("Controlled print mapping history is unavailable.")
        mapping = _mapping_value(mapping_document)
        if not _registry_enabled(mapping) or not _mapping_matches_snapshot(
            mapping,
            snapshot,
        ):
            return None
        if not mapping.authorizes(self.actor):
            return None
        output_name = frappe.db.get_value(
            "NPI Controlled Print Output",
            {
                "tenant_id": snapshot.tenant_id,
                "project_global_id": str(project_global_id),
                "snapshot_global_id": str(snapshot_global_id),
                "controlled_print_snapshot": str(snapshot_global_id),
            },
            "name",
        )
        if not output_name:
            raise RuntimeError("Controlled print retained output is unavailable.")
        output = _output_value(
            frappe.get_doc("NPI Controlled Print Output", str(output_name))
        )
        if (
            output.snapshot_global_id != snapshot.global_id
            or output.project_global_id != snapshot.project_global_id
            or output.tenant_id != snapshot.tenant_id
        ):
            raise RuntimeError("Controlled print output escaped its snapshot.")
        return project, snapshot, output

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise RuntimeError("Controlled print clock returned an invalid instant.")
        return value.astimezone(UTC)

    def _new_uuid(self) -> UUID:
        value = self._uuid_factory()
        if not isinstance(value, UUID) or value.version != 4:
            raise RuntimeError("Controlled print UUID source returned an invalid value.")
        return value


def _mapping_value(document: object) -> ControlledPrintRegistryVersion:
    mapping = ControlledPrintRegistryVersion(
        global_id=UUID(str(_value(document, "global_id"))),
        registry_global_id=UUID(str(_value(document, "registry_global_id"))),
        tenant_id=str(_value(document, "tenant_id")),
        mapping_key=str(_value(document, "mapping_key")),
        mapping_version=_integer(_value(document, "mapping_version")),
        title=str(_value(document, "title")),
        state=PrintRegistryState(str(_value(document, "publication_state"))),
        source_object_type=str(_value(document, "source_object_type")),
        project_type_key=str(_value(document, "project_type_key")),
        gate_key=(
            str(_value(document, "gate_key"))
            if _value(document, "gate_key") not in (None, "")
            else None
        ),
        source_state=str(_value(document, "source_state")),
        language=str(_value(document, "language")),
        delivery_mode=PrintDeliveryMode(str(_value(document, "delivery_mode"))),
        copy_state=PrintCopyState(str(_value(document, "copy_state"))),
        print_format_name=str(_value(document, "print_format_name")),
        template_content=str(_value(document, "template_content")),
        template_sha256=str(_value(document, "template_sha256")),
        watermark_source=str(_value(document, "watermark_source")),
        printer_user_ids=tuple(
            str(value)
            for value in _json_array(_value(document, "printer_user_ids"))
        ),
        effective_from=_datetime(_value(document, "effective_from")),
        effective_to=_optional_datetime(_value(document, "effective_to")),
        published_at=_optional_datetime(_value(document, "published_at")),
        snapshot_hash=str(_value(document, "snapshot_hash")),
    )
    if _json_object(_value(document, "mapping_snapshot")) != mapping.snapshot_payload():
        raise RuntimeError(
            "Persisted controlled print mapping snapshot does not match its fields."
        )
    if str(_value(document, "print_registry")) != str(mapping.registry_global_id):
        raise RuntimeError(
            "Persisted controlled print mapping escaped its registry parent."
        )
    return mapping


def _require_enabled_registry(
    document: object,
    mapping: ControlledPrintRegistryVersion,
) -> None:
    registry = _optional_doc(
        "NPI Controlled Print Registry",
        str(mapping.registry_global_id),
    )
    if (
        registry is None
        or str(_value(registry, "global_id")) != str(mapping.registry_global_id)
        or str(_value(registry, "tenant_id")) != mapping.tenant_id
        or int(_value(registry, "enabled") or 0) != 1
        or str(_value(document, "tenant_id")) != mapping.tenant_id
    ):
        raise RuntimeError(
            "Persisted controlled print mapping registry is unavailable."
        )


def _registry_enabled(mapping: ControlledPrintRegistryVersion) -> bool:
    registry = _optional_doc(
        "NPI Controlled Print Registry",
        str(mapping.registry_global_id),
    )
    return bool(
        registry is not None
        and str(_value(registry, "global_id")) == str(mapping.registry_global_id)
        and str(_value(registry, "tenant_id")) == mapping.tenant_id
        and int(_value(registry, "enabled") or 0) == 1
    )


def _mapping_matches_snapshot(
    mapping: ControlledPrintRegistryVersion,
    snapshot: ControlledPrintSnapshot,
) -> bool:
    context = ControlledPrintContext(
        tenant_id=snapshot.tenant_id,
        project_global_id=snapshot.project_global_id,
        source_object_type=snapshot.source.source_object_type,
        project_type_key=snapshot.project_type_key,
        gate_key=snapshot.gate_key,
        source_state=snapshot.source.source_state,
        language=snapshot.language,
        delivery_mode=snapshot.delivery_mode,
        copy_state=snapshot.copy_state,
    )
    try:
        reference = ControlledPrintRegistryReference.from_mapping(mapping)
    except ControlledPrintMappingUnavailable:
        return False
    return bool(
        mapping.matches(context, snapshot.printed_at)
        and reference == snapshot.registry
        and mapping.watermark_source == snapshot.watermark_source
    )


def _snapshot_value(document: object) -> ControlledPrintSnapshot:
    source_snapshot = _json_object(_value(document, "source_snapshot"))
    value = ControlledPrintSnapshot(
        global_id=UUID(str(_value(document, "global_id"))),
        tenant_id=str(_value(document, "tenant_id")),
        project_global_id=UUID(str(_value(document, "project_global_id"))),
        project_type_key=str(_value(document, "project_type_key")),
        gate_key=(
            str(_value(document, "gate_key"))
            if _value(document, "gate_key") not in (None, "")
            else None
        ),
        source=ControlledPrintSourceReference(
            source_object_type=str(_value(document, "source_object_type")),
            source_global_id=UUID(str(_value(document, "source_global_id"))),
            source_version=_integer(_value(document, "source_version")),
            source_state=str(_value(document, "source_state")),
            source_snapshot_hash=str(_value(document, "source_snapshot_hash")),
        ),
        registry=ControlledPrintRegistryReference(
            mapping_global_id=UUID(str(_value(document, "mapping_global_id"))),
            registry_global_id=UUID(str(_value(document, "registry_global_id"))),
            version=_integer(_value(document, "mapping_version")),
            snapshot_hash=str(_value(document, "mapping_snapshot_hash")),
            template_sha256=str(_value(document, "template_sha256")),
        ),
        language=str(_value(document, "language")),
        delivery_mode=PrintDeliveryMode(str(_value(document, "delivery_mode"))),
        copy_state=PrintCopyState(str(_value(document, "copy_state"))),
        watermark_source=str(_value(document, "watermark_source")),
        source_snapshot=source_snapshot,
        actor_user_id=str(_value(document, "actor_user_id")),
        printed_at=_datetime(_value(document, "printed_at")),
        request_id=UUID(str(_value(document, "request_id"))),
        trace_id=str(_value(document, "trace_id")),
        version=_integer(_value(document, "snapshot_version")),
        snapshot_hash=str(_value(document, "snapshot_hash")),
        verification_payload=str(_value(document, "verification_payload")),
    )
    if _json_object(_value(document, "snapshot")) != value.snapshot_payload():
        raise RuntimeError(
            "Persisted controlled print snapshot does not match its fields."
        )
    return value


def _output_value(document: object) -> ControlledPrintOutput:
    value = ControlledPrintOutput(
        global_id=UUID(str(_value(document, "global_id"))),
        tenant_id=str(_value(document, "tenant_id")),
        project_global_id=UUID(str(_value(document, "project_global_id"))),
        snapshot_global_id=UUID(str(_value(document, "snapshot_global_id"))),
        frappe_file_id=str(_value(document, "frappe_file_id")),
        file_name=str(_value(document, "file_name")),
        mime_type=str(_value(document, "mime_type")),
        size_bytes=_integer(_value(document, "size_bytes")),
        frappe_content_hash=str(_value(document, "frappe_content_hash")),
        sha256=str(_value(document, "sha256")),
        created_by_user_id=str(_value(document, "created_by_user_id")),
        created_at=_datetime(_value(document, "created_at")),
        record_hash=str(_value(document, "record_hash")),
    )
    if _json_object(_value(document, "output_snapshot")) != value.record_payload():
        raise RuntimeError(
            "Persisted controlled print output does not match its fields."
        )
    if str(_value(document, "controlled_print_snapshot")) != str(
        value.snapshot_global_id
    ):
        raise RuntimeError("Controlled print output escaped its snapshot parent.")
    return value


def _saved_file_matches(
    file_document: object,
    snapshot: ControlledPrintSnapshot,
    rendered: RenderedControlledPrintPdf,
) -> bool:
    content = file_document.get_content()
    if isinstance(content, str):
        content = content.encode("utf-8")
    return bool(
        isinstance(content, bytes)
        and content == rendered.content
        and str(_value(file_document, "attached_to_doctype"))
        == "NPI Controlled Print Snapshot"
        and str(_value(file_document, "attached_to_name")) == str(snapshot.global_id)
        and str(_value(file_document, "file_name")) == rendered.file_name
        and int(_value(file_document, "file_size") or 0) == rendered.size_bytes
        and int(_value(file_document, "is_private") or 0) == 1
        and int(_value(file_document, "is_remote_file") or 0) == 0
        and _private_file_url(_value(file_document, "file_url")) is not None
        and isinstance(_value(file_document, "content_hash"), str)
        and len(str(_value(file_document, "content_hash"))) == 32
        and all(
            character in "0123456789abcdef"
            for character in str(_value(file_document, "content_hash"))
        )
    )


def _file_identity_matches(
    file_document: object,
    output: ControlledPrintOutput,
) -> bool:
    return bool(
        str(_value(file_document, "name")) == output.frappe_file_id
        and str(_value(file_document, "file_name")) == output.file_name
        and int(_value(file_document, "file_size") or 0) == output.size_bytes
        and str(_value(file_document, "content_hash")) == output.frappe_content_hash
        and int(_value(file_document, "is_private") or 0) == 1
        and int(_value(file_document, "is_remote_file") or 0) == 0
        and str(_value(file_document, "attached_to_doctype"))
        == "NPI Controlled Print Snapshot"
        and str(_value(file_document, "attached_to_name"))
        == str(output.snapshot_global_id)
        and _private_file_url(_value(file_document, "file_url")) is not None
    )


def _private_file_url(value: object) -> PurePosixPath | None:
    file_url = str(value or "")
    parsed = PurePosixPath(file_url)
    if (
        not file_url.startswith("/private/files/")
        or len(parsed.parts) != 4
        or parsed.parts[:3] != ("/", "private", "files")
        or parsed.name in {"", ".", ".."}
    ):
        return None
    return parsed


def _register_orphan_cleanup(file_document: object) -> None:
    file_url = str(_value(file_document, "file_url"))
    parsed = _private_file_url(file_url)
    if parsed is None:
        raise RuntimeError("Controlled print private File path is invalid.")
    private_directory = Path(frappe.get_site_path("private", "files")).resolve()
    file_path = (private_directory / parsed.name).resolve()
    if file_path.parent != private_directory:
        raise RuntimeError("Controlled print private File escaped its boundary.")

    def cleanup_after_rollback() -> None:
        try:
            remaining = frappe.db.get_value(
                "File",
                {"file_url": file_url},
                "name",
            )
            if not remaining:
                file_path.unlink(missing_ok=True)
        except Exception as error:
            from npi_core.api import record_safe_diagnostic

            record_safe_diagnostic(
                code="CONTROLLED_PRINT_ORPHAN_FILE_CLEANUP_FAILED",
                title="NPI controlled print orphan file cleanup failed",
                exception_type=type(error).__name__,
            )

    frappe.db.after_rollback.add(cleanup_after_rollback)


@contextmanager
def _controlled_print_write_scope():
    flags = frappe.flags
    missing = object()
    previous = getattr(flags, "npi_audit_append", missing)
    setattr(flags, "npi_audit_append", True)
    try:
        with controlled_print_command_write():
            yield
    finally:
        if previous is missing:
            try:
                delattr(flags, "npi_audit_append")
            except AttributeError:
                pass
        else:
            setattr(flags, "npi_audit_append", previous)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _database_datetime(value: datetime) -> str:
    return _datetime(value).replace(tzinfo=None).isoformat(
        sep=" ",
        timespec="microseconds",
    )


def _optional_doc(doctype: str, name: str) -> object | None:
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _value(record: object, fieldname: str) -> object:
    if isinstance(record, Mapping):
        return record.get(fieldname)
    return getattr(record, fieldname, None)


def _integer(value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeError("Persisted controlled print integer is invalid.")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("Persisted controlled print integer is invalid.") from error


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "Persisted controlled print date and time is invalid."
            ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_datetime(value: object) -> datetime | None:
    return None if value in (None, "") else _datetime(value)


def _json_array(value: object) -> list[Any]:
    parsed = _json_value(value)
    if not isinstance(parsed, list):
        raise RuntimeError("Persisted controlled print JSON must be an array.")
    return parsed


def _json_object(value: object) -> dict[str, Any]:
    parsed = _json_value(value)
    if not isinstance(parsed, dict):
        raise RuntimeError("Persisted controlled print JSON must be an object.")
    return parsed


def _json_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value, parse_constant=_reject_json_constant)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Persisted controlled print JSON is invalid.") from error
    return value


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Unsupported JSON constant: {value}")
