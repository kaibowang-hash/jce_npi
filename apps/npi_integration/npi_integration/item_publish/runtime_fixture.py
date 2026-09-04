from __future__ import annotations

import os
from uuid import UUID

from .adapters import (
    ItemAdapterCommand,
    ItemAdapterRegistration,
    ItemAdapterRegistry,
    ItemAdapterResponse,
)
from .config import ItemExecutionProfile
from .domain import ITEM_PUBLISH_OPERATION, ItemTargetMode, canonical_hash


_RUNTIME_MARKER = "npi-one-item-publish-disposable-v1"
_ADAPTER_PATH = "npi_integration.item_publish.runtime_fixture.synthetic_adapter"
_synthetic_adapter_calls = 0
_synthetic_adapter_session_users: list[str] = []


def resolve_profile(
    tenant_id: str,
    project_global_id: str,
) -> ItemExecutionProfile | None:
    if not _enabled():
        return None
    configured_project = os.environ.get("NPI_P8_03_RUNTIME_PROJECT_ID", "")
    requester = os.environ.get("NPI_P8_03_RUNTIME_REQUESTER", "")
    worker = os.environ.get("NPI_P8_03_RUNTIME_WORKER", "")
    if (
        project_global_id != configured_project
        or str(UUID(project_global_id)) != project_global_id
        or not tenant_id
        or not requester
        or not worker
        or requester == worker
    ):
        return None
    return ItemExecutionProfile(
        profile_id="item-synthetic-disposable-v1",
        profile_version=1,
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        target_mode=ItemTargetMode.SYNTHETIC,
        environment_code="disposable-test",
        requester_user_ids=(requester,),
        service_actor_user_id=worker,
        allowed_operations=(ITEM_PUBLISH_OPERATION,),
        adapter_resolver=_ADAPTER_PATH,
        synthetic_test_only=True,
        disposable_runtime_marker=True,
    )


def resolve_adapter_registry() -> ItemAdapterRegistry | None:
    if not _enabled():
        return None
    return ItemAdapterRegistry(
        (
            ItemAdapterRegistration(
                resolver_path=_ADAPTER_PATH,
                target_mode=ItemTargetMode.SYNTHETIC,
                operation=ITEM_PUBLISH_OPERATION,
                adapter=synthetic_adapter,
            ),
        )
    )


def synthetic_adapter(command: ItemAdapterCommand) -> ItemAdapterResponse:
    global _synthetic_adapter_calls
    if not _enabled() or not isinstance(command, ItemAdapterCommand):
        raise RuntimeError("Disposable Item adapter is unavailable.")
    # The disposable adapter is the only permitted execution boundary in this
    # fixture.  Recording the ambient session here proves that the worker
    # switched to, and stayed in, the frozen service actor scope without
    # contacting a target endpoint.
    import frappe

    worker = os.environ.get("NPI_P8_03_RUNTIME_WORKER", "")
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    if session_user != worker:
        raise RuntimeError("Disposable Item adapter session actor drifted.")
    _synthetic_adapter_session_users.append(str(session_user))
    _synthetic_adapter_calls += 1
    response_hash = canonical_hash(
        {
            "adapter": "network-free-synthetic-v1",
            "attemptGlobalId": str(command.attempt_global_id),
            "attemptNumber": command.attempt_number,
            "requestGlobalId": str(command.request_global_id),
            "sourceHash": command.source_hash,
            "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        }
    )
    return ItemAdapterResponse(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        target_idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        response_hash=response_hash,
    )


def synthetic_adapter_call_count() -> int:
    if not _enabled():
        raise RuntimeError("Disposable Item adapter is unavailable.")
    return _synthetic_adapter_calls


def synthetic_adapter_session_users() -> tuple[str, ...]:
    """Return the exact actors observed at the synthetic adapter boundary."""

    if not _enabled():
        raise RuntimeError("Disposable Item adapter is unavailable.")
    return tuple(_synthetic_adapter_session_users)


def _enabled() -> bool:
    return bool(
        os.environ.get("NPI_P8_03_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_03_RUNTIME_MARKER") == _RUNTIME_MARKER
    )
