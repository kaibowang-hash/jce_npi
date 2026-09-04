from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from npi_core.change_control.domain import (
    AffectedObjectKind,
    AffectedObjectVersion,
    ClosureEvidence,
    CostSummary,
    DispositionDecision,
    DispositionKind,
    DispositionScope,
    EffectivityKind,
    EffectivityRule,
    FormalChangeObservation,
    ImpactAssessment,
    ImpactCategory,
    ImpactConclusion,
    ImplementationTaskKind,
    ImplementationTaskLink,
    RevalidationKind,
    RevalidationRequirement,
    RevalidationState,
)
from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps command parsing independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


CONTENT_FIELDS = frozenset(
    {
        "title",
        "reason",
        "impactAssessments",
        "affectedObjects",
        "implementationTasks",
        "effectivityRules",
        "dispositions",
        "revalidationRequirements",
        "costSummary",
        "closureEvidence",
    }
)
PREDECESSOR_FIELDS = frozenset(
    {
        "expectedRevision",
        "expectedRevisionGlobalId",
        "expectedRevisionSnapshotHash",
    }
)
OBSERVATION_FIELDS = frozenset(
    {
        "doctype",
        "documentName",
        "rawStatus",
        "sourceVersion",
        "sourceModifiedAt",
        "sourceHash",
        "observedAt",
    }
)


def closed_payload(
    value: object,
    path: str,
    allowed: frozenset[str],
    required: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _field(path, _("Enter a valid object."))
    required_fields = allowed if required is None else required
    unexpected = sorted(
        (name for name in value if not isinstance(name, str) or name not in allowed),
        key=str,
    )
    if unexpected:
        raise RequestValidationFailed(
            [
                {
                    "path": _child(path, str(name)),
                    "message": _("This field is not allowed."),
                }
                for name in unexpected
            ]
        )
    missing = sorted(required_fields - set(value))
    if missing:
        raise RequestValidationFailed(
            [
                {
                    "path": _child(path, name),
                    "message": _("This field is required."),
                }
                for name in missing
            ]
        )
    return dict(value)


def parse_predecessor(value: object, path: str = "predecessor") -> dict[str, object]:
    record = closed_payload(value, path, PREDECESSOR_FIELDS)
    return {
        "expected_revision": _positive(record["expectedRevision"], _child(path, "expectedRevision")),
        "expected_revision_global_id": _uuid(record["expectedRevisionGlobalId"], _child(path, "expectedRevisionGlobalId")),
        "expected_revision_snapshot_hash": _hash(record["expectedRevisionSnapshotHash"], _child(path, "expectedRevisionSnapshotHash")),
    }


def parse_revision_content(
    value: object,
    path: str = "content",
    *,
    require_closure: bool = False,
) -> dict[str, object]:
    required = CONTENT_FIELDS if require_closure else CONTENT_FIELDS - {"closureEvidence"}
    record = closed_payload(value, path, CONTENT_FIELDS, required)
    closure = record.get("closureEvidence")
    return {
        "title": _text(record["title"], _child(path, "title"), 280),
        "reason": _text(record["reason"], _child(path, "reason"), 4_000),
        "impact_assessments": _impact_assessments(record["impactAssessments"], _child(path, "impactAssessments")),
        "affected_objects": _affected_objects(record["affectedObjects"], _child(path, "affectedObjects")),
        "implementation_tasks": _implementation_tasks(record["implementationTasks"], _child(path, "implementationTasks")),
        "effectivity_rules": _effectivity_rules(record["effectivityRules"], _child(path, "effectivityRules")),
        "dispositions": _dispositions(record["dispositions"], _child(path, "dispositions")),
        "revalidation_requirements": _revalidations(record["revalidationRequirements"], _child(path, "revalidationRequirements")),
        "cost_summary": _cost(record["costSummary"], _child(path, "costSummary")),
        "closure_evidence": None if closure is None else _closure(closure, _child(path, "closureEvidence")),
    }


def parse_formal_observation(value: object, path: str = "formalChange") -> FormalChangeObservation:
    record = closed_payload(value, path, OBSERVATION_FIELDS)
    return FormalChangeObservation(
        doctype=_text(record["doctype"], _child(path, "doctype"), 140),
        document_name=_text(record["documentName"], _child(path, "documentName"), 140),
        raw_status=_text(record["rawStatus"], _child(path, "rawStatus"), 140),
        source_version=_text(record["sourceVersion"], _child(path, "sourceVersion"), 140),
        source_modified_at=_datetime(record["sourceModifiedAt"], _child(path, "sourceModifiedAt")),
        source_hash=_hash(record["sourceHash"], _child(path, "sourceHash")),
        observed_at=_datetime(record["observedAt"], _child(path, "observedAt")),
    )


def _impact_assessments(value: object, path: str) -> tuple[ImpactAssessment, ...]:
    fields = frozenset({"category", "conclusion", "responsibleUserId", "rationale", "evidenceReferenceGlobalIds"})
    return tuple(
        ImpactAssessment(
            category=_enum(record["category"], ImpactCategory, f"{item_path}.category"),
            conclusion=_enum(record["conclusion"], ImpactConclusion, f"{item_path}.conclusion"),
            responsible_user_id=_text(record["responsibleUserId"], f"{item_path}.responsibleUserId", 254),
            rationale=_text(record["rationale"], f"{item_path}.rationale", 4_000),
            evidence_reference_global_ids=_uuids(record["evidenceReferenceGlobalIds"], f"{item_path}.evidenceReferenceGlobalIds"),
        )
        for item_path, record in _records(value, path, fields, 12)
    )


def _affected_objects(value: object, path: str) -> tuple[AffectedObjectVersion, ...]:
    fields = frozenset({"category", "kind", "objectGlobalId", "priorVersionGlobalId", "priorSnapshotHash", "successorVersionGlobalId", "successorSnapshotHash"})
    return tuple(
        AffectedObjectVersion(
            category=_enum(record["category"], ImpactCategory, f"{item_path}.category"),
            kind=_enum(record["kind"], AffectedObjectKind, f"{item_path}.kind"),
            object_global_id=_uuid(record["objectGlobalId"], f"{item_path}.objectGlobalId"),
            prior_version_global_id=_optional_uuid(record["priorVersionGlobalId"], f"{item_path}.priorVersionGlobalId"),
            prior_snapshot_hash=_optional_hash(record["priorSnapshotHash"], f"{item_path}.priorSnapshotHash"),
            successor_version_global_id=_optional_uuid(record["successorVersionGlobalId"], f"{item_path}.successorVersionGlobalId"),
            successor_snapshot_hash=_optional_hash(record["successorSnapshotHash"], f"{item_path}.successorSnapshotHash"),
        )
        for item_path, record in _records(value, path, fields)
    )


def _implementation_tasks(value: object, path: str) -> tuple[ImplementationTaskLink, ...]:
    fields = frozenset({"kind", "workItemGlobalId", "purpose"})
    return tuple(
        ImplementationTaskLink(
            kind=_enum(record["kind"], ImplementationTaskKind, f"{item_path}.kind"),
            work_item_global_id=_uuid(record["workItemGlobalId"], f"{item_path}.workItemGlobalId"),
            purpose=_text(record["purpose"], f"{item_path}.purpose", 500),
        )
        for item_path, record in _records(value, path, fields)
    )


def _effectivity_rules(value: object, path: str) -> tuple[EffectivityRule, ...]:
    fields = frozenset({"kind", "effectiveDate", "selectorReference", "validationEvidenceGlobalId"})
    return tuple(
        EffectivityRule(
            kind=_enum(record["kind"], EffectivityKind, f"{item_path}.kind"),
            effective_date=_optional_date(record["effectiveDate"], f"{item_path}.effectiveDate"),
            selector_reference=_optional_text(record["selectorReference"], f"{item_path}.selectorReference", 280),
            validation_evidence_global_id=_optional_uuid(record["validationEvidenceGlobalId"], f"{item_path}.validationEvidenceGlobalId"),
        )
        for item_path, record in _records(value, path, fields)
    )


def _dispositions(value: object, path: str) -> tuple[DispositionDecision, ...]:
    fields = frozenset({"scope", "decision", "approvedByUserId", "approvalEvidenceGlobalId", "executionEvidenceGlobalId", "note"})
    return tuple(
        DispositionDecision(
            scope=_enum(record["scope"], DispositionScope, f"{item_path}.scope"),
            decision=_enum(record["decision"], DispositionKind, f"{item_path}.decision"),
            approved_by_user_id=_text(record["approvedByUserId"], f"{item_path}.approvedByUserId", 254),
            approval_evidence_global_id=_uuid(record["approvalEvidenceGlobalId"], f"{item_path}.approvalEvidenceGlobalId"),
            execution_evidence_global_id=_optional_uuid(record["executionEvidenceGlobalId"], f"{item_path}.executionEvidenceGlobalId"),
            note=_optional_text(record["note"], f"{item_path}.note", 2_000),
        )
        for item_path, record in _records(value, path, fields)
    )


def _revalidations(value: object, path: str) -> tuple[RevalidationRequirement, ...]:
    fields = frozenset({"kind", "state", "responsibleUserId", "workItemGlobalId", "gateReviewGlobalId", "evidenceReferenceGlobalIds", "waiverApprovalGlobalId"})
    return tuple(
        RevalidationRequirement(
            kind=_enum(record["kind"], RevalidationKind, f"{item_path}.kind"),
            state=_enum(record["state"], RevalidationState, f"{item_path}.state"),
            responsible_user_id=_text(record["responsibleUserId"], f"{item_path}.responsibleUserId", 254),
            work_item_global_id=_optional_uuid(record["workItemGlobalId"], f"{item_path}.workItemGlobalId"),
            gate_review_global_id=_optional_uuid(record["gateReviewGlobalId"], f"{item_path}.gateReviewGlobalId"),
            evidence_reference_global_ids=_uuids(record["evidenceReferenceGlobalIds"], f"{item_path}.evidenceReferenceGlobalIds"),
            waiver_approval_global_id=_optional_uuid(record["waiverApprovalGlobalId"], f"{item_path}.waiverApprovalGlobalId"),
        )
        for item_path, record in _records(value, path, fields)
    )


def _cost(value: object, path: str) -> CostSummary:
    fields = frozenset({"currency", "engineeringCost", "toolingCost", "scrapCost", "logisticsCost", "downtimeMinutes", "deliveryImpactDays"})
    record = closed_payload(value, path, fields)
    return CostSummary(
        currency=_text(record["currency"], f"{path}.currency", 3),
        engineering_cost=_decimal(record["engineeringCost"], f"{path}.engineeringCost"),
        tooling_cost=_decimal(record["toolingCost"], f"{path}.toolingCost"),
        scrap_cost=_decimal(record["scrapCost"], f"{path}.scrapCost"),
        logistics_cost=_decimal(record["logisticsCost"], f"{path}.logisticsCost"),
        downtime_minutes=_nonnegative(record["downtimeMinutes"], f"{path}.downtimeMinutes"),
        delivery_impact_days=_nonnegative(record["deliveryImpactDays"], f"{path}.deliveryImpactDays"),
    )


def _closure(value: object, path: str) -> ClosureEvidence:
    fields = frozenset({"newVersionsReleased", "erpUpdateObserved", "oldVersionsWithdrawn", "effectivityValidated", "dispositionsExecuted", "evidenceReferenceGlobalIds"})
    record = closed_payload(value, path, fields)
    return ClosureEvidence(
        new_versions_released=_boolean(record["newVersionsReleased"], f"{path}.newVersionsReleased"),
        erp_update_observed=_boolean(record["erpUpdateObserved"], f"{path}.erpUpdateObserved"),
        old_versions_withdrawn=_boolean(record["oldVersionsWithdrawn"], f"{path}.oldVersionsWithdrawn"),
        effectivity_validated=_boolean(record["effectivityValidated"], f"{path}.effectivityValidated"),
        dispositions_executed=_boolean(record["dispositionsExecuted"], f"{path}.dispositionsExecuted"),
        evidence_reference_global_ids=_uuids(record["evidenceReferenceGlobalIds"], f"{path}.evidenceReferenceGlobalIds"),
    )


def _records(value: object, path: str, fields: frozenset[str], exact_length: int | None = None):
    items = _array(value, path)
    if exact_length is not None and len(items) != exact_length:
        raise _field(path, _("Enter the exact required collection."))
    return tuple((f"{path}[{index}]", closed_payload(item, f"{path}[{index}]", fields)) for index, item in enumerate(items))


def _array(value: object, path: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or len(value) > 1_000:
        raise _field(path, _("Enter a valid bounded list."))
    return tuple(value)


def _uuids(value: object, path: str) -> tuple[UUID, ...]:
    result = tuple(_uuid(item, f"{path}[{index}]") for index, item in enumerate(_array(value, path)))
    if len(set(result)) != len(result):
        raise _field(path, _("Values must be unique."))
    return result


def _enum(value: object, enum_type, path: str):
    if not isinstance(value, str):
        raise _field(path, _("Select a supported value."))
    try:
        return enum_type(value)
    except ValueError as error:
        raise _field(path, _("Select a supported value.")) from error


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid global ID."))
    try:
        result = UUID(value)
    except ValueError as error:
        raise _field(path, _("Enter a valid global ID.")) from error
    if str(result) != value.casefold() or result.int == 0:
        raise _field(path, _("Enter a valid global ID."))
    return result


def _optional_uuid(value: object, path: str) -> UUID | None:
    return None if value is None else _uuid(value, path)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise _field(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise _field(path, _("Enter a valid value."))
    return value.strip()


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _field(path, _("Enter a non-negative integer."))
    return value


def _boolean(value: object, path: str) -> bool:
    if type(value) is not bool:
        raise _field(path, _("Enter a valid true or false value."))
    return value


def _date(value: object, path: str) -> date:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid date."))
    try:
        result = date.fromisoformat(value)
    except ValueError as error:
        raise _field(path, _("Enter a valid date.")) from error
    if result.isoformat() != value:
        raise _field(path, _("Enter a valid date."))
    return result


def _optional_date(value: object, path: str) -> date | None:
    return None if value is None else _date(value, path)


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise _field(path, _("Enter a valid timestamp."))
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _field(path, _("Enter a valid timestamp.")) from error
    if result.tzinfo is None:
        raise _field(path, _("Enter a valid timestamp."))
    return result.astimezone(UTC)


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool):
        raise _field(path, _("Enter a valid decimal value."))
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise _field(path, _("Enter a valid decimal value.")) from error
    if not result.is_finite():
        raise _field(path, _("Enter a finite decimal value."))
    return result


def _child(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _field(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
