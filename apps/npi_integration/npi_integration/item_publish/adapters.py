from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .config import ItemExecutionProfile
from .domain import (
    ITEM_PUBLISH_OPERATION,
    ItemAdapterObservation,
    ItemFaultKind,
    ItemPublishContractError,
    ItemPublishIntent,
    ItemPublishResultState,
    ItemResultAuthority,
    ItemTargetMode,
    canonical_hash,
    classify_adapter_fault,
)

ITEM_ADAPTER_CONTRACT_VERSION = 2
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class ItemAdapterCommand:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    actor_user_id: str
    source_snapshot: Mapping[str, object]
    intent: ItemPublishIntent
    expected_mapping_version: int
    expected_target_version: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(
            self.attempt_global_id, UUID
        ):
            raise ItemPublishContractError("Item adapter identities are invalid.")
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ItemPublishContractError("Item adapter attempt number is invalid.")
        for value in (self.target_idempotency_key_hash, self.source_hash):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ItemPublishContractError("Item adapter hash is invalid.")
        if (
            not isinstance(self.actor_user_id, str)
            or self.actor_user_id != self.actor_user_id.casefold()
            or len(self.actor_user_id) > 254
            or _ACTOR.fullmatch(self.actor_user_id) is None
            or self.actor_user_id in {"guest", "administrator"}
        ):
            raise ItemPublishContractError("Item adapter business actor is invalid.")
        if not isinstance(self.source_snapshot, Mapping):
            raise ItemPublishContractError("Item adapter source snapshot is invalid.")
        source = dict(self.source_snapshot)
        source_payload = dict(source)
        source_payload.pop("streamKeyHash", None)
        source_payload.pop("sourceHash", None)
        if (
            source.get("sourceHash") != self.source_hash
            or canonical_hash(source_payload) != self.source_hash
        ):
            raise ItemPublishContractError("Item adapter source hash is invalid.")
        if not isinstance(self.intent, ItemPublishIntent):
            raise ItemPublishContractError("Item adapter intent is invalid.")
        if (
            type(self.expected_mapping_version) is not int
            or self.expected_mapping_version < 0
        ):
            raise ItemPublishContractError(
                "Item adapter mapping expectation is invalid."
            )
        if self.expected_target_version is not None and (
            not isinstance(self.expected_target_version, str)
            or not self.expected_target_version
            or self.expected_target_version != self.expected_target_version.strip()
            or len(self.expected_target_version) > 140
        ):
            raise ItemPublishContractError(
                "Item adapter target version expectation is invalid."
            )

    def snapshot(self) -> dict[str, object]:
        return {
            "contractVersion": ITEM_ADAPTER_CONTRACT_VERSION,
            "operation": ITEM_PUBLISH_OPERATION,
            "requestGlobalId": str(self.request_global_id),
            "attemptGlobalId": str(self.attempt_global_id),
            "attemptNumber": self.attempt_number,
            "targetIdempotencyKeyHash": self.target_idempotency_key_hash,
            "sourceHash": self.source_hash,
            "actorUserId": self.actor_user_id,
            "source": dict(self.source_snapshot),
            "intent": self.intent.value,
            "expectedMappingVersion": self.expected_mapping_version,
            "expectedTargetVersion": self.expected_target_version,
        }


@dataclass(frozen=True, slots=True)
class ItemAdapterResponse:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    response_hash: str
    http_status: int | None = None
    response_authenticated: bool = False
    response_contract_valid: bool = True
    business_validation_failed: bool = False
    formal_item_code: str | None = None
    target_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(
            self.attempt_global_id, UUID
        ):
            raise ItemPublishContractError(
                "Item adapter response identities are invalid."
            )
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ItemPublishContractError(
                "Item adapter response attempt number is invalid."
            )
        for value in (
            self.target_idempotency_key_hash,
            self.source_hash,
            self.response_hash,
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ItemPublishContractError("Item adapter response hash is invalid.")
        if self.http_status is not None and (
            type(self.http_status) is not int or not 100 <= self.http_status <= 599
        ):
            raise ItemPublishContractError("Item adapter response status is invalid.")
        for value in (
            self.response_authenticated,
            self.response_contract_valid,
            self.business_validation_failed,
        ):
            if type(value) is not bool:
                raise ItemPublishContractError(
                    "Item adapter response flags are invalid."
                )
        for value in (self.formal_item_code, self.target_version):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or value != value.strip()
                or len(value) > 140
            ):
                raise ItemPublishContractError(
                    "Item adapter response target identity is invalid."
                )


ItemAdapter = Callable[[ItemAdapterCommand], ItemAdapterResponse]


@dataclass(frozen=True, slots=True)
class ItemAdapterRegistration:
    resolver_path: str
    target_mode: ItemTargetMode
    operation: str
    adapter: ItemAdapter

    def __post_init__(self) -> None:
        if (
            not isinstance(self.resolver_path, str)
            or not self.resolver_path
            or self.resolver_path != self.resolver_path.strip()
            or len(self.resolver_path) > 255
            or not isinstance(self.target_mode, ItemTargetMode)
            or self.operation != ITEM_PUBLISH_OPERATION
            or not callable(self.adapter)
        ):
            raise ItemPublishContractError("Item adapter registration is invalid.")


class ItemAdapterRegistry:
    """Closed operation registry; an empty registry is the safe default."""

    def __init__(
        self,
        registrations: tuple[ItemAdapterRegistration, ...] = (),
    ) -> None:
        if type(registrations) is not tuple or len(registrations) > 8:
            raise ItemPublishContractError("Item adapter registry is invalid.")
        values: dict[tuple[str, ItemTargetMode, str], ItemAdapter] = {}
        for registration in registrations:
            if not isinstance(registration, ItemAdapterRegistration):
                raise ItemPublishContractError("Item adapter registry is invalid.")
            key = (
                registration.resolver_path,
                registration.target_mode,
                registration.operation,
            )
            if key in values:
                raise ItemPublishContractError(
                    "Item adapter registration is ambiguous."
                )
            values[key] = registration.adapter
        self._values = values

    def resolve(self, profile: ItemExecutionProfile) -> ItemAdapter | None:
        if not isinstance(profile, ItemExecutionProfile):
            return None
        if profile.target_mode is ItemTargetMode.MOCK:
            return None
        resolver = profile.adapter_resolver
        if resolver is None:
            return None
        return self._values.get((resolver, profile.target_mode, ITEM_PUBLISH_OPERATION))


@dataclass(frozen=True, slots=True)
class ClassifiedItemAdapterResult:
    observation: ItemAdapterObservation
    transport_disposition: str
    target_status_code: int | None
    safe_error_code: str | None
    reconciliation_required: bool


def classify_item_adapter_response(
    *,
    profile: ItemExecutionProfile,
    command: ItemAdapterCommand,
    response: ItemAdapterResponse,
    observed_at: datetime,
) -> ClassifiedItemAdapterResult:
    if not isinstance(profile, ItemExecutionProfile):
        raise ItemPublishContractError("Item execution profile is invalid.")
    binding_matches = (
        response.request_global_id == command.request_global_id
        and response.attempt_global_id == command.attempt_global_id
        and response.attempt_number == command.attempt_number
        and response.target_idempotency_key_hash == command.target_idempotency_key_hash
        and response.source_hash == command.source_hash
    )
    if profile.target_mode is ItemTargetMode.SYNTHETIC:
        valid = (
            binding_matches
            and response.http_status is None
            and not response.response_authenticated
            and response.response_contract_valid
            and not response.business_validation_failed
            and response.formal_item_code is None
            and response.target_version is None
        )
        if valid:
            observation = ItemAdapterObservation(
                request_global_id=command.request_global_id,
                attempt_global_id=command.attempt_global_id,
                attempt_number=command.attempt_number,
                idempotency_key_hash=command.target_idempotency_key_hash,
                source_hash=command.source_hash,
                expected_target_version=command.expected_target_version,
                state=ItemPublishResultState.SYNTHETIC_VERIFIED,
                authority=ItemResultAuthority.SYNTHETIC,
                response_authenticated=False,
                response_hash=response.response_hash,
                observed_at=observed_at,
            )
            return ClassifiedItemAdapterResult(
                observation,
                "synthetic_verified",
                None,
                None,
                False,
            )

    contract_valid = response.response_contract_valid and binding_matches
    if profile.target_mode is not ItemTargetMode.SANDBOX:
        contract_valid = False
    if response.http_status is not None and 200 <= response.http_status < 300:
        contract_valid = bool(
            contract_valid and response.formal_item_code and response.target_version
        )
    classification = classify_adapter_fault(
        adapter_boundary_crossed=True,
        http_status=response.http_status,
        business_validation_failed=response.business_validation_failed,
        response_contract_valid=contract_valid,
        response_authenticated=response.response_authenticated,
    )
    authority = (
        ItemResultAuthority.AUTHORITATIVE_SANDBOX
        if response.response_authenticated
        and profile.target_mode is ItemTargetMode.SANDBOX
        else ItemResultAuthority.NONE
    )
    successful = classification.fault_kind is ItemFaultKind.NONE
    observation = ItemAdapterObservation(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        expected_target_version=command.expected_target_version,
        state=ItemPublishResultState(classification.request_state.value),
        authority=authority,
        response_authenticated=response.response_authenticated,
        response_hash=response.response_hash,
        observed_at=observed_at,
        formal_item_code=(response.formal_item_code if successful else None),
        target_version=(response.target_version if successful else None),
        fault_kind=classification.fault_kind,
    )
    safe_error = (
        None
        if successful
        else f"ITEM_PUBLISH_{classification.fault_kind.value.upper()}"
    )
    return ClassifiedItemAdapterResult(
        observation=observation,
        transport_disposition=(
            "observed_success" if successful else "observed_failure"
        ),
        target_status_code=response.http_status,
        safe_error_code=safe_error,
        reconciliation_required=classification.reconciliation_required,
    )


def uncertain_item_adapter_result(
    *,
    command: ItemAdapterCommand,
    observed_at: datetime,
    safe_error_code: str,
) -> ClassifiedItemAdapterResult:
    response_hash = canonical_hash(
        {
            "requestGlobalId": str(command.request_global_id),
            "attemptGlobalId": str(command.attempt_global_id),
            "attemptNumber": command.attempt_number,
            "safeErrorCode": safe_error_code,
            "state": ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT.value,
        }
    )
    observation = ItemAdapterObservation(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        expected_target_version=command.expected_target_version,
        state=ItemPublishResultState.UNCERTAIN_AFTER_TIMEOUT,
        authority=ItemResultAuthority.NONE,
        response_authenticated=False,
        response_hash=response_hash,
        observed_at=observed_at,
        fault_kind=ItemFaultKind.TIMEOUT_AFTER_POSSIBLE_COMMIT,
    )
    return ClassifiedItemAdapterResult(
        observation=observation,
        transport_disposition="uncertain",
        target_status_code=None,
        safe_error_code=safe_error_code,
        reconciliation_required=True,
    )


def failed_before_adapter_boundary_result(
    *,
    command: ItemAdapterCommand,
    observed_at: datetime,
    safe_error_code: str,
    retryable: bool = False,
) -> ClassifiedItemAdapterResult:
    state = (
        ItemPublishResultState.FAILED_RETRYABLE
        if retryable
        else ItemPublishResultState.FAILED_FINAL
    )
    response_hash = canonical_hash(
        {
            "requestGlobalId": str(command.request_global_id),
            "attemptGlobalId": str(command.attempt_global_id),
            "attemptNumber": command.attempt_number,
            "safeErrorCode": safe_error_code,
            "state": state.value,
        }
    )
    observation = ItemAdapterObservation(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        expected_target_version=command.expected_target_version,
        state=state,
        authority=ItemResultAuthority.NONE,
        response_authenticated=False,
        response_hash=response_hash,
        observed_at=observed_at,
        fault_kind=ItemFaultKind.TARGET_UNAVAILABLE,
    )
    return ClassifiedItemAdapterResult(
        observation=observation,
        transport_disposition="failed_before_boundary",
        target_status_code=None,
        safe_error_code=safe_error_code,
        reconciliation_required=False,
    )
