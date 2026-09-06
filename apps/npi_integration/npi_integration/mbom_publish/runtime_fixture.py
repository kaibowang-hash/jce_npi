from __future__ import annotations

import os
from uuid import UUID

from .adapters import (
    MbomAdapterCommand,
    MbomAdapterNodeResponse,
    MbomAdapterRegistration,
    MbomAdapterRegistry,
    MbomAdapterResponse,
)
from .config import MbomExecutionProfile
from .domain import MBOM_PUBLISH_OPERATION, MbomTargetMode, canonical_hash


_RUNTIME_MARKER = "npi-one-mbom-publish-disposable-v1"
_ADAPTER_PATH = "npi_integration.mbom_publish.runtime_fixture.synthetic_adapter"
_synthetic_adapter_calls = 0
_synthetic_adapter_session_users: list[str] = []


def resolve_profile(tenant_id: str, project_global_id: str) -> MbomExecutionProfile | None:
    if not _enabled():
        return None
    configured_project = os.environ.get("NPI_P8_04_RUNTIME_PROJECT_ID", "")
    requester = os.environ.get("NPI_P8_04_RUNTIME_REQUESTER", "")
    worker = os.environ.get("NPI_P8_04_RUNTIME_WORKER", "")
    if (
        project_global_id != configured_project
        or str(UUID(project_global_id)) != project_global_id
        or not tenant_id
        or not requester
        or not worker
        or requester == worker
    ):
        return None
    return MbomExecutionProfile(
        profile_id="mbom-synthetic-disposable-v1",
        profile_version=1,
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        target_mode=MbomTargetMode.SYNTHETIC,
        environment_code="disposable-test",
        requester_user_ids=(requester,),
        service_actor_user_id=worker,
        projection_policy_id="mbom-synthetic-projection-v1",
        projection_policy_version=1,
        projection_policy_hash="7" * 64,
        allowed_operations=(MBOM_PUBLISH_OPERATION,),
        adapter_resolver=_ADAPTER_PATH,
        synthetic_test_only=True,
        disposable_runtime_marker=True,
    )


def resolve_adapter_registry() -> MbomAdapterRegistry | None:
    if not _enabled():
        return None
    return MbomAdapterRegistry(
        (
            MbomAdapterRegistration(
                _ADAPTER_PATH,
                MbomTargetMode.SYNTHETIC,
                MBOM_PUBLISH_OPERATION,
                synthetic_adapter,
            ),
        )
    )


def synthetic_adapter(command: MbomAdapterCommand) -> MbomAdapterResponse:
    global _synthetic_adapter_calls
    if not _enabled() or not isinstance(command, MbomAdapterCommand):
        raise RuntimeError("Disposable MBOM adapter is unavailable.")
    import frappe

    worker = os.environ.get("NPI_P8_04_RUNTIME_WORKER", "")
    session_user = getattr(getattr(frappe, "session", None), "user", None)
    if session_user != worker:
        raise RuntimeError("Disposable MBOM adapter session actor drifted.")
    _synthetic_adapter_session_users.append(str(session_user))
    _synthetic_adapter_calls += 1
    nodes = tuple(
        MbomAdapterNodeResponse(
            stable_line_key=node.stable_line_key,
            assembly_source_key=node.assembly_source_key,
            response_hash=canonical_hash(
                {
                    "adapter": "network-free-mbom-synthetic-v1",
                    "attemptGlobalId": str(command.attempt_global_id),
                    "stableLineKey": node.stable_line_key,
                }
            ),
        )
        for node in command.nodes
    )
    response_hash = canonical_hash(
        {
            "adapter": "network-free-mbom-synthetic-v1",
            "attemptGlobalId": str(command.attempt_global_id),
            "nodeResponseHashes": [node.response_hash for node in nodes],
            "requestGlobalId": str(command.request_global_id),
            "sourceHash": command.source_hash,
            "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        }
    )
    return MbomAdapterResponse(
        command.request_global_id,
        command.attempt_global_id,
        command.attempt_number,
        command.target_idempotency_key_hash,
        command.source_hash,
        command.topology_hash,
        command.node_manifest_hash,
        response_hash,
        nodes,
    )


def synthetic_adapter_call_count() -> int:
    if not _enabled():
        raise RuntimeError("Disposable MBOM adapter is unavailable.")
    return _synthetic_adapter_calls


def synthetic_adapter_session_users() -> tuple[str, ...]:
    if not _enabled():
        raise RuntimeError("Disposable MBOM adapter is unavailable.")
    return tuple(_synthetic_adapter_session_users)


def _enabled() -> bool:
    return bool(
        os.environ.get("NPI_P8_04_RUNTIME_ENABLED") == "1"
        and os.environ.get("NPI_P8_04_RUNTIME_MARKER") == _RUNTIME_MARKER
    )
