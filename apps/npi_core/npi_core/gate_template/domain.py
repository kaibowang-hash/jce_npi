from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import Enum
from uuid import UUID, uuid5

from npi_core.foundation.concurrency import next_version
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.project.domain import ProjectType

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_GATE_REQUIREMENTS = 500


class GateTemplatePublicationState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class GateRequirementClassification(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class GateRequirementPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class EvidenceKind(str, Enum):
    WBS_ITEM = "wbs_item"
    FILE_REVISION = "file_revision"
    DOCUMENT_REVISION = "document_revision"
    TRIAL_ROUND = "trial_round"
    QUALITY_INSPECTION = "quality_inspection"
    CUSTOMER_APPROVAL = "customer_approval"
    EXTERNAL_LINK = "external_link"


PUBLISHABLE_EVIDENCE_KINDS = frozenset(
    {
        EvidenceKind.WBS_ITEM,
        EvidenceKind.FILE_REVISION,
    }
)


class PublishedGateTemplateImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PUBLISHED_GATE_TEMPLATE_IMMUTABLE",
            _("A published Gate Template version cannot be changed."),
        )


def _validation(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


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


def _require_enum(value: object, enum_type: type[Enum], path: str) -> None:
    if not isinstance(value, enum_type):
        raise _validation(path, _("Select a supported value."))


def validate_gate_template_code(value: object) -> str:
    return _require_text(
        value,
        "gateTemplateCode",
        maximum_length=64,
        pattern=_CODE_PATTERN,
    )


@dataclass(frozen=True, slots=True)
class GateRequirementDefinition:
    key: str
    title: str
    classification: GateRequirementClassification
    priority: GateRequirementPriority
    allowed_evidence_kinds: tuple[EvidenceKind, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "key",
            _require_text(
                self.key,
                "requirements.key",
                maximum_length=64,
                pattern=_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(
                self.title,
                "requirements.title",
                maximum_length=140,
            ),
        )
        _require_enum(
            self.classification,
            GateRequirementClassification,
            "requirements.classification",
        )
        _require_enum(
            self.priority,
            GateRequirementPriority,
            "requirements.priority",
        )
        evidence_kinds = tuple(self.allowed_evidence_kinds)
        if not evidence_kinds or any(
            not isinstance(value, EvidenceKind) for value in evidence_kinds
        ):
            raise _validation(
                "requirements.allowedEvidenceKinds",
                _("Select at least one supported evidence kind."),
            )
        evidence_kinds = tuple(sorted(evidence_kinds, key=lambda value: value.value))
        if len(set(evidence_kinds)) != len(evidence_kinds):
            raise _validation(
                "requirements.allowedEvidenceKinds",
                _("Evidence kinds must be unique."),
            )
        object.__setattr__(self, "allowed_evidence_kinds", evidence_kinds)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "classification": self.classification.value,
            "priority": self.priority.value,
            "allowedEvidenceKinds": [
                value.value for value in self.allowed_evidence_kinds
            ],
        }


@dataclass(frozen=True, slots=True)
class GateTemplateSnapshot:
    gate_template_global_id: UUID
    gate_template_code: str
    gate_template_version: int
    title: str
    applicable_project_types: tuple[ProjectType, ...]
    requirements: tuple[GateRequirementDefinition, ...]
    snapshot_hash: str

    def canonical_dict(self) -> dict[str, object]:
        return _snapshot_payload(
            gate_template_global_id=self.gate_template_global_id,
            gate_template_code=self.gate_template_code,
            gate_template_version=self.gate_template_version,
            title=self.title,
            applicable_project_types=self.applicable_project_types,
            requirements=self.requirements,
        )


@dataclass(frozen=True, slots=True)
class GateTemplateVersion:
    global_id: UUID
    gate_template_global_id: UUID
    gate_template_code: str
    gate_template_version: int
    version: int
    title: str
    publication_state: GateTemplatePublicationState
    applicable_project_types: tuple[ProjectType, ...]
    requirements: tuple[GateRequirementDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.global_id, UUID) or not isinstance(
            self.gate_template_global_id,
            UUID,
        ):
            raise _validation("gateTemplateGlobalId", _("Enter a valid global ID."))
        object.__setattr__(
            self,
            "gate_template_code",
            validate_gate_template_code(self.gate_template_code),
        )
        if (
            type(self.gate_template_version) is not int
            or self.gate_template_version < 1
        ):
            raise _validation(
                "gateTemplateVersion",
                _("Enter a positive Gate Template version."),
            )
        if type(self.version) is not int or self.version < 1:
            raise _validation(
                "expectedVersion",
                _("Enter a positive expected version."),
            )
        object.__setattr__(
            self,
            "title",
            _require_text(
                self.title,
                "gateTemplateTitle",
                maximum_length=140,
            ),
        )
        _require_enum(
            self.publication_state,
            GateTemplatePublicationState,
            "publicationState",
        )

        project_types = tuple(self.applicable_project_types)
        if not project_types or any(
            not isinstance(value, ProjectType) for value in project_types
        ):
            raise _validation(
                "applicableProjectTypes",
                _("Select at least one project type."),
            )
        project_types = tuple(sorted(project_types, key=lambda value: value.value))
        if len(set(project_types)) != len(project_types):
            raise _validation(
                "applicableProjectTypes",
                _("Project types must be unique."),
            )
        object.__setattr__(self, "applicable_project_types", project_types)

        requirements = tuple(self.requirements)
        if any(
            not isinstance(value, GateRequirementDefinition) for value in requirements
        ):
            raise _validation(
                "requirements",
                _("Enter valid Gate requirement definitions."),
            )
        if len(requirements) > MAX_GATE_REQUIREMENTS:
            raise _validation(
                "requirements",
                _("Add no more than 500 Gate requirements."),
            )
        if len({value.key.casefold() for value in requirements}) != len(requirements):
            raise _validation(
                "requirements",
                _("Gate requirement keys must be unique."),
            )
        object.__setattr__(self, "requirements", requirements)
        if self.publication_state is GateTemplatePublicationState.PUBLISHED:
            self._validate_publishable()

    @classmethod
    def create_draft(
        cls,
        *,
        gate_template_global_id: UUID,
        gate_template_code: str,
        gate_template_version: int,
        title: str,
        applicable_project_types: tuple[ProjectType, ...],
        requirements: tuple[GateRequirementDefinition, ...] = (),
    ) -> GateTemplateVersion:
        return cls(
            global_id=uuid5(
                gate_template_global_id,
                f"gate-template-version:{gate_template_version}",
            ),
            gate_template_global_id=gate_template_global_id,
            gate_template_code=gate_template_code,
            gate_template_version=gate_template_version,
            version=1,
            title=title,
            publication_state=GateTemplatePublicationState.DRAFT,
            applicable_project_types=applicable_project_types,
            requirements=requirements,
        )

    def edit_draft(
        self,
        *,
        expected_version: int,
        title: str | None = None,
        applicable_project_types: tuple[ProjectType, ...] | None = None,
        requirements: tuple[GateRequirementDefinition, ...] | None = None,
    ) -> GateTemplateVersion:
        if self.publication_state is GateTemplatePublicationState.PUBLISHED:
            raise PublishedGateTemplateImmutable()
        return replace(
            self,
            version=next_version(self.version, expected_version),
            title=self.title if title is None else title,
            applicable_project_types=(
                self.applicable_project_types
                if applicable_project_types is None
                else applicable_project_types
            ),
            requirements=self.requirements if requirements is None else requirements,
        )

    def publish(self, *, expected_version: int) -> GateTemplateVersion:
        if self.publication_state is GateTemplatePublicationState.PUBLISHED:
            raise PublishedGateTemplateImmutable()
        self._validate_publishable()
        return replace(
            self,
            version=next_version(self.version, expected_version),
            publication_state=GateTemplatePublicationState.PUBLISHED,
        )

    def next_draft(self) -> GateTemplateVersion:
        if self.publication_state is not GateTemplatePublicationState.PUBLISHED:
            raise _validation(
                "gateTemplateVersion",
                _(
                    "Publish the current Gate Template version before creating a revision."
                ),
            )
        return GateTemplateVersion.create_draft(
            gate_template_global_id=self.gate_template_global_id,
            gate_template_code=self.gate_template_code,
            gate_template_version=self.gate_template_version + 1,
            title=self.title,
            applicable_project_types=self.applicable_project_types,
            requirements=self.requirements,
        )

    def snapshot(self) -> GateTemplateSnapshot:
        if self.publication_state is not GateTemplatePublicationState.PUBLISHED:
            raise _validation(
                "gateTemplateVersion",
                _("Select a published Gate Template version."),
            )
        self._validate_publishable()
        return GateTemplateSnapshot(
            gate_template_global_id=self.gate_template_global_id,
            gate_template_code=self.gate_template_code,
            gate_template_version=self.gate_template_version,
            title=self.title,
            applicable_project_types=self.applicable_project_types,
            requirements=self.requirements,
            snapshot_hash=self.snapshot_hash,
        )

    @property
    def snapshot_hash(self) -> str:
        return hashlib.sha256(
            _canonical_json(
                _snapshot_payload(
                    gate_template_global_id=self.gate_template_global_id,
                    gate_template_code=self.gate_template_code,
                    gate_template_version=self.gate_template_version,
                    title=self.title,
                    applicable_project_types=self.applicable_project_types,
                    requirements=self.requirements,
                )
            ).encode("utf-8")
        ).hexdigest()

    def _validate_publishable(self) -> None:
        if not self.requirements:
            raise _validation(
                "requirements",
                _("Add at least one Gate requirement before publishing."),
            )
        if any(
            evidence_kind not in PUBLISHABLE_EVIDENCE_KINDS
            for requirement in self.requirements
            for evidence_kind in requirement.allowed_evidence_kinds
        ):
            raise _validation(
                "requirements.allowedEvidenceKinds",
                _("Select only evidence kinds supported by Gate requirement freezing."),
            )


def _snapshot_payload(
    *,
    gate_template_global_id: UUID,
    gate_template_code: str,
    gate_template_version: int,
    title: str,
    applicable_project_types: tuple[ProjectType, ...],
    requirements: tuple[GateRequirementDefinition, ...],
) -> dict[str, object]:
    return {
        "gateTemplateGlobalId": str(gate_template_global_id),
        "gateTemplateCode": gate_template_code,
        "gateTemplateVersion": gate_template_version,
        "title": title,
        "applicableProjectTypes": [value.value for value in applicable_project_types],
        "requirements": [value.canonical_dict() for value in requirements],
    }


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
