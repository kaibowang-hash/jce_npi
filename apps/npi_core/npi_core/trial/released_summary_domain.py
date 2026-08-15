from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from npi_core.controlled_print.domain import MAX_SOURCE_SNAPSHOT_BYTES
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed
from npi_core.trial.domain import sha256_json
from npi_core.trial.review_domain import (
    TrialConclusionCode,
    TrialConclusionRevisionState,
)

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


RELEASED_TRIAL_SUMMARY_SCHEMA_VERSION = "npi.released_trial_summary.v1"
RELEASED_TRIAL_SUMMARY_PROJECTION_SCHEMA_VERSION = (
    "npi.released_trial_summary.presentation.v1"
)
RELEASED_TRIAL_SUMMARY_REDACTION_SCHEMA_VERSION = (
    "npi.released_trial_summary.redaction.v1"
)

_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")


class ReleasedTrialSummarySourceKind(StrEnum):
    TRIAL_PLAN_REVISION = "trial_plan_revision"
    TRIAL_ROUND = "trial_round"
    TRIAL_INPUT_LOCK_REVISION = "trial_input_lock_revision"
    TRIAL_ACTUAL_REVISION = "trial_actual_revision"
    TRIAL_SAMPLE_BATCH_REVISION = "trial_sample_batch_revision"
    TRIAL_CAVITY_RESULT_REVISION = "trial_cavity_result_revision"
    TOOLING_DEFECT_REVISION = "tooling_defect_revision"
    TRIAL_DEFECT_REVISION = "trial_defect_revision"
    TRIAL_DEFECT_VERIFICATION_REVISION = "trial_defect_verification_revision"
    TRIAL_ROUND_COMPARISON_SNAPSHOT = "trial_round_comparison_snapshot"
    TRIAL_REVIEW_REFERENCE_REVISION = "trial_review_reference_revision"
    TRIAL_CONCLUSION_REVISION = "trial_conclusion_revision"


class ReleasedTrialSummaryFactValueState(StrEnum):
    MEASURED = "measured"
    NOT_MEASURED = "not_measured"
    UNAVAILABLE = "unavailable"
    SATISFIED = "satisfied"
    FAILED = "failed"
    OPEN = "open"
    CLOSED = "closed"
    INFORMATIONAL = "informational"


class ReleasedTrialSummaryUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            404,
            "RELEASED_TRIAL_SUMMARY_UNAVAILABLE",
            _("The Released Trial Summary is unavailable."),
        )


class ReleasedTrialSummaryConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "RELEASED_TRIAL_SUMMARY_CONFLICT",
            _("The Released Trial Summary source was changed by another user."),
        )


class ReleasedTrialSummaryRoutesDisabled(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "RELEASED_TRIAL_SUMMARY_ROUTES_DISABLED",
            _("The Released Trial Summary workspace is temporarily unavailable."),
            _("The summary routes are disabled while a reviewed forward fix is applied."),
            retryable=True,
        )


_SOURCE_ORDER = {kind: index for index, kind in enumerate(ReleasedTrialSummarySourceKind)}
_SINGLETON_SOURCE_KINDS = frozenset(
    {
        ReleasedTrialSummarySourceKind.TRIAL_PLAN_REVISION,
        ReleasedTrialSummarySourceKind.TRIAL_ROUND,
        ReleasedTrialSummarySourceKind.TRIAL_ACTUAL_REVISION,
        ReleasedTrialSummarySourceKind.TRIAL_ROUND_COMPARISON_SNAPSHOT,
        ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION,
    }
)
_OPTIONAL_SINGLETON_SOURCE_KINDS = frozenset(
    {ReleasedTrialSummarySourceKind.TRIAL_INPUT_LOCK_REVISION}
)

_REDACTION_RULES = (
    "exclude_credentials",
    "exclude_file_content",
    "exclude_private_locators",
    "exclude_provider_payloads",
    "exclude_unapproved_external_projection",
)
_EXCLUDED_SENSITIVE_FIELD_CLASSES = (
    "authorization_headers",
    "credentials",
    "file_content",
    "private_paths",
    "private_urls",
    "production_hostnames",
    "provider_payloads",
    "secrets",
    "session_cookies",
)
_FORBIDDEN_KEY_PARTS = (
    "authorization",
    "credential",
    "cookie",
    "filecontent",
    "hostname",
    "password",
    "privatepath",
    "privateurl",
    "providerpayload",
    "secret",
    "token",
)
_FORBIDDEN_VALUE_MARKERS = (
    "/private/files/",
    "authorization:",
    "bearer ",
    "cookie=",
    "file://",
    "http://",
    "https://",
)
_PRESENTATION_FACT_KEYS = frozenset(
    {
        "actualParameters",
        "blockers",
        "cavityResults",
        "comparison",
        "controlledReferences",
        "defects",
        "inputChanges",
        "samples",
    }
)
_PRESENTATION_FACT_FIELDS = frozenset(
    {"factKey", "valueState", "value", "unit", "sourceReferences"}
)


@dataclass(frozen=True, slots=True)
class ReleasedTrialSummarySourceReference:
    kind: ReleasedTrialSummarySourceKind
    global_id: UUID
    source_version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReleasedTrialSummarySourceKind):
            raise _problem("sourceManifest.kind", _("Select a supported summary source kind."))
        object.__setattr__(self, "global_id", _uuid(self.global_id, "sourceManifest.globalId"))
        object.__setattr__(
            self,
            "source_version",
            _positive(self.source_version, "sourceManifest.sourceVersion"),
        )
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "sourceManifest.snapshotHash"),
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "globalId": str(self.global_id),
            "sourceVersion": self.source_version,
            "snapshotHash": self.snapshot_hash,
        }


def build_released_trial_summary_redaction_manifest() -> dict[str, object]:
    return {
        "schemaVersion": RELEASED_TRIAL_SUMMARY_REDACTION_SCHEMA_VERSION,
        "appliedRuleCodes": list(_REDACTION_RULES),
        "excludedSensitiveFieldClasses": list(_EXCLUDED_SENSITIVE_FIELD_CLASSES),
        "externalProjection": "unavailable",
    }


def build_released_trial_summary_projection(
    *,
    project_global_id: UUID,
    trial_plan_global_id: UUID,
    trial_round_global_id: UUID,
    conclusion_revision: ReleasedTrialSummarySourceReference,
    conclusion_state: TrialConclusionRevisionState,
    conclusion_code: TrialConclusionCode,
    source_manifest: Sequence[ReleasedTrialSummarySourceReference],
    facts: Mapping[str, object],
) -> dict[str, object]:
    project_id = _uuid(project_global_id, "projectGlobalId")
    plan_id = _uuid(trial_plan_global_id, "trialPlanGlobalId")
    round_id = _uuid(trial_round_global_id, "trialRoundGlobalId")
    if (
        not isinstance(conclusion_revision, ReleasedTrialSummarySourceReference)
        or conclusion_revision.kind
        is not ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION
    ):
        raise _problem(
            "conclusionRevision",
            _("Select the exact decided Trial conclusion revision."),
        )
    state = _decided_state(conclusion_state)
    code = _conclusion_code(conclusion_code)
    manifest = _source_manifest(source_manifest)
    manifest_conclusion = next(
        item
        for item in manifest
        if item.kind is ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION
    )
    if conclusion_revision != manifest_conclusion:
        raise _problem(
            "conclusionRevision",
            _("Select the exact decided Trial conclusion revision."),
        )
    fact_record = _presentation_facts(facts, "facts", manifest)
    projection = {
        "schemaVersion": RELEASED_TRIAL_SUMMARY_PROJECTION_SCHEMA_VERSION,
        "projectGlobalId": str(project_id),
        "trialPlanGlobalId": str(plan_id),
        "trialRoundGlobalId": str(round_id),
        "conclusionRevision": conclusion_revision.snapshot_payload(),
        "conclusionState": state.value,
        "conclusionCode": code.value,
        "sourceManifest": [item.snapshot_payload() for item in manifest],
        "facts": fact_record,
        "externalEffects": _external_effects(),
    }
    _assert_sensitive_data_absent(projection)
    _bounded_json_object(projection, "presentationProjection")
    return projection


@dataclass(frozen=True, slots=True)
class ReleasedTrialSummaryRevision:
    global_id: UUID
    summary_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    trial_plan_global_id: UUID
    trial_round_global_id: UUID
    summary_version: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    trial_round_optimistic_version: int
    trial_round_snapshot_hash: str
    trial_plan_revision_global_id: UUID
    trial_plan_revision_snapshot_hash: str
    conclusion_revision_global_id: UUID
    conclusion_version: int
    conclusion_snapshot_hash: str
    conclusion_state: TrialConclusionRevisionState
    conclusion_code: TrialConclusionCode
    source_manifest: tuple[ReleasedTrialSummarySourceReference, ...]
    presentation_projection: Mapping[str, object]
    redaction_manifest: Mapping[str, object]
    reason: str
    created_by_user_id: str
    created_at: datetime
    request_id: UUID
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "global_id",
            "summary_global_id",
            "project_global_id",
            "trial_plan_global_id",
            "trial_round_global_id",
            "trial_plan_revision_global_id",
            "conclusion_revision_global_id",
            "request_id",
        ):
            object.__setattr__(self, name, _uuid(getattr(self, name), _camel(name)))
        object.__setattr__(self, "tenant_id", _key(self.tenant_id, "tenantId"))
        object.__setattr__(self, "summary_version", _positive(self.summary_version, "summaryVersion"))
        object.__setattr__(
            self,
            "trial_round_optimistic_version",
            _positive(self.trial_round_optimistic_version, "trialRoundOptimisticVersion"),
        )
        object.__setattr__(self, "conclusion_version", _positive(self.conclusion_version, "conclusionVersion"))
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
            self.summary_version,
            self.predecessor_global_id,
            self.predecessor_snapshot_hash,
        )
        for name in (
            "trial_round_snapshot_hash",
            "trial_plan_revision_snapshot_hash",
            "conclusion_snapshot_hash",
        ):
            object.__setattr__(self, name, _hash(getattr(self, name), _camel(name)))
        object.__setattr__(self, "conclusion_state", _decided_state(self.conclusion_state))
        object.__setattr__(self, "conclusion_code", _conclusion_code(self.conclusion_code))
        manifest = _source_manifest(self.source_manifest)
        object.__setattr__(self, "source_manifest", manifest)
        _validate_manifest_bindings(self, manifest)
        projection = _bounded_json_object(self.presentation_projection, "presentationProjection")
        _validate_projection(self, projection)
        object.__setattr__(self, "presentation_projection", _freeze_json(projection))
        redaction = _record(
            self.redaction_manifest,
            "redactionManifest",
            {
                "schemaVersion",
                "appliedRuleCodes",
                "excludedSensitiveFieldClasses",
                "externalProjection",
            },
        )
        if _plain_json(redaction) != build_released_trial_summary_redaction_manifest():
            raise _problem(
                "redactionManifest",
                _("The Released Trial Summary redaction rules cannot be changed."),
            )
        object.__setattr__(self, "redaction_manifest", _freeze_json(redaction))
        object.__setattr__(self, "reason", _text(self.reason, "reason", 2_000))
        object.__setattr__(
            self,
            "created_by_user_id",
            _actor(self.created_by_user_id, "createdByUserId"),
        )
        object.__setattr__(self, "created_at", _aware(self.created_at, "createdAt"))
        object.__setattr__(self, "trace_id", _key(self.trace_id, "traceId"))
        expected_hash = sha256_json(self.snapshot_payload())
        if self.snapshot_hash not in ("", expected_hash):
            raise _problem(
                "snapshotHash",
                _("The Released Trial Summary snapshot hash does not match."),
            )
        object.__setattr__(self, "snapshot_hash", expected_hash)

    @property
    def version_key_hash(self) -> str:
        return sha256_json(
            {
                "summaryGlobalId": str(self.summary_global_id),
                "summaryVersion": self.summary_version,
            }
        )

    @property
    def source_manifest_hash(self) -> str:
        return sha256_json([item.snapshot_payload() for item in self.source_manifest])

    @property
    def presentation_projection_hash(self) -> str:
        return sha256_json(_plain_json(self.presentation_projection))

    @property
    def redaction_manifest_hash(self) -> str:
        return sha256_json(_plain_json(self.redaction_manifest))

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": RELEASED_TRIAL_SUMMARY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "summaryGlobalId": str(self.summary_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "trialPlanGlobalId": str(self.trial_plan_global_id),
            "trialRoundGlobalId": str(self.trial_round_global_id),
            "summaryVersion": self.summary_version,
            "predecessorGlobalId": (
                str(self.predecessor_global_id) if self.predecessor_global_id else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "trialRoundOptimisticVersion": self.trial_round_optimistic_version,
            "trialRoundSnapshotHash": self.trial_round_snapshot_hash,
            "trialPlanRevisionGlobalId": str(self.trial_plan_revision_global_id),
            "trialPlanRevisionSnapshotHash": self.trial_plan_revision_snapshot_hash,
            "conclusionRevisionGlobalId": str(self.conclusion_revision_global_id),
            "conclusionVersion": self.conclusion_version,
            "conclusionSnapshotHash": self.conclusion_snapshot_hash,
            "conclusionState": self.conclusion_state.value,
            "conclusionCode": self.conclusion_code.value,
            "sourceManifest": [item.snapshot_payload() for item in self.source_manifest],
            "presentationProjection": _plain_json(self.presentation_projection),
            "redactionManifest": _plain_json(self.redaction_manifest),
            "reason": self.reason,
            "createdByUserId": self.created_by_user_id,
            "createdAt": self.created_at.isoformat().replace("+00:00", "Z"),
            "requestId": str(self.request_id),
            "traceId": self.trace_id,
            "versionKeyHash": self.version_key_hash,
            "sourceManifestHash": self.source_manifest_hash,
            "presentationProjectionHash": self.presentation_projection_hash,
            "redactionManifestHash": self.redaction_manifest_hash,
        }


def validate_released_trial_summary_successor(
    predecessor: ReleasedTrialSummaryRevision,
    successor: ReleasedTrialSummaryRevision,
) -> None:
    stable_fields = (
        "summary_global_id",
        "tenant_id",
        "project_global_id",
        "trial_plan_global_id",
        "trial_round_global_id",
    )
    if any(getattr(predecessor, name) != getattr(successor, name) for name in stable_fields):
        raise _problem(
            "summaryGlobalId",
            _("A Released Trial Summary successor must remain in the same summary stream."),
        )
    if (
        successor.summary_version != predecessor.summary_version + 1
        or successor.predecessor_global_id != predecessor.global_id
        or successor.predecessor_snapshot_hash != predecessor.snapshot_hash
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Select the exact current Released Trial Summary revision."),
        )
    if (
        successor.conclusion_revision_global_id == predecessor.conclusion_revision_global_id
        or successor.conclusion_version <= predecessor.conclusion_version
        or successor.conclusion_snapshot_hash == predecessor.conclusion_snapshot_hash
    ):
        raise _problem(
            "conclusionRevisionGlobalId",
            _("A summary successor requires a newly decided Trial conclusion."),
        )


def released_trial_summary_from_snapshot(value: object) -> ReleasedTrialSummaryRevision:
    record = _record(
        value,
        "releasedTrialSummary",
        {
            "schemaVersion",
            "globalId",
            "summaryGlobalId",
            "tenantId",
            "projectGlobalId",
            "trialPlanGlobalId",
            "trialRoundGlobalId",
            "summaryVersion",
            "predecessorGlobalId",
            "predecessorSnapshotHash",
            "trialRoundOptimisticVersion",
            "trialRoundSnapshotHash",
            "trialPlanRevisionGlobalId",
            "trialPlanRevisionSnapshotHash",
            "conclusionRevisionGlobalId",
            "conclusionVersion",
            "conclusionSnapshotHash",
            "conclusionState",
            "conclusionCode",
            "sourceManifest",
            "presentationProjection",
            "redactionManifest",
            "reason",
            "createdByUserId",
            "createdAt",
            "requestId",
            "traceId",
            "versionKeyHash",
            "sourceManifestHash",
            "presentationProjectionHash",
            "redactionManifestHash",
            "snapshotHash",
        },
    )
    if record["schemaVersion"] != RELEASED_TRIAL_SUMMARY_SCHEMA_VERSION:
        raise _problem("schemaVersion", _("Select a supported Released Trial Summary schema."))
    manifest = tuple(
        _source_reference_from_snapshot(item, index)
        for index, item in enumerate(_array(record["sourceManifest"], "sourceManifest"))
    )
    result = ReleasedTrialSummaryRevision(
        global_id=_uuid_text(record["globalId"], "globalId"),
        summary_global_id=_uuid_text(record["summaryGlobalId"], "summaryGlobalId"),
        tenant_id=record["tenantId"],
        project_global_id=_uuid_text(record["projectGlobalId"], "projectGlobalId"),
        trial_plan_global_id=_uuid_text(record["trialPlanGlobalId"], "trialPlanGlobalId"),
        trial_round_global_id=_uuid_text(record["trialRoundGlobalId"], "trialRoundGlobalId"),
        summary_version=record["summaryVersion"],
        predecessor_global_id=_optional_uuid_text(record["predecessorGlobalId"], "predecessorGlobalId"),
        predecessor_snapshot_hash=record["predecessorSnapshotHash"],
        trial_round_optimistic_version=record["trialRoundOptimisticVersion"],
        trial_round_snapshot_hash=record["trialRoundSnapshotHash"],
        trial_plan_revision_global_id=_uuid_text(
            record["trialPlanRevisionGlobalId"], "trialPlanRevisionGlobalId"
        ),
        trial_plan_revision_snapshot_hash=record["trialPlanRevisionSnapshotHash"],
        conclusion_revision_global_id=_uuid_text(
            record["conclusionRevisionGlobalId"], "conclusionRevisionGlobalId"
        ),
        conclusion_version=record["conclusionVersion"],
        conclusion_snapshot_hash=record["conclusionSnapshotHash"],
        conclusion_state=_enum_text(
            record["conclusionState"], TrialConclusionRevisionState, "conclusionState"
        ),
        conclusion_code=_enum_text(record["conclusionCode"], TrialConclusionCode, "conclusionCode"),
        source_manifest=manifest,
        presentation_projection=_record_any(record["presentationProjection"], "presentationProjection"),
        redaction_manifest=_record_any(record["redactionManifest"], "redactionManifest"),
        reason=record["reason"],
        created_by_user_id=record["createdByUserId"],
        created_at=_datetime_text(record["createdAt"], "createdAt"),
        request_id=_uuid_text(record["requestId"], "requestId"),
        trace_id=record["traceId"],
        snapshot_hash=record["snapshotHash"],
    )
    expected_derived = {
        "versionKeyHash": result.version_key_hash,
        "sourceManifestHash": result.source_manifest_hash,
        "presentationProjectionHash": result.presentation_projection_hash,
        "redactionManifestHash": result.redaction_manifest_hash,
    }
    for name, expected in expected_derived.items():
        if record[name] != expected:
            raise _problem(name, _("The Released Trial Summary derived hash does not match."))
    return result


def _source_reference_from_snapshot(
    value: object,
    index: int,
) -> ReleasedTrialSummarySourceReference:
    path = f"sourceManifest[{index}]"
    return _source_reference_from_payload(value, path)


def _source_reference_from_payload(
    value: object,
    path: str,
) -> ReleasedTrialSummarySourceReference:
    record = _record(value, path, {"kind", "globalId", "sourceVersion", "snapshotHash"})
    return ReleasedTrialSummarySourceReference(
        kind=_enum_text(record["kind"], ReleasedTrialSummarySourceKind, f"{path}.kind"),
        global_id=_uuid_text(record["globalId"], f"{path}.globalId"),
        source_version=record["sourceVersion"],
        snapshot_hash=record["snapshotHash"],
    )


def _source_manifest(
    values: Sequence[ReleasedTrialSummarySourceReference],
) -> tuple[ReleasedTrialSummarySourceReference, ...]:
    if isinstance(values, str | bytes | bytearray) or not isinstance(values, Sequence):
        raise _problem("sourceManifest", _("Enter a valid source manifest."))
    manifest = tuple(values)
    if len(manifest) < 6 or len(manifest) > 25_000:
        raise _problem("sourceManifest", _("Enter a complete bounded source manifest."))
    if not all(isinstance(value, ReleasedTrialSummarySourceReference) for value in manifest):
        raise _problem("sourceManifest", _("Enter exact summary source references."))
    identities = {(value.kind, value.global_id) for value in manifest}
    if len(identities) != len(manifest):
        raise _problem("sourceManifest", _("Summary source references must be unique."))
    expected_order = tuple(
        sorted(manifest, key=lambda value: (_SOURCE_ORDER[value.kind], str(value.global_id)))
    )
    if manifest != expected_order:
        raise _problem("sourceManifest", _("Summary source references must use canonical order."))
    counts = {kind: sum(value.kind is kind for value in manifest) for kind in ReleasedTrialSummarySourceKind}
    for kind in _SINGLETON_SOURCE_KINDS:
        if counts[kind] != 1:
            raise _problem("sourceManifest", _("The summary source manifest is incomplete."))
    for kind in _OPTIONAL_SINGLETON_SOURCE_KINDS:
        if counts[kind] > 1:
            raise _problem("sourceManifest", _("The summary source manifest contains duplicate truth."))
    if counts[ReleasedTrialSummarySourceKind.TRIAL_REVIEW_REFERENCE_REVISION] < 1:
        raise _problem("sourceManifest", _("Retain every exact Trial review reference."))
    return manifest


def _validate_manifest_bindings(
    summary: ReleasedTrialSummaryRevision,
    manifest: tuple[ReleasedTrialSummarySourceReference, ...],
) -> None:
    by_kind: dict[ReleasedTrialSummarySourceKind, list[ReleasedTrialSummarySourceReference]] = {}
    for source in manifest:
        by_kind.setdefault(source.kind, []).append(source)
    round_source = by_kind[ReleasedTrialSummarySourceKind.TRIAL_ROUND][0]
    plan_source = by_kind[ReleasedTrialSummarySourceKind.TRIAL_PLAN_REVISION][0]
    conclusion_source = by_kind[ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION][0]
    if (
        round_source.global_id != summary.trial_round_global_id
        or round_source.source_version != summary.trial_round_optimistic_version
        or round_source.snapshot_hash != summary.trial_round_snapshot_hash
    ):
        raise _problem("sourceManifest", _("The exact Trial Round source does not match the summary."))
    if (
        plan_source.global_id != summary.trial_plan_revision_global_id
        or plan_source.snapshot_hash != summary.trial_plan_revision_snapshot_hash
    ):
        raise _problem("sourceManifest", _("The exact Trial Plan source does not match the summary."))
    if (
        conclusion_source.global_id != summary.conclusion_revision_global_id
        or conclusion_source.source_version != summary.conclusion_version
        or conclusion_source.snapshot_hash != summary.conclusion_snapshot_hash
    ):
        raise _problem("sourceManifest", _("The exact Trial conclusion source does not match the summary."))


def _validate_projection(
    summary: ReleasedTrialSummaryRevision,
    projection: Mapping[str, object],
) -> None:
    record = _record(
        projection,
        "presentationProjection",
        {
            "schemaVersion",
            "projectGlobalId",
            "trialPlanGlobalId",
            "trialRoundGlobalId",
            "conclusionRevision",
            "conclusionState",
            "conclusionCode",
            "sourceManifest",
            "facts",
            "externalEffects",
        },
    )
    if record["schemaVersion"] != RELEASED_TRIAL_SUMMARY_PROJECTION_SCHEMA_VERSION:
        raise _problem("presentationProjection.schemaVersion", _("Select a supported summary presentation schema."))
    expected = {
        "projectGlobalId": str(summary.project_global_id),
        "trialPlanGlobalId": str(summary.trial_plan_global_id),
        "trialRoundGlobalId": str(summary.trial_round_global_id),
        "conclusionRevision": next(
            item.snapshot_payload()
            for item in summary.source_manifest
            if item.kind is ReleasedTrialSummarySourceKind.TRIAL_CONCLUSION_REVISION
        ),
        "conclusionState": summary.conclusion_state.value,
        "conclusionCode": summary.conclusion_code.value,
        "sourceManifest": [item.snapshot_payload() for item in summary.source_manifest],
        "externalEffects": _external_effects(),
    }
    for name, value in expected.items():
        if _plain_json(record[name]) != value:
            raise _problem(
                f"presentationProjection.{name}",
                _("The presentation projection does not match the exact summary sources."),
            )
    fact_record = _record(record["facts"], "presentationProjection.facts", _PRESENTATION_FACT_KEYS)
    normalized_facts = _presentation_facts(
        fact_record,
        "presentationProjection.facts",
        summary.source_manifest,
    )
    if _plain_json(fact_record) != normalized_facts:
        raise _problem(
            "presentationProjection.facts",
            _("The presentation projection does not match the exact summary sources."),
        )
    _assert_sensitive_data_absent(record)


def _presentation_facts(
    value: object,
    path: str,
    source_manifest: Sequence[ReleasedTrialSummarySourceReference],
) -> dict[str, list[dict[str, object]]]:
    record = _record(value, path, _PRESENTATION_FACT_KEYS)
    manifest_positions = {source: index for index, source in enumerate(source_manifest)}
    normalized: dict[str, list[dict[str, object]]] = {}
    for name in sorted(_PRESENTATION_FACT_KEYS):
        fact_path = f"{path}.{name}"
        items = _array(record[name], fact_path)
        if len(items) > 25_000:
            raise _problem(fact_path, _("The complete summary presentation is too large."))
        normalized[name] = [
            _presentation_fact(item, f"{fact_path}[{index}]", manifest_positions)
            for index, item in enumerate(items)
        ]
    return normalized


def _presentation_fact(
    value: object,
    path: str,
    manifest_positions: Mapping[ReleasedTrialSummarySourceReference, int],
) -> dict[str, object]:
    record = _record(value, path, _PRESENTATION_FACT_FIELDS)
    fact_key = _key(record["factKey"], f"{path}.factKey")
    value_state = _enum_text(
        record["valueState"],
        ReleasedTrialSummaryFactValueState,
        f"{path}.valueState",
    )
    fact_value = record["value"]
    if isinstance(fact_value, str):
        if len(fact_value) > 4_000:
            raise _problem(f"{path}.value", _("Enter a shorter value."))
    elif fact_value is not None and type(fact_value) not in {int, float, bool}:
        raise _problem(f"{path}.value", _("Enter a valid JSON value."))
    unit = record["unit"]
    if unit is not None:
        unit = _text(unit, f"{path}.unit", 64)
    source_values = _array(record["sourceReferences"], f"{path}.sourceReferences")
    if not 1 <= len(source_values) <= 100:
        raise _problem(
            f"{path}.sourceReferences",
            _("Enter a complete bounded source manifest."),
        )
    sources = tuple(
        _source_reference_from_payload(item, f"{path}.sourceReferences[{index}]")
        for index, item in enumerate(source_values)
    )
    if (
        len(set(sources)) != len(sources)
        or any(source not in manifest_positions for source in sources)
        or tuple(sorted(sources, key=manifest_positions.__getitem__)) != sources
    ):
        raise _problem(
            f"{path}.sourceReferences",
            _("The presentation projection does not match the exact summary sources."),
        )
    return {
        "factKey": fact_key,
        "valueState": value_state.value,
        "value": fact_value,
        "unit": unit,
        "sourceReferences": [source.snapshot_payload() for source in sources],
    }


def _external_effects() -> dict[str, str]:
    return {
        "customerApproval": "unavailable",
        "externalProjection": "unavailable",
        "formalSignature": "unavailable",
        "gateDecision": "unavailable",
        "productionAcceptance": "unavailable",
    }


def _assert_sensitive_data_absent(value: object, path: str = "presentationProjection") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise _problem(path, _("The summary presentation contains a forbidden sensitive field."))
            _assert_sensitive_data_absent(item, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, item in enumerate(value):
            _assert_sensitive_data_absent(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        candidate = value.casefold()
        if any(marker in candidate for marker in _FORBIDDEN_VALUE_MARKERS):
            raise _problem(path, _("The summary presentation contains a forbidden private locator."))


def _bounded_json_object(value: object, path: str) -> dict[str, object]:
    record = _record_any(value, path)
    plain = _plain_json(record)
    try:
        encoded = json.dumps(
            plain,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Enter a valid JSON value.")) from error
    if len(encoded) > MAX_SOURCE_SNAPSHOT_BYTES:
        raise _problem(path, _("The complete summary presentation is too large."))
    return plain


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(_freeze_json(item) for item in value)
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise _problem("value", _("Enter a valid JSON value."))


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_plain_json(item) for item in value]
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise _problem("value", _("Enter a valid JSON value."))


def _record(value: object, path: str, keys: set[str] | frozenset[str]) -> Mapping[str, object]:
    record = _record_any(value, path)
    if set(record) != set(keys):
        raise _problem(path, _("Enter the exact supported fields."))
    return record


def _record_any(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _problem(path, _("Enter a valid JSON object."))
    return value


def _array(value: object, path: str) -> Sequence[object]:
    if isinstance(value, str | bytes | bytearray) or not isinstance(value, Sequence):
        raise _problem(path, _("Enter a valid JSON array."))
    return value


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


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _problem(path, _("Enter a positive integer."))
    return value


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid SHA-256 hash."))
    return value


def _optional_hash(value: object, path: str) -> str | None:
    return None if value is None else _hash(value, path)


def _key(value: object, path: str) -> str:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid stable key."))
    return value


def _actor(value: object, path: str) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        raise _problem(path, _("Enter a valid user identity."))
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if not isinstance(value, str) or value != value.strip() or not value:
        raise _problem(path, _("Enter a valid value."))
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise _problem(path, _("Enter a shorter value."))
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


def _decided_state(value: object) -> TrialConclusionRevisionState:
    if value not in {
        TrialConclusionRevisionState.APPROVED,
        TrialConclusionRevisionState.REJECTED,
    }:
        raise _problem(
            "conclusionState",
            _("Only an approved or rejected Trial conclusion can be retained."),
        )
    return value


def _conclusion_code(value: object) -> TrialConclusionCode:
    if not isinstance(value, TrialConclusionCode):
        raise _problem("conclusionCode", _("Select a valid Trial conclusion code."))
    return value


def _enum_text(value: object, enum_type: type[StrEnum], path: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise _problem(path, _("Select a supported value.")) from error


def _require_predecessor(
    version: int,
    predecessor_global_id: UUID | None,
    predecessor_snapshot_hash: str | None,
) -> None:
    if (version == 1) != (
        predecessor_global_id is None and predecessor_snapshot_hash is None
    ):
        raise _problem(
            "predecessorGlobalId",
            _("Only the first summary revision may omit its exact predecessor."),
        )


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item.capitalize() for item in tail)
