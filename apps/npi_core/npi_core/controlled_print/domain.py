from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


CONTROLLED_PRINT_SCHEMA_VERSION = 1
CONTROLLED_PRINT_OPERATION = "create_controlled_print_snapshot"
MAX_SOURCE_SNAPSHOT_BYTES = 524_288
MAX_TEMPLATE_BYTES = 262_144

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LANGUAGE_CODES = frozenset({"en", "zh", "zh-TW"})
_MIME_TYPE = "application/pdf"


class ControlledPrintMappingUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "CONTROLLED_PRINT_MAPPING_UNAVAILABLE",
            _("No approved controlled print mapping is available."),
        )


class ControlledPrintMappingAmbiguous(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "CONTROLLED_PRINT_MAPPING_AMBIGUOUS",
            _("The controlled print mapping is unavailable."),
        )


class ControlledPrintUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "CONTROLLED_PRINT_UNAVAILABLE",
            _("The controlled print output is unavailable."),
        )


class ControlledPrintAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "CONTROLLED_PRINT_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to create this controlled print output."),
        )


class ControlledPrintStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "CONTROLLED_PRINT_STATE_CONFLICT",
            _("The controlled print source changed. Reload it before continuing."),
        )


class ControlledPrintIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "CONTROLLED_PRINT_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different print request."),
        )


class PrintRegistryState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class PrintDeliveryMode(StrEnum):
    CONTROLLED_PDF = "controlled_pdf"


class PrintCopyState(StrEnum):
    NOT_NUMBERED = "not_numbered"


class PrintAccessEventType(StrEnum):
    CREATED = "created"
    DOWNLOADED = "downloaded"


@dataclass(frozen=True, slots=True)
class ControlledPrintContext:
    tenant_id: str
    project_global_id: UUID
    source_object_type: str
    project_type_key: str
    gate_key: str | None
    source_state: str
    language: str
    delivery_mode: PrintDeliveryMode = PrintDeliveryMode.CONTROLLED_PDF
    copy_state: PrintCopyState = PrintCopyState.NOT_NUMBERED

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "projectGlobalId"),
        )
        for fieldname in ("source_object_type", "project_type_key", "source_state"):
            object.__setattr__(
                self,
                fieldname,
                _key(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "gate_key", _optional_key(self.gate_key, "gateKey"))
        object.__setattr__(self, "language", _language(self.language))
        if not isinstance(self.delivery_mode, PrintDeliveryMode):
            raise _field_problem("deliveryMode", _("Select a supported value."))
        if not isinstance(self.copy_state, PrintCopyState):
            raise _field_problem("copyState", _("Select a supported value."))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "sourceObjectType": self.source_object_type,
            "projectTypeKey": self.project_type_key,
            "gateKey": self.gate_key,
            "sourceState": self.source_state,
            "language": self.language,
            "deliveryMode": self.delivery_mode.value,
            "copyState": self.copy_state.value,
        }


@dataclass(frozen=True, slots=True)
class ControlledPrintRegistryVersion:
    global_id: UUID
    registry_global_id: UUID
    tenant_id: str
    mapping_key: str
    mapping_version: int
    title: str
    state: PrintRegistryState
    source_object_type: str
    project_type_key: str
    gate_key: str | None
    source_state: str
    language: str
    delivery_mode: PrintDeliveryMode
    copy_state: PrintCopyState
    print_format_name: str
    template_content: str
    template_sha256: str
    watermark_source: str
    printer_user_ids: tuple[str, ...]
    effective_from: datetime
    effective_to: datetime | None = None
    published_at: datetime | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "registry_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "mapping_key", _key(self.mapping_key, "mappingKey"))
        object.__setattr__(
            self,
            "mapping_version",
            _positive(self.mapping_version, "mappingVersion"),
        )
        object.__setattr__(self, "title", _text(self.title, "title", 140))
        if not isinstance(self.state, PrintRegistryState):
            raise _field_problem("state", _("Select a supported value."))
        for fieldname in ("source_object_type", "project_type_key", "source_state"):
            object.__setattr__(
                self,
                fieldname,
                _key(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "gate_key", _optional_key(self.gate_key, "gateKey"))
        object.__setattr__(self, "language", _language(self.language))
        if not isinstance(self.delivery_mode, PrintDeliveryMode):
            raise _field_problem("deliveryMode", _("Select a supported value."))
        if not isinstance(self.copy_state, PrintCopyState):
            raise _field_problem("copyState", _("Select a supported value."))
        object.__setattr__(
            self,
            "print_format_name",
            _text(self.print_format_name, "printFormatName", 140),
        )
        template_content = _template(self.template_content)
        object.__setattr__(self, "template_content", template_content)
        expected_template_hash = hashlib.sha256(
            template_content.encode("utf-8")
        ).hexdigest()
        supplied_template_hash = _hash(self.template_sha256, "templateSha256")
        if supplied_template_hash != expected_template_hash:
            raise _field_problem(
                "templateSha256",
                _("The Print Format content hash does not match."),
            )
        object.__setattr__(self, "template_sha256", supplied_template_hash)
        object.__setattr__(
            self,
            "watermark_source",
            _text(self.watermark_source, "watermarkSource", 140),
        )
        object.__setattr__(
            self,
            "printer_user_ids",
            _users(self.printer_user_ids, "printerUserIds"),
        )
        effective_from = _aware_utc(self.effective_from, "effectiveFrom")
        effective_to = (
            None
            if self.effective_to is None
            else _aware_utc(self.effective_to, "effectiveTo")
        )
        if effective_to is not None and effective_to <= effective_from:
            raise _field_problem(
                "effectiveTo",
                _("Effective To must be later than Effective From."),
            )
        object.__setattr__(self, "effective_from", effective_from)
        object.__setattr__(self, "effective_to", effective_to)
        if self.state is PrintRegistryState.PUBLISHED:
            if self.published_at is None:
                raise _field_problem(
                    "publishedAt",
                    _("Published At is required for a published mapping."),
                )
            object.__setattr__(
                self,
                "published_at",
                _aware_utc(self.published_at, "publishedAt"),
            )
        elif self.published_at is not None:
            raise _field_problem(
                "publishedAt",
                _("A draft mapping cannot have a publication time."),
            )
        expected_snapshot_hash = sha256_json(self.snapshot_payload())
        supplied_snapshot_hash = self.snapshot_hash
        if supplied_snapshot_hash and _hash(
            supplied_snapshot_hash,
            "snapshotHash",
        ) != expected_snapshot_hash:
            raise _field_problem(
                "snapshotHash",
                _("The controlled print mapping snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot_hash)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CONTROLLED_PRINT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "registryGlobalId": str(self.registry_global_id),
            "tenantId": self.tenant_id,
            "mappingKey": self.mapping_key,
            "mappingVersion": self.mapping_version,
            "title": self.title,
            "state": self.state.value,
            "sourceObjectType": self.source_object_type,
            "projectTypeKey": self.project_type_key,
            "gateKey": self.gate_key,
            "sourceState": self.source_state,
            "language": self.language,
            "deliveryMode": self.delivery_mode.value,
            "copyState": self.copy_state.value,
            "printFormatName": self.print_format_name,
            "templateContent": self.template_content,
            "templateSha256": self.template_sha256,
            "watermarkSource": self.watermark_source,
            "printerUserIds": list(self.printer_user_ids),
            "effectiveFrom": _utc_text(self.effective_from),
            "effectiveTo": (
                None if self.effective_to is None else _utc_text(self.effective_to)
            ),
            "publishedAt": (
                None if self.published_at is None else _utc_text(self.published_at)
            ),
        }

    def matches(self, context: ControlledPrintContext, at: datetime) -> bool:
        instant = _aware_utc(at, "at")
        return bool(
            self.state is PrintRegistryState.PUBLISHED
            and self.tenant_id == context.tenant_id
            and self.source_object_type == context.source_object_type
            and self.project_type_key == context.project_type_key
            and self.gate_key == context.gate_key
            and self.source_state == context.source_state
            and self.language == context.language
            and self.delivery_mode is context.delivery_mode
            and self.copy_state is context.copy_state
            and self.effective_from <= instant
            and (self.effective_to is None or instant < self.effective_to)
        )

    def authorizes(self, actor_user_id: str) -> bool:
        return _actor(actor_user_id, "actorUserId") in self.printer_user_ids

    def public_reference(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "registryGlobalId": str(self.registry_global_id),
            "version": self.mapping_version,
            "snapshotHash": self.snapshot_hash,
            "language": self.language,
            "deliveryMode": self.delivery_mode.value,
            "copyState": self.copy_state.value,
        }


def resolve_controlled_print_mapping(
    mappings: Sequence[ControlledPrintRegistryVersion],
    context: ControlledPrintContext,
    *,
    at: datetime,
) -> ControlledPrintRegistryVersion:
    matches = tuple(mapping for mapping in mappings if mapping.matches(context, at))
    if not matches:
        raise ControlledPrintMappingUnavailable()
    if len(matches) != 1:
        raise ControlledPrintMappingAmbiguous()
    return matches[0]


@dataclass(frozen=True, slots=True)
class ControlledPrintSourceReference:
    source_object_type: str
    source_global_id: UUID
    source_version: int
    source_state: str
    source_snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_object_type",
            _key(self.source_object_type, "sourceObjectType"),
        )
        object.__setattr__(
            self,
            "source_global_id",
            _uuid(self.source_global_id, "sourceGlobalId"),
        )
        object.__setattr__(
            self,
            "source_version",
            _positive(self.source_version, "sourceVersion"),
        )
        object.__setattr__(
            self,
            "source_state",
            _key(self.source_state, "sourceState"),
        )
        object.__setattr__(
            self,
            "source_snapshot_hash",
            _hash(self.source_snapshot_hash, "sourceSnapshotHash"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "sourceKind": self.source_object_type,
            "sourceGlobalId": str(self.source_global_id),
            "sourceVersion": self.source_version,
            "sourceState": self.source_state,
            "sourceSnapshotHash": self.source_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class ControlledPrintRegistryReference:
    mapping_global_id: UUID
    registry_global_id: UUID
    version: int
    snapshot_hash: str
    template_sha256: str

    def __post_init__(self) -> None:
        for fieldname in ("mapping_global_id", "registry_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "version", _positive(self.version, "version"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "registrySnapshotHash"),
        )
        object.__setattr__(
            self,
            "template_sha256",
            _hash(self.template_sha256, "templateSha256"),
        )

    @classmethod
    def from_mapping(
        cls,
        mapping: ControlledPrintRegistryVersion,
    ) -> "ControlledPrintRegistryReference":
        if mapping.state is not PrintRegistryState.PUBLISHED:
            raise ControlledPrintMappingUnavailable()
        return cls(
            mapping.global_id,
            mapping.registry_global_id,
            mapping.mapping_version,
            mapping.snapshot_hash,
            mapping.template_sha256,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.mapping_global_id),
            "registryGlobalId": str(self.registry_global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
            "templateSha256": self.template_sha256,
        }


@dataclass(frozen=True, slots=True)
class ControlledPrintSnapshot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    project_type_key: str
    gate_key: str | None
    source: ControlledPrintSourceReference
    registry: ControlledPrintRegistryReference
    language: str
    delivery_mode: PrintDeliveryMode
    copy_state: PrintCopyState
    watermark_source: str
    source_snapshot: Mapping[str, object]
    actor_user_id: str
    printed_at: datetime
    request_id: UUID
    trace_id: str
    version: int = 1
    snapshot_hash: str = ""
    verification_payload: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "globalId"))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "project_global_id",
            _uuid(self.project_global_id, "projectGlobalId"),
        )
        object.__setattr__(
            self,
            "project_type_key",
            _key(self.project_type_key, "projectTypeKey"),
        )
        object.__setattr__(self, "gate_key", _optional_key(self.gate_key, "gateKey"))
        if not isinstance(self.source, ControlledPrintSourceReference):
            raise _field_problem("source", _("Enter a valid value."))
        if not isinstance(self.registry, ControlledPrintRegistryReference):
            raise _field_problem("registry", _("Enter a valid value."))
        object.__setattr__(self, "language", _language(self.language))
        if not isinstance(self.delivery_mode, PrintDeliveryMode):
            raise _field_problem("deliveryMode", _("Select a supported value."))
        if not isinstance(self.copy_state, PrintCopyState):
            raise _field_problem("copyState", _("Select a supported value."))
        object.__setattr__(
            self,
            "watermark_source",
            _text(self.watermark_source, "watermarkSource", 140),
        )
        frozen_source = _freeze_json_object(self.source_snapshot, "sourceSnapshot")
        if sha256_json(frozen_source) != self.source.source_snapshot_hash:
            raise _field_problem(
                "sourceSnapshot",
                _("The controlled print source snapshot hash does not match."),
            )
        object.__setattr__(self, "source_snapshot", frozen_source)
        object.__setattr__(
            self,
            "actor_user_id",
            _actor(self.actor_user_id, "actorUserId"),
        )
        object.__setattr__(
            self,
            "printed_at",
            _aware_utc(self.printed_at, "printedAt"),
        )
        object.__setattr__(self, "request_id", _uuid(self.request_id, "requestId"))
        object.__setattr__(self, "trace_id", _trace(self.trace_id))
        object.__setattr__(self, "version", _positive(self.version, "version"))
        if self.version != 1:
            raise _field_problem(
                "version",
                _("Controlled print snapshots start at version 1."),
            )
        expected_snapshot_hash = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and _hash(
            self.snapshot_hash,
            "snapshotHash",
        ) != expected_snapshot_hash:
            raise _field_problem(
                "snapshotHash",
                _("The controlled print snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_snapshot_hash)
        expected_verification = (
            f"urn:npi:controlled-print:{self.global_id}:{expected_snapshot_hash}"
        )
        if self.verification_payload and self.verification_payload != expected_verification:
            raise _field_problem(
                "verificationPayload",
                _("The controlled print verification payload does not match."),
            )
        object.__setattr__(self, "verification_payload", expected_verification)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CONTROLLED_PRINT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "projectTypeKey": self.project_type_key,
            "gateKey": self.gate_key,
            "source": self.source.canonical_dict(),
            "registry": self.registry.canonical_dict(),
            "language": self.language,
            "deliveryMode": self.delivery_mode.value,
            "copyState": self.copy_state.value,
            "watermarkSource": self.watermark_source,
            "sourceSnapshot": _plain_json(self.source_snapshot),
            "actorUserId": self.actor_user_id,
            "printedAt": _utc_text(self.printed_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "version": self.version,
        }

    def public_dict(self, *, output: "ControlledPrintOutput | None" = None) -> dict[str, object]:
        body: dict[str, object] = {
            "globalId": str(self.global_id),
            "version": self.version,
            "source": self.source.canonical_dict(),
            "registry": self.registry.canonical_dict(),
            "language": self.language,
            "deliveryMode": self.delivery_mode.value,
            "copyState": self.copy_state.value,
            "watermarkSource": self.watermark_source,
            "actorUserId": self.actor_user_id,
            "printedAt": _utc_text(self.printed_at),
            "snapshotHash": self.snapshot_hash,
            "verificationPayload": self.verification_payload,
            "output": None,
        }
        if output is not None:
            if output.snapshot_global_id != self.global_id:
                raise _field_problem("output", _("Enter a valid value."))
            body["output"] = output.public_dict()
        return body


@dataclass(frozen=True, slots=True)
class ControlledPrintOutput:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    snapshot_global_id: UUID
    frappe_file_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    frappe_content_hash: str
    sha256: str
    created_by_user_id: str
    created_at: datetime
    record_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "project_global_id", "snapshot_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "frappe_file_id",
            _text(self.frappe_file_id, "frappeFileId", 140),
        )
        object.__setattr__(self, "file_name", _pdf_filename(self.file_name))
        if self.mime_type != _MIME_TYPE:
            raise _field_problem("mimeType", _("Select a supported value."))
        object.__setattr__(self, "size_bytes", _positive(self.size_bytes, "sizeBytes"))
        object.__setattr__(
            self,
            "frappe_content_hash",
            _hex(self.frappe_content_hash, "frappeContentHash", 32),
        )
        object.__setattr__(self, "sha256", _hash(self.sha256, "sha256"))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(
            self,
            "created_at",
            _aware_utc(self.created_at, "createdAt"),
        )
        expected_record_hash = sha256_json(self.record_payload())
        if self.record_hash and _hash(
            self.record_hash,
            "recordHash",
        ) != expected_record_hash:
            raise _field_problem(
                "recordHash",
                _("The controlled print output record hash does not match."),
            )
        object.__setattr__(self, "record_hash", expected_record_hash)

    def record_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CONTROLLED_PRINT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "snapshotGlobalId": str(self.snapshot_global_id),
            "frappeFileId": self.frappe_file_id,
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "frappeContentHash": self.frappe_content_hash,
            "sha256": self.sha256,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
        }

    def public_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "fileName": self.file_name,
            "mimeType": self.mime_type,
            "sizeBytes": self.size_bytes,
            "sha256": self.sha256,
            "recordHash": self.record_hash,
        }


@dataclass(frozen=True, slots=True)
class ControlledPrintAccessEvent:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    snapshot_global_id: UUID
    output_global_id: UUID
    event_type: PrintAccessEventType
    actor_user_id: str
    occurred_at: datetime
    trace_id: str
    event_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "snapshot_global_id",
            "output_global_id",
        ):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), _camel(fieldname)),
            )
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        if not isinstance(self.event_type, PrintAccessEventType):
            raise _field_problem("eventType", _("Select a supported value."))
        object.__setattr__(
            self,
            "actor_user_id",
            _actor(self.actor_user_id, "actorUserId"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _aware_utc(self.occurred_at, "occurredAt"),
        )
        object.__setattr__(self, "trace_id", _trace(self.trace_id))
        expected_event_hash = sha256_json(self.event_payload())
        if self.event_hash and _hash(
            self.event_hash,
            "eventHash",
        ) != expected_event_hash:
            raise _field_problem(
                "eventHash",
                _("The controlled print access event hash does not match."),
            )
        object.__setattr__(self, "event_hash", expected_event_hash)

    def event_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": CONTROLLED_PRINT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "snapshotGlobalId": str(self.snapshot_global_id),
            "outputGlobalId": str(self.output_global_id),
            "eventType": self.event_type.value,
            "actorUserId": self.actor_user_id,
            "occurredAt": _utc_text(self.occurred_at),
            "traceId": self.trace_id,
        }


def sha256_json(value: object) -> str:
    try:
        canonical = json.dumps(
            _plain_json(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise _field_problem("value", _("Enter a valid JSON value.")) from error
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def freeze_controlled_print_source(
    value: object,
) -> Mapping[str, object]:
    """Freeze one complete server-resolved source before mapping or rendering."""

    return _freeze_json_object(value, "sourceSnapshot")


def controlled_print_command_payload_hash(
    *,
    actor_user_id: object,
    tenant_id: object,
    project_global_id: object,
    source_object_type: object,
    source_global_id: object,
    source_version: object,
    language: object,
) -> str:
    """Bind one create request to its actor, Project and exact browser fields."""

    return sha256_json(
        {
            "operation": CONTROLLED_PRINT_OPERATION,
            "actorUserId": _actor(actor_user_id, "actorUserId"),
            "tenantId": _key(tenant_id, "tenantId"),
            "projectGlobalId": str(_uuid(project_global_id, "projectGlobalId")),
            "sourceKind": _key(source_object_type, "sourceKind"),
            "sourceGlobalId": str(_uuid(source_global_id, "sourceGlobalId")),
            "sourceVersion": _positive(source_version, "sourceVersion"),
            "language": _language(language),
        }
    )


def controlled_print_receipt_key(
    *,
    actor_user_id: object,
    tenant_id: object,
    project_global_id: object,
    idempotency_key_hash: object,
) -> str:
    """Return the persisted actor/Project/operation idempotency identity."""

    actor = _actor(actor_user_id, "actorUserId")
    tenant = _key(tenant_id, "tenantId")
    project_id = _uuid(project_global_id, "projectGlobalId")
    key_hash = _hash(idempotency_key_hash, "idempotencyKeyHash")
    return hashlib.sha256(
        (
            f"{tenant}\0{project_id}\0{actor}\0{CONTROLLED_PRINT_OPERATION}\0"
            f"{key_hash}"
        ).encode("utf-8")
    ).hexdigest()


def _freeze_json_object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise _field_problem(path, _("Enter a non-empty JSON object."))
    plain = _plain_json(value)
    try:
        encoded = json.dumps(
            plain,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid JSON value.")) from error
    if len(encoded) > MAX_SOURCE_SNAPSHOT_BYTES:
        raise _field_problem(path, _("The source snapshot is too large."))
    return _freeze_json(plain)  # type: ignore[return-value]


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise _field_problem("value", _("Enter a valid JSON value."))


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_plain_json(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise _field_problem("value", _("Enter a valid JSON value."))


def _uuid(value: object, path: str) -> UUID:
    try:
        result = value if isinstance(value, UUID) else UUID(str(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise _field_problem(path, _("Enter a valid UUID.")) from error
    if result.version != 4:
        raise _field_problem(path, _("Enter a version 4 UUID."))
    return result


def _positive(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _field_problem(path, _("Enter a positive integer."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or value != value.strip() or not value:
        raise _field_problem(path, _("Enter a valid value."))
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise _field_problem(path, _("Enter a shorter value."))
    return value


def _template(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem("templateContent", _("Enter a valid value."))
    if len(value.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise _field_problem("templateContent", _("Enter a shorter value."))
    if any(ord(character) < 32 and character not in "\t\r\n" for character in value):
        raise _field_problem("templateContent", _("Enter a valid value."))
    return value


def _key(value: object, path: str) -> str:
    result = _text(value, path, 128)
    if _KEY_PATTERN.fullmatch(result) is None:
        raise _field_problem(path, _("Enter a valid identifier."))
    return result


def _optional_key(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _key(value, path)


def _language(value: object) -> str:
    if value not in _LANGUAGE_CODES:
        raise _field_problem("language", _("Select a supported language."))
    return str(value)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a lowercase SHA-256 value."))
    return value


def _hex(value: object, path: str, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or re.fullmatch(r"[a-f0-9]+", value) is None
    ):
        raise _field_problem(path, _("Enter a valid lowercase hexadecimal value."))
    return value


def _actor(value: object, path: str) -> str:
    result = _text(value, path, 254)
    if _ACTOR_PATTERN.fullmatch(result) is None:
        raise _field_problem(path, _("Enter a valid user ID."))
    return result


def _users(values: object, path: str) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise _field_problem(path, _("Enter one or more user IDs."))
    users = tuple(sorted({_actor(value, path) for value in values}))
    if not users or len(users) > 100 or len(users) != len(values):
        raise _field_problem(path, _("Enter one or more unique user IDs."))
    return users


def _trace(value: object) -> str:
    result = _text(value, "traceId", 128)
    if len(result) < 8 or re.fullmatch(r"[A-Za-z0-9._:-]+", result) is None:
        raise _field_problem("traceId", _("Enter a valid Trace ID."))
    return result


def _aware_utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _pdf_filename(value: object) -> str:
    result = _text(value, "fileName", 140)
    if "/" in result or "\\" in result or not result.casefold().endswith(".pdf"):
        raise _field_problem("fileName", _("Enter a valid PDF file name."))
    return result


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
