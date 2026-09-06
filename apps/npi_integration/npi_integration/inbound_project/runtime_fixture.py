from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import frappe

from .config import (
    InboundProjectProfile,
    ProjectIntakePolicy,
    WebhookKeyDescriptor,
)
from .domain import ProjectSourceEventType, ProjectSourceObjectType


_RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"
_OLD_REFERENCE = "secrets/p8-02-runtime-old"
_NEW_REFERENCE = "secrets/p8-02-runtime-new"


def resolve_profile() -> InboundProjectProfile | None:
    """Return a synthetic profile only in the guarded disposable Site runtime."""
    if (
        os.environ.get("NPI_P8_02_RUNTIME_ENABLED") != "1"
        or frappe.conf.get("npi_runtime_disposable_marker") != _RUNTIME_MARKER
    ):
        return None
    actor = _runtime_email("NPI_P8_02_RUNTIME_ACTOR")
    owner = _runtime_email("NPI_P8_02_RUNTIME_OWNER")
    tenant_id = str(frappe.conf.get("npi_tenant_id") or "")
    template_global_id = UUID(_required_environment("NPI_P8_02_RUNTIME_TEMPLATE_ID"))
    if not tenant_id:
        return None
    policies = tuple(
        ProjectIntakePolicy(
            source_object_type=object_type,
            template_global_id=template_global_id,
            template_version=1,
            project_type="new_tool",
            owner_user_id=owner,
        )
        for object_type in (
            ProjectSourceObjectType.QUOTATION,
            ProjectSourceObjectType.SALES_ORDER,
        )
    )
    return InboundProjectProfile(
        profile_id="p8-02-disposable-runtime",
        version=1,
        tenant_id=tenant_id,
        environment_code="disposable-test",
        non_production_attested=True,
        enabled=True,
        trusted_tls_termination=True,
        service_actor_user_id=actor,
        allowed_event_types=(
            ProjectSourceEventType.QUOTATION_SUBMITTED,
            ProjectSourceEventType.SALES_ORDER_SUBMITTED,
        ),
        keys=(
            WebhookKeyDescriptor(
                key_id="p8-runtime-old",
                secret_reference=_OLD_REFERENCE,
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                valid_until=datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
            ),
            WebhookKeyDescriptor(
                key_id="p8-runtime-new",
                secret_reference=_NEW_REFERENCE,
                valid_from=datetime(2026, 8, 1, tzinfo=UTC),
                valid_until=datetime(2027, 12, 31, 23, 59, 59, tzinfo=UTC),
            ),
        ),
        policies=policies,
    )


def resolve_secret(secret_reference: str) -> bytes:
    if (
        os.environ.get("NPI_P8_02_RUNTIME_ENABLED") != "1"
        or frappe.conf.get("npi_runtime_disposable_marker") != _RUNTIME_MARKER
    ):
        raise KeyError("Inbound Project runtime secret is unavailable.")
    variable = {
        _OLD_REFERENCE: "NPI_P8_02_RUNTIME_SECRET_OLD",
        _NEW_REFERENCE: "NPI_P8_02_RUNTIME_SECRET_NEW",
    }.get(secret_reference)
    if variable is None:
        raise KeyError("Inbound Project runtime secret is unavailable.")
    secret = _required_environment(variable).encode("utf-8")
    if len(secret) < 32:
        raise KeyError("Inbound Project runtime secret is unavailable.")
    return secret


def _runtime_email(name: str) -> str:
    value = _required_environment(name)
    if not value.endswith("@example.invalid"):
        raise RuntimeError("Inbound Project runtime identity is invalid.")
    return value


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("Inbound Project runtime configuration is incomplete.")
    return value
