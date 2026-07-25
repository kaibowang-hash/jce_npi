from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid5

from npi_core.foundation.concurrency import next_version
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain model testable without a Bench runtime.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_PROJECT_ID_NAMESPACE = UUID("44db5db6-a778-4d5d-af32-d5301c286f00")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_IDEMPOTENCY_HEADER_PATTERN = re.compile(r"^[\x21-\x7e]{16,255}$")
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


class ProjectType(str, Enum):
    CUSTOMER_OWNED_TOOL = "customer_owned_tool"
    NEW_TOOL = "new_tool"
    TOOL_CHANGE = "tool_change"


class ProjectReferenceType(str, Enum):
    CUSTOMER = "customer"
    PRODUCT = "product"
    PART = "part"
    TOOLING = "tooling"
    ORDER = "order"


class ReferenceSourceSystem(str, Enum):
    NPI_ONE = "NPI_ONE"
    ERPNEXT = "ERPNEXT"


class ProjectSourceSystem(str, Enum):
    NPI_ONE = "NPI_ONE"


class TemplatePublicationState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ProjectLifecycleState(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class GateShellState(str, Enum):
    NOT_STARTED = "not_started"


class TemplateUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "PROJECT_TEMPLATE_UNAVAILABLE",
            _("The selected project template version is unavailable."),
            field_errors=[
                {
                    "path": "templateVersion",
                    "message": _("Select an available project template version."),
                }
            ],
        )


class TemplateNotPublished(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "PROJECT_TEMPLATE_NOT_PUBLISHED",
            _("The selected project template version is not published."),
            field_errors=[
                {
                    "path": "templateVersion",
                    "message": _("Select a published project template version."),
                }
            ],
        )


class PublishedTemplateImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PUBLISHED_TEMPLATE_IMMUTABLE",
            _("A published project template version cannot be changed."),
        )


class IdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "IDEMPOTENCY_KEY_CONFLICT",
            _("The idempotency key was already used for a different request."),
        )


class BusinessCodeConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PROJECT_BUSINESS_CODE_CONFLICT",
            _("The project business code is already in use."),
            field_errors=[
                {
                    "path": "businessCode",
                    "message": _("Enter a unique project business code."),
                }
            ],
        )


def _validation(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _require_enum(value: object, expected_type: type[Enum], path: str) -> None:
    if not isinstance(value, expected_type):
        raise _validation(path, _("Select a supported value."))


def _require_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _validation(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum_length or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        raise _validation(path, _("Enter a valid value."))
    return normalized


def validate_template_code(value: object) -> str:
    """Return the canonical code accepted by every Project Template version."""
    return _require_text(
        value,
        "templateCode",
        maximum_length=64,
        pattern=_CODE_PATTERN,
    )


@dataclass(frozen=True, slots=True)
class TemplateReferenceRule:
    reference_type: ProjectReferenceType
    required: bool = False
    allow_multiple: bool = False

    def __post_init__(self) -> None:
        _require_enum(self.reference_type, ProjectReferenceType, "referenceRules.type")
        if type(self.required) is not bool or type(self.allow_multiple) is not bool:
            raise _validation("referenceRules", _("Enter valid reference rules."))


@dataclass(frozen=True, slots=True)
class GateDefinition:
    key: str
    title: str
    sequence: int
    gate_template_global_id: UUID | None = None
    gate_template_version: int | None = None
    gate_template_snapshot_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key",
            _require_text(
                self.key,
                "gates.key",
                maximum_length=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "gates.title", maximum_length=140),
        )
        if type(self.sequence) is not int or self.sequence < 1:
            raise _validation(
                "gates.sequence",
                _("Enter a positive gate sequence."),
            )
        template_ref = (
            self.gate_template_global_id,
            self.gate_template_version,
            self.gate_template_snapshot_hash,
        )
        if any(value is not None for value in template_ref) and not all(
            value is not None for value in template_ref
        ):
            raise _validation(
                "gates.gateTemplateRef",
                _("Enter a complete Gate Template reference."),
            )
        if self.gate_template_global_id is not None:
            if not isinstance(self.gate_template_global_id, UUID):
                raise _validation(
                    "gates.gateTemplateRef.globalId",
                    _("Enter a valid global ID."),
                )
            if (
                type(self.gate_template_version) is not int
                or self.gate_template_version < 1
            ):
                raise _validation(
                    "gates.gateTemplateRef.version",
                    _("Enter a positive Gate Template version."),
                )
            if (
                not isinstance(self.gate_template_snapshot_hash, str)
                or _HASH_PATTERN.fullmatch(self.gate_template_snapshot_hash) is None
            ):
                raise _validation(
                    "gates.gateTemplateRef.snapshotHash",
                    _("Enter a valid Gate Template snapshot hash."),
                )

    @property
    def has_gate_template_ref(self) -> bool:
        return self.gate_template_global_id is not None

    def canonical_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "key": self.key,
            "title": self.title,
            "sequence": self.sequence,
        }
        if self.has_gate_template_ref:
            value["gateTemplateRef"] = {
                "globalId": str(self.gate_template_global_id),
                "version": self.gate_template_version,
                "snapshotHash": self.gate_template_snapshot_hash,
            }
        return value


@dataclass(frozen=True, slots=True)
class TypedReference:
    reference_type: ProjectReferenceType
    source_system: ReferenceSourceSystem
    source_object_id: str
    global_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_enum(self.reference_type, ProjectReferenceType, "references.type")
        _require_enum(
            self.source_system, ReferenceSourceSystem, "references.sourceSystem"
        )
        object.__setattr__(
            self,
            "source_object_id",
            _require_text(
                self.source_object_id,
                "references.sourceObjectId",
                maximum_length=128,
                pattern=_IDENTIFIER_PATTERN,
            ),
        )
        if self.global_id is not None and not isinstance(self.global_id, UUID):
            raise _validation("references.globalId", _("Enter a valid global ID."))

    def canonical_dict(self) -> dict[str, str | None]:
        return {
            "type": self.reference_type.value,
            "sourceSystem": self.source_system.value,
            "sourceObjectId": self.source_object_id,
            "globalId": str(self.global_id) if self.global_id is not None else None,
        }


@dataclass(frozen=True, slots=True)
class TemplateSnapshot:
    template_global_id: UUID
    template_code: str
    template_version: int
    snapshot_hash: str
    applicable_project_types: tuple[ProjectType, ...]
    reference_rules: tuple[TemplateReferenceRule, ...]
    gates: tuple[GateDefinition, ...]


@dataclass(frozen=True, slots=True)
class ProjectTemplateVersion:
    global_id: UUID
    template_global_id: UUID
    template_code: str
    template_version: int
    version: int
    title: str
    publication_state: TemplatePublicationState
    applicable_project_types: tuple[ProjectType, ...]
    reference_rules: tuple[TemplateReferenceRule, ...]
    gates: tuple[GateDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.global_id, UUID) or not isinstance(
            self.template_global_id, UUID
        ):
            raise _validation("templateGlobalId", _("Enter a valid global ID."))
        object.__setattr__(
            self,
            "template_code",
            validate_template_code(self.template_code),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "templateTitle", maximum_length=140),
        )
        if type(self.template_version) is not int or self.template_version < 1:
            raise _validation(
                "templateVersion",
                _("Enter a positive template version."),
            )
        if type(self.version) is not int or self.version < 1:
            raise _validation(
                "expectedVersion",
                _("Enter a positive expected version."),
            )
        _require_enum(
            self.publication_state,
            TemplatePublicationState,
            "publicationState",
        )
        project_types = tuple(self.applicable_project_types)
        if not project_types or any(
            not isinstance(item, ProjectType) for item in project_types
        ):
            raise _validation(
                "applicableProjectTypes",
                _("Select at least one project type."),
            )
        project_types = tuple(sorted(project_types, key=lambda item: item.value))
        if len(set(project_types)) != len(project_types):
            raise _validation(
                "applicableProjectTypes",
                _("Project types must be unique."),
            )
        object.__setattr__(self, "applicable_project_types", project_types)

        rules = tuple(self.reference_rules)
        if any(not isinstance(item, TemplateReferenceRule) for item in rules):
            raise _validation("referenceRules", _("Enter valid reference rules."))
        rules = tuple(sorted(rules, key=lambda item: item.reference_type.value))
        if len({rule.reference_type for rule in rules}) != len(rules):
            raise _validation(
                "referenceRules",
                _("Reference rule types must be unique."),
            )
        object.__setattr__(self, "reference_rules", rules)

        gates = tuple(self.gates)
        if any(not isinstance(item, GateDefinition) for item in gates):
            raise _validation("gates", _("Enter valid gate definitions."))
        gates = tuple(sorted(gates, key=lambda item: (item.sequence, item.key)))
        if len({gate.key.casefold() for gate in gates}) != len(gates):
            raise _validation("gates", _("Gate keys must be unique."))
        if len({gate.sequence for gate in gates}) != len(gates):
            raise _validation("gates", _("Gate sequences must be unique."))
        object.__setattr__(self, "gates", gates)
        if self.publication_state is TemplatePublicationState.PUBLISHED:
            self._validate_publishable()

    @classmethod
    def create_draft(
        cls,
        *,
        template_global_id: UUID,
        template_code: str,
        template_version: int,
        title: str,
        applicable_project_types: tuple[ProjectType, ...],
        reference_rules: tuple[TemplateReferenceRule, ...] = (),
        gates: tuple[GateDefinition, ...] = (),
    ) -> ProjectTemplateVersion:
        version_global_id = uuid5(
            template_global_id,
            f"project-template-version:{template_version}",
        )
        return cls(
            global_id=version_global_id,
            template_global_id=template_global_id,
            template_code=template_code,
            template_version=template_version,
            version=1,
            title=title,
            publication_state=TemplatePublicationState.DRAFT,
            applicable_project_types=applicable_project_types,
            reference_rules=reference_rules,
            gates=gates,
        )

    def edit_draft(
        self,
        *,
        expected_version: int,
        title: str | None = None,
        applicable_project_types: tuple[ProjectType, ...] | None = None,
        reference_rules: tuple[TemplateReferenceRule, ...] | None = None,
        gates: tuple[GateDefinition, ...] | None = None,
    ) -> ProjectTemplateVersion:
        if self.publication_state is TemplatePublicationState.PUBLISHED:
            raise PublishedTemplateImmutable()
        updated_version = next_version(self.version, expected_version)
        return replace(
            self,
            version=updated_version,
            title=self.title if title is None else title,
            applicable_project_types=(
                self.applicable_project_types
                if applicable_project_types is None
                else applicable_project_types
            ),
            reference_rules=(
                self.reference_rules if reference_rules is None else reference_rules
            ),
            gates=self.gates if gates is None else gates,
        )

    def publish(self, *, expected_version: int) -> ProjectTemplateVersion:
        if self.publication_state is TemplatePublicationState.PUBLISHED:
            raise PublishedTemplateImmutable()
        self._validate_publishable()
        return replace(
            self,
            version=next_version(self.version, expected_version),
            publication_state=TemplatePublicationState.PUBLISHED,
        )

    def next_draft(self) -> ProjectTemplateVersion:
        if self.publication_state is not TemplatePublicationState.PUBLISHED:
            raise _validation(
                "templateVersion",
                _("Publish the current template version before creating a revision."),
            )
        return ProjectTemplateVersion.create_draft(
            template_global_id=self.template_global_id,
            template_code=self.template_code,
            template_version=self.template_version + 1,
            title=self.title,
            applicable_project_types=self.applicable_project_types,
            reference_rules=self.reference_rules,
            gates=self.gates,
        )

    def snapshot(self) -> TemplateSnapshot:
        if self.publication_state is not TemplatePublicationState.PUBLISHED:
            raise TemplateNotPublished()
        self._validate_publishable()
        return TemplateSnapshot(
            template_global_id=self.template_global_id,
            template_code=self.template_code,
            template_version=self.template_version,
            snapshot_hash=self.snapshot_hash,
            applicable_project_types=self.applicable_project_types,
            reference_rules=self.reference_rules,
            gates=self.gates,
        )

    @property
    def snapshot_hash(self) -> str:
        payload = {
            "templateGlobalId": str(self.template_global_id),
            "templateCode": self.template_code,
            "templateVersion": self.template_version,
            "applicableProjectTypes": [
                item.value for item in self.applicable_project_types
            ],
            "referenceRules": [
                {
                    "type": rule.reference_type.value,
                    "required": rule.required,
                    "allowMultiple": rule.allow_multiple,
                }
                for rule in self.reference_rules
            ],
            "gates": [gate.canonical_dict() for gate in self.gates],
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()

    def _validate_publishable(self) -> None:
        if not self.gates:
            raise _validation(
                "gates",
                _("Add at least one gate before publishing."),
            )


@dataclass(frozen=True, slots=True)
class CreateProjectCommand:
    idempotency_key: str
    tenant_id: str
    business_code: str
    title: str
    project_type: ProjectType
    owner_user_id: str
    target_sop: date
    template_global_id: UUID
    template_version: int
    expected_version: int
    references: tuple[TypedReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "idempotency_key",
            _require_text(
                self.idempotency_key,
                "idempotencyKey",
                maximum_length=128,
                pattern=_IDENTIFIER_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "tenant_id",
            _require_text(
                self.tenant_id,
                "tenantId",
                maximum_length=128,
                pattern=_IDENTIFIER_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "business_code",
            _require_text(
                self.business_code,
                "businessCode",
                maximum_length=64,
                pattern=_CODE_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum_length=140),
        )
        _require_enum(self.project_type, ProjectType, "projectType")
        object.__setattr__(
            self,
            "owner_user_id",
            _require_text(
                self.owner_user_id,
                "ownerUserId",
                maximum_length=254,
                pattern=_EMAIL_PATTERN,
            ),
        )
        if type(self.target_sop) is not date:
            raise _validation("targetSop", _("Enter a valid target SOP date."))
        if not isinstance(self.template_global_id, UUID):
            raise _validation("templateGlobalId", _("Enter a valid global ID."))
        if type(self.template_version) is not int or self.template_version < 1:
            raise _validation(
                "templateVersion",
                _("Enter a positive template version."),
            )
        if type(self.expected_version) is not int or self.expected_version < 1:
            raise _validation(
                "expectedVersion",
                _("Enter a positive expected version."),
            )
        references = tuple(self.references)
        if any(not isinstance(item, TypedReference) for item in references):
            raise _validation("references", _("Enter valid project references."))
        references = tuple(
            sorted(
                references,
                key=lambda item: (
                    item.reference_type.value,
                    item.source_system.value,
                    item.source_object_id,
                    str(item.global_id or ""),
                ),
            )
        )
        object.__setattr__(self, "references", references)

    @property
    def payload_hash(self) -> str:
        payload = {
            "tenantId": self.tenant_id,
            "businessCode": self.business_code,
            "title": self.title,
            "projectType": self.project_type.value,
            "ownerUserId": self.owner_user_id.casefold(),
            "targetSop": self.target_sop.isoformat(),
            "templateGlobalId": str(self.template_global_id),
            "templateVersion": self.template_version,
            "expectedVersion": self.expected_version,
            "references": [item.canonical_dict() for item in self.references],
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EngineeringProject:
    global_id: UUID
    tenant_id: str
    business_code: str
    title: str
    project_type: ProjectType
    owner_user_id: str
    target_sop: date
    state: ProjectLifecycleState
    version: int
    source_system: ProjectSourceSystem
    template_snapshot: TemplateSnapshot
    references: tuple[TypedReference, ...]
    creation_payload_hash: str


@dataclass(frozen=True, slots=True)
class GateShell:
    global_id: UUID
    project_global_id: UUID
    key: str
    title: str
    sequence: int
    state: GateShellState
    version: int
    template_global_id: UUID
    template_version: int
    template_snapshot_hash: str
    gate_template_global_id: UUID | None = None
    gate_template_version: int | None = None
    gate_template_snapshot_hash: str | None = None

    def __post_init__(self) -> None:
        # Gate shells freeze the exact Project Template gate definition used at
        # project creation. Reusing GateDefinition keeps the optional
        # Gate-Template reference complete-or-empty and hash validation rules
        # identical at both boundaries.
        self.template_gate_definition

    @property
    def template_gate_definition(self) -> GateDefinition:
        return GateDefinition(
            key=self.key,
            title=self.title,
            sequence=self.sequence,
            gate_template_global_id=self.gate_template_global_id,
            gate_template_version=self.gate_template_version,
            gate_template_snapshot_hash=self.gate_template_snapshot_hash,
        )


@dataclass(frozen=True, slots=True)
class ProjectInstantiation:
    project: EngineeringProject
    gates: tuple[GateShell, ...]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    key: str
    payload_hash: str
    result: ProjectInstantiation


class ProjectInstantiationStore(Protocol):
    def get_template_version(
        self, template_global_id: UUID, template_version: int
    ) -> ProjectTemplateVersion | None: ...

    def get_idempotency_record(self, key: str) -> IdempotencyRecord | None: ...

    def business_code_exists(self, tenant_id: str, business_code: str) -> bool: ...

    def save_atomic(
        self,
        result: ProjectInstantiation,
        idempotency_record: IdempotencyRecord,
    ) -> ProjectInstantiation: ...


class ProjectInstantiationService:
    def __init__(self, store: ProjectInstantiationStore) -> None:
        self._store = store

    def instantiate(self, command: CreateProjectCommand) -> ProjectInstantiation:
        payload_hash = command.payload_hash
        existing_record = self._store.get_idempotency_record(command.idempotency_key)
        if existing_record is not None:
            if existing_record.payload_hash != payload_hash:
                raise IdempotencyConflict()
            return replace(existing_record.result, replayed=True)

        template = self._store.get_template_version(
            command.template_global_id,
            command.template_version,
        )
        if template is None:
            raise TemplateUnavailable()
        if template.publication_state is not TemplatePublicationState.PUBLISHED:
            raise TemplateNotPublished()
        next_version(template.version, command.expected_version)
        if command.project_type not in template.applicable_project_types:
            raise _validation(
                "projectType",
                _("Select a project type supported by the template."),
            )
        _validate_references(command.references, template.reference_rules)
        if self._store.business_code_exists(command.tenant_id, command.business_code):
            raise BusinessCodeConflict()

        snapshot = template.snapshot()
        project_global_id = uuid5(
            _PROJECT_ID_NAMESPACE,
            f"{command.idempotency_key}:{payload_hash}",
        )
        project = EngineeringProject(
            global_id=project_global_id,
            tenant_id=command.tenant_id,
            business_code=command.business_code,
            title=command.title,
            project_type=command.project_type,
            owner_user_id=command.owner_user_id,
            target_sop=command.target_sop,
            state=ProjectLifecycleState.DRAFT,
            version=1,
            source_system=ProjectSourceSystem.NPI_ONE,
            template_snapshot=snapshot,
            references=command.references,
            creation_payload_hash=payload_hash,
        )
        gates = tuple(
            GateShell(
                global_id=uuid5(
                    project_global_id,
                    f"gate-shell:{gate.sequence}:{gate.key}",
                ),
                project_global_id=project_global_id,
                key=gate.key,
                title=gate.title,
                sequence=gate.sequence,
                state=GateShellState.NOT_STARTED,
                version=1,
                template_global_id=snapshot.template_global_id,
                template_version=snapshot.template_version,
                template_snapshot_hash=snapshot.snapshot_hash,
                gate_template_global_id=gate.gate_template_global_id,
                gate_template_version=gate.gate_template_version,
                gate_template_snapshot_hash=gate.gate_template_snapshot_hash,
            )
            for gate in snapshot.gates
        )
        result = ProjectInstantiation(project=project, gates=gates)
        record = IdempotencyRecord(
            key=command.idempotency_key,
            payload_hash=payload_hash,
            result=result,
        )
        return self._store.save_atomic(result, record)


FailureHook = Callable[[str], None]


class InMemoryProjectStore:
    """Transactional reference store used to prove domain atomicity and retry rules."""

    def __init__(self, *, failure_hook: FailureHook | None = None) -> None:
        self._template_versions: dict[tuple[UUID, int], ProjectTemplateVersion] = {}
        self._template_codes: dict[str, UUID] = {}
        self._projects: dict[UUID, EngineeringProject] = {}
        self._gates: dict[UUID, GateShell] = {}
        self._idempotency: dict[str, IdempotencyRecord] = {}
        self._business_codes: dict[tuple[str, str], UUID] = {}
        self._failure_hook = failure_hook

    def add_template_version(self, template: ProjectTemplateVersion) -> None:
        key = (template.template_global_id, template.template_version)
        existing = self._template_versions.get(key)
        if existing is not None:
            if existing == template:
                return
            if existing.publication_state is TemplatePublicationState.PUBLISHED:
                raise PublishedTemplateImmutable()
            if existing.global_id != template.global_id:
                raise _validation(
                    "templateGlobalId",
                    _("Template version identity cannot be changed."),
                )
        normalized_code = template.template_code.casefold()
        code_owner = self._template_codes.get(normalized_code)
        if code_owner is not None and code_owner != template.template_global_id:
            raise _validation("templateCode", _("Template codes must be unique."))
        self._template_codes[normalized_code] = template.template_global_id
        self._template_versions[key] = template

    def get_template_version(
        self, template_global_id: UUID, template_version: int
    ) -> ProjectTemplateVersion | None:
        return self._template_versions.get((template_global_id, template_version))

    def get_idempotency_record(self, key: str) -> IdempotencyRecord | None:
        return self._idempotency.get(key)

    def business_code_exists(self, tenant_id: str, business_code: str) -> bool:
        return (tenant_id.casefold(), business_code.casefold()) in self._business_codes

    def save_atomic(
        self,
        result: ProjectInstantiation,
        idempotency_record: IdempotencyRecord,
    ) -> ProjectInstantiation:
        existing_record = self._idempotency.get(idempotency_record.key)
        if existing_record is not None:
            if existing_record.payload_hash != idempotency_record.payload_hash:
                raise IdempotencyConflict()
            return replace(existing_record.result, replayed=True)

        code_key = (
            result.project.tenant_id.casefold(),
            result.project.business_code.casefold(),
        )
        if code_key in self._business_codes:
            raise BusinessCodeConflict()

        staged_projects = self._projects.copy()
        staged_gates = self._gates.copy()
        staged_idempotency = self._idempotency.copy()
        staged_business_codes = self._business_codes.copy()

        if result.project.global_id in staged_projects:
            raise IdempotencyConflict()
        staged_projects[result.project.global_id] = result.project
        self._run_failure_hook("after_project")
        for gate in result.gates:
            if gate.global_id in staged_gates:
                raise IdempotencyConflict()
            staged_gates[gate.global_id] = gate
            self._run_failure_hook("after_gate")
        staged_idempotency[idempotency_record.key] = idempotency_record
        staged_business_codes[code_key] = result.project.global_id
        self._run_failure_hook("before_commit")

        self._projects = staged_projects
        self._gates = staged_gates
        self._idempotency = staged_idempotency
        self._business_codes = staged_business_codes
        return result

    @property
    def projects(self) -> tuple[EngineeringProject, ...]:
        return tuple(self._projects.values())

    @property
    def gates(self) -> tuple[GateShell, ...]:
        return tuple(sorted(self._gates.values(), key=lambda gate: gate.sequence))

    @property
    def idempotency_records(self) -> tuple[IdempotencyRecord, ...]:
        return tuple(self._idempotency.values())

    def _run_failure_hook(self, point: str) -> None:
        if self._failure_hook is not None:
            self._failure_hook(point)


def _validate_references(
    references: tuple[TypedReference, ...],
    rules: tuple[TemplateReferenceRule, ...],
) -> None:
    rule_by_type = {rule.reference_type: rule for rule in rules}
    counts: dict[ProjectReferenceType, int] = {}
    identities: set[tuple[ProjectReferenceType, ReferenceSourceSystem, str]] = set()
    for reference in references:
        if reference.reference_type not in rule_by_type:
            raise _validation(
                "references",
                _("Remove reference types that are not allowed by the template."),
            )
        identity = (
            reference.reference_type,
            reference.source_system,
            reference.source_object_id.casefold(),
        )
        if identity in identities:
            raise _validation("references", _("Project references must be unique."))
        identities.add(identity)
        counts[reference.reference_type] = counts.get(reference.reference_type, 0) + 1

    for rule in rules:
        count = counts.get(rule.reference_type, 0)
        if rule.required and count == 0:
            raise _validation(
                "references",
                _("Add every reference required by the project template."),
            )
        if not rule.allow_multiple and count > 1:
            raise _validation(
                "references",
                _("Only one reference of this type is allowed by the template."),
            )


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def actor_idempotency_key_hash(actor: str, idempotency_key: str) -> str:
    """Hash the security principal and raw retry key without persisting the key."""
    normalized_actor = _require_text(
        actor,
        "actor",
        maximum_length=254,
        pattern=_ACTOR_PATTERN,
    ).casefold()
    normalized_key = _require_text(
        idempotency_key,
        "idempotencyKey",
        maximum_length=255,
        pattern=_IDEMPOTENCY_HEADER_PATTERN,
    )
    return hashlib.sha256(
        f"{normalized_actor}\x1f{normalized_key}".encode("utf-8")
    ).hexdigest()


def business_code_reservation_hash(tenant_id: str, business_code: str) -> str:
    """Build the deterministic tenant-scoped, case-insensitive uniqueness key."""
    normalized_tenant = _require_text(
        tenant_id,
        "tenantId",
        maximum_length=128,
        pattern=_IDENTIFIER_PATTERN,
    ).casefold()
    normalized_code = _require_text(
        business_code,
        "businessCode",
        maximum_length=64,
        pattern=_CODE_PATTERN,
    ).casefold()
    return hashlib.sha256(
        f"{normalized_tenant}\x1f{normalized_code}".encode("utf-8")
    ).hexdigest()
