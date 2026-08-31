from __future__ import annotations

import os
from uuid import UUID

import frappe

from .adapters import (
    AdapterCommand,
    AdapterRegistration,
    AdapterRegistry,
)
from .config import IntegrationProfile
from .domain import AdapterResponse, SUMMARY_OPERATION, TargetMode, canonical_hash


_RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
_PROFILE_ID = "engineering-change-synthetic-disposable-v1"
_ADAPTER_PATH = "npi_integration.engineering_change.runtime_fixture.synthetic_adapter"
_KEY_ID = "p9-01c-runtime"
_adapter_calls = 0


def resolve_profile(
    tenant_id: str,
    project_global_id: object,
) -> IntegrationProfile | None:
    if not _enabled():
        return None
    project = _environment("NPI_P9_01C_RUNTIME_PROJECT_ID")
    requester = _environment("NPI_P9_01C_RUNTIME_REQUESTER")
    worker = _environment("NPI_P9_01C_RUNTIME_WORKER")
    candidate_project = str(project_global_id)
    if (
        candidate_project != project
        or str(UUID(candidate_project)) != candidate_project
        or tenant_id != str(frappe.conf.get("npi_tenant_id") or "")
        or requester == worker
    ):
        return None
    return IntegrationProfile(
        profile_id=_PROFILE_ID,
        profile_version=1,
        tenant_id=tenant_id,
        project_global_id=project,
        target_mode=TargetMode.SYNTHETIC,
        requester_user_ids=(requester,),
        service_actor_user_id=worker,
        signing_key_ids=(_KEY_ID,),
        adapter_resolver=_ADAPTER_PATH,
        disposable_runtime_marker=True,
    )


def resolve_secret(key_id: str) -> bytes:
    if not _enabled() or key_id != _KEY_ID:
        raise KeyError("Engineering Change runtime secret is unavailable.")
    secret = _environment("NPI_P9_01C_RUNTIME_SECRET").encode("utf-8")
    if len(secret) < 32:
        raise KeyError("Engineering Change runtime secret is unavailable.")
    return secret


def resolve_adapter_registry() -> AdapterRegistry | None:
    if not _enabled():
        return None
    return AdapterRegistry(
        (
            AdapterRegistration(
                resolver_path=_ADAPTER_PATH,
                target_mode=TargetMode.SYNTHETIC,
                operation=SUMMARY_OPERATION,
                adapter=synthetic_adapter,
            ),
        )
    )


def synthetic_adapter(command: AdapterCommand) -> AdapterResponse:
    global _adapter_calls
    if not _enabled() or not isinstance(command, AdapterCommand):
        raise RuntimeError("Engineering Change runtime adapter is unavailable.")
    if str(getattr(frappe.session, "user", "")) != _environment(
        "NPI_P9_01C_RUNTIME_WORKER"
    ):
        raise RuntimeError("Engineering Change runtime actor drifted.")
    _adapter_calls += 1
    return AdapterResponse(
        http_status=200,
        response_hash=canonical_hash(
            {
                "adapter": "network-free-engineering-change-v1",
                "attemptGlobalId": str(command.attempt_global_id),
                "requestGlobalId": str(command.request_global_id),
                "sourceHash": command.source_hash,
            }
        ),
        authenticated=True,
        contract_valid=True,
    )


def synthetic_adapter_call_count() -> int:
    if not _enabled():
        raise RuntimeError("Engineering Change runtime adapter is unavailable.")
    return _adapter_calls


def _enabled() -> bool:
    return bool(
        os.environ.get("NPI_P9_01C_RUNTIME_ENABLED") == "1"
        and frappe.conf.get("npi_runtime_disposable_marker") == _RUNTIME_MARKER
    )


def _environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Engineering Change runtime configuration is incomplete.")
    return value
