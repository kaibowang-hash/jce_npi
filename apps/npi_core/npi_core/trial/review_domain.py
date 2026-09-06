from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Iterable, Sequence
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.tooling.engineering_controls_domain import ToolingDefectState
from npi_core.tooling.manufacturing_domain import ProjectMemberResponsibility
from npi_core.trial.domain import TRIAL_SCHEMA_VERSION, sha256_json

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


class TrialConclusionCode(StrEnum):
    PASS = "pass"
    CONDITIONAL_PASS = "conditional_pass"
    TOOLING_CHANGE = "tooling_change"
    DESIGN_CHANGE = "design_change"
    PROCESS_TUNING = "process_tuning"
    MATERIAL_CHANGE = "material_change"
    CANCELLED = "cancelled"


class TrialConclusionCapability(StrEnum):
    SUBMIT = "submit"
    DECIDE = "decide"
    REOPEN = "reopen"


class TrialComparisonMetricKind(StrEnum):
    PARAMETER = "parameter"
    DIMENSION = "dimension"
    CYCLE_TIME = "cycle_time"
    YIELD = "yield"


class TrialComparisonCellState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"
    UNAVAILABLE = "unavailable"


class TrialComparisonState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"
    UNAVAILABLE = "unavailable"
    WITHIN_SPEC = "within_spec"
    OUT_OF_SPEC = "out_of_spec"


class TrialComparisonUnitState(StrEnum):
    COMPARABLE = "comparable"
    UNIT_MISMATCH = "unit_mismatch"
    UNAVAILABLE = "unavailable"


class TrialInputChangeState(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    SAME = "same"


class TrialDefectSourceKind(StrEnum):
    TOOLING = "tooling"
    TRIAL = "trial"


class TrialDefectTrendState(StrEnum):
    NEW = "new"
    CONTINUED = "continued"
    RESOLVED = "resolved"
    REOPENED = "reopened"


class TrialReviewReferenceKind(StrEnum):
    CONTROLLED_QUALITY_REPORT = "controlled_quality_report"
    INTERNAL_SAMPLE_REVIEW = "internal_sample_review"
    CUSTOMER_EVIDENCE = "customer_evidence"
    DEVIATION_OR_WAIVER = "deviation_or_waiver"


class TrialConclusionRevisionState(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REOPENED = "reopened"


class TrialConclusionBlockerCode(StrEnum):
    MISSING_INPUT_LOCK = "missing_input_lock"
    MISSING_ACTUAL = "missing_actual"
    REQUIRED_PARAMETER_NOT_MEASURED = "required_parameter_not_measured"
    MISSING_CAVITY_RESULT = "missing_cavity_result"
    REQUIRED_DIMENSION_NOT_MEASURED = "required_dimension_not_measured"
    OPEN_BLOCKING_DEFECT = "open_blocking_defect"
    REQUIRED_ACTION_NOT_VERIFIED = "required_action_not_verified"
    REQUIRED_REVIEW_REFERENCE_UNAVAILABLE = "required_review_reference_unavailable"
    OUT_OF_SPEC_BLOCKING = "out_of_spec_blocking"


class TrialReviewUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "TRIAL_REVIEW_UNAVAILABLE",
            _("The Trial review object is unavailable."),
        )


class TrialReviewConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "TRIAL_REVIEW_CONFLICT",
            _("The Trial review record was changed by another user."),
        )


class TrialReviewRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "TRIAL_REVIEW_ROUTES_DISABLED",
            _("The Trial review workspace is temporarily unavailable."),
            _("The review routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


@dataclass(frozen=True, slots=True)
class TrialExactReference:
    global_id: UUID
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "reference.globalId"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "reference.snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {"globalId": str(self.global_id), "snapshotHash": self.snapshot_hash}


@dataclass(frozen=True, slots=True)
class TrialPolicyAuthorityBinding:
    member: ProjectMemberResponsibility
    capabilities: tuple[TrialConclusionCapability, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.member, ProjectMemberResponsibility):
            raise _problem("authorityBindings.member", _("Select a valid Project member."))
        capabilities = _typed_tuple(
            self.capabilities,
            TrialConclusionCapability,
            "authorityBindings.capabilities",
            minimum=1,
            maximum=3,
        )
        _unique(capabilities, "authorityBindings.capabilities")
        object.__setattr__(self, "capabilities", tuple(sorted(capabilities, key=str)))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "member": self.member.snapshot_payload(),
            "capabilities": [value.value for value in self.capabilities],
        }


@dataclass(frozen=True, slots=True)
class TrialConclusionPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_plan_global_id: UUID
    trial_plan_revision_global_id: UUID
    trial_plan_revision_snapshot_hash: str
    policy_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    required_parameter_keys: tuple[str, ...]
    required_dimension_keys: tuple[str, ...]
    required_reference_kinds: tuple[TrialReviewReferenceKind, ...]
    require_cavity_results: bool
    block_on_open_blocking_defects: bool
    block_on_unverified_required_actions: bool
    allowed_conclusion_codes: tuple[TrialConclusionCode, ...]
    out_of_spec_blocking_codes: tuple[TrialConclusionCode, ...]
    authority_bindings: tuple[TrialPolicyAuthorityBinding, ...]
    published_by_user_id: str
    published_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "policy_global_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_plan_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_plan_revision_snapshot_hash",
            _hash(
                self.trial_plan_revision_snapshot_hash,
                "trialPlanRevisionSnapshotHash",
            ),
        )
        object.__setattr__(self, "policy_version", _positive(self.policy_version, "policyVersion"))
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
        )
        _require_predecessor(
            self.policy_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        object.__setattr__(
            self,
            "required_parameter_keys",
            _key_tuple(self.required_parameter_keys, "requiredParameterKeys", 250),
        )
        object.__setattr__(
            self,
            "required_dimension_keys",
            _key_tuple(self.required_dimension_keys, "requiredDimensionKeys", 1_000),
        )
        reference_kinds = _typed_tuple(
            self.required_reference_kinds,
            TrialReviewReferenceKind,
            "requiredReferenceKinds",
            minimum=1,
            maximum=len(TrialReviewReferenceKind),
        )
        _unique(reference_kinds, "requiredReferenceKinds")
        object.__setattr__(
            self,
            "required_reference_kinds",
            tuple(sorted(reference_kinds, key=str)),
        )
        for fieldname in (
            "require_cavity_results",
            "block_on_open_blocking_defects",
            "block_on_unverified_required_actions",
        ):
            if type(getattr(self, fieldname)) is not bool:
                raise _problem(_camel(fieldname), _("Select a valid true or false value."))
        allowed_codes = _typed_tuple(
            self.allowed_conclusion_codes,
            TrialConclusionCode,
            "allowedConclusionCodes",
            minimum=1,
            maximum=len(TrialConclusionCode),
        )
        _unique(allowed_codes, "allowedConclusionCodes")
        object.__setattr__(
            self,
            "allowed_conclusion_codes",
            tuple(sorted(allowed_codes, key=str)),
        )
        blocking_codes = _typed_tuple(
            self.out_of_spec_blocking_codes,
            TrialConclusionCode,
            "outOfSpecBlockingCodes",
            minimum=0,
            maximum=len(TrialConclusionCode),
        )
        _unique(blocking_codes, "outOfSpecBlockingCodes")
        if not set(blocking_codes).issubset(allowed_codes):
            raise _problem(
                "outOfSpecBlockingCodes",
                _("Out-of-specification blocker codes must be allowed conclusions."),
            )
        object.__setattr__(
            self,
            "out_of_spec_blocking_codes",
            tuple(sorted(blocking_codes, key=str)),
        )
        bindings = _typed_tuple(
            self.authority_bindings,
            TrialPolicyAuthorityBinding,
            "authorityBindings",
            minimum=1,
            maximum=100,
        )
        _unique((value.member.global_id for value in bindings), "authorityBindings")
        bound_capabilities = {
            capability for binding in bindings for capability in binding.capabilities
        }
        if bound_capabilities != set(TrialConclusionCapability):
            raise _problem(
                "authorityBindings",
                _("Bind submit, decision and reopen authority explicitly."),
            )
        object.__setattr__(
            self,
            "authority_bindings",
            tuple(sorted(bindings, key=lambda value: str(value.member.global_id))),
        )
        object.__setattr__(
            self,
            "published_by_user_id",
            _actor(self.published_by_user_id, "publishedByUserId"),
        )
        object.__setattr__(self, "published_at", _aware(self.published_at, "publishedAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial conclusion policy snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "policyGlobalId": str(self.policy_global_id),
                "policyVersion": self.policy_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialPlanGlobalId": str(self.trial_plan_global_id),
            "trialPlanRevisionGlobalId": str(self.trial_plan_revision_global_id),
            "trialPlanRevisionSnapshotHash": self.trial_plan_revision_snapshot_hash,
            "policyVersion": self.policy_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "requiredParameterKeys": list(self.required_parameter_keys),
            "requiredDimensionKeys": list(self.required_dimension_keys),
            "requiredReferenceKinds": [value.value for value in self.required_reference_kinds],
            "requireCavityResults": self.require_cavity_results,
            "blockOnOpenBlockingDefects": self.block_on_open_blocking_defects,
            "blockOnUnverifiedRequiredActions": self.block_on_unverified_required_actions,
            "allowedConclusionCodes": [value.value for value in self.allowed_conclusion_codes],
            "outOfSpecBlockingCodes": [value.value for value in self.out_of_spec_blocking_codes],
            "authorityBindings": [value.snapshot_payload() for value in self.authority_bindings],
            "publishedByUserId": self.published_by_user_id,
            "publishedAt": _utc_text(self.published_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_conclusion_policy_successor(
    predecessor: TrialConclusionPolicyVersion,
    successor: TrialConclusionPolicyVersion,
) -> None:
    if (
        predecessor.policy_global_id != successor.policy_global_id
        or predecessor.tenant_id != successor.tenant_id
        or predecessor.project_global_id != successor.project_global_id
        or predecessor.trial_plan_global_id != successor.trial_plan_global_id
        or successor.policy_version != predecessor.policy_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial conclusion policy version."),
        )


@dataclass(frozen=True, slots=True)
class TrialCavityResultTip:
    cavity_global_id: UUID
    revision: TrialExactReference

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cavity_global_id",
            _uuid(self.cavity_global_id, "cavityResults.cavityGlobalId"),
        )
        if not isinstance(self.revision, TrialExactReference):
            raise _problem("cavityResults.revision", _("Select an exact Trial revision."))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "cavityGlobalId": str(self.cavity_global_id),
            "revision": self.revision.snapshot_payload(),
        }


@dataclass(frozen=True, slots=True)
class TrialDefectTip:
    defect_global_id: UUID
    source_kind: TrialDefectSourceKind
    revision: TrialExactReference
    state: ToolingDefectState
    blocking: bool
    required_actions_unverified: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "defect_global_id",
            _uuid(self.defect_global_id, "defects.defectGlobalId"),
        )
        _enum(self.source_kind, TrialDefectSourceKind, "defects.sourceKind")
        if not isinstance(self.revision, TrialExactReference):
            raise _problem("defects.revision", _("Select an exact Trial revision."))
        _enum(self.state, ToolingDefectState, "defects.state")
        if type(self.blocking) is not bool:
            raise _problem("defects.blocking", _("Select a valid true or false value."))
        object.__setattr__(
            self,
            "required_actions_unverified",
            _nonnegative(
                self.required_actions_unverified,
                "defects.requiredActionsUnverified",
            ),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "defectGlobalId": str(self.defect_global_id),
            "sourceKind": self.source_kind.value,
            "revision": self.revision.snapshot_payload(),
            "state": self.state.value,
            "blocking": self.blocking,
            "requiredActionsUnverified": self.required_actions_unverified,
        }


@dataclass(frozen=True, slots=True)
class TrialRoundComparisonSource:
    sequence: int
    trial_round_global_id: UUID
    trial_round_optimistic_version: int
    trial_round_snapshot_hash: str
    trial_plan_revision: TrialExactReference
    input_lock_revision: TrialExactReference | None
    actual_revision: TrialExactReference | None
    sample_revisions: tuple[TrialExactReference, ...]
    cavity_results: tuple[TrialCavityResultTip, ...]
    defect_tips: tuple[TrialDefectTip, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence", _positive(self.sequence, "sources.sequence"))
        object.__setattr__(
            self,
            "trial_round_global_id",
            _uuid(self.trial_round_global_id, "sources.trialRoundGlobalId"),
        )
        object.__setattr__(
            self,
            "trial_round_optimistic_version",
            _positive(
                self.trial_round_optimistic_version,
                "sources.trialRoundOptimisticVersion",
            ),
        )
        object.__setattr__(
            self,
            "trial_round_snapshot_hash",
            _hash(self.trial_round_snapshot_hash, "sources.trialRoundSnapshotHash"),
        )
        if not isinstance(self.trial_plan_revision, TrialExactReference):
            raise _problem("sources.trialPlanRevision", _("Select an exact Trial revision."))
        for fieldname in ("input_lock_revision", "actual_revision"):
            value = getattr(self, fieldname)
            if value is not None and not isinstance(value, TrialExactReference):
                raise _problem(_camel(fieldname), _("Select an exact Trial revision."))
        samples = _typed_tuple(
            self.sample_revisions,
            TrialExactReference,
            "sources.sampleRevisions",
            minimum=0,
            maximum=1_000,
        )
        _unique((value.global_id for value in samples), "sources.sampleRevisions")
        object.__setattr__(
            self,
            "sample_revisions",
            tuple(sorted(samples, key=lambda value: str(value.global_id))),
        )
        cavities = _typed_tuple(
            self.cavity_results,
            TrialCavityResultTip,
            "sources.cavityResults",
            minimum=0,
            maximum=1_000,
        )
        _unique((value.cavity_global_id for value in cavities), "sources.cavityResults")
        object.__setattr__(
            self,
            "cavity_results",
            tuple(sorted(cavities, key=lambda value: str(value.cavity_global_id))),
        )
        defects = _typed_tuple(
            self.defect_tips,
            TrialDefectTip,
            "sources.defects",
            minimum=0,
            maximum=10_000,
        )
        _unique((value.defect_global_id for value in defects), "sources.defects")
        object.__setattr__(
            self,
            "defect_tips",
            tuple(sorted(defects, key=lambda value: str(value.defect_global_id))),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "trialRoundOptimisticVersion": self.trial_round_optimistic_version,
            "trialRoundSnapshotHash": self.trial_round_snapshot_hash,
            "trialPlanRevision": self.trial_plan_revision.snapshot_payload(),
            "inputLockRevision": (
                self.input_lock_revision.snapshot_payload()
                if self.input_lock_revision
                else None
            ),
            "actualRevision": (
                self.actual_revision.snapshot_payload() if self.actual_revision else None
            ),
            "sampleRevisions": [value.snapshot_payload() for value in self.sample_revisions],
            "cavityResults": [value.snapshot_payload() for value in self.cavity_results],
            "defects": [value.snapshot_payload() for value in self.defect_tips],
        }


@dataclass(frozen=True, slots=True)
class TrialInputComparisonCell:
    trial_round_global_id: UUID
    canonical_value: str | None
    source_revision: TrialExactReference | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "trial_round_global_id",
            _uuid(self.trial_round_global_id, "inputRows.cells.trialRoundGlobalId"),
        )
        object.__setattr__(
            self,
            "canonical_value",
            _optional_text(self.canonical_value, "inputRows.cells.canonicalValue", 2_000),
        )
        if self.source_revision is not None and not isinstance(
            self.source_revision,
            TrialExactReference,
        ):
            raise _problem("inputRows.cells.sourceRevision", _("Select an exact Trial revision."))
        if self.canonical_value is not None and self.source_revision is None:
            raise _problem(
                "inputRows.cells.sourceRevision",
                _("A comparison value requires its exact source revision."),
            )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "canonicalValue": self.canonical_value,
            "sourceRevision": (
                self.source_revision.snapshot_payload() if self.source_revision else None
            ),
        }


@dataclass(frozen=True, slots=True)
class TrialInputComparisonRow:
    semantic_key: str
    cells: tuple[TrialInputComparisonCell, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "semantic_key", _key(self.semantic_key, "inputRows.semanticKey"))
        cells = _typed_tuple(
            self.cells,
            TrialInputComparisonCell,
            "inputRows.cells",
            minimum=2,
            maximum=100,
        )
        _unique((value.trial_round_global_id for value in cells), "inputRows.cells")
        object.__setattr__(self, "cells", cells)

    @property
    def change_state(self) -> TrialInputChangeState:
        first = self.cells[0].canonical_value
        last = self.cells[-1].canonical_value
        if first is None and last is not None:
            return TrialInputChangeState.ADDED
        if first is not None and last is None:
            return TrialInputChangeState.REMOVED
        if all(value.canonical_value == first for value in self.cells):
            return TrialInputChangeState.SAME
        return TrialInputChangeState.CHANGED

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "semanticKey": self.semantic_key,
            "changeState": self.change_state.value,
            "cells": [value.snapshot_payload() for value in self.cells],
        }


@dataclass(frozen=True, slots=True)
class TrialMetricComparisonCell:
    trial_round_global_id: UUID
    state: TrialComparisonCellState
    value: str | None
    unit: str | None
    lower_limit: str | None
    upper_limit: str | None
    source_revision: TrialExactReference | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "trial_round_global_id",
            _uuid(self.trial_round_global_id, "metricRows.cells.trialRoundGlobalId"),
        )
        _enum(self.state, TrialComparisonCellState, "metricRows.cells.state")
        object.__setattr__(self, "unit", _optional_text(self.unit, "metricRows.cells.unit", 32))
        for fieldname in ("value", "lower_limit", "upper_limit"):
            object.__setattr__(
                self,
                fieldname,
                _optional_decimal(getattr(self, fieldname), f"metricRows.cells.{_camel(fieldname)}"),
            )
        if (self.lower_limit is None) != (self.upper_limit is None):
            raise _problem(
                "metricRows.cells.lowerLimit",
                _("Enter both specification limits, or leave both empty."),
            )
        if self.lower_limit is not None and Decimal(self.lower_limit) > Decimal(self.upper_limit or "0"):
            raise _problem(
                "metricRows.cells.upperLimit",
                _("The upper limit must not be lower than the lower limit."),
            )
        if self.state is TrialComparisonCellState.MEASURED:
            if self.value is None or self.unit is None or self.source_revision is None:
                raise _problem(
                    "metricRows.cells.value",
                    _("A measured comparison value requires its unit and exact source revision."),
                )
        elif self.value is not None:
            raise _problem(
                "metricRows.cells.value",
                _("A missing comparison value cannot contain a numeric value."),
            )
        if self.state is TrialComparisonCellState.UNAVAILABLE and self.source_revision is not None:
            raise _problem(
                "metricRows.cells.sourceRevision",
                _("An unavailable comparison value cannot claim a source revision."),
            )
        if self.source_revision is not None and not isinstance(
            self.source_revision,
            TrialExactReference,
        ):
            raise _problem("metricRows.cells.sourceRevision", _("Select an exact Trial revision."))

    @property
    def comparison_state(self) -> TrialComparisonState:
        if self.state is TrialComparisonCellState.UNAVAILABLE:
            return TrialComparisonState.UNAVAILABLE
        if self.state is TrialComparisonCellState.NOT_MEASURED:
            return TrialComparisonState.NOT_MEASURED
        if self.lower_limit is None:
            return TrialComparisonState.MEASURED
        value = Decimal(self.value or "0")
        if Decimal(self.lower_limit) <= value <= Decimal(self.upper_limit or "0"):
            return TrialComparisonState.WITHIN_SPEC
        return TrialComparisonState.OUT_OF_SPEC

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "state": self.state.value,
            "value": self.value,
            "unit": self.unit,
            "lowerLimit": self.lower_limit,
            "upperLimit": self.upper_limit,
            "comparisonState": self.comparison_state.value,
            "sourceRevision": (
                self.source_revision.snapshot_payload() if self.source_revision else None
            ),
        }


@dataclass(frozen=True, slots=True)
class TrialMetricComparisonRow:
    metric_kind: TrialComparisonMetricKind
    metric_key: str
    cavity_global_id: UUID | None
    cells: tuple[TrialMetricComparisonCell, ...]

    def __post_init__(self) -> None:
        _enum(self.metric_kind, TrialComparisonMetricKind, "metricRows.metricKind")
        object.__setattr__(self, "metric_key", _key(self.metric_key, "metricRows.metricKey"))
        object.__setattr__(
            self,
            "cavity_global_id",
            _optional_uuid(self.cavity_global_id, "metricRows.cavityGlobalId"),
        )
        cells = _typed_tuple(
            self.cells,
            TrialMetricComparisonCell,
            "metricRows.cells",
            minimum=2,
            maximum=100,
        )
        _unique((value.trial_round_global_id for value in cells), "metricRows.cells")
        object.__setattr__(self, "cells", cells)
        unavailable_dimension = (
            self.metric_kind is TrialComparisonMetricKind.DIMENSION
            and self.metric_key == "unavailable"
            and self.cavity_global_id is None
            and all(value.state is TrialComparisonCellState.UNAVAILABLE for value in cells)
        )
        if (
            self.metric_kind is TrialComparisonMetricKind.DIMENSION
            and self.cavity_global_id is None
            and not unavailable_dimension
        ) or (
            self.metric_kind is not TrialComparisonMetricKind.DIMENSION
            and self.cavity_global_id is not None
        ):
            raise _problem(
                "metricRows.cavityGlobalId",
                _("Only dimension comparisons require one exact cavity identity."),
            )

    @property
    def unit_state(self) -> TrialComparisonUnitState:
        measured = [value for value in self.cells if value.state is TrialComparisonCellState.MEASURED]
        if not measured:
            return TrialComparisonUnitState.UNAVAILABLE
        if len({value.unit for value in measured}) > 1:
            return TrialComparisonUnitState.UNIT_MISMATCH
        return TrialComparisonUnitState.COMPARABLE

    @property
    def deltas(self) -> tuple[str | None, ...]:
        if self.unit_state is not TrialComparisonUnitState.COMPARABLE:
            return tuple(None for _ in self.cells)
        result: list[str | None] = []
        previous: Decimal | None = None
        for cell in self.cells:
            if cell.state is not TrialComparisonCellState.MEASURED:
                result.append(None)
                previous = None
                continue
            current = Decimal(cell.value or "0")
            result.append(None if previous is None else _decimal_text(current - previous))
            previous = current
        return tuple(result)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "metricKind": self.metric_kind.value,
            "metricKey": self.metric_key,
            "cavityGlobalId": str(self.cavity_global_id) if self.cavity_global_id else None,
            "unitState": self.unit_state.value,
            "cells": [
                {**cell.snapshot_payload(), "deltaFromPrevious": delta}
                for cell, delta in zip(self.cells, self.deltas, strict=True)
            ],
        }


@dataclass(frozen=True, slots=True)
class TrialRoundComparisonSnapshot:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_plan_global_id: UUID
    target_round_global_id: UUID
    policy_revision: TrialExactReference
    sources: tuple[TrialRoundComparisonSource, ...]
    input_rows: tuple[TrialInputComparisonRow, ...]
    metric_rows: tuple[TrialMetricComparisonRow, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "project_global_id",
            "trial_plan_global_id",
            "target_round_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        if not isinstance(self.policy_revision, TrialExactReference):
            raise _problem("policyRevision", _("Select an exact Trial revision."))
        sources = _typed_tuple(
            self.sources,
            TrialRoundComparisonSource,
            "sources",
            minimum=2,
            maximum=100,
        )
        if [value.sequence for value in sources] != list(range(1, len(sources) + 1)):
            raise _problem("sources.sequence", _("Comparison source sequences must be consecutive."))
        _unique((value.trial_round_global_id for value in sources), "sources")
        if sources[-1].trial_round_global_id != self.target_round_global_id:
            raise _problem(
                "targetRoundGlobalId",
                _("The comparison target must be the final exact Round source."),
            )
        object.__setattr__(self, "sources", sources)
        expected_rounds = tuple(value.trial_round_global_id for value in sources)
        input_rows = _typed_tuple(
            self.input_rows,
            TrialInputComparisonRow,
            "inputRows",
            minimum=1,
            maximum=2_000,
        )
        _unique((value.semantic_key for value in input_rows), "inputRows")
        for row in input_rows:
            if tuple(cell.trial_round_global_id for cell in row.cells) != expected_rounds:
                raise _problem(
                    "inputRows.cells",
                    _("Comparison cells must follow the exact Round source order."),
                )
        object.__setattr__(
            self,
            "input_rows",
            tuple(sorted(input_rows, key=lambda value: value.semantic_key)),
        )
        metric_rows = _typed_tuple(
            self.metric_rows,
            TrialMetricComparisonRow,
            "metricRows",
            minimum=len(TrialComparisonMetricKind),
            maximum=10_000,
        )
        _unique(
            (
                (
                    value.metric_kind,
                    value.metric_key,
                    value.cavity_global_id,
                )
                for value in metric_rows
            ),
            "metricRows",
        )
        if {value.metric_kind for value in metric_rows} != set(TrialComparisonMetricKind):
            raise _problem(
                "metricRows",
                _("Represent parameter, dimension, cycle time and yield comparison truth."),
            )
        for row in metric_rows:
            if tuple(cell.trial_round_global_id for cell in row.cells) != expected_rounds:
                raise _problem(
                    "metricRows.cells",
                    _("Comparison cells must follow the exact Round source order."),
                )
        object.__setattr__(
            self,
            "metric_rows",
            tuple(
                sorted(
                    metric_rows,
                    key=lambda value: (
                        value.metric_kind.value,
                        str(value.cavity_global_id or ""),
                        value.metric_key,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial Round comparison snapshot hash does not match."),
        )

    @property
    def defect_trends(self) -> tuple[tuple[UUID, TrialDefectTrendState], ...]:
        defect_ids = sorted(
            {
                value.defect_global_id
                for source in self.sources
                for value in source.defect_tips
            },
            key=str,
        )
        result: list[tuple[UUID, TrialDefectTrendState]] = []
        for defect_id in defect_ids:
            observations = [
                next(
                    (value for value in source.defect_tips if value.defect_global_id == defect_id),
                    None,
                )
                for source in self.sources
            ]
            first_index = next(index for index, value in enumerate(observations) if value)
            latest = next(value for value in reversed(observations) if value)
            if latest.state is ToolingDefectState.REOPENED:
                state = TrialDefectTrendState.REOPENED
            elif latest.state is ToolingDefectState.CLOSED:
                state = TrialDefectTrendState.RESOLVED
            elif first_index > 0:
                state = TrialDefectTrendState.NEW
            else:
                state = TrialDefectTrendState.CONTINUED
            result.append((defect_id, state))
        return tuple(result)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialPlanGlobalId": str(self.trial_plan_global_id),
            "targetRoundGlobalId": str(self.target_round_global_id),
            "policyRevision": self.policy_revision.snapshot_payload(),
            "sources": [value.snapshot_payload() for value in self.sources],
            "inputRows": [value.snapshot_payload() for value in self.input_rows],
            "metricRows": [value.snapshot_payload() for value in self.metric_rows],
            "defectTrends": [
                {"defectGlobalId": str(global_id), "state": state.value}
                for global_id, state in self.defect_trends
            ],
            "formalErpQuality": "unavailable",
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class TrialReviewReferenceRevision:
    global_id: UUID
    reference_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    comparison_snapshot: TrialExactReference
    reference_kind: TrialReviewReferenceKind
    reference_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    part_revision: TrialExactReference
    tooling_master_global_id: UUID
    tooling_revision: TrialExactReference
    tooling_set: TrialExactReference
    file_revision: TrialExactReference
    effective_from: date | None
    effective_to: date | None
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "reference_global_id",
            "project_global_id",
            "trial_round_global_id",
            "tooling_master_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        for fieldname in (
            "comparison_snapshot",
            "part_revision",
            "tooling_revision",
            "tooling_set",
            "file_revision",
        ):
            if not isinstance(getattr(self, fieldname), TrialExactReference):
                raise _problem(_camel(fieldname), _("Select an exact Trial revision."))
        _enum(self.reference_kind, TrialReviewReferenceKind, "referenceKind")
        object.__setattr__(
            self,
            "reference_version",
            _positive(self.reference_version, "referenceVersion"),
        )
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
        )
        _require_predecessor(
            self.reference_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        object.__setattr__(self, "effective_from", _optional_date(self.effective_from, "effectiveFrom"))
        object.__setattr__(self, "effective_to", _optional_date(self.effective_to, "effectiveTo"))
        if self.effective_to and not self.effective_from:
            raise _problem("effectiveFrom", _("Enter the effectivity start date."))
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise _problem("effectiveTo", _("The effectivity end cannot precede the start."))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 1_000))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial review reference snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "referenceGlobalId": str(self.reference_global_id),
                "referenceVersion": self.reference_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "referenceGlobalId": str(self.reference_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "comparisonSnapshot": self.comparison_snapshot.snapshot_payload(),
            "referenceKind": self.reference_kind.value,
            "referenceVersion": self.reference_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "partRevision": self.part_revision.snapshot_payload(),
            "toolingMasterGlobalId": str(self.tooling_master_global_id),
            "toolingRevision": self.tooling_revision.snapshot_payload(),
            "toolingSet": self.tooling_set.snapshot_payload(),
            "fileRevision": self.file_revision.snapshot_payload(),
            "effectiveFrom": self.effective_from.isoformat() if self.effective_from else None,
            "effectiveTo": self.effective_to.isoformat() if self.effective_to else None,
            "approvalAuthority": "unavailable",
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


def validate_review_reference_successor(
    predecessor: TrialReviewReferenceRevision,
    successor: TrialReviewReferenceRevision,
) -> None:
    stable_fields = (
        "reference_global_id",
        "tenant_id",
        "project_global_id",
        "trial_round_global_id",
        "comparison_snapshot",
        "reference_kind",
        "part_revision",
        "tooling_master_global_id",
        "tooling_revision",
        "tooling_set",
    )
    if (
        any(getattr(predecessor, name) != getattr(successor, name) for name in stable_fields)
        or successor.reference_version != predecessor.reference_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial review reference revision."),
        )


@dataclass(frozen=True, slots=True)
class TrialConclusionBlocker:
    code: TrialConclusionBlockerCode
    source_key: str

    def __post_init__(self) -> None:
        _enum(self.code, TrialConclusionBlockerCode, "blockers.code")
        object.__setattr__(self, "source_key", _key(self.source_key, "blockers.sourceKey"))

    def snapshot_payload(self) -> dict[str, object]:
        return {"code": self.code.value, "sourceKey": self.source_key}


def derive_conclusion_blockers(
    policy: TrialConclusionPolicyVersion,
    comparison: TrialRoundComparisonSnapshot,
    references: Sequence[TrialReviewReferenceRevision],
    conclusion_code: TrialConclusionCode,
) -> tuple[TrialConclusionBlocker, ...]:
    if (
        policy.tenant_id != comparison.tenant_id
        or policy.project_global_id != comparison.project_global_id
        or policy.trial_plan_global_id != comparison.trial_plan_global_id
        or comparison.policy_revision.global_id != policy.global_id
        or comparison.policy_revision.snapshot_hash != policy.snapshot_hash
    ):
        raise _problem("policyRevision", _("Select the exact published Trial conclusion policy."))
    _enum(conclusion_code, TrialConclusionCode, "conclusionCode")
    if conclusion_code not in policy.allowed_conclusion_codes:
        raise _problem(
            "conclusionCode",
            _("Select a conclusion code allowed by the exact policy."),
        )
    target = comparison.sources[-1]
    blockers: list[TrialConclusionBlocker] = []
    if target.input_lock_revision is None:
        blockers.append(
            TrialConclusionBlocker(
                TrialConclusionBlockerCode.MISSING_INPUT_LOCK,
                "target_round",
            )
        )
    if target.actual_revision is None:
        blockers.append(
            TrialConclusionBlocker(TrialConclusionBlockerCode.MISSING_ACTUAL, "target_round")
        )
    metric_rows = {
        (value.metric_kind, value.metric_key, value.cavity_global_id): value
        for value in comparison.metric_rows
    }
    for key in policy.required_parameter_keys:
        row = metric_rows.get((TrialComparisonMetricKind.PARAMETER, key, None))
        if row is None or row.cells[-1].state is not TrialComparisonCellState.MEASURED:
            blockers.append(
                TrialConclusionBlocker(
                    TrialConclusionBlockerCode.REQUIRED_PARAMETER_NOT_MEASURED,
                    key,
                )
            )
    if policy.require_cavity_results and not target.cavity_results:
        blockers.append(
            TrialConclusionBlocker(
                TrialConclusionBlockerCode.MISSING_CAVITY_RESULT,
                "target_round",
            )
        )
    for key in policy.required_dimension_keys:
        try:
            cavity_text, metric_key = key.split(":", 1)
            cavity_id = UUID(cavity_text)
        except (ValueError, AttributeError) as error:
            raise _problem(
                "requiredDimensionKeys",
                _("Use an exact cavity global ID and characteristic key."),
            ) from error
        row = metric_rows.get((TrialComparisonMetricKind.DIMENSION, metric_key, cavity_id))
        if row is None or row.cells[-1].state is not TrialComparisonCellState.MEASURED:
            blockers.append(
                TrialConclusionBlocker(
                    TrialConclusionBlockerCode.REQUIRED_DIMENSION_NOT_MEASURED,
                    key,
                )
            )
    if policy.block_on_open_blocking_defects:
        blockers.extend(
            TrialConclusionBlocker(
                TrialConclusionBlockerCode.OPEN_BLOCKING_DEFECT,
                str(value.defect_global_id),
            )
            for value in target.defect_tips
            if value.blocking and value.state is not ToolingDefectState.CLOSED
        )
    if policy.block_on_unverified_required_actions:
        blockers.extend(
            TrialConclusionBlocker(
                TrialConclusionBlockerCode.REQUIRED_ACTION_NOT_VERIFIED,
                str(value.defect_global_id),
            )
            for value in target.defect_tips
            if value.required_actions_unverified > 0
        )
    reference_kinds = {
        value.reference_kind
        for value in references
        if value.tenant_id == comparison.tenant_id
        and value.project_global_id == comparison.project_global_id
        and value.trial_round_global_id == comparison.target_round_global_id
        and value.comparison_snapshot.global_id == comparison.global_id
        and value.comparison_snapshot.snapshot_hash == comparison.snapshot_hash
    }
    for kind in policy.required_reference_kinds:
        if kind not in reference_kinds:
            blockers.append(
                TrialConclusionBlocker(
                    TrialConclusionBlockerCode.REQUIRED_REVIEW_REFERENCE_UNAVAILABLE,
                    kind.value,
                )
            )
    if conclusion_code in policy.out_of_spec_blocking_codes:
        blockers.extend(
            TrialConclusionBlocker(
                TrialConclusionBlockerCode.OUT_OF_SPEC_BLOCKING,
                (
                    f"{value.cavity_global_id}:{value.metric_key}"
                    if value.cavity_global_id
                    else value.metric_key
                ),
            )
            for value in comparison.metric_rows
            if value.cells[-1].comparison_state is TrialComparisonState.OUT_OF_SPEC
        )
    unique = {(value.code, value.source_key): value for value in blockers}
    return tuple(sorted(unique.values(), key=lambda value: (value.code.value, value.source_key)))


def build_one_page_summary_input(
    comparison: TrialRoundComparisonSnapshot,
    references: Sequence[TrialReviewReferenceRevision],
    conclusion_code: TrialConclusionCode,
    conclusion_state: TrialConclusionRevisionState,
) -> dict[str, object]:
    input_counts = {value.value: 0 for value in TrialInputChangeState}
    for row in comparison.input_rows:
        input_counts[row.change_state.value] += 1
    defect_counts = {value.value: 0 for value in TrialDefectTrendState}
    for _, state in comparison.defect_trends:
        defect_counts[state.value] += 1
    target = comparison.target_round_global_id

    def metric_state(kind: TrialComparisonMetricKind) -> str:
        rows = [value for value in comparison.metric_rows if value.metric_kind is kind]
        if not rows:
            return TrialComparisonState.UNAVAILABLE.value
        states = {value.cells[-1].comparison_state for value in rows}
        if TrialComparisonState.OUT_OF_SPEC in states:
            return TrialComparisonState.OUT_OF_SPEC.value
        if TrialComparisonState.WITHIN_SPEC in states:
            return TrialComparisonState.WITHIN_SPEC.value
        if TrialComparisonState.MEASURED in states:
            return TrialComparisonState.MEASURED.value
        if TrialComparisonState.NOT_MEASURED in states:
            return TrialComparisonState.NOT_MEASURED.value
        return TrialComparisonState.UNAVAILABLE.value

    exact_references = sorted(
        (
            {
                "globalId": str(value.global_id),
                "snapshotHash": value.snapshot_hash,
                "referenceKind": value.reference_kind.value,
            }
            for value in references
        ),
        key=lambda value: (value["referenceKind"], value["globalId"]),
    )
    return {
        "schemaVersion": TRIAL_SCHEMA_VERSION,
        "comparisonSnapshot": {
            "globalId": str(comparison.global_id),
            "snapshotHash": comparison.snapshot_hash,
        },
        "rounds": [
            {
                "globalId": str(value.trial_round_global_id),
                "snapshotHash": value.trial_round_snapshot_hash,
            }
            for value in comparison.sources
        ],
        "targetRoundGlobalId": str(target),
        "inputChangeCounts": input_counts,
        "metricRowHashes": [sha256_json(value.snapshot_payload()) for value in comparison.metric_rows],
        "defectTrendCounts": defect_counts,
        "reviewReferences": exact_references,
        "cycleTimeState": metric_state(TrialComparisonMetricKind.CYCLE_TIME),
        "yieldState": metric_state(TrialComparisonMetricKind.YIELD),
        "formalErpQuality": "unavailable",
        "conclusionCode": conclusion_code.value,
        "conclusionState": conclusion_state.value,
        "externalEffects": {
            "nextWork": "proposal_only",
            "gate": "unavailable",
            "npiReadiness": "unavailable",
            "toolingLifecycle": "unavailable",
        },
    }


@dataclass(frozen=True, slots=True)
class TrialConclusionRevision:
    global_id: UUID
    conclusion_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_round_global_id: UUID
    trial_round_optimistic_version: int
    trial_round_snapshot_hash: str
    conclusion_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    state: TrialConclusionRevisionState
    conclusion_code: TrialConclusionCode
    policy_revision: TrialExactReference
    comparison_snapshot: TrialExactReference
    review_references: tuple[TrialExactReference, ...]
    blockers: tuple[TrialConclusionBlocker, ...]
    summary_input: dict[str, object]
    proposed_next_work: tuple[str, ...]
    proposed_gate_effect: str
    proposed_npi_effect: str
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in (
            "global_id",
            "conclusion_global_id",
            "project_global_id",
            "trial_round_global_id",
            "request_id",
        ):
            object.__setattr__(self, fieldname, _uuid(getattr(self, fieldname), _camel(fieldname)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(
            self,
            "trial_round_optimistic_version",
            _positive(self.trial_round_optimistic_version, "trialRoundOptimisticVersion"),
        )
        object.__setattr__(
            self,
            "trial_round_snapshot_hash",
            _hash(self.trial_round_snapshot_hash, "trialRoundSnapshotHash"),
        )
        object.__setattr__(
            self,
            "conclusion_version",
            _positive(self.conclusion_version, "conclusionVersion"),
        )
        object.__setattr__(
            self,
            "predecessor_global_id",
            _optional_uuid(self.predecessor_global_id, "predecessorGlobalId"),
        )
        object.__setattr__(
            self,
            "predecessor_snapshot_hash",
            _optional_hash(self.predecessor_snapshot_hash, "predecessorSnapshotHash"),
        )
        _require_predecessor(
            self.conclusion_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
            "predecessorGlobalId",
        )
        _enum(self.state, TrialConclusionRevisionState, "state")
        _enum(self.conclusion_code, TrialConclusionCode, "conclusionCode")
        if self.conclusion_version == 1 and self.state is not TrialConclusionRevisionState.SUBMITTED:
            raise _problem("state", _("The first Trial conclusion revision must be submitted."))
        for fieldname in ("policy_revision", "comparison_snapshot"):
            if not isinstance(getattr(self, fieldname), TrialExactReference):
                raise _problem(_camel(fieldname), _("Select an exact Trial revision."))
        references = _typed_tuple(
            self.review_references,
            TrialExactReference,
            "reviewReferences",
            minimum=1,
            maximum=100,
        )
        _unique((value.global_id for value in references), "reviewReferences")
        object.__setattr__(
            self,
            "review_references",
            tuple(sorted(references, key=lambda value: str(value.global_id))),
        )
        blockers = _typed_tuple(
            self.blockers,
            TrialConclusionBlocker,
            "blockers",
            minimum=0,
            maximum=10_000,
        )
        _unique(((value.code, value.source_key) for value in blockers), "blockers")
        if blockers:
            raise _problem(
                "blockers",
                _("Resolve every critical Trial blocker before conclusion submission."),
            )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(
            self,
            "summary_input",
            _json_object(self.summary_input, "summaryInput"),
        )
        summary = _record(
            self.summary_input,
            "summaryInput",
            {
                "schemaVersion",
                "comparisonSnapshot",
                "rounds",
                "targetRoundGlobalId",
                "inputChangeCounts",
                "metricRowHashes",
                "defectTrendCounts",
                "reviewReferences",
                "cycleTimeState",
                "yieldState",
                "formalErpQuality",
                "conclusionCode",
                "conclusionState",
                "externalEffects",
            },
        )
        if (
            summary["schemaVersion"] != TRIAL_SCHEMA_VERSION
            or summary["comparisonSnapshot"]
            != self.comparison_snapshot.snapshot_payload()
            or summary["targetRoundGlobalId"] != str(self.trial_round_global_id)
            or summary["formalErpQuality"] != "unavailable"
            or summary["conclusionCode"] != self.conclusion_code.value
            or summary["conclusionState"] != self.state.value
            or summary["externalEffects"]
            != {
                "nextWork": "proposal_only",
                "gate": "unavailable",
                "npiReadiness": "unavailable",
                "toolingLifecycle": "unavailable",
            }
        ):
            raise _problem(
                "summaryInput",
                _("The one-page Trial summary input has invalid controlled fields."),
            )
        next_work = tuple(_text(value, "proposedNextWork", 1_000) for value in self.proposed_next_work)
        if not next_work or len(next_work) > 100:
            raise _problem("proposedNextWork", _("Enter the proposed next Trial work."))
        object.__setattr__(self, "proposed_next_work", next_work)
        object.__setattr__(
            self,
            "proposed_gate_effect",
            _text(self.proposed_gate_effect, "proposedGateEffect", 1_000),
        )
        object.__setattr__(
            self,
            "proposed_npi_effect",
            _text(self.proposed_npi_effect, "proposedNpiEffect", 1_000),
        )
        object.__setattr__(self, "reason", _text(self.reason, "reason", 2_000))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        _set_snapshot_hash(
            self,
            self.snapshot_hash,
            self.snapshot_payload(),
            _("The Trial conclusion snapshot hash does not match."),
        )

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "conclusionGlobalId": str(self.conclusion_global_id),
                "conclusionVersion": self.conclusion_version,
            }
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": TRIAL_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "conclusionGlobalId": str(self.conclusion_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "trialRoundOptimisticVersion": self.trial_round_optimistic_version,
            "trialRoundSnapshotHash": self.trial_round_snapshot_hash,
            "conclusionVersion": self.conclusion_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "state": self.state.value,
            "conclusionCode": self.conclusion_code.value,
            "policyRevision": self.policy_revision.snapshot_payload(),
            "comparisonSnapshot": self.comparison_snapshot.snapshot_payload(),
            "reviewReferences": [value.snapshot_payload() for value in self.review_references],
            "blockers": [value.snapshot_payload() for value in self.blockers],
            "summaryInput": self.summary_input,
            "proposedNextWork": list(self.proposed_next_work),
            "proposedGateEffect": self.proposed_gate_effect,
            "proposedNpiEffect": self.proposed_npi_effect,
            "externalEffects": {
                "nextWork": "proposal_only",
                "gate": "unavailable",
                "npiReadiness": "unavailable",
                "toolingLifecycle": "unavailable",
                "formalErpQuality": "unavailable",
                "customerSignature": "unavailable",
            },
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": _utc_text(self.created_at),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
        }


_CONCLUSION_TRANSITIONS: dict[
    TrialConclusionRevisionState,
    frozenset[TrialConclusionRevisionState],
] = {
    TrialConclusionRevisionState.SUBMITTED: frozenset(
        {
            TrialConclusionRevisionState.APPROVED,
            TrialConclusionRevisionState.REJECTED,
            TrialConclusionRevisionState.REOPENED,
        }
    ),
    TrialConclusionRevisionState.APPROVED: frozenset({TrialConclusionRevisionState.REOPENED}),
    TrialConclusionRevisionState.REJECTED: frozenset({TrialConclusionRevisionState.REOPENED}),
    TrialConclusionRevisionState.REOPENED: frozenset({TrialConclusionRevisionState.SUBMITTED}),
}


def validate_conclusion_successor(
    predecessor: TrialConclusionRevision,
    successor: TrialConclusionRevision,
) -> None:
    if (
        predecessor.conclusion_global_id != successor.conclusion_global_id
        or predecessor.tenant_id != successor.tenant_id
        or predecessor.project_global_id != successor.project_global_id
        or predecessor.trial_round_global_id != successor.trial_round_global_id
        or successor.conclusion_version != predecessor.conclusion_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
        or successor.state not in _CONCLUSION_TRANSITIONS[predecessor.state]
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Trial conclusion revision and transition."),
        )
    if successor.state is not TrialConclusionRevisionState.SUBMITTED:
        if (
            successor.trial_round_optimistic_version
            != predecessor.trial_round_optimistic_version + 1
            or successor.trial_round_snapshot_hash
            == predecessor.trial_round_snapshot_hash
        ):
            raise _problem(
                "trialRoundOptimisticVersion",
                _("Select the exact current Trial conclusion revision and transition."),
            )
        stable = (
            "conclusion_code",
            "policy_revision",
            "comparison_snapshot",
            "review_references",
            "blockers",
            "proposed_next_work",
            "proposed_gate_effect",
            "proposed_npi_effect",
        )
        if any(getattr(predecessor, name) != getattr(successor, name) for name in stable):
            raise _problem(
                "comparisonSnapshot",
                _("A Trial conclusion decision or reopen must retain the submitted sources."),
            )


def validate_conclusion_sources(
    policy: TrialConclusionPolicyVersion,
    comparison: TrialRoundComparisonSnapshot,
    references: Sequence[TrialReviewReferenceRevision],
    conclusion: TrialConclusionRevision,
) -> None:
    if any(
        value.tenant_id != comparison.tenant_id
        or value.project_global_id != comparison.project_global_id
        or value.trial_round_global_id != comparison.target_round_global_id
        or value.comparison_snapshot
        != TrialExactReference(comparison.global_id, comparison.snapshot_hash)
        for value in references
    ) or len({value.reference_global_id for value in references}) != len(references):
        raise _problem(
            "reviewReferences",
            _("Trial review references must match the exact comparison scope."),
        )
    expected_references = tuple(
        sorted(
            (TrialExactReference(value.global_id, value.snapshot_hash) for value in references),
            key=lambda value: str(value.global_id),
        )
    )
    if (
        conclusion.tenant_id != comparison.tenant_id
        or conclusion.project_global_id != comparison.project_global_id
        or conclusion.trial_round_global_id != comparison.target_round_global_id
        or conclusion.policy_revision != TrialExactReference(policy.global_id, policy.snapshot_hash)
        or conclusion.comparison_snapshot
        != TrialExactReference(comparison.global_id, comparison.snapshot_hash)
        or conclusion.review_references != expected_references
    ):
        raise _problem(
            "comparisonSnapshot",
            _("The Trial conclusion sources do not match the exact review snapshots."),
        )
    blockers = derive_conclusion_blockers(
        policy,
        comparison,
        references,
        conclusion.conclusion_code,
    )
    if blockers != conclusion.blockers:
        raise _problem("blockers", _("Trial conclusion blockers do not match server truth."))
    expected_summary = build_one_page_summary_input(
        comparison,
        references,
        conclusion.conclusion_code,
        conclusion.state,
    )
    if conclusion.summary_input != expected_summary:
        raise _problem(
            "summaryInput",
            _("The one-page Trial summary input does not match the exact snapshots."),
        )


def policy_from_snapshot(value: object) -> TrialConclusionPolicyVersion:
    record = _record(value, "policySnapshot", _POLICY_KEYS)
    _schema_version(record["schemaVersion"])
    return TrialConclusionPolicyVersion(
        global_id=_uuid_text(record["globalId"], "globalId"),
        policy_global_id=_uuid_text(record["policyGlobalId"], "policyGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_plan_global_id=_uuid_text(record["trialPlanGlobalId"], "trialPlanGlobalId"),
        trial_plan_revision_global_id=_uuid_text(
            record["trialPlanRevisionGlobalId"],
            "trialPlanRevisionGlobalId",
        ),
        trial_plan_revision_snapshot_hash=record["trialPlanRevisionSnapshotHash"],
        policy_version=record["policyVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        required_parameter_keys=tuple(_sequence(record["requiredParameterKeys"], "requiredParameterKeys", 250)),
        required_dimension_keys=tuple(_sequence(record["requiredDimensionKeys"], "requiredDimensionKeys", 1_000)),
        required_reference_kinds=tuple(
            _enum_text(item, TrialReviewReferenceKind, "requiredReferenceKinds")
            for item in _sequence(record["requiredReferenceKinds"], "requiredReferenceKinds", 10)
        ),
        require_cavity_results=record["requireCavityResults"],
        block_on_open_blocking_defects=record["blockOnOpenBlockingDefects"],
        block_on_unverified_required_actions=record["blockOnUnverifiedRequiredActions"],
        allowed_conclusion_codes=tuple(
            _enum_text(item, TrialConclusionCode, "allowedConclusionCodes")
            for item in _sequence(record["allowedConclusionCodes"], "allowedConclusionCodes", 10)
        ),
        out_of_spec_blocking_codes=tuple(
            _enum_text(item, TrialConclusionCode, "outOfSpecBlockingCodes")
            for item in _sequence(record["outOfSpecBlockingCodes"], "outOfSpecBlockingCodes", 10)
        ),
        authority_bindings=tuple(
            _authority_binding_from_snapshot(item)
            for item in _sequence(record["authorityBindings"], "authorityBindings", 100)
        ),
        published_by_user_id=record["publishedByUserId"],
        published_at=_datetime_text(record["publishedAt"], "publishedAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def comparison_from_snapshot(value: object) -> TrialRoundComparisonSnapshot:
    record = _record(value, "comparisonSnapshot", _COMPARISON_KEYS)
    _schema_version(record["schemaVersion"])
    result = TrialRoundComparisonSnapshot(
        global_id=_uuid_text(record["globalId"], "globalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_plan_global_id=_uuid_text(record["trialPlanGlobalId"], "trialPlanGlobalId"),
        target_round_global_id=_uuid_text(record["targetRoundGlobalId"], "targetRoundGlobalId"),
        policy_revision=_reference_from_snapshot(record["policyRevision"], "policyRevision"),
        sources=tuple(
            _comparison_source_from_snapshot(item)
            for item in _sequence(record["sources"], "sources", 100)
        ),
        input_rows=tuple(
            _input_row_from_snapshot(item)
            for item in _sequence(record["inputRows"], "inputRows", 2_000)
        ),
        metric_rows=tuple(
            _metric_row_from_snapshot(item)
            for item in _sequence(record["metricRows"], "metricRows", 10_000)
        ),
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )
    if record["defectTrends"] != result.snapshot_payload()["defectTrends"]:
        raise _problem("defectTrends", _("Trial defect trends do not match exact source truth."))
    if record["formalErpQuality"] != "unavailable":
        raise _problem("formalErpQuality", _("Formal ERP quality is unavailable in this task."))
    return result


def review_reference_from_snapshot(value: object) -> TrialReviewReferenceRevision:
    record = _record(value, "referenceSnapshot", _REFERENCE_KEYS)
    _schema_version(record["schemaVersion"])
    if record["approvalAuthority"] != "unavailable":
        raise _problem(
            "approvalAuthority",
            _("Customer and production approval authority is unavailable in this task."),
        )
    return TrialReviewReferenceRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        reference_global_id=_uuid_text(record["referenceGlobalId"], "referenceGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        comparison_snapshot=_reference_from_snapshot(record["comparisonSnapshot"], "comparisonSnapshot"),
        reference_kind=_enum_text(record["referenceKind"], TrialReviewReferenceKind, "referenceKind"),
        reference_version=record["referenceVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        part_revision=_reference_from_snapshot(record["partRevision"], "partRevision"),
        tooling_master_global_id=_uuid_text(record["toolingMasterGlobalId"], "toolingMasterGlobalId"),
        tooling_revision=_reference_from_snapshot(record["toolingRevision"], "toolingRevision"),
        tooling_set=_reference_from_snapshot(record["toolingSet"], "toolingSet"),
        file_revision=_reference_from_snapshot(record["fileRevision"], "fileRevision"),
        effective_from=_optional_date_text(record["effectiveFrom"], "effectiveFrom"),
        effective_to=_optional_date_text(record["effectiveTo"], "effectiveTo"),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


def conclusion_from_snapshot(value: object) -> TrialConclusionRevision:
    record = _record(value, "conclusionSnapshot", _CONCLUSION_KEYS)
    _schema_version(record["schemaVersion"])
    expected_external = {
        "nextWork": "proposal_only",
        "gate": "unavailable",
        "npiReadiness": "unavailable",
        "toolingLifecycle": "unavailable",
        "formalErpQuality": "unavailable",
        "customerSignature": "unavailable",
    }
    if record["externalEffects"] != expected_external:
        raise _problem("externalEffects", _("Trial conclusion external effects are unavailable."))
    return TrialConclusionRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        conclusion_global_id=_uuid_text(record["conclusionGlobalId"], "conclusionGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        trial_round_optimistic_version=record["trialRoundOptimisticVersion"],
        trial_round_snapshot_hash=record["trialRoundSnapshotHash"],
        conclusion_version=record["conclusionVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        state=_enum_text(record["state"], TrialConclusionRevisionState, "state"),
        conclusion_code=_enum_text(record["conclusionCode"], TrialConclusionCode, "conclusionCode"),
        policy_revision=_reference_from_snapshot(record["policyRevision"], "policyRevision"),
        comparison_snapshot=_reference_from_snapshot(record["comparisonSnapshot"], "comparisonSnapshot"),
        review_references=tuple(
            _reference_from_snapshot(item, "reviewReferences")
            for item in _sequence(record["reviewReferences"], "reviewReferences", 100)
        ),
        blockers=tuple(
            _blocker_from_snapshot(item)
            for item in _sequence(record["blockers"], "blockers", 10_000)
        ),
        summary_input=record["summaryInput"],
        proposed_next_work=tuple(_sequence(record["proposedNextWork"], "proposedNextWork", 100)),
        proposed_gate_effect=record["proposedGateEffect"],
        proposed_npi_effect=record["proposedNpiEffect"],
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
    )


_POLICY_KEYS = {
    "schemaVersion", "globalId", "policyGlobalId", "tenantId",
    "projectGlobalId", "trialPlanGlobalId", "trialPlanRevisionGlobalId",
    "trialPlanRevisionSnapshotHash", "policyVersion", "predecessorGlobalId",
    "predecessorSnapshotHash", "requiredParameterKeys", "requiredDimensionKeys",
    "requiredReferenceKinds", "requireCavityResults",
    "blockOnOpenBlockingDefects", "blockOnUnverifiedRequiredActions",
    "allowedConclusionCodes", "outOfSpecBlockingCodes", "authorityBindings",
    "publishedByUserId", "publishedAt", "requestId", "traceId",
}
_COMPARISON_KEYS = {
    "schemaVersion", "globalId", "tenantId", "projectGlobalId",
    "trialPlanGlobalId", "targetRoundGlobalId", "policyRevision", "sources",
    "inputRows", "metricRows", "defectTrends", "formalErpQuality",
    "createdByUserId", "createdAt", "requestId", "traceId",
}
_REFERENCE_KEYS = {
    "schemaVersion", "globalId", "referenceGlobalId", "tenantId",
    "projectGlobalId", "trialRoundGlobalId", "comparisonSnapshot",
    "referenceKind", "referenceVersion", "predecessorGlobalId",
    "predecessorSnapshotHash", "partRevision", "toolingMasterGlobalId",
    "toolingRevision", "toolingSet", "fileRevision", "effectiveFrom",
    "effectiveTo", "approvalAuthority", "reason", "createdByUserId",
    "createdAt", "requestId", "traceId",
}
_CONCLUSION_KEYS = {
    "schemaVersion", "globalId", "conclusionGlobalId", "tenantId",
    "projectGlobalId", "trialRoundGlobalId", "trialRoundOptimisticVersion",
    "trialRoundSnapshotHash", "conclusionVersion", "predecessorGlobalId",
    "predecessorSnapshotHash", "state", "conclusionCode", "policyRevision",
    "comparisonSnapshot", "reviewReferences", "blockers", "summaryInput",
    "proposedNextWork", "proposedGateEffect", "proposedNpiEffect",
    "externalEffects", "reason", "createdByUserId", "createdAt", "requestId",
    "traceId",
}


def _authority_binding_from_snapshot(value: object) -> TrialPolicyAuthorityBinding:
    record = _record(value, "authorityBindings", {"member", "capabilities"})
    return TrialPolicyAuthorityBinding(
        member=_member_from_snapshot(record["member"], "authorityBindings.member"),
        capabilities=tuple(
            _enum_text(item, TrialConclusionCapability, "authorityBindings.capabilities")
            for item in _sequence(record["capabilities"], "authorityBindings.capabilities", 3)
        ),
    )


def _comparison_source_from_snapshot(value: object) -> TrialRoundComparisonSource:
    record = _record(
        value,
        "sources",
        {
            "sequence", "trialRoundGlobalId", "trialRoundOptimisticVersion",
            "trialRoundSnapshotHash", "trialPlanRevision", "inputLockRevision",
            "actualRevision", "sampleRevisions", "cavityResults", "defects",
        },
    )
    return TrialRoundComparisonSource(
        sequence=record["sequence"],
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "sources.trialRoundGlobalId"),
        trial_round_optimistic_version=record["trialRoundOptimisticVersion"],
        trial_round_snapshot_hash=record["trialRoundSnapshotHash"],
        trial_plan_revision=_reference_from_snapshot(record["trialPlanRevision"], "sources.trialPlanRevision"),
        input_lock_revision=(
            None if record["inputLockRevision"] is None
            else _reference_from_snapshot(record["inputLockRevision"], "sources.inputLockRevision")
        ),
        actual_revision=(
            None if record["actualRevision"] is None
            else _reference_from_snapshot(record["actualRevision"], "sources.actualRevision")
        ),
        sample_revisions=tuple(
            _reference_from_snapshot(item, "sources.sampleRevisions")
            for item in _sequence(record["sampleRevisions"], "sources.sampleRevisions", 1_000)
        ),
        cavity_results=tuple(
            _cavity_tip_from_snapshot(item)
            for item in _sequence(record["cavityResults"], "sources.cavityResults", 1_000)
        ),
        defect_tips=tuple(
            _defect_tip_from_snapshot(item)
            for item in _sequence(record["defects"], "sources.defects", 10_000)
        ),
    )


def _cavity_tip_from_snapshot(value: object) -> TrialCavityResultTip:
    record = _record(value, "cavityResults", {"cavityGlobalId", "revision"})
    return TrialCavityResultTip(
        cavity_global_id=_uuid_text(record["cavityGlobalId"], "cavityResults.cavityGlobalId"),
        revision=_reference_from_snapshot(record["revision"], "cavityResults.revision"),
    )


def _defect_tip_from_snapshot(value: object) -> TrialDefectTip:
    record = _record(
        value,
        "defects",
        {
            "defectGlobalId", "sourceKind", "revision", "state", "blocking",
            "requiredActionsUnverified",
        },
    )
    return TrialDefectTip(
        defect_global_id=_uuid_text(record["defectGlobalId"], "defects.defectGlobalId"),
        source_kind=_enum_text(record["sourceKind"], TrialDefectSourceKind, "defects.sourceKind"),
        revision=_reference_from_snapshot(record["revision"], "defects.revision"),
        state=_enum_text(record["state"], ToolingDefectState, "defects.state"),
        blocking=record["blocking"],
        required_actions_unverified=record["requiredActionsUnverified"],
    )


def _input_row_from_snapshot(value: object) -> TrialInputComparisonRow:
    record = _record(value, "inputRows", {"semanticKey", "changeState", "cells"})
    result = TrialInputComparisonRow(
        semantic_key=record["semanticKey"],
        cells=tuple(
            _input_cell_from_snapshot(item)
            for item in _sequence(record["cells"], "inputRows.cells", 100)
        ),
    )
    if record["changeState"] != result.change_state.value:
        raise _problem("inputRows.changeState", _("The input change state does not match."))
    return result


def _input_cell_from_snapshot(value: object) -> TrialInputComparisonCell:
    record = _record(
        value,
        "inputRows.cells",
        {"trialRoundGlobalId", "canonicalValue", "sourceRevision"},
    )
    return TrialInputComparisonCell(
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "inputRows.cells.trialRoundGlobalId"),
        canonical_value=record["canonicalValue"],
        source_revision=(
            None if record["sourceRevision"] is None
            else _reference_from_snapshot(record["sourceRevision"], "inputRows.cells.sourceRevision")
        ),
    )


def _metric_row_from_snapshot(value: object) -> TrialMetricComparisonRow:
    record = _record(
        value,
        "metricRows",
        {"metricKind", "metricKey", "cavityGlobalId", "unitState", "cells"},
    )
    cells: list[TrialMetricComparisonCell] = []
    supplied_deltas: list[object] = []
    for item in _sequence(record["cells"], "metricRows.cells", 100):
        cell_record = _record(
            item,
            "metricRows.cells",
            {
                "trialRoundGlobalId", "state", "value", "unit", "lowerLimit",
                "upperLimit", "comparisonState", "sourceRevision",
                "deltaFromPrevious",
            },
        )
        cell = TrialMetricComparisonCell(
            trial_round_global_id=_uuid_text(cell_record["trialRoundGlobalId"], "metricRows.cells.trialRoundGlobalId"),
            state=_enum_text(cell_record["state"], TrialComparisonCellState, "metricRows.cells.state"),
            value=cell_record["value"],
            unit=cell_record["unit"],
            lower_limit=cell_record["lowerLimit"],
            upper_limit=cell_record["upperLimit"],
            source_revision=(
                None if cell_record["sourceRevision"] is None
                else _reference_from_snapshot(cell_record["sourceRevision"], "metricRows.cells.sourceRevision")
            ),
        )
        if cell_record["comparisonState"] != cell.comparison_state.value:
            raise _problem("metricRows.cells.comparisonState", _("The metric comparison state does not match."))
        cells.append(cell)
        supplied_deltas.append(cell_record["deltaFromPrevious"])
    result = TrialMetricComparisonRow(
        metric_kind=_enum_text(record["metricKind"], TrialComparisonMetricKind, "metricRows.metricKind"),
        metric_key=record["metricKey"],
        cavity_global_id=_optional_uuid_text(record["cavityGlobalId"], "metricRows.cavityGlobalId"),
        cells=tuple(cells),
    )
    if record["unitState"] != result.unit_state.value or tuple(supplied_deltas) != result.deltas:
        raise _problem("metricRows.unitState", _("The metric comparison delta does not match."))
    return result


def _reference_from_snapshot(value: object, path: str) -> TrialExactReference:
    record = _record(value, path, {"globalId", "snapshotHash"})
    return TrialExactReference(
        global_id=_uuid_text(record["globalId"], f"{path}.globalId"),
        snapshot_hash=record["snapshotHash"],
    )


def _blocker_from_snapshot(value: object) -> TrialConclusionBlocker:
    record = _record(value, "blockers", {"code", "sourceKey"})
    return TrialConclusionBlocker(
        code=_enum_text(record["code"], TrialConclusionBlockerCode, "blockers.code"),
        source_key=record["sourceKey"],
    )


def _member_from_snapshot(value: object, path: str) -> ProjectMemberResponsibility:
    record = _record(value, path, {"globalId", "userId", "optimisticVersion"})
    return ProjectMemberResponsibility(
        global_id=_uuid_text(record["globalId"], f"{path}.globalId"),
        user_id=record["userId"],
        optimistic_version=record["optimisticVersion"],
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
    result = value.strip()
    if len(result) > maximum:
        raise _problem(path, _("Enter a shorter value."))
    return result


def _optional_text(value: object, path: str, maximum: int) -> str | None:
    return None if value is None else _text(value, path, maximum)


def _key(value: object, path: str) -> str:
    result = _text(value, path, 256)
    if not result[0].isalnum() or any(
        character
        not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:@/-"
        for character in result
    ):
        raise _problem(path, _("Enter a valid value."))
    return result


def _actor(value: object, path: str) -> str:
    result = _text(value, path, 254).casefold()
    if any(character.isspace() or ord(character) < 32 for character in result):
        raise _problem(path, _("Enter a valid user ID."))
    return result


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _nonnegative(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise _problem(path, _("Enter a non-negative integer."))
    return value


def _hash(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


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


def _optional_date(value: object, path: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise _problem(path, _("Enter a valid date."))
    return value


def _optional_date_text(value: object, path: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid date."))
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _problem(path, _("Enter a valid date.")) from error


def _optional_decimal(value: object, path: str) -> str | None:
    if value is None:
        return None
    try:
        result = Decimal(_text(value, path, 64))
    except InvalidOperation as error:
        raise _problem(path, _("Enter a valid numeric value.")) from error
    if not result.is_finite():
        raise _problem(path, _("Enter a valid numeric value."))
    return _decimal_text(result)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _enum(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    if not isinstance(value, enum_type):
        raise _problem(path, _("Select a supported value."))
    return value


def _enum_text(value: object, enum_type: type[StrEnum], path: str) -> StrEnum:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error


def _typed_tuple(
    values: Sequence[object],
    expected_type: type,
    path: str,
    *,
    minimum: int,
    maximum: int,
) -> tuple:
    result = tuple(values)
    if not minimum <= len(result) <= maximum or any(
        not isinstance(value, expected_type) for value in result
    ):
        raise _problem(path, _("Enter a valid bounded list."))
    return result


def _key_tuple(values: Sequence[object], path: str, maximum: int) -> tuple[str, ...]:
    result = tuple(_key(value, path) for value in values)
    if len(result) > maximum:
        raise _problem(path, _("Enter a valid bounded list."))
    _unique(result, path)
    return tuple(sorted(result))


def _unique(values: Iterable[object], path: str) -> None:
    result = tuple(values)
    if len(result) != len(set(result)):
        raise _problem(path, _("Values must be unique."))


def _require_predecessor(
    version: int,
    predecessor_global_id: UUID | None,
    predecessor_snapshot_hash: str | None,
    path: str,
) -> None:
    if version == 1:
        if predecessor_global_id is not None or predecessor_snapshot_hash is not None:
            raise _problem(path, _("The first version cannot have a predecessor."))
    elif predecessor_global_id is None or predecessor_snapshot_hash is None:
        raise _problem(path, _("A successor requires its exact predecessor."))


def _set_snapshot_hash(
    value: object,
    supplied_hash: str,
    payload: dict[str, object],
    message: str,
) -> None:
    expected = sha256_json(payload)
    if supplied_hash and _hash(supplied_hash, "snapshotHash") != expected:
        raise _problem("snapshotHash", message)
    object.__setattr__(value, "snapshot_hash", expected)


def _record(value: object, path: str, expected_keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise _problem(path, _("Enter a valid closed snapshot."))
    return value


def _sequence(value: object, path: str, maximum: int) -> list[object]:
    if not isinstance(value, list) or len(value) > maximum:
        raise _problem(path, _("Enter a valid bounded list."))
    return value


def _json_object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _problem(path, _("Enter a valid closed snapshot."))
    try:
        return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Enter a valid closed snapshot.")) from error


def _schema_version(value: object) -> None:
    if value != TRIAL_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Use the supported Trial schema version."))


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)
