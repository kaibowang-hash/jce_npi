from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .config import MbomExecutionProfile
from .domain import (
    MBOM_PUBLISH_OPERATION,
    MbomFaultKind,
    MbomMappingExpectation,
    MbomNodeObservation,
    MbomNodeResultState,
    MbomPublishContractError,
    MbomPublishIntent,
    MbomPublishRequestState,
    MbomResultAuthority,
    MbomTargetMode,
    MbomTargetSubmissionState,
    aggregate_node_results,
    canonical_hash,
    classify_adapter_fault,
)


MBOM_ADAPTER_CONTRACT_VERSION = 1


def _hash(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MbomPublishContractError(f"{label} is invalid.")
    return value


@dataclass(frozen=True, slots=True)
class MbomAdapterNodeCommand:
    node_global_id: UUID
    stable_line_key: str
    assembly_source_key: str
    intent: MbomPublishIntent
    expected_mapping_version: int
    expected_formal_bom_id: str | None
    expected_target_version: str | None
    node_snapshot: Mapping[str, object]
    node_snapshot_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.node_global_id, UUID):
            raise MbomPublishContractError("MBOM adapter node identity is invalid.")
        if (
            not isinstance(self.stable_line_key, str)
            or not self.stable_line_key
            or self.stable_line_key != self.stable_line_key.strip()
            or len(self.stable_line_key) > 128
        ):
            raise MbomPublishContractError("MBOM adapter node key is invalid.")
        _hash(self.assembly_source_key, "MBOM adapter assembly source key")
        _hash(self.node_snapshot_hash, "MBOM adapter node snapshot hash")
        if not isinstance(self.intent, MbomPublishIntent):
            raise MbomPublishContractError("MBOM adapter node intent is invalid.")
        if type(self.expected_mapping_version) is not int or self.expected_mapping_version < 0:
            raise MbomPublishContractError("MBOM adapter node mapping expectation is invalid.")
        if not isinstance(self.node_snapshot, Mapping) or canonical_hash(
            dict(self.node_snapshot)
        ) != self.node_snapshot_hash:
            raise MbomPublishContractError("MBOM adapter node snapshot is invalid.")
        for value in (self.expected_formal_bom_id, self.expected_target_version):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 140
            ):
                raise MbomPublishContractError("MBOM adapter node target expectation is invalid.")
        if self.intent is MbomPublishIntent.CREATE_DRAFT:
            if self.expected_mapping_version != 0 or any(
                (self.expected_formal_bom_id, self.expected_target_version)
            ):
                raise MbomPublishContractError("MBOM create intent cannot claim target truth.")
        elif self.expected_mapping_version < 1 or not all(
            (self.expected_formal_bom_id, self.expected_target_version)
        ):
            raise MbomPublishContractError("MBOM update intent requires exact target truth.")

    @classmethod
    def from_expectation(
        cls,
        expectation: MbomMappingExpectation,
        *,
        node_global_id: UUID,
        node_snapshot: Mapping[str, object],
    ) -> "MbomAdapterNodeCommand":
        return cls(
            node_global_id=node_global_id,
            stable_line_key=expectation.stable_line_key,
            assembly_source_key=expectation.assembly_source_key,
            intent=expectation.intent,
            expected_mapping_version=expectation.mapping_version,
            expected_formal_bom_id=expectation.formal_bom_id,
            expected_target_version=expectation.target_version,
            node_snapshot=node_snapshot,
            node_snapshot_hash=canonical_hash(dict(node_snapshot)),
        )


@dataclass(frozen=True, slots=True)
class MbomAdapterCommand:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    topology_hash: str
    item_mapping_set_hash: str
    mbom_mapping_set_hash: str
    node_manifest_hash: str
    request_snapshot: Mapping[str, object]
    nodes: tuple[MbomAdapterNodeCommand, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(
            self.attempt_global_id, UUID
        ):
            raise MbomPublishContractError("MBOM adapter identities are invalid.")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise MbomPublishContractError("MBOM adapter attempt number is invalid.")
        for value, label in (
            (self.target_idempotency_key_hash, "target idempotency key hash"),
            (self.source_hash, "source hash"),
            (self.topology_hash, "topology hash"),
            (self.item_mapping_set_hash, "Item mapping-set hash"),
            (self.mbom_mapping_set_hash, "MBOM mapping-set hash"),
            (self.node_manifest_hash, "node manifest hash"),
        ):
            _hash(value, f"MBOM adapter {label}")
        if not isinstance(self.request_snapshot, Mapping):
            raise MbomPublishContractError("MBOM adapter request snapshot is invalid.")
        snapshot = dict(self.request_snapshot)
        source_snapshot = snapshot.get("source")
        source_hash = (
            source_snapshot.get("sourceHash")
            if isinstance(source_snapshot, Mapping)
            else snapshot.get("sourceHash")
        )
        topology_hash = (
            source_snapshot.get("topologyHash")
            if isinstance(source_snapshot, Mapping)
            else snapshot.get("topologyHash")
        )
        if (
            snapshot.get("globalId") != str(self.request_global_id)
            or source_hash != self.source_hash
            or topology_hash != self.topology_hash
            or snapshot.get("itemMappingSetHash") != self.item_mapping_set_hash
            or snapshot.get("mbomMappingSetHash") != self.mbom_mapping_set_hash
            or snapshot.get("targetIdempotencyKeyHash")
            != self.target_idempotency_key_hash
        ):
            raise MbomPublishContractError("MBOM adapter request binding is invalid.")
        if type(self.nodes) is not tuple or not self.nodes or not all(
            isinstance(node, MbomAdapterNodeCommand) for node in self.nodes
        ):
            raise MbomPublishContractError("MBOM adapter node manifest is invalid.")
        if tuple(node.stable_line_key for node in self.nodes) != tuple(
            sorted(node.stable_line_key for node in self.nodes)
        ) or len({node.stable_line_key for node in self.nodes}) != len(self.nodes):
            raise MbomPublishContractError("MBOM adapter node manifest is not canonical.")
        manifest = [
            {
                "globalId": str(node.node_global_id),
                "stableLineKey": node.stable_line_key,
                "nodeSnapshotHash": node.node_snapshot_hash,
            }
            for node in self.nodes
        ]
        if canonical_hash(
            {"requestGlobalId": str(self.request_global_id), "nodes": manifest}
        ) != self.node_manifest_hash:
            raise MbomPublishContractError("MBOM adapter node manifest hash is invalid.")

    def snapshot(self) -> dict[str, object]:
        return {
            "contractVersion": MBOM_ADAPTER_CONTRACT_VERSION,
            "operation": MBOM_PUBLISH_OPERATION,
            "requestGlobalId": str(self.request_global_id),
            "attemptGlobalId": str(self.attempt_global_id),
            "attemptNumber": self.attempt_number,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "sourceHash": self.source_hash,
            "topologyHash": self.topology_hash,
            "itemMappingSetHash": self.item_mapping_set_hash,
            "mbomMappingSetHash": self.mbom_mapping_set_hash,
            "nodeManifestHash": self.node_manifest_hash,
            "request": dict(self.request_snapshot),
            "nodes": [dict(node.node_snapshot) for node in self.nodes],
        }


@dataclass(frozen=True, slots=True)
class MbomAdapterNodeResponse:
    stable_line_key: str
    assembly_source_key: str
    response_hash: str
    http_status: int | None = None
    response_authenticated: bool = False
    response_contract_valid: bool = True
    business_validation_failed: bool = False
    timed_out: bool = False
    formal_bom_id: str | None = None
    target_version: str | None = None
    target_submission_state: MbomTargetSubmissionState | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stable_line_key, str) or not self.stable_line_key:
            raise MbomPublishContractError("MBOM adapter response node key is invalid.")
        _hash(self.assembly_source_key, "MBOM adapter response assembly source key")
        _hash(self.response_hash, "MBOM adapter response hash")
        if self.http_status is not None and (
            type(self.http_status) is not int or not 100 <= self.http_status <= 599
        ):
            raise MbomPublishContractError("MBOM adapter response status is invalid.")
        for value in (
            self.response_authenticated,
            self.response_contract_valid,
            self.business_validation_failed,
            self.timed_out,
        ):
            if type(value) is not bool:
                raise MbomPublishContractError("MBOM adapter response flags are invalid.")
        for value in (self.formal_bom_id, self.target_version):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 140
            ):
                raise MbomPublishContractError("MBOM adapter response target identity is invalid.")
        if self.target_submission_state is not None and not isinstance(
            self.target_submission_state, MbomTargetSubmissionState
        ):
            raise MbomPublishContractError("MBOM adapter response submission state is invalid.")


@dataclass(frozen=True, slots=True)
class MbomAdapterResponse:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    topology_hash: str
    node_manifest_hash: str
    response_hash: str
    nodes: tuple[MbomAdapterNodeResponse, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(
            self.attempt_global_id, UUID
        ):
            raise MbomPublishContractError("MBOM adapter response identities are invalid.")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise MbomPublishContractError("MBOM adapter response attempt number is invalid.")
        for value in (
            self.target_idempotency_key_hash,
            self.source_hash,
            self.topology_hash,
            self.node_manifest_hash,
            self.response_hash,
        ):
            _hash(value, "MBOM adapter response binding hash")
        if type(self.nodes) is not tuple or not self.nodes or not all(
            isinstance(node, MbomAdapterNodeResponse) for node in self.nodes
        ):
            raise MbomPublishContractError("MBOM adapter response node manifest is invalid.")


MbomAdapter = Callable[[MbomAdapterCommand], MbomAdapterResponse]


@dataclass(frozen=True, slots=True)
class MbomAdapterRegistration:
    resolver_path: str
    target_mode: MbomTargetMode
    operation: str
    adapter: MbomAdapter

    def __post_init__(self) -> None:
        if (
            not isinstance(self.resolver_path, str)
            or not self.resolver_path
            or self.resolver_path != self.resolver_path.strip()
            or len(self.resolver_path) > 255
            or not isinstance(self.target_mode, MbomTargetMode)
            or self.operation != MBOM_PUBLISH_OPERATION
            or not callable(self.adapter)
        ):
            raise MbomPublishContractError("MBOM adapter registration is invalid.")


class MbomAdapterRegistry:
    """Closed operation registry; an empty registry is the safe default."""

    def __init__(self, registrations: tuple[MbomAdapterRegistration, ...] = ()) -> None:
        if type(registrations) is not tuple or len(registrations) > 8:
            raise MbomPublishContractError("MBOM adapter registry is invalid.")
        values: dict[tuple[str, MbomTargetMode, str], MbomAdapter] = {}
        for registration in registrations:
            if not isinstance(registration, MbomAdapterRegistration):
                raise MbomPublishContractError("MBOM adapter registry is invalid.")
            key = (
                registration.resolver_path,
                registration.target_mode,
                registration.operation,
            )
            if key in values:
                raise MbomPublishContractError("MBOM adapter registration is ambiguous.")
            values[key] = registration.adapter
        self._values = values

    def resolve(self, profile: MbomExecutionProfile) -> MbomAdapter | None:
        if (
            not isinstance(profile, MbomExecutionProfile)
            or profile.target_mode is MbomTargetMode.MOCK
            or profile.adapter_resolver is None
        ):
            return None
        return self._values.get(
            (profile.adapter_resolver, profile.target_mode, MBOM_PUBLISH_OPERATION)
        )


@dataclass(frozen=True, slots=True)
class ClassifiedMbomAdapterResult:
    observations: tuple[MbomNodeObservation, ...]
    state: MbomPublishRequestState
    authority: MbomResultAuthority
    response_hash: str
    transport_disposition: str
    safe_error_code: str | None
    reconciliation_required: bool


def classify_mbom_adapter_response(
    *,
    profile: MbomExecutionProfile,
    command: MbomAdapterCommand,
    response: MbomAdapterResponse,
    observed_at: datetime,
) -> ClassifiedMbomAdapterResult:
    if not isinstance(profile, MbomExecutionProfile):
        raise MbomPublishContractError("MBOM execution profile is invalid.")
    request_binding = (
        response.request_global_id == command.request_global_id
        and response.attempt_global_id == command.attempt_global_id
        and response.attempt_number == command.attempt_number
        and response.target_idempotency_key_hash == command.target_idempotency_key_hash
        and response.source_hash == command.source_hash
        and response.topology_hash == command.topology_hash
        and response.node_manifest_hash == command.node_manifest_hash
    )
    expected = {node.stable_line_key: node for node in command.nodes}
    actual = {node.stable_line_key: node for node in response.nodes}
    unique_manifest = len(actual) == len(response.nodes) and set(actual) == set(expected)
    observations: list[MbomNodeObservation] = []
    for stable_key, node_command in expected.items():
        node = actual.get(stable_key)
        binding = bool(
            request_binding
            and unique_manifest
            and node is not None
            and node.assembly_source_key == node_command.assembly_source_key
        )
        if profile.target_mode is MbomTargetMode.SYNTHETIC and node is not None:
            valid = (
                binding
                and node.http_status is None
                and not node.response_authenticated
                and node.response_contract_valid
                and not node.business_validation_failed
                and not node.timed_out
                and node.formal_bom_id is None
                and node.target_version is None
                and node.target_submission_state is None
            )
            if valid:
                observations.append(
                    MbomNodeObservation(
                        stable_key,
                        node_command.assembly_source_key,
                        MbomNodeResultState.SYNTHETIC_VERIFIED,
                        MbomResultAuthority.SYNTHETIC,
                        False,
                        node.response_hash,
                    )
                )
                continue
        contract_valid = bool(
            node is not None and node.response_contract_valid and binding
        )
        if profile.target_mode is not MbomTargetMode.SANDBOX:
            contract_valid = False
        if node is not None and node.http_status is not None and 200 <= node.http_status < 300:
            contract_valid = bool(
                contract_valid
                and node.formal_bom_id
                and node.target_version
                and node.target_submission_state
            )
        if (
            node is not None
            and binding
            and node.response_authenticated
            and node.response_contract_valid
            and node.target_submission_state
            is MbomTargetSubmissionState.SUBMITTED_IMMUTABLE
        ):
            observations.append(
                MbomNodeObservation(
                    stable_key,
                    node_command.assembly_source_key,
                    MbomNodeResultState.BLOCKED_SUBMITTED,
                    MbomResultAuthority.NONE,
                    False,
                    node.response_hash,
                    fault_kind=MbomFaultKind.SUBMITTED_BOM,
                )
            )
            continue
        decision = classify_adapter_fault(
            adapter_boundary_crossed=True,
            timed_out=bool(node is not None and node.timed_out),
            http_status=(
                None
                if node is None
                else (422 if node.business_validation_failed else node.http_status)
            ),
            response_contract_valid=contract_valid,
            response_authenticated=bool(node is not None and node.response_authenticated),
        )
        successful = decision.fault_kind is MbomFaultKind.NONE
        node_state = (
            MbomNodeResultState.SUCCEEDED_AUTHORITATIVE
            if successful
            else {
                MbomPublishRequestState.FAILED_RETRYABLE: MbomNodeResultState.FAILED_RETRYABLE,
                MbomPublishRequestState.FAILED_FINAL: MbomNodeResultState.FAILED_FINAL,
                MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT: MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT,
            }[decision.request_state]
        )
        response_hash = (
            node.response_hash
            if node is not None
            else canonical_hash(
                {
                    "attemptGlobalId": str(command.attempt_global_id),
                    "stableLineKey": stable_key,
                    "safeErrorCode": "MBOM_PUBLISH_RESPONSE_NODE_MISSING",
                }
            )
        )
        observations.append(
            MbomNodeObservation(
                stable_key,
                node_command.assembly_source_key,
                node_state,
                (
                    MbomResultAuthority.AUTHORITATIVE_SANDBOX
                    if successful
                    else MbomResultAuthority.NONE
                ),
                bool(successful and node and node.response_authenticated),
                response_hash,
                formal_bom_id=node.formal_bom_id if successful and node else None,
                target_version=node.target_version if successful and node else None,
                target_submission_state=(
                    node.target_submission_state if successful and node else None
                ),
                fault_kind=decision.fault_kind,
            )
        )
    values = tuple(observations)
    state = aggregate_node_results(values)
    authority = (
        MbomResultAuthority.SYNTHETIC
        if all(value.authority is MbomResultAuthority.SYNTHETIC for value in values)
        else (
            MbomResultAuthority.AUTHORITATIVE_SANDBOX
            if all(
                value.authority is MbomResultAuthority.AUTHORITATIVE_SANDBOX
                for value in values
            )
            else MbomResultAuthority.NONE
        )
    )
    fault = next(
        (value.fault_kind for value in values if value.fault_kind is not MbomFaultKind.NONE),
        MbomFaultKind.NONE,
    )
    reconciliation = any(
        value.state in {
            MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT,
            MbomNodeResultState.OBSERVED_CONFLICT,
            MbomNodeResultState.BLOCKED_SUBMITTED,
        }
        for value in values
    )
    return ClassifiedMbomAdapterResult(
        observations=values,
        state=state,
        authority=authority,
        response_hash=response.response_hash,
        transport_disposition=(
            "synthetic_verified"
            if state is MbomPublishRequestState.SYNTHETIC_VERIFIED
            else (
                "observed_success"
                if state is MbomPublishRequestState.SUCCEEDED
                else (
                    "observed_partial"
                    if state is MbomPublishRequestState.PARTIALLY_SUCCEEDED
                    else "observed_failure"
                )
            )
        ),
        safe_error_code=(
            None if fault is MbomFaultKind.NONE else f"MBOM_PUBLISH_{fault.value.upper()}"
        ),
        reconciliation_required=reconciliation,
    )


def uncertain_mbom_adapter_result(
    *, command: MbomAdapterCommand, safe_error_code: str
) -> ClassifiedMbomAdapterResult:
    observations = tuple(
        MbomNodeObservation(
            node.stable_line_key,
            node.assembly_source_key,
            MbomNodeResultState.UNCERTAIN_AFTER_TIMEOUT,
            MbomResultAuthority.NONE,
            False,
            canonical_hash(
                {
                    "attemptGlobalId": str(command.attempt_global_id),
                    "safeErrorCode": safe_error_code,
                    "stableLineKey": node.stable_line_key,
                }
            ),
            fault_kind=MbomFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
        )
        for node in command.nodes
    )
    return ClassifiedMbomAdapterResult(
        observations,
        MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT,
        MbomResultAuthority.NONE,
        canonical_hash(
            {
                "attemptGlobalId": str(command.attempt_global_id),
                "safeErrorCode": safe_error_code,
                "state": MbomPublishRequestState.UNCERTAIN_AFTER_TIMEOUT.value,
            }
        ),
        "uncertain",
        safe_error_code,
        True,
    )


def failed_before_mbom_adapter_boundary_result(
    *, command: MbomAdapterCommand, safe_error_code: str
) -> ClassifiedMbomAdapterResult:
    observations = tuple(
        MbomNodeObservation(
            node.stable_line_key,
            node.assembly_source_key,
            MbomNodeResultState.FAILED_FINAL,
            MbomResultAuthority.NONE,
            False,
            canonical_hash(
                {
                    "attemptGlobalId": str(command.attempt_global_id),
                    "safeErrorCode": safe_error_code,
                    "stableLineKey": node.stable_line_key,
                }
            ),
            fault_kind=MbomFaultKind.TARGET_UNAVAILABLE,
        )
        for node in command.nodes
    )
    return ClassifiedMbomAdapterResult(
        observations,
        MbomPublishRequestState.FAILED_FINAL,
        MbomResultAuthority.NONE,
        canonical_hash(
            {
                "attemptGlobalId": str(command.attempt_global_id),
                "safeErrorCode": safe_error_code,
                "state": MbomPublishRequestState.FAILED_FINAL.value,
            }
        ),
        "failed_before_boundary",
        safe_error_code,
        False,
    )
