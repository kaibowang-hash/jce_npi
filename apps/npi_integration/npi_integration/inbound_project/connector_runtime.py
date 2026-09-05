from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime

import frappe

from .config import InboundProjectProfile, ProjectIntakePolicy, WebhookKeyDescriptor
from .domain import (
    ProjectSourceContractError,
    ProjectSourceEventType,
    ProjectSourceObjectType,
)
from .runtime_fixture import resolve_profile as resolve_disposable_profile
from .runtime_fixture import resolve_secret as resolve_disposable_secret


INGRESS_ENABLED_KEY = "npi_erp_project_ingress_enabled"
INGRESS_PROFILE_KEY = "npi_erp_project_ingress_profile"
INGRESS_SECRETS_ENV = "NPI_ERP_PROJECT_INGRESS_SECRETS"
_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "tenantId",
    "environmentCode",
    "serviceActorUserId",
    "ownerUserId",
    "templateGlobalId",
    "templateVersion",
    "projectType",
    "keyId",
    "secretReference",
    "validFrom",
    "validUntil",
}


def resolve_profile() -> InboundProjectProfile | None:
    disposable = resolve_disposable_profile()
    if disposable is not None:
        return disposable
    if frappe.conf.get(INGRESS_ENABLED_KEY) is not True:
        return None
    return load_project_ingress_profile(frappe.conf.get(INGRESS_PROFILE_KEY))


def resolve_secret(secret_reference: str) -> bytes:
    try:
        return resolve_disposable_secret(secret_reference)
    except (KeyError, RuntimeError):
        pass
    if frappe.conf.get(INGRESS_ENABLED_KEY) is not True:
        raise KeyError("Inbound Project secret is unavailable.")
    serialized = os.environ.get(INGRESS_SECRETS_ENV, "")
    if not serialized or len(serialized) > 65_536:
        raise KeyError("Inbound Project secret is unavailable.")
    try:
        values = json.loads(serialized, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise KeyError("Inbound Project secret is unavailable.") from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 8:
        raise KeyError("Inbound Project secret is unavailable.")
    secret = values.get(secret_reference)
    if (
        not isinstance(secret, str)
        or not 32 <= len(secret) <= 512
        or any(character in secret for character in "\r\n\x00")
    ):
        raise KeyError("Inbound Project secret is unavailable.")
    return secret.encode("utf-8")


def load_project_ingress_profile(value: object) -> InboundProjectProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise ProjectSourceContractError("Inbound Project profile shape is invalid.")
    key = WebhookKeyDescriptor(
        key_id=value["keyId"],
        secret_reference=value["secretReference"],
        valid_from=_utc_datetime(value["validFrom"], "validFrom"),
        valid_until=(
            _utc_datetime(value["validUntil"], "validUntil")
            if value["validUntil"] is not None
            else None
        ),
    )
    policy = ProjectIntakePolicy(
        source_object_type=ProjectSourceObjectType.PROJECT,
        template_global_id=value["templateGlobalId"],
        template_version=value["templateVersion"],
        project_type=value["projectType"],
        owner_user_id=value["ownerUserId"],
    )
    return InboundProjectProfile(
        profile_id=value["profileId"],
        version=value["profileVersion"],
        tenant_id=value["tenantId"],
        environment_code=value["environmentCode"],
        non_production_attested=True,
        enabled=True,
        trusted_tls_termination=True,
        service_actor_user_id=value["serviceActorUserId"],
        allowed_event_types=(ProjectSourceEventType.ERP_PROJECT_CREATED,),
        keys=(key,),
        policies=(policy,),
    )


def _utc_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise ProjectSourceContractError(f"Inbound Project {name} is invalid.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ProjectSourceContractError(
            f"Inbound Project {name} is invalid."
        ) from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ProjectSourceContractError(f"Inbound Project {name} is invalid.")
    return parsed


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = item
    return result
