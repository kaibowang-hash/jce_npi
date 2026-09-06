from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from .config import IntegrationProfile
from .domain import AdapterResponse, EngineeringChangeIntegrationError, SUMMARY_OPERATION, SummaryRequest, TargetMode


@dataclass(frozen=True, slots=True)
class AdapterCommand:
    request_global_id: UUID
    attempt_global_id: UUID
    attempt_number: int
    target_idempotency_key_hash: str
    source_hash: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.request_global_id, UUID) or not isinstance(self.attempt_global_id, UUID) or type(self.attempt_number) is not int or self.attempt_number < 1:
            raise EngineeringChangeIntegrationError("Adapter command identity is invalid.")
        if not isinstance(self.payload, Mapping) or self.payload.get("source_hash") != self.source_hash:
            raise EngineeringChangeIntegrationError("Adapter command source is invalid.")


Adapter = Callable[[AdapterCommand], AdapterResponse]


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    resolver_path: str
    target_mode: TargetMode
    operation: str
    adapter: Adapter

    def __post_init__(self) -> None:
        if self.operation != SUMMARY_OPERATION or not callable(self.adapter):
            raise EngineeringChangeIntegrationError("Adapter registration is invalid.")


class AdapterRegistry:
    def __init__(self, registrations: tuple[AdapterRegistration, ...] = ()) -> None:
        if type(registrations) is not tuple or len(registrations) > 8:
            raise EngineeringChangeIntegrationError("Adapter registry is invalid.")
        self._values: dict[tuple[str, TargetMode, str], Adapter] = {}
        for registration in registrations:
            if not isinstance(registration, AdapterRegistration):
                raise EngineeringChangeIntegrationError("Adapter registry is invalid.")
            key = (registration.resolver_path, registration.target_mode, registration.operation)
            if key in self._values:
                raise EngineeringChangeIntegrationError("Adapter registration is ambiguous.")
            self._values[key] = registration.adapter

    def resolve(self, profile: IntegrationProfile) -> Adapter | None:
        if not isinstance(profile, IntegrationProfile) or profile.target_mode is TargetMode.DISABLED or profile.adapter_resolver is None:
            return None
        return self._values.get((profile.adapter_resolver, profile.target_mode, SUMMARY_OPERATION))


def command_for(request: SummaryRequest, *, attempt_global_id: UUID, attempt_number: int) -> AdapterCommand:
    return AdapterCommand(
        request_global_id=request.global_id,
        attempt_global_id=attempt_global_id,
        attempt_number=attempt_number,
        target_idempotency_key_hash=request.idempotency_key_hash,
        source_hash=request.summary.source_hash,
        payload=request.event_payload(),
    )
