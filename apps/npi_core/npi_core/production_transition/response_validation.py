from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import UUID

from npi_core.production_transition.domain import (
    HandoverAcknowledgement,
    HandoverPackageRevision,
    acknowledgement_from_snapshot,
    derive_fully_acknowledged,
    handover_package_from_snapshot,
    observation_from_snapshot,
    policy_from_snapshot,
)
from npi_core.production_transition.request_validation import (
    MANDATORY_EXTERNAL_PROVIDER_KINDS,
    MANDATORY_EXTERNAL_PROVIDER_ORDER,
)


EXTERNAL_UNAVAILABLE_REASON_CODES = {
    "actual_sop": "actual_sop_provider_unavailable",
    "first_batch_yield": "first_batch_yield_provider_unavailable",
    "customer_complaint": "customer_complaint_provider_unavailable",
    "production_cycle_time": "production_cycle_time_provider_unavailable",
    "tooling_stability": "tooling_stability_provider_unavailable",
}
_POLICY_OPERATIONS = frozenset(
    {
        "production_transition_policy.create",
        "production_transition_policy.edit",
        "production_transition_policy.publish",
        "production_transition_policy.next_version",
    }
)
_HANDOVER_OPERATIONS = frozenset(
    {"production_handover.create", "production_handover.revise"}
)
_OBSERVATION_OPERATIONS = frozenset(
    {"observation_period.create", "observation_period.revise"}
)

_HASH = re.compile(r"^[0-9a-f]{64}$")
_UNAVAILABLE_FIELDS = frozenset(
    {"kind", "state", "reasonCode", "sourceIdentity", "observedAt", "value", "unit"}
)
_OBSERVATION_REFERENCE_FIELDS = frozenset(
    {"kind", "globalId", "sourceVersion", "snapshotHash", "usage"}
)


class ProductionTransitionResponseInvalid(RuntimeError):
    """Fail closed without retaining or exposing an invalid response value."""

    def __init__(self) -> None:
        super().__init__("The production-transition response is invalid.")


def validate_policy_version_response(value: object) -> dict[str, Any]:
    """Validate one response against the exact canonical domain snapshot."""

    return _validated(lambda: _canonical_snapshot(value, policy_from_snapshot))


def validate_handover_package_response(value: object) -> dict[str, Any]:
    """Validate one immutable package without accepting acknowledgement derivations."""

    return _validated(lambda: _canonical_snapshot(value, handover_package_from_snapshot))


def validate_acknowledgement_response(value: object) -> dict[str, Any]:
    """Validate one actor-bound acknowledgement against its canonical snapshot."""

    return _validated(lambda: _canonical_snapshot(value, acknowledgement_from_snapshot))


def validate_observation_revision_response(value: object) -> dict[str, Any]:
    """Validate one independent observation revision against canonical domain truth."""

    def validate() -> dict[str, Any]:
        canonical = _canonical_snapshot(value, observation_from_snapshot)
        _require_observation_reference_usage(
            canonical["contextReferences"],
            expected_usage="context",
        )
        _require_observation_reference_usage(
            canonical["retrospectiveReferences"],
            expected_usage="retrospective",
        )
        return canonical

    return _validated(validate)


def validate_receipt_response(
    operation: object,
    value: object,
    *,
    target_global_id: object,
    project_global_id: object | None,
) -> dict[str, Any]:
    """Validate a sealed replay response against operation, target and Project scope."""

    def validate() -> dict[str, Any]:
        target_id = _canonical_uuid(target_global_id)
        if operation in _POLICY_OPERATIONS:
            if project_global_id is not None:
                raise ProductionTransitionResponseInvalid()
            policy = validate_policy_version_response(value)
            _validate_policy_operation(operation, policy, target_id)
            return policy
        project_id = _canonical_uuid(project_global_id)
        if operation in _HANDOVER_OPERATIONS:
            wrapper = _closed_record(
                value,
                frozenset({"projectGlobalId", "handoverPackage"}),
            )
            if _canonical_uuid(wrapper["projectGlobalId"]) != project_id:
                raise ProductionTransitionResponseInvalid()
            package = validate_handover_package_response(wrapper["handoverPackage"])
            if (
                package["project"]["globalId"] != project_id
                or package["globalId"] != target_id
                or (
                    operation == "production_handover.create"
                    and package["handoverVersion"] != 1
                )
                or (
                    operation == "production_handover.revise"
                    and package["handoverVersion"] < 2
                )
            ):
                raise ProductionTransitionResponseInvalid()
            return {"projectGlobalId": project_id, "handoverPackage": package}
        if operation == "production_handover.acknowledge":
            wrapper = _closed_record(
                value,
                frozenset(
                    {"projectGlobalId", "handoverPackage", "acknowledgement"}
                ),
            )
            if _canonical_uuid(wrapper["projectGlobalId"]) != project_id:
                raise ProductionTransitionResponseInvalid()
            package_value, package = _canonical_domain_snapshot(
                wrapper["handoverPackage"],
                handover_package_from_snapshot,
            )
            acknowledgement_value, acknowledgement = _canonical_domain_snapshot(
                wrapper["acknowledgement"],
                acknowledgement_from_snapshot,
            )
            if (
                package["project"]["globalId"] != project_id
                or acknowledgement["globalId"] != target_id
                or acknowledgement["handoverGlobalId"]
                != package["handoverGlobalId"]
                or acknowledgement["packageRevisionGlobalId"] != package["globalId"]
                or acknowledgement["packageVersion"] != package["handoverVersion"]
                or acknowledgement["packageSnapshotHash"] != package["snapshotHash"]
            ):
                raise ProductionTransitionResponseInvalid()
            _require_exact_acknowledgement_binding(
                package_value,
                acknowledgement_value,
            )
            return {
                "projectGlobalId": project_id,
                "handoverPackage": package,
                "acknowledgement": acknowledgement,
            }
        if operation in _OBSERVATION_OPERATIONS:
            wrapper = _closed_record(
                value,
                frozenset({"projectGlobalId", "observationPeriod"}),
            )
            if _canonical_uuid(wrapper["projectGlobalId"]) != project_id:
                raise ProductionTransitionResponseInvalid()
            observation = validate_observation_revision_response(
                wrapper["observationPeriod"]
            )
            if (
                observation["project"]["globalId"] != project_id
                or observation["globalId"] != target_id
                or (
                    operation == "observation_period.create"
                    and observation["observationVersion"] != 1
                )
                or (
                    operation == "observation_period.revise"
                    and observation["observationVersion"] < 2
                )
            ):
                raise ProductionTransitionResponseInvalid()
            return {"projectGlobalId": project_id, "observationPeriod": observation}
        raise ProductionTransitionResponseInvalid()

    return _validated(validate)


def _validate_policy_operation(
    operation: object,
    policy: Mapping[str, Any],
    target_id: str,
) -> None:
    state = policy["publicationState"]
    version = policy["policyVersion"]
    if (
        (operation == "production_transition_policy.create" and (
            policy["policyGlobalId"] != target_id or version != 1 or state != "draft"
        ))
        or (operation == "production_transition_policy.edit" and (
            policy["globalId"] != target_id or state != "draft"
        ))
        or (operation == "production_transition_policy.publish" and (
            policy["globalId"] != target_id or state != "published"
        ))
        or (operation == "production_transition_policy.next_version" and (
            policy["globalId"] != target_id
            or version < 2
            or state != "draft"
            or policy["priorVersionRef"] is None
        ))
    ):
        raise ProductionTransitionResponseInvalid()


def validate_unavailable_provider_responses(value: object) -> list[dict[str, Any]]:
    """Validate the complete identity-free, provider-specific unavailable set."""

    return _validated(lambda: _unavailable_provider_responses(value))


def validate_handover_acknowledgement_projection(
    value: object,
    *,
    handover_package: object,
) -> dict[str, Any]:
    """Validate one immutable acknowledgement fact against exact package truth."""

    def validate() -> dict[str, Any]:
        package_value, _package = _canonical_domain_snapshot(
            handover_package,
            handover_package_from_snapshot,
        )
        acknowledgement_value, acknowledgement = _canonical_domain_snapshot(
            value,
            acknowledgement_from_snapshot,
        )
        _require_exact_acknowledgement_binding(
            package_value,
            acknowledgement_value,
        )
        return acknowledgement

    return _validated(validate)


def validate_fully_acknowledged_projection(
    value: object,
    *,
    handover_package: object,
) -> dict[str, Any]:
    """Ensure fullyAcknowledged is a response-only derivation from immutable facts."""

    def validate() -> dict[str, Any]:
        package_value, _package = _canonical_domain_snapshot(
            handover_package,
            handover_package_from_snapshot,
        )
        record = _closed_record(
            value,
            frozenset({"acknowledgements", "fullyAcknowledged"}),
        )
        acknowledgements = _bounded_list(record["acknowledgements"], maximum=1_000)
        acknowledgement_values: list[HandoverAcknowledgement] = []
        parsed: list[dict[str, Any]] = []
        for item in acknowledgements:
            acknowledgement_value, acknowledgement = _canonical_domain_snapshot(
                item,
                acknowledgement_from_snapshot,
            )
            _require_exact_acknowledgement_binding(
                package_value,
                acknowledgement_value,
            )
            acknowledgement_values.append(acknowledgement_value)
            parsed.append(acknowledgement)
        acknowledgement_ids = tuple(value.global_id for value in acknowledgement_values)
        acknowledgement_slots = tuple(value.slot_key for value in acknowledgement_values)
        if (
            len(acknowledgement_ids) != len(set(acknowledgement_ids))
            or len(acknowledgement_slots) != len(set(acknowledgement_slots))
        ):
            raise ProductionTransitionResponseInvalid()
        expected = derive_fully_acknowledged(
            package_value,
            acknowledgement_values,
        )
        if type(record["fullyAcknowledged"]) is not bool:
            raise ProductionTransitionResponseInvalid()
        if record["fullyAcknowledged"] is not expected:
            raise ProductionTransitionResponseInvalid()
        return {
            "acknowledgements": parsed,
            "fullyAcknowledged": expected,
        }

    return _validated(validate)


def validate_observation_projection(value: object) -> dict[str, Any]:
    """Validate P7-06's unavailable external truth and not-evaluable result."""

    def validate() -> dict[str, Any]:
        fields = frozenset(
            {
                "providers",
                "observedStart",
                "observedEnd",
                "technicalDisposition",
            }
        )
        record = _closed_record(value, fields)
        providers = _unavailable_provider_responses(record["providers"])
        if (
            record["observedStart"] is not None
            or record["observedEnd"] is not None
            or record["technicalDisposition"] != "not_evaluable"
        ):
            raise ProductionTransitionResponseInvalid()
        return {
            "providers": providers,
            "observedStart": None,
            "observedEnd": None,
            "technicalDisposition": "not_evaluable",
        }

    return _validated(validate)


def _unavailable_provider_responses(value: object) -> list[dict[str, Any]]:
    records = _bounded_list(value, maximum=5)
    if len(records) != 5:
        raise ProductionTransitionResponseInvalid()
    result: list[dict[str, Any]] = []
    for item in records:
        record = _closed_record(item, _UNAVAILABLE_FIELDS)
        kind = record["kind"]
        if (
            kind not in MANDATORY_EXTERNAL_PROVIDER_KINDS
            or record["state"] != "unavailable"
            or record["reasonCode"] != EXTERNAL_UNAVAILABLE_REASON_CODES[kind]
            or any(
                record[field] is not None
                for field in ("sourceIdentity", "observedAt", "value", "unit")
            )
        ):
            raise ProductionTransitionResponseInvalid()
        result.append(
            {
                "kind": kind,
                "state": "unavailable",
                "reasonCode": EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
                "sourceIdentity": None,
                "observedAt": None,
                "value": None,
                "unit": None,
            }
        )
    if tuple(item["kind"] for item in result) != MANDATORY_EXTERNAL_PROVIDER_ORDER:
        raise ProductionTransitionResponseInvalid()
    return result


def _require_observation_reference_usage(
    value: object,
    *,
    expected_usage: str,
) -> None:
    """Keep observation references distinct from requirement-bound manifest rows."""

    records = _bounded_list(value, maximum=1_000)
    for item in records:
        record = _closed_record(item, _OBSERVATION_REFERENCE_FIELDS)
        if record["usage"] != expected_usage:
            raise ProductionTransitionResponseInvalid()


def _canonical_snapshot(
    value: object,
    parser: Callable[[Mapping[str, object]], Any],
) -> dict[str, Any]:
    _parsed, canonical = _canonical_domain_snapshot(value, parser)
    return canonical


def _canonical_domain_snapshot(
    value: object,
    parser: Callable[[Mapping[str, object]], Any],
) -> tuple[Any, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ProductionTransitionResponseInvalid()
    record = dict(value)
    snapshot_hash = record.pop("snapshotHash", None)
    if not isinstance(snapshot_hash, str) or _HASH.fullmatch(snapshot_hash) is None:
        raise ProductionTransitionResponseInvalid()
    parsed = parser(record)
    canonical = parsed.snapshot_payload()
    if record != canonical or parsed.snapshot_hash != snapshot_hash:
        raise ProductionTransitionResponseInvalid()
    return parsed, {**canonical, "snapshotHash": snapshot_hash}


def _require_exact_acknowledgement_binding(
    package: HandoverPackageRevision,
    acknowledgement: HandoverAcknowledgement,
) -> None:
    matches = [
        slot for slot in package.slots if slot.slot_key == acknowledgement.slot_key
    ]
    if len(matches) != 1:
        raise ProductionTransitionResponseInvalid()
    slot = matches[0]
    if (
        acknowledgement.handover_global_id != package.handover_global_id
        or acknowledgement.package_revision_global_id != package.global_id
        or acknowledgement.package_version != package.handover_version
        or acknowledgement.package_snapshot_hash != package.snapshot_hash
        or acknowledgement.actor_user_id != slot.member.user_id
        or acknowledgement.member_global_id != slot.member.global_id
        or acknowledgement.member_optimistic_version
        != slot.member.optimistic_version
        or acknowledgement.member_snapshot_hash != slot.member.snapshot_hash
        or acknowledgement.role_global_id != slot.role.global_id
        or acknowledgement.role_optimistic_version != slot.role.optimistic_version
        or acknowledgement.role_snapshot_hash != slot.role.snapshot_hash
        or not slot.member.is_effective(acknowledgement.acknowledged_at.date())
        or not slot.role.is_effective(acknowledgement.acknowledged_at.date())
    ):
        raise ProductionTransitionResponseInvalid()


def _validated(validate: Callable[[], Any]) -> Any:
    try:
        return validate()
    except ProductionTransitionResponseInvalid:
        raise
    except Exception as error:
        raise ProductionTransitionResponseInvalid() from error


def _closed_record(value: object, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ProductionTransitionResponseInvalid()
    return dict(value)


def _bounded_list(value: object, *, maximum: int) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or len(value) > maximum
    ):
        raise ProductionTransitionResponseInvalid()
    return list(value)


def _canonical_uuid(value: object) -> str:
    if isinstance(value, UUID):
        if value.int == 0:
            raise ProductionTransitionResponseInvalid()
        return str(value)
    if not isinstance(value, str):
        raise ProductionTransitionResponseInvalid()
    parsed = UUID(value)
    if str(parsed) != value.casefold():
        raise ProductionTransitionResponseInvalid()
    return str(parsed)
