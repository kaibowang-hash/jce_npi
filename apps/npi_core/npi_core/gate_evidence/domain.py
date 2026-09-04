from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from uuid import UUID, uuid5

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


FROZEN_REQUIREMENT_SCHEMA_VERSION = 1
EVIDENCE_SOURCE_SCHEMA_VERSION = 1


def _sha256_json(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class GateRequirementsAlreadyFrozen(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "GATE_REQUIREMENTS_ALREADY_FROZEN",
            _("The Gate requirements are already frozen."),
        )


class GateRequirementsNotFrozen(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "GATE_REQUIREMENTS_NOT_FROZEN",
            _("Freeze the Gate requirements before attaching evidence."),
        )


class GateTemplateUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "GATE_TEMPLATE_UNAVAILABLE",
            _("The Gate Template version is unavailable."),
        )


class EvidenceSourceUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            422,
            "EVIDENCE_SOURCE_UNAVAILABLE",
            _("The exact evidence source is unavailable."),
        )


class EvidenceVersionConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "EVIDENCE_VERSION_CONFLICT",
            _("The evidence source version or hash has changed."),
        )


class EvidenceAlreadyAttached(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "EVIDENCE_ALREADY_ATTACHED",
            _("The exact evidence reference is already attached."),
        )


def build_frozen_requirement_snapshot(
    *,
    gate_global_id: UUID,
    gate_template_snapshot: object,
    gate_due_date: date,
    assignments: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], str]:
    """Return one deterministic Project-specific requirement snapshot and hash."""
    if not isinstance(gate_global_id, UUID) or not isinstance(gate_due_date, date):
        raise _field_problem("gateId", _("Enter a valid value."))
    requirements = tuple(getattr(gate_template_snapshot, "requirements", ()))
    if not requirements:
        raise GateTemplateUnavailable()

    prepared_assignments: dict[str, Mapping[str, object]] = {}
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, Mapping):
            raise _field_problem(
                f"requirements[{index}]",
                _("Enter a valid value."),
            )
        key = assignment.get("key")
        if not isinstance(key, str) or not key:
            raise _field_problem(
                f"requirements[{index}].key",
                _("Enter a valid value."),
            )
        folded = key.casefold()
        if folded in prepared_assignments:
            raise _field_problem(
                "requirements",
                _("Requirement assignment keys must be unique."),
            )
        prepared_assignments[folded] = assignment

    template_keys = tuple(str(requirement.key) for requirement in requirements)
    if set(prepared_assignments) != {value.casefold() for value in template_keys}:
        raise _field_problem(
            "requirements",
            _("Assign every requirement from the selected Gate Template version."),
        )

    frozen: list[dict[str, object]] = []
    for requirement in requirements:
        assignment = prepared_assignments[str(requirement.key).casefold()]
        owner_member_id = assignment.get("owner_member_id")
        due_date = assignment.get("due_date")
        reviewer_values = assignment.get("reviewer_member_ids")
        if not isinstance(owner_member_id, UUID):
            raise _field_problem(
                f"requirements.{requirement.key}.ownerMemberId",
                _("Enter a valid global ID."),
            )
        if not isinstance(due_date, date):
            raise _field_problem(
                f"requirements.{requirement.key}.dueDate",
                _("Enter a valid date."),
            )
        if not isinstance(reviewer_values, Sequence) or isinstance(
            reviewer_values,
            (str, bytes),
        ):
            raise _field_problem(
                f"requirements.{requirement.key}.reviewerMemberIds",
                _("Enter a valid list."),
            )
        reviewers = tuple(reviewer_values)
        if (
            not reviewers
            or any(not isinstance(value, UUID) for value in reviewers)
            or len(reviewers) != len(set(reviewers))
        ):
            raise _field_problem(
                f"requirements.{requirement.key}.reviewerMemberIds",
                _("Enter unique Project member identities."),
            )
        canonical_definition = requirement.canonical_dict()
        frozen.append(
            {
                "globalId": str(
                    requirement_global_id(gate_global_id, str(requirement.key))
                ),
                **canonical_definition,
                "ownerMemberId": str(owner_member_id),
                "reviewerMemberIds": sorted(str(value) for value in reviewers),
                "dueDate": due_date.isoformat(),
            }
        )

    reference = {
        "globalId": str(
            getattr(
                gate_template_snapshot,
                "gate_template_global_id",
            )
        ),
        "version": int(
            getattr(
                gate_template_snapshot,
                "gate_template_version",
            )
        ),
        "snapshotHash": str(
            getattr(
                gate_template_snapshot,
                "snapshot_hash",
            )
        ),
    }
    snapshot: dict[str, object] = {
        "schemaVersion": FROZEN_REQUIREMENT_SCHEMA_VERSION,
        "gateTemplateRef": reference,
        "gateDueDate": gate_due_date.isoformat(),
        "requirements": frozen,
    }
    return snapshot, _sha256_json(snapshot)


def requirement_global_id(gate_global_id: UUID, requirement_key: str) -> UUID:
    return uuid5(
        gate_global_id,
        f"gate-requirement:{requirement_key.casefold()}",
    )


def evidence_reference_key(
    *,
    tenant_id: str,
    project_global_id: str,
    gate_global_id: str,
    requirement_global_id: str,
    requirement_key: str,
    evidence_kind: str,
    source_object_type: str,
    source_global_id: str,
    source_version: int,
    source_hash: str,
) -> str:
    identity = {
        "evidenceKind": evidence_kind,
        "gateGlobalId": gate_global_id,
        "projectGlobalId": project_global_id,
        "requirementGlobalId": requirement_global_id,
        "requirementKey": requirement_key,
        "sourceGlobalId": source_global_id,
        "sourceHash": source_hash,
        "sourceObjectType": source_object_type,
        "sourceVersion": source_version,
        "tenantId": tenant_id,
    }
    return _sha256_json(identity)


def wbs_source_snapshot(document: object) -> tuple[dict[str, object], str]:
    """Capture the exact safe WBS revision metadata attached as Gate evidence."""
    get = _document_getter(document)
    snapshot: dict[str, object] = {
        "globalId": str(UUID(str(get("global_id")))),
        "tenantId": str(get("tenant_id")),
        "projectGlobalId": str(UUID(str(get("project_global_id")))),
        "workPolicyGlobalId": str(UUID(str(get("work_policy_global_id")))),
        "workPolicyVersion": int(get("work_policy_version")),
        "workPolicySnapshotHash": str(get("work_policy_snapshot_hash")),
        "wbsCode": str(get("wbs_code")),
        "title": str(get("title")),
        "parentGlobalId": _optional_uuid_text(get("parent_global_id")),
        "ownerRoleAssignmentGlobalId": _optional_uuid_text(
            get("owner_role_assignment_global_id")
        ),
        "plannedStart": _optional_date_text(get("planned_start")),
        "plannedEnd": _optional_date_text(get("planned_end")),
        "actualStart": _optional_date_text(get("actual_start")),
        "actualEnd": _optional_date_text(get("actual_end")),
        "milestone": bool(get("milestone")),
        "statusKey": str(get("status_key")),
        "statusLabelSource": str(get("status_label_source")),
        "progressPercent": int(get("progress_percent")),
        "criticalTask": bool(get("critical_task")),
        "planRevision": int(get("plan_revision")),
        "optimisticVersion": int(get("optimistic_version")),
    }
    return snapshot, _sha256_json(snapshot)


def _document_getter(document: object):
    if isinstance(document, Mapping):
        return document.get
    return lambda name: getattr(document, name, None)


def _optional_uuid_text(value: object) -> str | None:
    return None if value in (None, "") else str(UUID(str(value)))


def _date_text(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _optional_date_text(value: object) -> str | None:
    return None if value in (None, "") else _date_text(value)


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])
