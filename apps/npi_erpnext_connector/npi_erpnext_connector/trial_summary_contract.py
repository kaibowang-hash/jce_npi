from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

CONTRACT_VERSION = 1
SOURCE_SCHEMA_VERSION = "npi.released_trial_summary.erp_projection.v1"
PRESENTATION_SCHEMA_VERSION = "npi.released_trial_summary.presentation.v1"
OPERATION = "publish_released_trial_summary"
RECONCILE_OPERATION = "reconcile_released_trial_summary"
MAX_REQUEST_BYTES = 1_048_576
MAX_FACTS = 25_000

FACT_GROUPS = (
    "actualParameters",
    "blockers",
    "cavityResults",
    "comparison",
    "controlledReferences",
    "defects",
    "inputChanges",
    "samples",
)
VALUE_STATES = frozenset(
    {
        "measured",
        "not_measured",
        "unavailable",
        "satisfied",
        "failed",
        "open",
        "closed",
        "informational",
    }
)
CONCLUSION_STATES = frozenset({"approved", "rejected"})
CONCLUSION_CODES = frozenset(
    {
        "pass",
        "conditional_pass",
        "tooling_change",
        "design_change",
        "process_tuning",
        "material_change",
        "cancelled",
    }
)
EXTERNAL_EFFECTS = {
    "customerApproval": "unavailable",
    "externalProjection": "unavailable",
    "formalSignature": "unavailable",
    "gateDecision": "unavailable",
    "productionAcceptance": "unavailable",
}

_HASH = re.compile(r"^[a-f0-9]{64}$")
_ACTOR = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_CREATED_AT = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
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


class TrialSummaryContractError(ValueError):
    """Raised when a Trial Summary command is not exactly contract-shaped."""


@dataclass(frozen=True, slots=True)
class TrialSummaryFact:
    group: str
    fact_type: str
    fact_key: str
    value_state: str
    value: str | int | float | bool | None
    unit: str | None
    source_references: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class TrialSummaryCommand:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    actor_user_id: str
    projection_purpose: str
    formal_mp_acceptance: bool
    tenant_id: str
    project_global_id: str
    trial_plan_global_id: str
    trial_round_global_id: str
    summary_global_id: str
    summary_revision_global_id: str
    summary_version: int
    predecessor_global_id: str | None
    source_snapshot_hash: str
    source_manifest_hash: str
    presentation_projection_hash: str
    redaction_manifest_hash: str
    conclusion_state: str
    conclusion_code: str
    created_by_user_id: str
    created_at: str
    presentation_projection: Mapping[str, object]
    redaction_manifest: Mapping[str, object]
    facts: tuple[TrialSummaryFact, ...]
    raw: Mapping[str, object]

    @property
    def semantic_request_hash(self) -> str:
        value = dict(self.raw)
        value.pop("attemptGlobalId", None)
        value.pop("attemptNumber", None)
        return canonical_hash(value)


@dataclass(frozen=True, slots=True)
class TrialSummaryReconcileCommand:
    request_global_id: str
    attempt_global_id: str
    target_idempotency_key_hash: str
    source_hash: str


def decode_trial_summary_command(raw_body: bytes) -> TrialSummaryCommand:
    value = _decode(raw_body, "Trial Summary command")
    return parse_trial_summary_command(value)


def parse_trial_summary_command(value: object) -> TrialSummaryCommand:
    command = _closed(
        value,
        {
            "contractVersion",
            "operation",
            "requestGlobalId",
            "attemptGlobalId",
            "attemptNumber",
            "targetIdempotencyKeyHash",
            "sourceHash",
            "actorUserId",
            "source",
        },
        "Trial Summary command",
    )
    if command["contractVersion"] != CONTRACT_VERSION or command["operation"] != OPERATION:
        raise TrialSummaryContractError("Trial Summary command contract is unsupported.")
    request_id = _uuid(command["requestGlobalId"], "requestGlobalId")
    attempt_id = _uuid(command["attemptGlobalId"], "attemptGlobalId")
    attempt_number = _positive(command["attemptNumber"], "attemptNumber")
    idempotency_hash = _hash(
        command["targetIdempotencyKeyHash"], "targetIdempotencyKeyHash"
    )
    source_hash = _hash(command["sourceHash"], "sourceHash")
    actor = _actor(command["actorUserId"], "actorUserId")
    source = _closed(
        command["source"],
        {
            "schemaVersion",
            "projectionPurpose",
            "formalMpAcceptance",
            "tenantId",
            "projectGlobalId",
            "trialPlanGlobalId",
            "trialRoundGlobalId",
            "summaryGlobalId",
            "summaryRevisionGlobalId",
            "summaryVersion",
            "predecessorGlobalId",
            "sourceSnapshotHash",
            "sourceManifestHash",
            "presentationProjectionHash",
            "redactionManifestHash",
            "conclusionState",
            "conclusionCode",
            "createdByUserId",
            "createdAt",
            "presentationProjection",
            "redactionManifest",
        },
        "Trial Summary source",
    )
    if source["schemaVersion"] != SOURCE_SCHEMA_VERSION:
        raise TrialSummaryContractError("Trial Summary source contract is unsupported.")
    if (
        source["projectionPurpose"] != "erpnext_read_only_engineering_evidence"
        or source["formalMpAcceptance"] is not False
    ):
        raise TrialSummaryContractError("Trial Summary projection purpose is invalid.")
    tenant_id = _text(source["tenantId"], "tenantId", 128)
    project_id = _uuid(source["projectGlobalId"], "projectGlobalId")
    plan_id = _uuid(source["trialPlanGlobalId"], "trialPlanGlobalId")
    round_id = _uuid(source["trialRoundGlobalId"], "trialRoundGlobalId")
    summary_id = _uuid(source["summaryGlobalId"], "summaryGlobalId")
    revision_id = _uuid(source["summaryRevisionGlobalId"], "summaryRevisionGlobalId")
    version = _positive(source["summaryVersion"], "summaryVersion")
    predecessor = _optional_uuid(source["predecessorGlobalId"], "predecessorGlobalId")
    if (version == 1) != (predecessor is None):
        raise TrialSummaryContractError("Trial Summary predecessor is invalid.")
    snapshot_hash = _hash(source["sourceSnapshotHash"], "sourceSnapshotHash")
    manifest_hash = _hash(source["sourceManifestHash"], "sourceManifestHash")
    projection_hash = _hash(
        source["presentationProjectionHash"], "presentationProjectionHash"
    )
    redaction_hash = _hash(source["redactionManifestHash"], "redactionManifestHash")
    conclusion_state = _enum(source["conclusionState"], CONCLUSION_STATES, "conclusionState")
    conclusion_code = _enum(source["conclusionCode"], CONCLUSION_CODES, "conclusionCode")
    created_by = _actor(source["createdByUserId"], "createdByUserId")
    created_at = source["createdAt"]
    if not isinstance(created_at, str) or _CREATED_AT.fullmatch(created_at) is None:
        raise TrialSummaryContractError("createdAt is invalid.")

    projection, facts = _presentation_projection(
        source["presentationProjection"],
        project_id=project_id,
        plan_id=plan_id,
        round_id=round_id,
        conclusion_state=conclusion_state,
        conclusion_code=conclusion_code,
    )
    redaction = _redaction_manifest(source["redactionManifest"])
    if canonical_hash(projection["sourceManifest"]) != manifest_hash:
        raise TrialSummaryContractError("Trial Summary source manifest hash does not match.")
    if canonical_hash(projection) != projection_hash:
        raise TrialSummaryContractError("Trial Summary projection hash does not match.")
    if canonical_hash(redaction) != redaction_hash:
        raise TrialSummaryContractError("Trial Summary redaction hash does not match.")
    source_payload = dict(source)
    if canonical_hash(source_payload) != source_hash:
        raise TrialSummaryContractError("Trial Summary source hash does not match.")
    expected_idempotency = canonical_hash(
        {"operation": OPERATION, "summaryRevisionGlobalId": revision_id}
    )
    if idempotency_hash != expected_idempotency:
        raise TrialSummaryContractError("Trial Summary idempotency identity does not match.")
    _assert_sensitive_data_absent(source)
    return TrialSummaryCommand(
        request_id,
        attempt_id,
        attempt_number,
        idempotency_hash,
        source_hash,
        actor,
        "erpnext_read_only_engineering_evidence",
        False,
        tenant_id,
        project_id,
        plan_id,
        round_id,
        summary_id,
        revision_id,
        version,
        predecessor,
        snapshot_hash,
        manifest_hash,
        projection_hash,
        redaction_hash,
        conclusion_state,
        conclusion_code,
        created_by,
        created_at,
        projection,
        redaction,
        facts,
        command,
    )


def decode_reconcile_command(raw_body: bytes) -> TrialSummaryReconcileCommand:
    value = _closed(
        _decode(raw_body, "Trial Summary reconciliation command"),
        {
            "contractVersion",
            "operation",
            "requestGlobalId",
            "attemptGlobalId",
            "targetIdempotencyKeyHash",
            "sourceHash",
        },
        "Trial Summary reconciliation command",
    )
    if value["contractVersion"] != CONTRACT_VERSION or value["operation"] != RECONCILE_OPERATION:
        raise TrialSummaryContractError("Trial Summary reconciliation contract is unsupported.")
    return TrialSummaryReconcileCommand(
        _uuid(value["requestGlobalId"], "requestGlobalId"),
        _uuid(value["attemptGlobalId"], "attemptGlobalId"),
        _hash(value["targetIdempotencyKeyHash"], "targetIdempotencyKeyHash"),
        _hash(value["sourceHash"], "sourceHash"),
    )


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def fact_type(fact_key: str, group: str | None = None) -> str:
    if fact_key.startswith("toolingDefect."):
        return "tooling_action" if ".action." in fact_key else "tooling_defect"
    if fact_key.startswith("defectVerification."):
        return "defect_verification"
    if fact_key.startswith("defect."):
        return "trial_action" if ".action." in fact_key else "trial_defect"
    if fact_key.startswith("actual.parameter."):
        return "actual_parameter"
    if fact_key.startswith("cavity."):
        return "cavity_result"
    if fact_key.startswith("comparison."):
        return "comparison"
    if fact_key.startswith("reference."):
        return "controlled_reference"
    if fact_key.startswith("blocker."):
        return "blocker"
    if fact_key.startswith("sample."):
        return "sample"
    if fact_key.startswith("input."):
        return "input_change"
    return {
        "actualParameters": "actual_parameter",
        "blockers": "blocker",
        "cavityResults": "cavity_result",
        "comparison": "comparison",
        "controlledReferences": "controlled_reference",
        "inputChanges": "input_change",
        "samples": "sample",
    }.get(group, "other")


def _decode(raw_body: bytes, label: str) -> object:
    if not isinstance(raw_body, bytes) or not raw_body or len(raw_body) > MAX_REQUEST_BYTES:
        raise TrialSummaryContractError(f"{label} body is invalid.")
    try:
        return json.loads(raw_body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrialSummaryContractError(f"{label} JSON is invalid.") from error


def _presentation_projection(
    value: object,
    *,
    project_id: str,
    plan_id: str,
    round_id: str,
    conclusion_state: str,
    conclusion_code: str,
) -> tuple[Mapping[str, object], tuple[TrialSummaryFact, ...]]:
    projection = _closed(
        value,
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
        "Trial Summary presentation projection",
    )
    if (
        projection["schemaVersion"] != PRESENTATION_SCHEMA_VERSION
        or projection["projectGlobalId"] != project_id
        or projection["trialPlanGlobalId"] != plan_id
        or projection["trialRoundGlobalId"] != round_id
        or projection["conclusionState"] != conclusion_state
        or projection["conclusionCode"] != conclusion_code
        or projection["externalEffects"] != EXTERNAL_EFFECTS
    ):
        raise TrialSummaryContractError("Trial Summary presentation identity is invalid.")
    manifest = projection["sourceManifest"]
    if (
        isinstance(manifest, (str, bytes))
        or not isinstance(manifest, Sequence)
        or not 6 <= len(manifest) <= MAX_FACTS
    ):
        raise TrialSummaryContractError("Trial Summary source manifest is invalid.")
    source_keys: set[tuple[str, str, int, str]] = set()
    for item in manifest:
        source = _closed(
            item,
            {"kind", "globalId", "sourceVersion", "snapshotHash"},
            "Trial Summary source reference",
        )
        key = (
            _text(source["kind"], "sourceReference.kind", 64),
            _uuid(source["globalId"], "sourceReference.globalId"),
            _positive(source["sourceVersion"], "sourceReference.sourceVersion"),
            _hash(source["snapshotHash"], "sourceReference.snapshotHash"),
        )
        if key in source_keys:
            raise TrialSummaryContractError("Trial Summary source references are duplicated.")
        source_keys.add(key)
    conclusion = _closed(
        projection["conclusionRevision"],
        {"kind", "globalId", "sourceVersion", "snapshotHash"},
        "Trial Summary conclusion reference",
    )
    conclusion_key = (
        conclusion["kind"],
        conclusion["globalId"],
        conclusion["sourceVersion"],
        conclusion["snapshotHash"],
    )
    if conclusion_key not in source_keys or conclusion["kind"] != "trial_conclusion_revision":
        raise TrialSummaryContractError("Trial Summary conclusion reference is invalid.")
    grouped = _closed(projection["facts"], set(FACT_GROUPS), "Trial Summary facts")
    result: list[TrialSummaryFact] = []
    identities: set[tuple[str, str]] = set()
    for group in FACT_GROUPS:
        items = grouped[group]
        if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
            raise TrialSummaryContractError("Trial Summary facts are invalid.")
        for item in items:
            fact = _closed(
                item,
                {"factKey", "valueState", "value", "unit", "sourceReferences"},
                "Trial Summary fact",
            )
            fact_key = _pattern(fact["factKey"], _KEY, "factKey")
            identity = (group, fact_key)
            if identity in identities:
                raise TrialSummaryContractError("Trial Summary fact identities are duplicated.")
            identities.add(identity)
            state = _enum(fact["valueState"], VALUE_STATES, "valueState")
            fact_value = fact["value"]
            if isinstance(fact_value, str):
                _text(fact_value, "value", 4_000, allow_empty=True)
            elif fact_value is not None and type(fact_value) not in {int, float, bool}:
                raise TrialSummaryContractError("Trial Summary fact value is invalid.")
            unit = fact["unit"]
            if unit is not None:
                unit = _text(unit, "unit", 64)
            references = fact["sourceReferences"]
            if (
                isinstance(references, (str, bytes))
                or not isinstance(references, Sequence)
                or not 1 <= len(references) <= 100
            ):
                raise TrialSummaryContractError("Trial Summary fact sources are invalid.")
            reference_values: list[Mapping[str, object]] = []
            for reference in references:
                source = _closed(
                    reference,
                    {"kind", "globalId", "sourceVersion", "snapshotHash"},
                    "Trial Summary fact source",
                )
                source_key = (
                    source["kind"],
                    source["globalId"],
                    source["sourceVersion"],
                    source["snapshotHash"],
                )
                if source_key not in source_keys:
                    raise TrialSummaryContractError("Trial Summary fact source is unavailable.")
                reference_values.append(source)
            result.append(
                TrialSummaryFact(
                    group,
                    fact_type(fact_key, group),
                    fact_key,
                    state,
                    fact_value,
                    unit,
                    tuple(reference_values),
                )
            )
            if len(result) > MAX_FACTS:
                raise TrialSummaryContractError("Trial Summary facts exceed the safe bound.")
    return projection, tuple(result)


def _redaction_manifest(value: object) -> Mapping[str, object]:
    manifest = _closed(
        value,
        {
            "schemaVersion",
            "appliedRuleCodes",
            "excludedSensitiveFieldClasses",
            "externalProjection",
        },
        "Trial Summary redaction manifest",
    )
    if manifest["externalProjection"] != "unavailable":
        raise TrialSummaryContractError("Trial Summary redaction manifest is invalid.")
    for key in ("appliedRuleCodes", "excludedSensitiveFieldClasses"):
        values = manifest[key]
        if (
            isinstance(values, (str, bytes))
            or not isinstance(values, Sequence)
            or not values
            or len(values) > 64
            or any(not isinstance(item, str) or not item for item in values)
            or len(set(values)) != len(values)
        ):
            raise TrialSummaryContractError("Trial Summary redaction manifest is invalid.")
    return manifest


def _assert_sensitive_data_absent(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise TrialSummaryContractError("Trial Summary contains a forbidden field.")
            _assert_sensitive_data_absent(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _assert_sensitive_data_absent(item)
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(marker in lowered for marker in _FORBIDDEN_VALUE_MARKERS):
            raise TrialSummaryContractError("Trial Summary contains a forbidden value.")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise TrialSummaryContractError("Trial Summary JSON contains duplicate keys.")
        value[key] = item
    return value


def _closed(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise TrialSummaryContractError(f"{label} shape is invalid.")
    return value


def _uuid(value: object, label: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise TrialSummaryContractError(f"{label} is invalid.") from error
    if parsed.int == 0 or str(parsed) != str(value).casefold():
        raise TrialSummaryContractError(f"{label} is invalid.")
    return str(parsed)


def _optional_uuid(value: object, label: str) -> str | None:
    return None if value is None else _uuid(value, label)


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value


def _actor(value: object, label: str) -> str:
    if not isinstance(value, str) or _ACTOR.fullmatch(value) is None:
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value


def _pattern(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value


def _text(value: object, label: str, maximum: int, *, allow_empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or (not allow_empty and not value)
        or value != value.strip()
        or len(value) > maximum
    ):
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value


def _enum(value: object, values: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in values:
        raise TrialSummaryContractError(f"{label} is invalid.")
    return value
