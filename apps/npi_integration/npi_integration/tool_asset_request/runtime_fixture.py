from __future__ import annotations

import os
from uuid import UUID

import frappe

from .adapters import (
    ToolAssetAdapterFieldResponse,
    ToolAssetAdapterRegistration,
    ToolAssetAdapterRegistry,
    ToolAssetAdapterResponse,
)
from .config import ToolAssetExecutionProfile
from .execution_domain import TOOL_ASSET_OWNED_FIELDS, ToolAssetExecutionOperation, ToolAssetExecutionTargetMode, canonical_hash


_RUNTIME_MARKER = "npi-one-tool-asset-disposable-v1"
_ADAPTER_PATH = "npi_integration.tool_asset_request.runtime_fixture.synthetic_adapter"
_CALLS = 0


def resolve_profile(tenant_id: str, project_global_id: str) -> ToolAssetExecutionProfile | None:
    if not _enabled():
        return None
    return ToolAssetExecutionProfile(
        profile_id="tool-asset-disposable-synthetic-v1", profile_version=1,
        tenant_id=tenant_id, project_global_id=str(UUID(project_global_id)),
        target_mode=ToolAssetExecutionTargetMode.SYNTHETIC, environment_code="testing",
        requester_user_ids=(os.environ["NPI_TOOL_ASSET_REQUESTER_USER"],),
        service_actor_user_id=os.environ["NPI_TOOL_ASSET_WORKER_USER"],
        projection_policy_id="tool-asset-synthetic-projection-v1", projection_policy_version=1,
        projection_policy_hash=canonical_hash({"authority":"synthetic","formalAssetIds":False}),
        allowed_operations=("create_tool_asset", "update_tool_asset"), adapter_resolver=_ADAPTER_PATH,
        synthetic_test_only=True, disposable_runtime_marker=True,
    )


def resolve_adapter_registry() -> ToolAssetAdapterRegistry | None:
    if not _enabled():
        return None
    return ToolAssetAdapterRegistry(tuple(ToolAssetAdapterRegistration(_ADAPTER_PATH, ToolAssetExecutionTargetMode.SYNTHETIC, operation, synthetic_adapter) for operation in ToolAssetExecutionOperation))


def synthetic_adapter(command):
    global _CALLS
    if not _enabled() or getattr(getattr(frappe, "session", None), "user", None) != os.environ.get("NPI_TOOL_ASSET_WORKER_USER"):
        raise RuntimeError("Tool Asset synthetic adapter scope is invalid.")
    _CALLS += 1
    fields = tuple(ToolAssetAdapterFieldResponse(code, canonical_hash({"fieldCode":code,"attemptGlobalId":str(command.attempt_global_id)})) for code in TOOL_ASSET_OWNED_FIELDS)
    return ToolAssetAdapterResponse(command.request_global_id, command.attempt_global_id, command.attempt_number, command.operation, command.target_idempotency_key_hash, command.source_hash, canonical_hash({"attemptGlobalId":str(command.attempt_global_id),"fieldCount":len(fields)}), fields)


def synthetic_adapter_call_count() -> int:
    return _CALLS


def _enabled() -> bool:
    return os.environ.get("NPI_TOOL_ASSET_RUNTIME_MARKER") == _RUNTIME_MARKER and all(os.environ.get(name) for name in ("NPI_TOOL_ASSET_REQUESTER_USER", "NPI_TOOL_ASSET_WORKER_USER"))
