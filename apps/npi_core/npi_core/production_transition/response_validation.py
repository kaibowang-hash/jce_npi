from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import UUID, uuid5

from npi_core.production_transition.domain import (
    HandoverAcknowledgement,
    HandoverPackageRevision,
    ObservationPeriodRevision,
    PolicyPublicationState,
    ProductionTransitionPolicyVersion,
    acknowledgement_from_snapshot,
    derive_fully_acknowledged,
    handover_package_from_snapshot,
    observation_from_snapshot,
    policy_from_snapshot,
    validate_handover_successor,
    validate_observation_successor,
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
_TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_UNAVAILABLE_FIELDS = frozenset(
    {"kind", "state", "reasonCode", "sourceIdentity", "observedAt", "value", "unit"}
)
_OBSERVATION_REFERENCE_FIELDS = frozenset(
    {"kind", "globalId", "sourceVersion", "snapshotHash", "usage"}
)
_CATALOG_FIELDS = frozenset({"projectGlobalId", "policies"})
_WORKSPACE_FIELDS = frozenset(
    {
        "projectGlobalId",
        "currentHandover",
        "handoverHistory",
        "currentObservation",
        "observationHistory",
        "unavailableProviders",
        "permissions",
    }
)
_HANDOVER_VIEW_FIELDS = frozenset(
    {"revision", "acknowledgements", "fullyAcknowledged"}
)
_PERMISSION_FIELDS = frozenset(
    {
        "canManagePolicies",
        "canCreateHandover",
        "canReviseHandover",
        "canAcknowledgeSlots",
        "canCreateObservation",
        "canReviseObservation",
    }
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


def validate_policy_catalog_response(
    value: object,
    *,
    project_global_id: object | None = None,
    tenant_id: object,
) -> dict[str, Any]:
    """Validate one closed, published, Project-bound policy catalog."""

    return _validated(
        lambda: _policy_catalog(
            value,
            project_global_id=project_global_id,
            tenant_id=tenant_id,
        )
    )


def validate_workspace_response(
    value: object,
    *,
    project_global_id: object | None = None,
    tenant_id: object,
) -> dict[str, Any]:
    """Validate exact independent handover and observation histories."""

    return _validated(
        lambda: _workspace(
            value,
            project_global_id=project_global_id,
            tenant_id=tenant_id,
        )
    )


def validate_command_response(
    operation: object,
    value: object,
    *,
    target_global_id: object,
    tenant_id: object,
    policy_global_id: object | None = None,
    policy_version: object | None = None,
    policy_snapshot_hash: object | None = None,
    project_global_id: object | None = None,
    handover_global_id: object | None = None,
    handover_version: object | None = None,
    handover_revision_global_id: object | None = None,
    handover_snapshot_hash: object | None = None,
    observation_global_id: object | None = None,
    expected_revision_global_id: object | None = None,
    expected_snapshot_hash: object | None = None,
    slot_key: object | None = None,
) -> dict[str, Any]:
    """Bind a sealed command response to every route and request identity."""

    return _validated(
        lambda: _command_response(
            operation,
            value,
            target_global_id=target_global_id,
            tenant_id=tenant_id,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
            project_global_id=project_global_id,
            handover_global_id=handover_global_id,
            handover_version=handover_version,
            handover_revision_global_id=handover_revision_global_id,
            handover_snapshot_hash=handover_snapshot_hash,
            observation_global_id=observation_global_id,
            expected_revision_global_id=expected_revision_global_id,
            expected_snapshot_hash=expected_snapshot_hash,
            slot_key=slot_key,
        )
    )


def _policy_catalog(
    value: object,
    *,
    project_global_id: object | None,
    tenant_id: object | None,
) -> dict[str, Any]:
    record = _closed_record(value, _CATALOG_FIELDS)
    project_id = _canonical_uuid(record["projectGlobalId"])
    if (
        project_global_id is not None
        and _canonical_uuid(project_global_id) != project_id
    ):
        raise ProductionTransitionResponseInvalid()
    policies: list[dict[str, Any]] = []
    parsed: list[ProductionTransitionPolicyVersion] = []
    expected_tenant_id = _required_tenant_id(tenant_id)
    for item in _bounded_list(record["policies"], maximum=1_000):
        policy, policy_value = _canonical_domain_snapshot(item, policy_from_snapshot)
        if (
            policy.publication_state is not PolicyPublicationState.PUBLISHED
            or (
                expected_tenant_id is not None
                and policy.tenant_id != expected_tenant_id
            )
        ):
            raise ProductionTransitionResponseInvalid()
        explicit_project_ids = policy.applicability.project_global_ids
        if explicit_project_ids and UUID(project_id) not in explicit_project_ids:
            raise ProductionTransitionResponseInvalid()
        policies.append(policy_value)
        parsed.append(policy)
    identities = tuple((item.policy_global_id, item.policy_version) for item in parsed)
    revision_ids = tuple(item.global_id for item in parsed)
    if (
        len(set(identities)) != len(identities)
        or len(set(revision_ids)) != len(revision_ids)
    ):
        raise ProductionTransitionResponseInvalid()
    expected = {"projectGlobalId": project_id, "policies": policies}
    if record != expected:
        raise ProductionTransitionResponseInvalid()
    return expected


def _workspace(
    value: object,
    *,
    project_global_id: object | None,
    tenant_id: object | None,
) -> dict[str, Any]:
    record = _closed_record(value, _WORKSPACE_FIELDS)
    project_id = _canonical_uuid(record["projectGlobalId"])
    if (
        project_global_id is not None
        and _canonical_uuid(project_global_id) != project_id
    ):
        raise ProductionTransitionResponseInvalid()
    expected_tenant_id = (
        _required_tenant_id(tenant_id) if tenant_id is not None else None
    )

    handover_views: list[dict[str, Any]] = []
    handovers: list[HandoverPackageRevision] = []
    for item in _bounded_list(record["handoverHistory"], maximum=1_000):
        view, revision = _handover_view(
            item,
            project_id=project_id,
            tenant_id=expected_tenant_id,
        )
        handover_views.append(view)
        handovers.append(revision)
    _require_handover_history(handovers)
    current_handover = _current_handover(
        record["currentHandover"],
        project_id=project_id,
        tenant_id=expected_tenant_id,
        history=handover_views,
    )

    observation_values: list[dict[str, Any]] = []
    observations: list[ObservationPeriodRevision] = []
    for item in _bounded_list(record["observationHistory"], maximum=1_000):
        observation, response = _canonical_domain_snapshot(
            item,
            observation_from_snapshot,
        )
        _require_observation_reference_usage(
            response["contextReferences"],
            expected_usage="context",
        )
        _require_observation_reference_usage(
            response["retrospectiveReferences"],
            expected_usage="retrospective",
        )
        if (
            response["project"]["globalId"] != project_id
            or (
                expected_tenant_id is not None
                and observation.tenant_id != expected_tenant_id
            )
        ):
            raise ProductionTransitionResponseInvalid()
        observation_values.append(response)
        observations.append(observation)
    _require_observation_history(observations)
    current_observation = _current_observation(
        record["currentObservation"],
        project_id=project_id,
        tenant_id=expected_tenant_id,
        history=observation_values,
    )
    if (
        handovers
        and observations
        and handovers[0].handover_global_id
        == observations[0].observation_global_id
    ):
        raise ProductionTransitionResponseInvalid()

    providers = _unavailable_provider_responses(record["unavailableProviders"])
    permissions = _permissions(
        record["permissions"],
        current_handover=current_handover,
    )
    expected = {
        "projectGlobalId": project_id,
        "currentHandover": current_handover,
        "handoverHistory": handover_views,
        "currentObservation": current_observation,
        "observationHistory": observation_values,
        "unavailableProviders": providers,
        "permissions": permissions,
    }
    if record != expected:
        raise ProductionTransitionResponseInvalid()
    return expected


def _handover_view(
    value: object,
    *,
    project_id: str,
    tenant_id: str | None,
) -> tuple[dict[str, Any], HandoverPackageRevision]:
    record = _closed_record(value, _HANDOVER_VIEW_FIELDS)
    revision, package = _canonical_domain_snapshot(
        record["revision"],
        handover_package_from_snapshot,
    )
    if (
        package["project"]["globalId"] != project_id
        or (tenant_id is not None and revision.tenant_id != tenant_id)
    ):
        raise ProductionTransitionResponseInvalid()
    projection = validate_fully_acknowledged_projection(
        {
            "acknowledgements": record["acknowledgements"],
            "fullyAcknowledged": record["fullyAcknowledged"],
        },
        handover_package=package,
    )
    expected = {
        "revision": package,
        "acknowledgements": projection["acknowledgements"],
        "fullyAcknowledged": projection["fullyAcknowledged"],
    }
    if record != expected:
        raise ProductionTransitionResponseInvalid()
    return expected, revision


def _require_handover_history(
    history: Sequence[HandoverPackageRevision],
) -> None:
    if history and history[0].handover_version != 1:
        raise ProductionTransitionResponseInvalid()
    stream_ids = {item.handover_global_id for item in history}
    revision_ids = tuple(item.global_id for item in history)
    if len(stream_ids) > 1 or len(set(revision_ids)) != len(revision_ids):
        raise ProductionTransitionResponseInvalid()
    for current, successor in zip(history, history[1:]):
        validate_handover_successor(current, successor)


def _require_observation_history(
    history: Sequence[ObservationPeriodRevision],
) -> None:
    if history and history[0].observation_version != 1:
        raise ProductionTransitionResponseInvalid()
    stream_ids = {item.observation_global_id for item in history}
    revision_ids = tuple(item.global_id for item in history)
    if len(stream_ids) > 1 or len(set(revision_ids)) != len(revision_ids):
        raise ProductionTransitionResponseInvalid()
    for current, successor in zip(history, history[1:]):
        validate_observation_successor(current, successor)


def _current_handover(
    value: object,
    *,
    project_id: str,
    tenant_id: str | None,
    history: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if value is None:
        if history:
            raise ProductionTransitionResponseInvalid()
        return None
    current, _revision = _handover_view(
        value,
        project_id=project_id,
        tenant_id=tenant_id,
    )
    if not history or current != history[-1]:
        raise ProductionTransitionResponseInvalid()
    return current


def _current_observation(
    value: object,
    *,
    project_id: str,
    tenant_id: str | None,
    history: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    if value is None:
        if history:
            raise ProductionTransitionResponseInvalid()
        return None
    current = validate_observation_revision_response(value)
    if (
        current["project"]["globalId"] != project_id
        or (tenant_id is not None and current["tenantId"] != tenant_id)
        or not history
        or current != history[-1]
    ):
        raise ProductionTransitionResponseInvalid()
    return current


def _permissions(
    value: object,
    *,
    current_handover: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record = _closed_record(value, _PERMISSION_FIELDS)
    boolean_fields = _PERMISSION_FIELDS - frozenset({"canAcknowledgeSlots"})
    if any(type(record[field]) is not bool for field in boolean_fields):
        raise ProductionTransitionResponseInvalid()
    slots = _bounded_list(record["canAcknowledgeSlots"], maximum=100)
    canonical_slots = tuple(_bounded_key(item) for item in slots)
    if len(set(canonical_slots)) != len(canonical_slots):
        raise ProductionTransitionResponseInvalid()
    allowed_slots = (
        {
            slot["slotKey"]
            for slot in current_handover["revision"]["slots"]
        }
        if current_handover is not None
        else set()
    )
    if not set(canonical_slots).issubset(allowed_slots):
        raise ProductionTransitionResponseInvalid()
    return {
        "canManagePolicies": record["canManagePolicies"],
        "canCreateHandover": record["canCreateHandover"],
        "canReviseHandover": record["canReviseHandover"],
        "canAcknowledgeSlots": list(canonical_slots),
        "canCreateObservation": record["canCreateObservation"],
        "canReviseObservation": record["canReviseObservation"],
    }


def _command_response(
    operation: object,
    value: object,
    *,
    target_global_id: object,
    tenant_id: object | None,
    policy_global_id: object | None,
    policy_version: object | None,
    policy_snapshot_hash: object | None,
    project_global_id: object | None,
    handover_global_id: object | None,
    handover_version: object | None,
    handover_revision_global_id: object | None,
    handover_snapshot_hash: object | None,
    observation_global_id: object | None,
    expected_revision_global_id: object | None,
    expected_snapshot_hash: object | None,
    slot_key: object | None,
) -> dict[str, Any]:
    response = validate_receipt_response(
        operation,
        value,
        target_global_id=target_global_id,
        project_global_id=project_global_id,
        tenant_id=tenant_id,
    )
    if operation in _POLICY_OPERATIONS:
        _reject_supplied(
            project_global_id,
            handover_global_id,
            handover_version,
            handover_revision_global_id,
            handover_snapshot_hash,
            observation_global_id,
            expected_revision_global_id,
            expected_snapshot_hash,
            slot_key,
        )
        return _bind_policy_command(
            operation,
            response,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
        )
    if operation in _HANDOVER_OPERATIONS:
        _reject_supplied(
            observation_global_id,
            handover_version,
            handover_revision_global_id,
            handover_snapshot_hash,
            slot_key,
        )
        return _bind_handover_command(
            operation,
            response,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
            handover_global_id=handover_global_id,
            expected_revision_global_id=expected_revision_global_id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
    if operation == "production_handover.acknowledge":
        _reject_supplied(
            policy_global_id,
            policy_version,
            policy_snapshot_hash,
            observation_global_id,
        )
        return _bind_acknowledgement_command(
            response,
            handover_global_id=handover_global_id,
            handover_version=handover_version,
            expected_revision_global_id=expected_revision_global_id,
            expected_snapshot_hash=expected_snapshot_hash,
            slot_key=slot_key,
            handover_revision_global_id=handover_revision_global_id,
            handover_snapshot_hash=handover_snapshot_hash,
        )
    if operation in _OBSERVATION_OPERATIONS:
        _reject_supplied(slot_key)
        return _bind_observation_command(
            operation,
            response,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            policy_snapshot_hash=policy_snapshot_hash,
            handover_global_id=handover_global_id,
            handover_version=handover_version,
            handover_revision_global_id=handover_revision_global_id,
            handover_snapshot_hash=handover_snapshot_hash,
            observation_global_id=observation_global_id,
            expected_revision_global_id=expected_revision_global_id,
            expected_snapshot_hash=expected_snapshot_hash,
        )
    raise ProductionTransitionResponseInvalid()


def _bind_policy_command(
    operation: object,
    response: dict[str, Any],
    *,
    policy_global_id: object | None,
    policy_version: object | None,
    policy_snapshot_hash: object | None,
) -> dict[str, Any]:
    if operation == "production_transition_policy.create":
        _reject_supplied(policy_global_id, policy_version, policy_snapshot_hash)
        return response
    expected_policy_id = _required_uuid(policy_global_id)
    expected_version = _required_positive(policy_version)
    if response["policyGlobalId"] != expected_policy_id:
        raise ProductionTransitionResponseInvalid()
    if operation in {
        "production_transition_policy.edit",
        "production_transition_policy.publish",
    }:
        if response["policyVersion"] != expected_version:
            raise ProductionTransitionResponseInvalid()
        if policy_snapshot_hash is not None:
            _canonical_hash(policy_snapshot_hash)
        return response
    if operation == "production_transition_policy.next_version":
        expected_hash = _required_hash(policy_snapshot_hash)
        prior = response["priorVersionRef"]
        if (
            response["policyVersion"] != expected_version + 1
            or prior is None
            or prior["version"] != expected_version
            or prior["snapshotHash"] != expected_hash
        ):
            raise ProductionTransitionResponseInvalid()
        return response
    raise ProductionTransitionResponseInvalid()


def _bind_handover_command(
    operation: object,
    response: dict[str, Any],
    *,
    policy_global_id: object | None,
    policy_version: object | None,
    policy_snapshot_hash: object | None,
    handover_global_id: object | None,
    expected_revision_global_id: object | None,
    expected_snapshot_hash: object | None,
) -> dict[str, Any]:
    package = response["handoverPackage"]
    _require_policy_reference(
        package["policyRef"],
        global_id=policy_global_id,
        version=policy_version,
        snapshot_hash=policy_snapshot_hash,
    )
    if operation == "production_handover.create":
        _reject_supplied(
            handover_global_id,
            expected_revision_global_id,
            expected_snapshot_hash,
        )
        return response
    if package["handoverGlobalId"] != _required_uuid(handover_global_id):
        raise ProductionTransitionResponseInvalid()
    if (
        package["predecessorGlobalId"]
        != _required_uuid(expected_revision_global_id)
        or package["predecessorSnapshotHash"]
        != _required_hash(expected_snapshot_hash)
    ):
        raise ProductionTransitionResponseInvalid()
    return response


def _bind_acknowledgement_command(
    response: dict[str, Any],
    *,
    handover_global_id: object | None,
    handover_version: object | None,
    expected_revision_global_id: object | None,
    expected_snapshot_hash: object | None,
    slot_key: object | None,
    handover_revision_global_id: object | None,
    handover_snapshot_hash: object | None,
) -> dict[str, Any]:
    package = response["handoverPackage"]
    acknowledgement = response["acknowledgement"]
    expected_revision = _required_uuid(expected_revision_global_id)
    expected_hash = _required_hash(expected_snapshot_hash)
    if (
        package["handoverGlobalId"] != _required_uuid(handover_global_id)
        or package["handoverVersion"] != _required_positive(handover_version)
        or package["globalId"] != expected_revision
        or package["snapshotHash"] != expected_hash
        or acknowledgement["slotKey"] != _required_key(slot_key)
    ):
        raise ProductionTransitionResponseInvalid()
    if handover_revision_global_id is not None and (
        _canonical_uuid(handover_revision_global_id) != expected_revision
    ):
        raise ProductionTransitionResponseInvalid()
    if handover_snapshot_hash is not None and (
        _canonical_hash(handover_snapshot_hash) != expected_hash
    ):
        raise ProductionTransitionResponseInvalid()
    return response


def _bind_observation_command(
    operation: object,
    response: dict[str, Any],
    *,
    policy_global_id: object | None,
    policy_version: object | None,
    policy_snapshot_hash: object | None,
    handover_global_id: object | None,
    handover_version: object | None,
    handover_revision_global_id: object | None,
    handover_snapshot_hash: object | None,
    observation_global_id: object | None,
    expected_revision_global_id: object | None,
    expected_snapshot_hash: object | None,
) -> dict[str, Any]:
    observation = response["observationPeriod"]
    if operation == "observation_period.create":
        _require_policy_reference(
            observation["policyRef"],
            global_id=policy_global_id,
            version=policy_version,
            snapshot_hash=policy_snapshot_hash,
        )
        handover_ref = observation["handoverPackageRef"]
        handover_args = (
            handover_global_id,
            handover_version,
            handover_revision_global_id,
            handover_snapshot_hash,
        )
        if all(item is None for item in handover_args):
            if handover_ref is not None:
                raise ProductionTransitionResponseInvalid()
        elif any(item is None for item in handover_args) or handover_ref is None:
            raise ProductionTransitionResponseInvalid()
        else:
            if (
                handover_ref["globalId"]
                != _required_uuid(handover_revision_global_id)
                or handover_ref["version"]
                != _required_positive(handover_version)
                or handover_ref["snapshotHash"]
                != _required_hash(handover_snapshot_hash)
            ):
                raise ProductionTransitionResponseInvalid()
            expected_handover_revision_id = str(
                uuid5(
                    UUID(_required_uuid(handover_global_id)),
                    (
                        "npi-handover-package-revision:"
                        f"{_required_positive(handover_version)}"
                    ),
                )
            )
            if handover_ref["globalId"] != expected_handover_revision_id:
                raise ProductionTransitionResponseInvalid()
        _reject_supplied(
            observation_global_id,
            expected_revision_global_id,
            expected_snapshot_hash,
        )
        return response
    _reject_supplied(
        policy_global_id,
        policy_version,
        policy_snapshot_hash,
        handover_global_id,
        handover_version,
        handover_revision_global_id,
        handover_snapshot_hash,
    )
    if observation["observationGlobalId"] != _required_uuid(observation_global_id):
        raise ProductionTransitionResponseInvalid()
    if (
        observation["predecessorGlobalId"]
        != _required_uuid(expected_revision_global_id)
        or observation["predecessorSnapshotHash"]
        != _required_hash(expected_snapshot_hash)
    ):
        raise ProductionTransitionResponseInvalid()
    return response


def _require_policy_reference(
    value: Mapping[str, Any],
    *,
    global_id: object | None,
    version: object | None,
    snapshot_hash: object | None,
) -> None:
    policy_id = UUID(_required_uuid(global_id))
    policy_version = _required_positive(version)
    expected_revision_id = str(
        uuid5(
            policy_id,
            f"npi-production-transition-policy-version:{policy_version}",
        )
    )
    if (
        value["globalId"] != expected_revision_id
        or value["version"] != policy_version
        or value["snapshotHash"] != _required_hash(snapshot_hash)
    ):
        raise ProductionTransitionResponseInvalid()


def _reject_supplied(*values: object | None) -> None:
    if any(value is not None for value in values):
        raise ProductionTransitionResponseInvalid()


def validate_receipt_response(
    operation: object,
    value: object,
    *,
    target_global_id: object,
    project_global_id: object | None,
    tenant_id: object,
) -> dict[str, Any]:
    """Validate a sealed replay response against operation, target and Project scope."""

    def validate() -> dict[str, Any]:
        target_id = _canonical_uuid(target_global_id)
        expected_tenant_id = _required_tenant_id(tenant_id)
        if operation in _POLICY_OPERATIONS:
            if project_global_id is not None:
                raise ProductionTransitionResponseInvalid()
            policy = validate_policy_version_response(value)
            if policy["tenantId"] != expected_tenant_id:
                raise ProductionTransitionResponseInvalid()
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
                or package["tenantId"] != expected_tenant_id
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
                or package["tenantId"] != expected_tenant_id
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
                or observation["tenantId"] != expected_tenant_id
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


def _bounded_key(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ProductionTransitionResponseInvalid()
    if re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$", value) is None:
        raise ProductionTransitionResponseInvalid()
    return value


def _required_key(value: object | None) -> str:
    if value is None:
        raise ProductionTransitionResponseInvalid()
    return _bounded_key(value)


def _required_uuid(value: object | None) -> str:
    if value is None:
        raise ProductionTransitionResponseInvalid()
    return _canonical_uuid(value)


def _required_positive(value: object | None) -> int:
    if type(value) is not int or value < 1:
        raise ProductionTransitionResponseInvalid()
    return value


def _canonical_hash(value: object) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ProductionTransitionResponseInvalid()
    return value


def _required_hash(value: object | None) -> str:
    if value is None:
        raise ProductionTransitionResponseInvalid()
    return _canonical_hash(value)


def _required_tenant_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or _TENANT.fullmatch(value) is None
    ):
        raise ProductionTransitionResponseInvalid()
    return value


def _canonical_uuid(value: object) -> str:
    if isinstance(value, UUID):
        if value.int == 0:
            raise ProductionTransitionResponseInvalid()
        return str(value)
    if not isinstance(value, str):
        raise ProductionTransitionResponseInvalid()
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value.casefold():
        raise ProductionTransitionResponseInvalid()
    return str(parsed)
