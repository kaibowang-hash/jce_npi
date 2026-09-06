from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


RELEASED_SUMMARY_SCHEMA_VERSION = "npi.released_trial_summary.v1"
RELEASED_SUMMARY_PRESENTATION_SCHEMA_VERSION = (
    "npi.released_trial_summary.presentation.v1"
)
RELEASED_SUMMARY_REDACTION_SCHEMA_VERSION = (
    "npi.released_trial_summary.redaction.v1"
)

_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ReleasedSummaryProjectionContractError(ValueError):
    """Raised when the internal read-only seam is not exact and closed."""


class ReleasedSummarySourceState(StrEnum):
    CURRENT = "current"
    UNAVAILABLE = "unavailable"
    CONFLICT = "conflict"


class ExternalProjectionState(StrEnum):
    UNAVAILABLE = "unavailable"


class UnavailableReason(StrEnum):
    EXTERNAL_CONTRACT_HELD = "external_contract_held"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_CONFLICT = "source_conflict"


@dataclass(frozen=True, slots=True)
class ReleasedSummarySourceDescriptor:
    """Exact immutable P7-07 identity; contains no presentation or provider values."""

    project_global_id: UUID
    summary_revision_global_id: UUID
    summary_global_id: UUID
    trial_round_global_id: UUID
    summary_version: int
    snapshot_hash: str
    source_manifest_hash: str
    presentation_projection_hash: str
    redaction_manifest_hash: str
    schema_version: str = RELEASED_SUMMARY_SCHEMA_VERSION
    presentation_schema_version: str = RELEASED_SUMMARY_PRESENTATION_SCHEMA_VERSION
    redaction_schema_version: str = RELEASED_SUMMARY_REDACTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "project_global_id",
            "summary_revision_global_id",
            "summary_global_id",
            "trial_round_global_id",
        ):
            if not isinstance(getattr(self, name), UUID):
                raise ReleasedSummaryProjectionContractError(
                    f"{name} must be one exact UUID."
                )
        if type(self.summary_version) is not int or self.summary_version < 1:
            raise ReleasedSummaryProjectionContractError(
                "summary_version must be a positive whole number."
            )
        for name in (
            "snapshot_hash",
            "source_manifest_hash",
            "presentation_projection_hash",
            "redaction_manifest_hash",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
                raise ReleasedSummaryProjectionContractError(
                    f"{name} must be one lowercase SHA-256 value."
                )
        expected_schemas = {
            "schema_version": RELEASED_SUMMARY_SCHEMA_VERSION,
            "presentation_schema_version": RELEASED_SUMMARY_PRESENTATION_SCHEMA_VERSION,
            "redaction_schema_version": RELEASED_SUMMARY_REDACTION_SCHEMA_VERSION,
        }
        for name, expected in expected_schemas.items():
            if getattr(self, name) != expected:
                raise ReleasedSummaryProjectionContractError(
                    f"{name} does not match the retained P7-07 schema."
                )

    @property
    def fingerprint(self) -> str:
        payload = {
            "projectGlobalId": str(self.project_global_id),
            "redactionManifestHash": self.redaction_manifest_hash,
            "redactionSchemaVersion": self.redaction_schema_version,
            "schemaVersion": self.schema_version,
            "snapshotHash": self.snapshot_hash,
            "sourceManifestHash": self.source_manifest_hash,
            "summaryGlobalId": str(self.summary_global_id),
            "summaryRevisionGlobalId": str(self.summary_revision_global_id),
            "summaryVersion": self.summary_version,
            "presentationProjectionHash": self.presentation_projection_hash,
            "presentationSchemaVersion": self.presentation_schema_version,
            "trialRoundGlobalId": str(self.trial_round_global_id),
        }
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleasedSummaryProjectionResult:
    source_state: ReleasedSummarySourceState
    external_projection_state: ExternalProjectionState
    unavailable_reason: UnavailableReason
    trace_id: str
    source: ReleasedSummarySourceDescriptor | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_state, ReleasedSummarySourceState):
            raise ReleasedSummaryProjectionContractError(
                "Released summary source state is unsupported."
            )
        if self.external_projection_state is not ExternalProjectionState.UNAVAILABLE:
            raise ReleasedSummaryProjectionContractError(
                "External projection must remain explicitly unavailable."
            )
        if not isinstance(self.unavailable_reason, UnavailableReason):
            raise ReleasedSummaryProjectionContractError(
                "Released summary unavailable reason is unsupported."
            )
        if not isinstance(self.trace_id, str) or _TRACE_PATTERN.fullmatch(self.trace_id) is None:
            raise ReleasedSummaryProjectionContractError(
                "Released summary projection trace identity is invalid."
            )
        expected = {
            ReleasedSummarySourceState.CURRENT: UnavailableReason.EXTERNAL_CONTRACT_HELD,
            ReleasedSummarySourceState.UNAVAILABLE: UnavailableReason.SOURCE_UNAVAILABLE,
            ReleasedSummarySourceState.CONFLICT: UnavailableReason.SOURCE_CONFLICT,
        }[self.source_state]
        if self.unavailable_reason is not expected:
            raise ReleasedSummaryProjectionContractError(
                "Released summary state and unavailable reason do not match."
            )
        if self.source_state is ReleasedSummarySourceState.CURRENT:
            if not isinstance(self.source, ReleasedSummarySourceDescriptor):
                raise ReleasedSummaryProjectionContractError(
                    "A current source requires one exact immutable descriptor."
                )
        elif self.source is not None:
            raise ReleasedSummaryProjectionContractError(
                "Unavailable or conflicting source truth cannot carry a descriptor."
            )

    def safe_status(self) -> dict[str, str | None]:
        """Return structure-only status; never presentation values or target details."""

        return {
            "sourceState": self.source_state.value,
            "sourceFingerprint": self.source.fingerprint if self.source else None,
            "externalProjection": self.external_projection_state.value,
            "unavailableReasonCode": self.unavailable_reason.value,
            "traceId": self.trace_id,
        }
