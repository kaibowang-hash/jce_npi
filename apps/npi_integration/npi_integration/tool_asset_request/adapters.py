from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .config import ToolAssetExecutionProfile
from .execution_domain import (
    TOOL_ASSET_OWNED_FIELDS,
    ToolAssetExecutionContractError,
    ToolAssetExecutionOperation,
    ToolAssetExecutionRequestState,
    ToolAssetExecutionTargetMode,
    ToolAssetFaultKind,
    ToolAssetFieldResult,
    ToolAssetFieldResultState,
    ToolAssetMappingExpectation,
    ToolAssetResultAuthority,
    aggregate_field_results,
    canonical_hash,
    classify_adapter_fault,
)


TOOL_ASSET_ADAPTER_CONTRACT_VERSION = 1


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ToolAssetExecutionContractError(f"{label} is invalid.")
    return value


@dataclass(frozen=True, slots=True)
class ToolAssetAdapterCommand:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    operation: ToolAssetExecutionOperation
    target_idempotency_key_hash: str
    source_hash: str
    mapping_expectation: ToolAssetMappingExpectation
    request_snapshot: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(self.attempt_global_id, UUID):
            raise ToolAssetExecutionContractError("Tool Asset adapter identities are invalid.")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ToolAssetExecutionContractError("Tool Asset adapter attempt number is invalid.")
        if not isinstance(self.operation, ToolAssetExecutionOperation) or self.mapping_expectation.operation is not self.operation:
            raise ToolAssetExecutionContractError("Tool Asset adapter operation is invalid.")
        _hash(self.target_idempotency_key_hash, "Tool Asset target idempotency hash")
        _hash(self.source_hash, "Tool Asset source hash")
        if not isinstance(self.request_snapshot, Mapping):
            raise ToolAssetExecutionContractError("Tool Asset adapter request snapshot is invalid.")

    @property
    def snapshot(self) -> dict[str, object]:
        return {
            "contractVersion": TOOL_ASSET_ADAPTER_CONTRACT_VERSION,
            "operation": self.operation.value,
            "requestGlobalId": str(self.request_global_id),
            "attemptGlobalId": str(self.attempt_global_id),
            "attemptNumber": self.attempt_number,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "sourceHash": self.source_hash,
            "mappingExpectation": self.mapping_expectation.canonical_mapping(),
            "request": dict(self.request_snapshot),
            "ownedFieldsManifest": list(TOOL_ASSET_OWNED_FIELDS),
        }

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self.snapshot)


@dataclass(frozen=True, slots=True)
class ToolAssetAdapterFieldResponse:
    field_code: str
    response_hash: str
    http_status: int | None = None
    response_authenticated: bool = False
    response_contract_valid: bool = True
    business_validation_failed: bool = False
    timed_out: bool = False

    def __post_init__(self) -> None:
        if self.field_code not in TOOL_ASSET_OWNED_FIELDS:
            raise ToolAssetExecutionContractError("Tool Asset adapter response field is invalid.")
        _hash(self.response_hash, "Tool Asset field response hash")
        if self.http_status is not None and (type(self.http_status) is not int or not 100 <= self.http_status <= 599):
            raise ToolAssetExecutionContractError("Tool Asset adapter response status is invalid.")
        if any(type(v) is not bool for v in (self.response_authenticated, self.response_contract_valid, self.business_validation_failed, self.timed_out)):
            raise ToolAssetExecutionContractError("Tool Asset adapter response flags are invalid.")


@dataclass(frozen=True, slots=True)
class ToolAssetAdapterResponse:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    operation: ToolAssetExecutionOperation
    target_idempotency_key_hash: str
    source_hash: str
    response_hash: str
    fields: tuple[ToolAssetAdapterFieldResponse, ...]
    formal_asset_id: str | None = None
    target_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(self.attempt_global_id, UUID):
            raise ToolAssetExecutionContractError("Tool Asset adapter response identities are invalid.")
        if type(self.attempt_number) is not int or self.attempt_number < 1 or not isinstance(self.operation, ToolAssetExecutionOperation):
            raise ToolAssetExecutionContractError("Tool Asset adapter response binding is invalid.")
        for value in (self.target_idempotency_key_hash, self.source_hash, self.response_hash):
            _hash(value, "Tool Asset adapter response binding hash")
        if type(self.fields) is not tuple or len(self.fields) != len(TOOL_ASSET_OWNED_FIELDS) or {v.field_code for v in self.fields} != set(TOOL_ASSET_OWNED_FIELDS):
            raise ToolAssetExecutionContractError("Tool Asset adapter response field manifest is invalid.")
        for value in (self.formal_asset_id, self.target_version):
            if value is not None and (not isinstance(value, str) or not value or value != value.strip() or len(value) > 140):
                raise ToolAssetExecutionContractError("Tool Asset adapter target identity is invalid.")


ToolAssetAdapter = Callable[[ToolAssetAdapterCommand], ToolAssetAdapterResponse]


@dataclass(frozen=True, slots=True)
class ToolAssetAdapterRegistration:
    resolver_path: str
    target_mode: ToolAssetExecutionTargetMode
    operation: ToolAssetExecutionOperation
    adapter: ToolAssetAdapter

    def __post_init__(self) -> None:
        if not isinstance(self.resolver_path, str) or not self.resolver_path or not isinstance(self.target_mode, ToolAssetExecutionTargetMode) or not isinstance(self.operation, ToolAssetExecutionOperation) or not callable(self.adapter):
            raise ToolAssetExecutionContractError("Tool Asset adapter registration is invalid.")


class ToolAssetAdapterRegistry:
    """Closed operation registry; the safe default is empty."""

    def __init__(self, registrations: tuple[ToolAssetAdapterRegistration, ...] = ()) -> None:
        if type(registrations) is not tuple or len(registrations) > 8:
            raise ToolAssetExecutionContractError("Tool Asset adapter registry is invalid.")
        values: dict[tuple[str, ToolAssetExecutionTargetMode, ToolAssetExecutionOperation], ToolAssetAdapter] = {}
        for registration in registrations:
            if not isinstance(registration, ToolAssetAdapterRegistration):
                raise ToolAssetExecutionContractError("Tool Asset adapter registry is invalid.")
            key = (registration.resolver_path, registration.target_mode, registration.operation)
            if key in values:
                raise ToolAssetExecutionContractError("Tool Asset adapter registration is ambiguous.")
            values[key] = registration.adapter
        self._values = values

    def resolve(self, profile: ToolAssetExecutionProfile, operation: ToolAssetExecutionOperation) -> ToolAssetAdapter | None:
        if not isinstance(profile, ToolAssetExecutionProfile) or profile.target_mode is ToolAssetExecutionTargetMode.MOCK or profile.adapter_resolver is None:
            return None
        return self._values.get((profile.adapter_resolver, profile.target_mode, operation))


@dataclass(frozen=True, slots=True)
class ClassifiedToolAssetAdapterResult:
    fields: tuple[ToolAssetFieldResult, ...]
    state: ToolAssetExecutionRequestState
    authority: ToolAssetResultAuthority
    response_hash: str
    fault_kind: ToolAssetFaultKind
    formal_asset_id: str | None
    target_version: str | None
    transport_disposition: str
    safe_error_code: str | None
    reconciliation_required: bool


def classify_tool_asset_adapter_response(*, profile: ToolAssetExecutionProfile, command: ToolAssetAdapterCommand, response: ToolAssetAdapterResponse, observed_at: datetime) -> ClassifiedToolAssetAdapterResult:
    del observed_at
    binding = (
        response.request_global_id == command.request_global_id
        and response.attempt_global_id == command.attempt_global_id
        and response.attempt_number == command.attempt_number
        and response.operation is command.operation
        and response.target_idempotency_key_hash == command.target_idempotency_key_hash
        and response.source_hash == command.source_hash
    )
    actual = {value.field_code: value for value in response.fields}
    fields: list[ToolAssetFieldResult] = []
    for code in TOOL_ASSET_OWNED_FIELDS:
        value = actual[code]
        if profile.target_mode is ToolAssetExecutionTargetMode.SYNTHETIC:
            valid = binding and not value.timed_out and value.response_contract_valid and not value.response_authenticated and not value.business_validation_failed and value.http_status is None
            state = ToolAssetFieldResultState.SYNTHETIC_VERIFIED if valid else ToolAssetFieldResultState.FAILED_FINAL
            authority = ToolAssetResultAuthority.SYNTHETIC if valid else ToolAssetResultAuthority.NONE
            fault = ToolAssetFaultKind.NONE if valid else ToolAssetFaultKind.RESPONSE_CONTRACT_INVALID
        else:
            fault = classify_adapter_fault(adapter_boundary_crossed=True, timeout=value.timed_out, status_code=value.http_status, business_rejected=value.business_validation_failed, response_contract_valid=binding and value.response_contract_valid, response_authenticated=value.response_authenticated)
            if fault is ToolAssetFaultKind.NONE:
                state, authority = ToolAssetFieldResultState.SUCCEEDED_AUTHORITATIVE, ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX
            elif fault in {ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT, ToolAssetFaultKind.RESPONSE_CONTRACT_INVALID}:
                state, authority = ToolAssetFieldResultState.UNCERTAIN_AFTER_TIMEOUT, ToolAssetResultAuthority.NONE
            elif fault in {ToolAssetFaultKind.RATE_LIMITED, ToolAssetFaultKind.TARGET_SERVER_ERROR, ToolAssetFaultKind.TARGET_UNAVAILABLE}:
                state, authority = ToolAssetFieldResultState.FAILED_RETRYABLE, ToolAssetResultAuthority.NONE
            else:
                state, authority = ToolAssetFieldResultState.FAILED_FINAL, ToolAssetResultAuthority.NONE
        fields.append(ToolAssetFieldResult(code, state, authority, bool(authority is ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX), value.response_hash, fault))
    result_fields = tuple(fields)
    state = aggregate_field_results(result_fields)
    authoritative = state is ToolAssetExecutionRequestState.SUCCEEDED
    authority = ToolAssetResultAuthority.AUTHORITATIVE_SANDBOX if authoritative else (ToolAssetResultAuthority.SYNTHETIC if state is ToolAssetExecutionRequestState.SYNTHETIC_VERIFIED else ToolAssetResultAuthority.NONE)
    formal_id = response.formal_asset_id if authoritative else None
    version = response.target_version if authoritative else None
    if authoritative and (not formal_id or not version):
        return uncertain_tool_asset_adapter_result(command=command, safe_error_code="TOOL_ASSET_RESPONSE_IDENTITY_INVALID", response_hash=response.response_hash)
    faults = {value.fault_kind for value in result_fields if value.fault_kind is not ToolAssetFaultKind.NONE}
    fault = next(iter(faults)) if len(faults) == 1 else (ToolAssetFaultKind.RESPONSE_CONTRACT_INVALID if faults else ToolAssetFaultKind.NONE)
    return ClassifiedToolAssetAdapterResult(result_fields, state, authority, response.response_hash, fault, formal_id, version, "observed", None if not faults else "TOOL_ASSET_FIELD_RESULT_INCOMPLETE", state in {ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT, ToolAssetExecutionRequestState.PARTIALLY_SUCCEEDED})


def uncertain_tool_asset_adapter_result(*, command: ToolAssetAdapterCommand, safe_error_code: str, response_hash: str | None = None) -> ClassifiedToolAssetAdapterResult:
    digest = response_hash or canonical_hash({"requestGlobalId": str(command.request_global_id), "attemptGlobalId": str(command.attempt_global_id), "disposition": "uncertain"})
    fields = tuple(ToolAssetFieldResult(code, ToolAssetFieldResultState.UNCERTAIN_AFTER_TIMEOUT, ToolAssetResultAuthority.NONE, False, digest, ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT) for code in TOOL_ASSET_OWNED_FIELDS)
    return ClassifiedToolAssetAdapterResult(fields, ToolAssetExecutionRequestState.UNCERTAIN_AFTER_TIMEOUT, ToolAssetResultAuthority.NONE, digest, ToolAssetFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT, None, None, "uncertain", safe_error_code, True)


def failed_before_tool_asset_adapter_boundary_result(*, command: ToolAssetAdapterCommand, safe_error_code: str) -> ClassifiedToolAssetAdapterResult:
    digest = canonical_hash({"requestGlobalId": str(command.request_global_id), "attemptGlobalId": str(command.attempt_global_id), "disposition": "failed_before_boundary"})
    fields = tuple(ToolAssetFieldResult(code, ToolAssetFieldResultState.FAILED_FINAL, ToolAssetResultAuthority.NONE, False, digest, ToolAssetFaultKind.TARGET_UNAVAILABLE) for code in TOOL_ASSET_OWNED_FIELDS)
    return ClassifiedToolAssetAdapterResult(fields, ToolAssetExecutionRequestState.FAILED_FINAL, ToolAssetResultAuthority.NONE, digest, ToolAssetFaultKind.TARGET_UNAVAILABLE, None, None, "failed_before_boundary", safe_error_code, False)
