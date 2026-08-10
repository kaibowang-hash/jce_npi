from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Sequence
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.trial.domain import TRIAL_SCHEMA_VERSION, sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


class TrialLockedReferenceKind(StrEnum):
    DESIGN_BASELINE = "design_baseline"
    PART_REVISION = "part_revision"
    TOOLING_REVISION = "tooling_revision"
    TOOLING_SET = "tooling_set"
    TOOLING_SET_BINDING = "tooling_set_binding"
    CAVITY = "cavity"
    PROCESS_CHAIN = "process_chain"
    INSPECTION_DOCUMENT = "inspection_document"


class TrialParameterValueKind(StrEnum):
    DECIMAL = "decimal"
    INTEGER = "integer"
    TEXT = "text"
    BOOLEAN = "boolean"


class TrialMeasurementState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"


class TrialAcquisitionMode(StrEnum):
    MANUAL = "manual"


class TrialActualResourceKind(StrEnum):
    MACHINE = "machine"
    AUXILIARY_EQUIPMENT = "auxiliary_equipment"


class TrialEvidenceRole(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    PARAMETER_CURVE = "parameter_curve"
    MEASUREMENT_REPORT = "measurement_report"
    CUSTOMER_FEEDBACK = "customer_feedback"


class TrialExecutionUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TRIAL_EXECUTION_UNAVAILABLE",
            _("The Trial execution object is unavailable."),
        )


class TrialExecutionReferenceUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TRIAL_EXECUTION_REFERENCE_UNAVAILABLE",
            _("The related Trial execution reference is unavailable."),
        )


class TrialExecutionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TRIAL_EXECUTION_CONFLICT",
            _("The Trial execution record was changed by another user."),
        )


class TrialExecutionRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "TRIAL_EXECUTION_ROUTES_DISABLED",
            _("The Trial execution workspace is temporarily unavailable."),
            _("The execution routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


_REQUIRED_LOCK_KINDS = frozenset(
    {
        TrialLockedReferenceKind.DESIGN_BASELINE,
        TrialLockedReferenceKind.PART_REVISION,
        TrialLockedReferenceKind.TOOLING_REVISION,
        TrialLockedReferenceKind.TOOLING_SET,
        TrialLockedReferenceKind.TOOLING_SET_BINDING,
        TrialLockedReferenceKind.CAVITY,
        TrialLockedReferenceKind.PROCESS_CHAIN,
        TrialLockedReferenceKind.INSPECTION_DOCUMENT,
    }
)


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _problem(path, _("Enter a valid global ID."))
    return value


def _uuid_text(value: object, path: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _problem(path, _("Enter a valid global ID.")) from error


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _optional_uuid_text(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid_text(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum:
        raise _problem(path, _("Enter a shorter value."))
    return normalized


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    normalized = _text(value, path, 128)
    if not normalized[0].isalnum() or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
        for character in normalized
    ):
        raise _problem(path, _("Enter a valid value."))
    return normalized


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _aware(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _problem(path, _("Enter a valid date and time."))
    return value.astimezone(UTC)


def _datetime_text(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid date and time."))
    try:
        return _aware(datetime.fromisoformat(value.replace("Z", "+00:00")), path)
    except ValueError as error:
        raise _problem(path, _("Enter a valid date and time.")) from error


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _hash(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _enum(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    if not isinstance(value, enum_type):
        raise _problem(path, _("Select a supported value."))
    return value


def _enum_text(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error


def _decimal(value: object, path: str) -> str:
    normalized = _text(value, path, 64)
    try:
        parsed = Decimal(normalized)
    except InvalidOperation as error:
        raise _problem(path, _("Enter a valid numeric value.")) from error
    if not parsed.is_finite():
        raise _problem(path, _("Enter a valid numeric value."))
    return format(parsed.normalize(), "f")


def _record(value: object, path: str, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise _problem(path, _("Enter a valid closed object."))
    return value


def _sequence(value: object, path: str, maximum: int) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise _problem(path, _("Enter a valid list."))
    return value


def _schema_version(value: object) -> None:
    if value != TRIAL_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported schema version."))


def _set_snapshot_hash(instance: object, supplied: str, payload: object, label: str) -> None:
    expected = sha256_json(payload)
    if supplied and _hash(supplied, "snapshotHash") != expected:
        raise _problem("snapshotHash", label)
    object.__setattr__(instance, "snapshot_hash", expected)


@dataclass(frozen=True, slots=True)
class TrialLockedReference:
    global_id: UUID
    kind: TrialLockedReferenceKind
    optimistic_version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "references.globalId"))
        _enum(self.kind, TrialLockedReferenceKind, "references.kind")
        object.__setattr__(
            self,
            "optimistic_version",
            _positive(self.optimistic_version, "references.optimisticVersion"),
        )
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "references.snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "kind": self.kind.value,
            "optimisticVersion": self.optimistic_version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class TrialMaterialObservation:
    source_system: str
    source_object_id: str
    lot_batch_code: str
    label: str
    observed_at: datetime
    confirmed_by_user_id: str
    color: str | None = None
    additive: str | None = None

    def __post_init__(self) -> None:
        if self.source_system not in {"NPI_ONE", "ERPNEXT"}:
            raise _problem("material.sourceSystem", _("Select a supported value."))
        object.__setattr__(
            self,
            "source_object_id",
            _key(self.source_object_id, "material.sourceObjectId"),
        )
        object.__setattr__(
            self,
            "lot_batch_code",
            _key(self.lot_batch_code, "material.lotBatchCode"),
        )
        object.__setattr__(self, "label", _text(self.label, "material.label", 140))
        object.__setattr__(self, "color", _optional_text(self.color, "material.color", 80))
        object.__setattr__(
            self,
            "additive",
            _optional_text(self.additive, "material.additive", 140),
        )
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "material.observedAt"))
        object.__setattr__(
            self,
            "confirmed_by_user_id",
            _text(self.confirmed_by_user_id, "material.confirmedByUserId", 254).casefold(),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sourceSystem": self.source_system,
            "sourceObjectId": self.source_object_id,
            "lotBatchCode": self.lot_batch_code,
            "label": self.label,
            "color": self.color,
            "additive": self.additive,
            "observedAt": _utc_text(self.observed_at),
            "confirmedByUserId": self.confirmed_by_user_id,
            "erpVerification": "unavailable",
        }


@dataclass(frozen=True, slots=True)
class TrialParameterDefinition:
    key: str
    category: str
    value_kind: TrialParameterValueKind
    required: bool
    unit: str | None = None
    target_value: str | None = None
    lower_limit: str | None = None
    upper_limit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "parameters.key"))
        object.__setattr__(self, "category", _text(self.category, "parameters.category", 80))
        _enum(self.value_kind, TrialParameterValueKind, "parameters.valueKind")
        if type(self.required) is not bool:
            raise _problem("parameters.required", _("Select a valid true or false value."))
        numeric = self.value_kind in {
            TrialParameterValueKind.DECIMAL,
            TrialParameterValueKind.INTEGER,
        }
        if numeric:
            object.__setattr__(self, "unit", _text(self.unit, "parameters.unit", 32))
            for fieldname in ("target_value", "lower_limit", "upper_limit"):
                value = getattr(self, fieldname)
                if value is not None:
                    normalized = _decimal(value, f"parameters.{fieldname}")
                    if self.value_kind is TrialParameterValueKind.INTEGER and Decimal(normalized) % 1:
                        raise _problem(f"parameters.{fieldname}", _("Enter a whole number."))
                    object.__setattr__(self, fieldname, normalized)
            if (self.lower_limit is None) != (self.upper_limit is None):
                raise _problem(
                    "parameters.lowerLimit",
                    _("Enter both parameter limits, or leave both empty."),
                )
            if self.lower_limit is not None:
                lower = Decimal(self.lower_limit)
                upper = Decimal(self.upper_limit or "0")
                if lower > upper:
                    raise _problem(
                        "parameters.upperLimit",
                        _("The upper limit must not be below the lower limit."),
                    )
        else:
            if any(
                value is not None
                for value in (self.unit, self.lower_limit, self.upper_limit)
            ):
                raise _problem(
                    "parameters.unit",
                    _("Only numeric parameters can use a unit or limits."),
                )
            if self.target_value is not None:
                object.__setattr__(
                    self,
                    "target_value",
                    _text(self.target_value, "parameters.targetValue", 280),
                )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "category": self.category,
            "valueKind": self.value_kind.value,
            "required": self.required,
            "unit": self.unit,
            "targetValue": self.target_value,
            "lowerLimit": self.lower_limit,
            "upperLimit": self.upper_limit,
        }


@dataclass(frozen=True, slots=True)
class TrialRoundInputLockRevision:
    global_id: UUID
    input_lock_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    trial_plan_revision_global_id: UUID
    trial_plan_revision_snapshot_hash: str
    lock_version: int
    references: tuple[TrialLockedReference, ...]
    material: TrialMaterialObservation
    parameter_definitions: tuple[TrialParameterDefinition, ...]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    predecessor_global_id: UUID | None = None
    predecessor_snapshot_hash: str | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "input_lock_global_id",
            "project_global_id",
            "trial_round_global_id",
            "trial_plan_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), fieldname))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_plan_revision_snapshot_hash",
            _hash(
                self.trial_plan_revision_snapshot_hash,
                "trialPlanRevisionSnapshotHash",
            ),
        )
        object.__setattr__(self, "lock_version", _positive(self.lock_version, "lockVersion"))
        references = tuple(self.references)
        if not references or len(references) > 100 or any(
            not isinstance(value, TrialLockedReference) for value in references
        ):
            raise _problem("references", _("Enter valid locked Trial references."))
        if {value.kind for value in references} != _REQUIRED_LOCK_KINDS:
            raise _problem(
                "references",
                _("Lock every required Trial input before preparation."),
            )
        if len({(value.kind, value.global_id) for value in references}) != len(references):
            raise _problem("references", _("Locked Trial references must be unique."))
        object.__setattr__(
            self,
            "references",
            tuple(sorted(references, key=lambda value: (value.kind.value, str(value.global_id)))),
        )
        if not isinstance(self.material, TrialMaterialObservation):
            raise _problem("material", _("Enter a valid material observation."))
        definitions = tuple(self.parameter_definitions)
        if not definitions or len(definitions) > 250 or any(
            not isinstance(value, TrialParameterDefinition) for value in definitions
        ):
            raise _problem("parameterDefinitions", _("Enter valid Trial parameter definitions."))
        if len({value.key for value in definitions}) != len(definitions):
            raise _problem("parameterDefinitions", _("Trial parameter keys must be unique."))
        object.__setattr__(
            self,
            "parameter_definitions",
            tuple(sorted(definitions, key=lambda value: value.key)),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(self.created_by_user_id, "createdByUserId", 254).casefold(),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        if self.predecessor_snapshot_hash is not None:
            object.__setattr__(
                self,
                "predecessor_snapshot_hash",
                _hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
            )
        if self.lock_version == 1:
            if self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None:
                raise _problem(
                    "predecessorGlobalId",
                    _("The first input lock revision cannot have a predecessor."),
                )
        elif self.predecessor_global_id is None or self.predecessor_snapshot_hash is None:
            raise _problem(
                "predecessorGlobalId",
                _("An input lock successor requires its exact predecessor."),
            )
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial input lock snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "inputLockGlobalId": str(self.input_lock_global_id),
                "lockVersion": self.lock_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "inputLockGlobalId": str(self.input_lock_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "trialPlanRevisionGlobalId": str(self.trial_plan_revision_global_id),
            "trialPlanRevisionSnapshotHash": self.trial_plan_revision_snapshot_hash,
            "lockVersion": self.lock_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "references": [value.snapshot_payload() for value in self.references],
            "material": self.material.snapshot_payload(),
            "parameterDefinitions": [
                value.snapshot_payload() for value in self.parameter_definitions
            ],
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_input_lock_successor(
    predecessor: TrialRoundInputLockRevision,
    successor: TrialRoundInputLockRevision,
) -> None:
    if (
        successor.input_lock_global_id != predecessor.input_lock_global_id
        or successor.tenant_id != predecessor.tenant_id
        or successor.project_global_id != predecessor.project_global_id
        or successor.trial_round_global_id != predecessor.trial_round_global_id
        or successor.trial_plan_revision_global_id
        != predecessor.trial_plan_revision_global_id
        or successor.trial_plan_revision_snapshot_hash
        != predecessor.trial_plan_revision_snapshot_hash
        or successor.lock_version != predecessor.lock_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial input lock revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialActualResourceObservation:
    kind: TrialActualResourceKind
    source_system: str
    source_object_id: str
    label: str

    def __post_init__(self) -> None:
        _enum(self.kind, TrialActualResourceKind, "resources.kind")
        if self.source_system not in {"NPI_ONE", "ERPNEXT"}:
            raise _problem("resources.sourceSystem", _("Select a supported value."))
        object.__setattr__(
            self,
            "source_object_id",
            _key(self.source_object_id, "resources.sourceObjectId"),
        )
        object.__setattr__(self, "label", _text(self.label, "resources.label", 140))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "sourceSystem": self.source_system,
            "sourceObjectId": self.source_object_id,
            "label": self.label,
            "erpVerification": "unavailable",
        }


@dataclass(frozen=True, slots=True)
class TrialEnvironmentObservation:
    key: str
    value: str
    observed_at: datetime
    unit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _key(self.key, "environment.key"))
        object.__setattr__(self, "value", _text(self.value, "environment.value", 140))
        object.__setattr__(self, "unit", _optional_text(self.unit, "environment.unit", 32))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "environment.observedAt"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "value": self.value,
            "unit": self.unit,
            "observedAt": _utc_text(self.observed_at),
        }


@dataclass(frozen=True, slots=True)
class TrialParameterObservation:
    definition_key: str
    state: TrialMeasurementState
    value: str | None = None
    unit: str | None = None
    source: TrialAcquisitionMode | None = None
    observed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition_key", _key(self.definition_key, "parameters.definitionKey"))
        _enum(self.state, TrialMeasurementState, "parameters.state")
        if self.state is TrialMeasurementState.NOT_MEASURED:
            if any(value is not None for value in (self.value, self.unit, self.source, self.observed_at)):
                raise _problem(
                    "parameters.state",
                    _("A not-measured parameter cannot contain a measured value."),
                )
            return
        object.__setattr__(self, "value", _text(self.value, "parameters.value", 280))
        object.__setattr__(self, "unit", _optional_text(self.unit, "parameters.unit", 32))
        if self.source is not TrialAcquisitionMode.MANUAL:
            raise _problem(
                "parameters.source",
                _("Only manual Trial acquisition is available."),
            )
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "parameters.observedAt"))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "definitionKey": self.definition_key,
            "state": self.state.value,
            "value": self.value,
            "unit": self.unit,
            "source": self.source.value if self.source else None,
            "observedAt": _utc_text(self.observed_at) if self.observed_at else None,
        }


@dataclass(frozen=True, slots=True)
class TrialRoundActualRevision:
    global_id: UUID
    actual_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    input_lock_revision_global_id: UUID
    input_lock_revision_snapshot_hash: str
    actual_version: int
    acquisition_mode: TrialAcquisitionMode
    resources: tuple[TrialActualResourceObservation, ...]
    material: TrialMaterialObservation
    environment: tuple[TrialEnvironmentObservation, ...]
    parameters: tuple[TrialParameterObservation, ...]
    operator_user_id: str
    confirmed_by_user_id: str
    execution_started_at: datetime
    reason: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    predecessor_global_id: UUID | None = None
    predecessor_snapshot_hash: str | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "actual_global_id",
            "project_global_id",
            "trial_round_global_id",
            "input_lock_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), fieldname))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "input_lock_revision_snapshot_hash",
            _hash(self.input_lock_revision_snapshot_hash, "inputLockRevisionSnapshotHash"),
        )
        object.__setattr__(self, "actual_version", _positive(self.actual_version, "actualVersion"))
        if self.acquisition_mode is not TrialAcquisitionMode.MANUAL:
            raise _problem("acquisitionMode", _("Only manual Trial acquisition is available."))
        resources = tuple(self.resources)
        if not resources or len(resources) > 25 or any(
            not isinstance(value, TrialActualResourceObservation) for value in resources
        ):
            raise _problem("resources", _("Enter valid actual Trial resources."))
        if sum(value.kind is TrialActualResourceKind.MACHINE for value in resources) != 1:
            raise _problem("resources", _("Select exactly one actual Trial machine."))
        if len({(value.kind, value.source_system, value.source_object_id) for value in resources}) != len(resources):
            raise _problem("resources", _("Actual Trial resources must be unique."))
        object.__setattr__(
            self,
            "resources",
            tuple(sorted(resources, key=lambda value: (value.kind.value, value.source_object_id))),
        )
        if not isinstance(self.material, TrialMaterialObservation):
            raise _problem("material", _("Enter a valid material observation."))
        environment = tuple(self.environment)
        if len(environment) > 50 or any(
            not isinstance(value, TrialEnvironmentObservation) for value in environment
        ):
            raise _problem("environment", _("Enter valid Trial environment observations."))
        if len({value.key for value in environment}) != len(environment):
            raise _problem("environment", _("Trial environment keys must be unique."))
        object.__setattr__(self, "environment", tuple(sorted(environment, key=lambda value: value.key)))
        parameters = tuple(self.parameters)
        if not parameters or len(parameters) > 250 or any(
            not isinstance(value, TrialParameterObservation) for value in parameters
        ):
            raise _problem("parameters", _("Enter valid Trial parameter observations."))
        if len({value.definition_key for value in parameters}) != len(parameters):
            raise _problem("parameters", _("Trial parameter observations must be unique."))
        object.__setattr__(self, "parameters", tuple(sorted(parameters, key=lambda value: value.definition_key)))
        for fieldname in ("operator_user_id", "confirmed_by_user_id"):
            object.__setattr__(
                self,
                fieldname,
                _text(getattr(self, fieldname), fieldname, 254).casefold(),
            )
        object.__setattr__(
            self,
            "execution_started_at",
            _aware(self.execution_started_at, "executionStartedAt"),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        if self.predecessor_snapshot_hash is not None:
            object.__setattr__(
                self,
                "predecessor_snapshot_hash",
                _hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
            )
        if self.actual_version == 1:
            if self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None:
                raise _problem(
                    "predecessorGlobalId",
                    _("The first Trial Actual revision cannot have a predecessor."),
                )
        elif self.predecessor_global_id is None or self.predecessor_snapshot_hash is None:
            raise _problem(
                "predecessorGlobalId",
                _("A Trial Actual successor requires its exact predecessor."),
            )
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial Actual snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {"actualGlobalId": str(self.actual_global_id), "actualVersion": self.actual_version}
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "actualGlobalId": str(self.actual_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "inputLockRevisionGlobalId": str(self.input_lock_revision_global_id),
            "inputLockRevisionSnapshotHash": self.input_lock_revision_snapshot_hash,
            "actualVersion": self.actual_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "acquisitionMode": self.acquisition_mode.value,
            "resources": [value.snapshot_payload() for value in self.resources],
            "material": self.material.snapshot_payload(),
            "environment": [value.snapshot_payload() for value in self.environment],
            "parameters": [value.snapshot_payload() for value in self.parameters],
            "operatorUserId": self.operator_user_id,
            "confirmedByUserId": self.confirmed_by_user_id,
            "executionStartedAt": _utc_text(self.execution_started_at),
            "machineImport": "unavailable",
            "reason": self.reason,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_trial_actual_against_lock(
    input_lock: TrialRoundInputLockRevision,
    actual: TrialRoundActualRevision,
) -> None:
    if (
        actual.tenant_id != input_lock.tenant_id
        or actual.project_global_id != input_lock.project_global_id
        or actual.trial_round_global_id != input_lock.trial_round_global_id
        or actual.input_lock_revision_global_id != input_lock.global_id
        or actual.input_lock_revision_snapshot_hash != input_lock.snapshot_hash
    ):
        raise _problem(
            "inputLockRevisionGlobalId",
            _("Select the exact prepared Trial input lock revision."),
        )
    definitions = {value.key: value for value in input_lock.parameter_definitions}
    observations = {value.definition_key: value for value in actual.parameters}
    if set(observations) != set(definitions):
        raise _problem(
            "parameters",
            _("Record one explicit observation for every locked Trial parameter."),
        )
    for key, definition in definitions.items():
        observation = observations[key]
        if observation.state is TrialMeasurementState.NOT_MEASURED:
            continue
        if observation.unit != definition.unit:
            raise _problem("parameters.unit", _("The measured unit does not match the locked definition."))
        if definition.value_kind in {
            TrialParameterValueKind.DECIMAL,
            TrialParameterValueKind.INTEGER,
        }:
            normalized = _decimal(observation.value, "parameters.value")
            if definition.value_kind is TrialParameterValueKind.INTEGER and Decimal(normalized) % 1:
                raise _problem("parameters.value", _("Enter a whole number."))
        elif definition.value_kind is TrialParameterValueKind.BOOLEAN and observation.value not in {"true", "false"}:
            raise _problem("parameters.value", _("Enter true or false."))


def validate_trial_actual_successor(
    predecessor: TrialRoundActualRevision,
    successor: TrialRoundActualRevision,
) -> None:
    if (
        successor.actual_global_id != predecessor.actual_global_id
        or successor.tenant_id != predecessor.tenant_id
        or successor.project_global_id != predecessor.project_global_id
        or successor.trial_round_global_id != predecessor.trial_round_global_id
        or successor.input_lock_revision_global_id
        != predecessor.input_lock_revision_global_id
        or successor.input_lock_revision_snapshot_hash
        != predecessor.input_lock_revision_snapshot_hash
        or successor.actual_version != predecessor.actual_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial Actual revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialSampleBatchRevision:
    global_id: UUID
    sample_batch_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    input_lock_revision_global_id: UUID
    input_lock_revision_snapshot_hash: str
    sample_version: int
    label: str
    cavity_global_ids: tuple[UUID, ...]
    material_snapshot_hash: str
    quantity: int
    unit: str
    packaging: str
    destination: str
    feedback_text: str | None
    feedback_source: str | None
    feedback_observed_at: datetime | None
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    predecessor_global_id: UUID | None = None
    predecessor_snapshot_hash: str | None = None
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "sample_batch_global_id",
            "project_global_id",
            "trial_round_global_id",
            "input_lock_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), fieldname))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "input_lock_revision_snapshot_hash",
            _hash(self.input_lock_revision_snapshot_hash, "inputLockRevisionSnapshotHash"),
        )
        object.__setattr__(self, "sample_version", _positive(self.sample_version, "sampleVersion"))
        object.__setattr__(self, "label", _key(self.label, "label"))
        cavities = tuple(_uuid(value, "cavityGlobalIds") for value in self.cavity_global_ids)
        if not cavities or len(cavities) > 128 or len(set(cavities)) != len(cavities):
            raise _problem("cavityGlobalIds", _("Select unique cavities for the Sample Batch."))
        object.__setattr__(self, "cavity_global_ids", tuple(sorted(cavities, key=str)))
        object.__setattr__(
            self,
            "material_snapshot_hash",
            _hash(self.material_snapshot_hash, "materialSnapshotHash"),
        )
        object.__setattr__(self, "quantity", _positive(self.quantity, "quantity"))
        object.__setattr__(self, "unit", _text(self.unit, "unit", 32))
        object.__setattr__(self, "packaging", _text(self.packaging, "packaging", 280))
        object.__setattr__(self, "destination", _text(self.destination, "destination", 280))
        feedback = (self.feedback_text, self.feedback_source, self.feedback_observed_at)
        if any(value is not None for value in feedback):
            if not all(value is not None for value in feedback):
                raise _problem(
                    "feedbackText",
                    _("Enter the complete Sample Batch feedback observation."),
                )
            object.__setattr__(self, "feedback_text", _text(self.feedback_text, "feedbackText", 4000))
            object.__setattr__(self, "feedback_source", _text(self.feedback_source, "feedbackSource", 140))
            object.__setattr__(
                self,
                "feedback_observed_at",
                _aware(self.feedback_observed_at, "feedbackObservedAt"),
            )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 500))
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(self.created_by_user_id, "createdByUserId", 254).casefold(),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        if self.predecessor_snapshot_hash is not None:
            object.__setattr__(
                self,
                "predecessor_snapshot_hash",
                _hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
            )
        if self.sample_version == 1:
            if self.predecessor_global_id is not None or self.predecessor_snapshot_hash is not None:
                raise _problem(
                    "predecessorGlobalId",
                    _("The first Sample Batch revision cannot have a predecessor."),
                )
        elif self.predecessor_global_id is None or self.predecessor_snapshot_hash is None:
            raise _problem(
                "predecessorGlobalId",
                _("A Sample Batch successor requires its exact predecessor."),
            )
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Sample Batch snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "sampleBatchGlobalId": str(self.sample_batch_global_id),
                "sampleVersion": self.sample_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "sampleBatchGlobalId": str(self.sample_batch_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "inputLockRevisionGlobalId": str(self.input_lock_revision_global_id),
            "inputLockRevisionSnapshotHash": self.input_lock_revision_snapshot_hash,
            "sampleVersion": self.sample_version,
            "predecessorGlobalId": str(self.predecessor_global_id) if self.predecessor_global_id else None,
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "label": self.label,
            "cavityGlobalIds": [str(value) for value in self.cavity_global_ids],
            "materialSnapshotHash": self.material_snapshot_hash,
            "quantity": self.quantity,
            "unit": self.unit,
            "packaging": self.packaging,
            "destination": self.destination,
            "feedbackText": self.feedback_text,
            "feedbackSource": self.feedback_source,
            "feedbackObservedAt": _utc_text(self.feedback_observed_at) if self.feedback_observed_at else None,
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_sample_batch_successor(
    predecessor: TrialSampleBatchRevision,
    successor: TrialSampleBatchRevision,
) -> None:
    if (
        successor.sample_batch_global_id != predecessor.sample_batch_global_id
        or successor.tenant_id != predecessor.tenant_id
        or successor.project_global_id != predecessor.project_global_id
        or successor.trial_round_global_id != predecessor.trial_round_global_id
        or successor.input_lock_revision_global_id
        != predecessor.input_lock_revision_global_id
        or successor.input_lock_revision_snapshot_hash
        != predecessor.input_lock_revision_snapshot_hash
        or successor.sample_version != predecessor.sample_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
        or successor.label != predecessor.label
        or successor.cavity_global_ids != predecessor.cavity_global_ids
        or successor.material_snapshot_hash != predecessor.material_snapshot_hash
        or successor.quantity != predecessor.quantity
        or successor.unit != predecessor.unit
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Sample Batch revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialEvidenceReference:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    role: TrialEvidenceRole
    file_revision_global_id: UUID
    file_sha256: str
    file_size_bytes: int
    file_mime_type: str
    sample_batch_revision_global_id: UUID | None
    sample_batch_revision_snapshot_hash: str | None
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "trial_round_global_id",
            "file_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), fieldname))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        _enum(self.role, TrialEvidenceRole, "role")
        object.__setattr__(self, "file_sha256", _hash(self.file_sha256, "fileSha256"))
        object.__setattr__(self, "file_size_bytes", _positive(self.file_size_bytes, "fileSizeBytes"))
        object.__setattr__(self, "file_mime_type", _text(self.file_mime_type, "fileMimeType", 140).casefold())
        object.__setattr__(
            self,
            "sample_batch_revision_global_id",
            _optional_uuid(self.sample_batch_revision_global_id, "sampleBatchRevisionGlobalId"),
        )
        if (self.sample_batch_revision_global_id is None) != (
            self.sample_batch_revision_snapshot_hash is None
        ):
            raise _problem(
                "sampleBatchRevisionGlobalId",
                _("Select one complete Sample Batch revision, or leave it empty."),
            )
        if self.sample_batch_revision_snapshot_hash is not None:
            object.__setattr__(
                self,
                "sample_batch_revision_snapshot_hash",
                _hash(
                    self.sample_batch_revision_snapshot_hash,
                    "sampleBatchRevisionSnapshotHash",
                ),
            )
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(self.created_by_user_id, "createdByUserId", 254).casefold(),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial evidence reference snapshot hash does not match."),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "role": self.role.value,
            "sampleBatchRevisionGlobalId": str(self.sample_batch_revision_global_id) if self.sample_batch_revision_global_id else None,
            "sampleBatchRevisionSnapshotHash": self.sample_batch_revision_snapshot_hash,
            "fileRevisionGlobalId": str(self.file_revision_global_id),
            "fileSha256": self.file_sha256,
            "fileSizeBytes": self.file_size_bytes,
            "fileMimeType": self.file_mime_type,
            "scanState": "clean",
            "privacy": "private",
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def input_lock_from_snapshot(value: object) -> TrialRoundInputLockRevision:
    record = _record(
        value,
        "inputLockSnapshot",
        {
            "schemaVersion", "globalId", "inputLockGlobalId", "tenantId",
            "projectGlobalId", "trialRoundGlobalId", "trialPlanRevisionGlobalId",
            "trialPlanRevisionSnapshotHash", "lockVersion", "predecessorGlobalId",
            "predecessorSnapshotHash", "references", "material",
            "parameterDefinitions", "reason", "createdByUserId", "createdAt",
            "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return TrialRoundInputLockRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        input_lock_global_id=_uuid_text(record["inputLockGlobalId"], "inputLockGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        trial_plan_revision_global_id=_uuid_text(record["trialPlanRevisionGlobalId"], "trialPlanRevisionGlobalId"),
        trial_plan_revision_snapshot_hash=record["trialPlanRevisionSnapshotHash"],
        lock_version=record["lockVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        references=tuple(_locked_reference_from_snapshot(item) for item in _sequence(record["references"], "references", 100)),
        material=_material_from_snapshot(record["material"]),
        parameter_definitions=tuple(_parameter_definition_from_snapshot(item) for item in _sequence(record["parameterDefinitions"], "parameterDefinitions", 250)),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def actual_revision_from_snapshot(value: object) -> TrialRoundActualRevision:
    record = _record(
        value,
        "actualSnapshot",
        {
            "schemaVersion", "globalId", "actualGlobalId", "tenantId",
            "projectGlobalId", "trialRoundGlobalId", "inputLockRevisionGlobalId",
            "inputLockRevisionSnapshotHash", "actualVersion", "predecessorGlobalId",
            "predecessorSnapshotHash", "acquisitionMode", "resources", "material",
            "environment", "parameters", "operatorUserId", "confirmedByUserId",
            "executionStartedAt", "machineImport", "reason", "createdAt",
            "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    if record["machineImport"] != "unavailable":
        raise _problem("machineImport", _("Automatic machine import is unavailable."))
    return TrialRoundActualRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        actual_global_id=_uuid_text(record["actualGlobalId"], "actualGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        input_lock_revision_global_id=_uuid_text(record["inputLockRevisionGlobalId"], "inputLockRevisionGlobalId"),
        input_lock_revision_snapshot_hash=record["inputLockRevisionSnapshotHash"],
        actual_version=record["actualVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        acquisition_mode=_enum_text(record["acquisitionMode"], TrialAcquisitionMode, "acquisitionMode"),
        resources=tuple(_actual_resource_from_snapshot(item) for item in _sequence(record["resources"], "resources", 25)),
        material=_material_from_snapshot(record["material"]),
        environment=tuple(_environment_from_snapshot(item) for item in _sequence(record["environment"], "environment", 50)),
        parameters=tuple(_parameter_observation_from_snapshot(item) for item in _sequence(record["parameters"], "parameters", 250)),
        operator_user_id=record["operatorUserId"],
        confirmed_by_user_id=record["confirmedByUserId"],
        execution_started_at=_datetime_text(record["executionStartedAt"], "executionStartedAt"),
        reason=record["reason"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def sample_batch_from_snapshot(value: object) -> TrialSampleBatchRevision:
    record = _record(
        value,
        "sampleSnapshot",
        {
            "schemaVersion", "globalId", "sampleBatchGlobalId", "tenantId",
            "projectGlobalId", "trialRoundGlobalId", "inputLockRevisionGlobalId",
            "inputLockRevisionSnapshotHash", "sampleVersion", "predecessorGlobalId",
            "predecessorSnapshotHash", "label", "cavityGlobalIds",
            "materialSnapshotHash", "quantity", "unit", "packaging", "destination",
            "feedbackText", "feedbackSource", "feedbackObservedAt", "reason",
            "createdByUserId", "createdAt", "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    return TrialSampleBatchRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        sample_batch_global_id=_uuid_text(record["sampleBatchGlobalId"], "sampleBatchGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        input_lock_revision_global_id=_uuid_text(record["inputLockRevisionGlobalId"], "inputLockRevisionGlobalId"),
        input_lock_revision_snapshot_hash=record["inputLockRevisionSnapshotHash"],
        sample_version=record["sampleVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        label=record["label"],
        cavity_global_ids=tuple(_uuid_text(item, "cavityGlobalIds") for item in _sequence(record["cavityGlobalIds"], "cavityGlobalIds", 128)),
        material_snapshot_hash=record["materialSnapshotHash"],
        quantity=record["quantity"],
        unit=record["unit"],
        packaging=record["packaging"],
        destination=record["destination"],
        feedback_text=record["feedbackText"],
        feedback_source=record["feedbackSource"],
        feedback_observed_at=None if record["feedbackObservedAt"] is None else _datetime_text(record["feedbackObservedAt"], "feedbackObservedAt"),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def evidence_reference_from_snapshot(value: object) -> TrialEvidenceReference:
    record = _record(
        value,
        "evidenceSnapshot",
        {
            "schemaVersion", "globalId", "tenantId", "projectGlobalId",
            "trialRoundGlobalId", "role", "sampleBatchRevisionGlobalId",
            "sampleBatchRevisionSnapshotHash", "fileRevisionGlobalId", "fileSha256",
            "fileSizeBytes", "fileMimeType", "scanState", "privacy",
            "createdByUserId", "createdAt", "requestId", "traceId",
        },
    )
    _schema_version(record["schemaVersion"])
    if record["scanState"] != "clean" or record["privacy"] != "private":
        raise _problem("fileRevisionGlobalId", _("Select an exact clean private file revision."))
    return TrialEvidenceReference(
        global_id=_uuid_text(record["globalId"], "globalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        role=_enum_text(record["role"], TrialEvidenceRole, "role"),
        sample_batch_revision_global_id=_optional_uuid_text(record["sampleBatchRevisionGlobalId"], "sampleBatchRevisionGlobalId"),
        sample_batch_revision_snapshot_hash=record["sampleBatchRevisionSnapshotHash"],
        file_revision_global_id=_uuid_text(record["fileRevisionGlobalId"], "fileRevisionGlobalId"),
        file_sha256=record["fileSha256"],
        file_size_bytes=record["fileSizeBytes"],
        file_mime_type=record["fileMimeType"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def _locked_reference_from_snapshot(value: object) -> TrialLockedReference:
    record = _record(value, "references", {"globalId", "kind", "optimisticVersion", "snapshotHash"})
    return TrialLockedReference(
        global_id=_uuid_text(record["globalId"], "references.globalId"),
        kind=_enum_text(record["kind"], TrialLockedReferenceKind, "references.kind"),
        optimistic_version=record["optimisticVersion"],
        snapshot_hash=record["snapshotHash"],
    )


def _material_from_snapshot(value: object) -> TrialMaterialObservation:
    record = _record(
        value,
        "material",
        {"sourceSystem", "sourceObjectId", "lotBatchCode", "label", "color", "additive", "observedAt", "confirmedByUserId", "erpVerification"},
    )
    if record["erpVerification"] != "unavailable":
        raise _problem("material.erpVerification", _("ERP material verification is unavailable."))
    return TrialMaterialObservation(
        source_system=record["sourceSystem"],
        source_object_id=record["sourceObjectId"],
        lot_batch_code=record["lotBatchCode"],
        label=record["label"],
        color=record["color"],
        additive=record["additive"],
        observed_at=_datetime_text(record["observedAt"], "material.observedAt"),
        confirmed_by_user_id=record["confirmedByUserId"],
    )


def _parameter_definition_from_snapshot(value: object) -> TrialParameterDefinition:
    record = _record(value, "parameterDefinitions", {"key", "category", "valueKind", "required", "unit", "targetValue", "lowerLimit", "upperLimit"})
    return TrialParameterDefinition(
        key=record["key"],
        category=record["category"],
        value_kind=_enum_text(record["valueKind"], TrialParameterValueKind, "parameters.valueKind"),
        required=record["required"],
        unit=record["unit"],
        target_value=record["targetValue"],
        lower_limit=record["lowerLimit"],
        upper_limit=record["upperLimit"],
    )


def _actual_resource_from_snapshot(value: object) -> TrialActualResourceObservation:
    record = _record(value, "resources", {"kind", "sourceSystem", "sourceObjectId", "label", "erpVerification"})
    if record["erpVerification"] != "unavailable":
        raise _problem("resources.erpVerification", _("ERP resource verification is unavailable."))
    return TrialActualResourceObservation(
        kind=_enum_text(record["kind"], TrialActualResourceKind, "resources.kind"),
        source_system=record["sourceSystem"],
        source_object_id=record["sourceObjectId"],
        label=record["label"],
    )


def _environment_from_snapshot(value: object) -> TrialEnvironmentObservation:
    record = _record(value, "environment", {"key", "value", "unit", "observedAt"})
    return TrialEnvironmentObservation(
        key=record["key"],
        value=record["value"],
        unit=record["unit"],
        observed_at=_datetime_text(record["observedAt"], "environment.observedAt"),
    )


def _parameter_observation_from_snapshot(value: object) -> TrialParameterObservation:
    record = _record(value, "parameters", {"definitionKey", "state", "value", "unit", "source", "observedAt"})
    return TrialParameterObservation(
        definition_key=record["definitionKey"],
        state=_enum_text(record["state"], TrialMeasurementState, "parameters.state"),
        value=record["value"],
        unit=record["unit"],
        source=None if record["source"] is None else _enum_text(record["source"], TrialAcquisitionMode, "parameters.source"),
        observed_at=None if record["observedAt"] is None else _datetime_text(record["observedAt"], "parameters.observedAt"),
    )
