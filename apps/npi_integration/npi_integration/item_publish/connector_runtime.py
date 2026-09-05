from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .adapters import (
    ITEM_ADAPTER_CONTRACT_VERSION,
    ItemAdapterCommand,
    ItemAdapterRegistration,
    ItemAdapterRegistry,
    ItemAdapterResponse,
)
from .config import ItemExecutionProfile
from .domain import (
    ITEM_PUBLISH_OPERATION,
    ItemPublishContractError,
    ItemTargetMode,
    canonical_hash,
)
from .runtime_fixture import (
    resolve_adapter_registry as resolve_synthetic_adapter_registry,
)
from .runtime_fixture import resolve_profile as resolve_synthetic_profile

SANDBOX_ENABLED_KEY = "npi_item_publish_sandbox_enabled"
SANDBOX_PROFILES_KEY = "npi_item_publish_sandbox_profiles"
SANDBOX_SECRETS_ENV = "NPI_ITEM_PUBLISH_SANDBOX_SECRETS"
SANDBOX_ADAPTER_PATH = "npi_integration.item_publish.connector_runtime.sandbox_adapter"
ITEM_METHOD_PATH = "/api/method/npi_erpnext_connector.item_api.publish_item"
SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_RESPONSE_BYTES = 262_144
MAX_CLOCK_SKEW_SECONDS = 300

_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "tenantId",
    "projectGlobalId",
    "environmentCode",
    "requesterUserIds",
    "serviceActorUserId",
    "baseUrl",
    "allowedHostnames",
    "secretReference",
    "connectTimeoutSeconds",
    "readTimeoutSeconds",
}
_CREDENTIAL_KEYS = {"apiKey", "apiSecret"}
_API_KEY = re.compile(r"^[A-Za-z0-9]{8,128}$")
_API_SECRET = re.compile(r"^[^\s\x00-\x1f\x7f]{8,512}$")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class SandboxCredential:
    api_key: str
    api_secret: str

    @property
    def authorization_value(self) -> str:
        return f"token {self.api_key}:{self.api_secret}"

    @property
    def signing_secret(self) -> str:
        return f"{self.api_key}:{self.api_secret}"


def resolve_profile(
    tenant_id: str,
    project_global_id: str,
) -> ItemExecutionProfile | None:
    synthetic = resolve_synthetic_profile(tenant_id, project_global_id)
    if synthetic is not None:
        return synthetic
    import frappe

    return load_sandbox_profile(frappe.conf, tenant_id, project_global_id)


def resolve_adapter_registry() -> ItemAdapterRegistry | None:
    synthetic = resolve_synthetic_adapter_registry()
    if synthetic is not None:
        return synthetic
    import frappe

    if _sandbox_enabled(frappe.conf):
        return ItemAdapterRegistry(
            (
                ItemAdapterRegistration(
                    resolver_path=SANDBOX_ADAPTER_PATH,
                    target_mode=ItemTargetMode.SANDBOX,
                    operation=ITEM_PUBLISH_OPERATION,
                    adapter=sandbox_adapter,
                ),
            )
        )
    return None


def load_sandbox_profile(
    configuration: object,
    tenant_id: str,
    project_global_id: str,
) -> ItemExecutionProfile | None:
    if not _sandbox_enabled(configuration):
        return None
    if not hasattr(configuration, "get"):
        raise ItemPublishContractError("Sandbox Item configuration is unavailable.")
    raw_profiles = configuration.get(SANDBOX_PROFILES_KEY)
    if (
        isinstance(raw_profiles, (str, bytes))
        or not isinstance(raw_profiles, Sequence)
        or not 1 <= len(raw_profiles) <= 32
    ):
        raise ItemPublishContractError("Sandbox Item profiles are invalid.")
    matches: list[ItemExecutionProfile] = []
    for raw_profile in raw_profiles:
        profile = _profile(raw_profile)
        if (
            profile.tenant_id == tenant_id
            and profile.project_global_id == project_global_id
        ):
            matches.append(profile)
    if len(matches) > 1:
        raise ItemPublishContractError("Sandbox Item profile resolution is ambiguous.")
    return matches[0] if matches else None


def sandbox_adapter(command: ItemAdapterCommand) -> ItemAdapterResponse:
    if not isinstance(command, ItemAdapterCommand):
        raise ItemPublishContractError("Sandbox Item command is invalid.")
    import frappe

    source = command.source_snapshot
    profile = load_sandbox_profile(
        frappe.conf,
        str(source.get("tenantId", "")),
        str(source.get("projectGlobalId", "")),
    )
    if profile is None:
        raise ItemPublishContractError("Sandbox Item profile is unavailable.")
    actor = str(getattr(getattr(frappe, "session", None), "user", "") or "")
    if actor != profile.service_actor_user_id:
        raise ItemPublishContractError("Sandbox Item service actor drifted.")
    credential = load_sandbox_credential(
        profile.secret_reference,
        os.environ.get(SANDBOX_SECRETS_ENV, ""),
    )
    return execute_sandbox_item(command, profile, credential)


def load_sandbox_credential(
    secret_reference: str | None,
    serialized_secrets: str,
) -> SandboxCredential:
    if not isinstance(secret_reference, str) or not secret_reference:
        raise ItemPublishContractError("Sandbox Item credential reference is invalid.")
    if not isinstance(serialized_secrets, str) or len(serialized_secrets) > 65_536:
        raise ItemPublishContractError("Sandbox Item credentials are unavailable.")
    try:
        values = json.loads(serialized_secrets, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ItemPublishContractError(
            "Sandbox Item credentials are unavailable."
        ) from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise ItemPublishContractError("Sandbox Item credentials are unavailable.")
    raw = values.get(secret_reference)
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise ItemPublishContractError("Sandbox Item credential is unavailable.")
    api_key = raw["apiKey"]
    api_secret = raw["apiSecret"]
    if (
        not isinstance(api_key, str)
        or _API_KEY.fullmatch(api_key) is None
        or not isinstance(api_secret, str)
        or _API_SECRET.fullmatch(api_secret) is None
        or len(f"{api_key}:{api_secret}") < 24
    ):
        raise ItemPublishContractError("Sandbox Item credential is invalid.")
    return SandboxCredential(api_key, api_secret)


def execute_sandbox_item(
    command: ItemAdapterCommand,
    profile: ItemExecutionProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> ItemAdapterResponse:
    if (
        not isinstance(command, ItemAdapterCommand)
        or not isinstance(profile, ItemExecutionProfile)
        or profile.target_mode is not ItemTargetMode.SANDBOX
        or profile.adapter_resolver != SANDBOX_ADAPTER_PATH
        or not isinstance(credential, SandboxCredential)
    ):
        raise ItemPublishContractError("Sandbox Item adapter inputs are invalid.")
    source = command.source_snapshot
    if (
        source.get("tenantId") != profile.tenant_id
        or source.get("projectGlobalId") != profile.project_global_id
    ):
        raise ItemPublishContractError(
            "Sandbox Item command scope does not match its profile."
        )
    body = _canonical_json(command.snapshot()).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _request_signature(
        credential.signing_secret,
        ITEM_METHOD_PATH,
        timestamp,
        body,
    )
    base_url = profile.base_url
    if not isinstance(base_url, str):
        raise ItemPublishContractError("Sandbox Item base URL is invalid.")
    endpoint = f"{base_url.rstrip('/')}{ITEM_METHOD_PATH}"
    if session_factory is None:
        import requests

        session_factory = requests.Session
    session = session_factory()
    session.trust_env = False
    response = None
    try:
        response = session.post(
            endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": credential.authorization_value,
                "Content-Type": "application/json; charset=utf-8",
                "X-NPI-Signature": signature,
                "X-NPI-Timestamp": timestamp,
                "X-NPI-Trace-ID": f"item-{command.attempt_global_id}",
            },
            allow_redirects=False,
            timeout=(
                profile.connect_timeout_seconds,
                profile.read_timeout_seconds,
            ),
            stream=True,
        )
        response_body = _bounded_response(response)
        return _decode_response(
            command,
            response.status_code,
            response.headers,
            response_body,
            credential.signing_secret,
            now=int(clock()),
        )
    finally:
        if response is not None:
            response.close()
        session.close()


def _profile(value: object) -> ItemExecutionProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise ItemPublishContractError("Sandbox Item profile shape is invalid.")
    requesters = _strings(value["requesterUserIds"], "requesterUserIds", maximum=100)
    hostnames = _strings(value["allowedHostnames"], "allowedHostnames", maximum=8)
    return ItemExecutionProfile(
        profile_id=value["profileId"],
        profile_version=value["profileVersion"],
        tenant_id=value["tenantId"],
        project_global_id=value["projectGlobalId"],
        target_mode=ItemTargetMode.SANDBOX,
        environment_code=value["environmentCode"],
        requester_user_ids=requesters,
        service_actor_user_id=value["serviceActorUserId"],
        allowed_operations=(ITEM_PUBLISH_OPERATION,),
        adapter_resolver=SANDBOX_ADAPTER_PATH,
        base_url=value["baseUrl"],
        allowed_hostnames=hostnames,
        secret_reference=value["secretReference"],
        response_authentication="hmac-sha256-v1",
        connect_timeout_seconds=value["connectTimeoutSeconds"],
        read_timeout_seconds=value["readTimeoutSeconds"],
        non_production_attested=True,
    )


def _sandbox_enabled(configuration: object) -> bool:
    return bool(
        hasattr(configuration, "get") and configuration.get(SANDBOX_ENABLED_KEY) is True
    )


def _strings(value: object, label: str, *, maximum: int) -> tuple[str, ...]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not 1 <= len(value) <= maximum
        or any(not isinstance(item, str) for item in value)
    ):
        raise ItemPublishContractError(f"Sandbox Item {label} is invalid.")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise ItemPublishContractError(f"Sandbox Item {label} is invalid.")
    return result


def _request_signature(secret: str, path: str, timestamp: str, body: bytes) -> str:
    message = "\n".join(
        (
            SIGNATURE_VERSION,
            "POST",
            path,
            timestamp,
            hashlib.sha256(body).hexdigest(),
        )
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _bounded_response(response: Any) -> bytes:
    raw_length = response.headers.get("Content-Length")
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError) as error:
            raise ItemPublishContractError(
                "Sandbox Item response length is invalid."
            ) from error
        if content_length < 0 or content_length > MAX_RESPONSE_BYTES:
            raise ItemPublishContractError("Sandbox Item response is too large.")
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise ItemPublishContractError("Sandbox Item response body is invalid.")
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise ItemPublishContractError("Sandbox Item response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(
    command: ItemAdapterCommand,
    http_status: object,
    headers: object,
    body: bytes,
    secret: str,
    *,
    now: int,
) -> ItemAdapterResponse:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise ItemPublishContractError("Sandbox Item HTTP status is invalid.")
    content_type = (
        str(headers.get("Content-Type", "")) if hasattr(headers, "get") else ""
    )
    if not content_type.casefold().startswith("application/json"):
        return _invalid_response(command, http_status, fallback_hash)
    try:
        envelope = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _invalid_response(command, http_status, fallback_hash)
    if not isinstance(envelope, Mapping) or set(envelope) != {"message"}:
        return _invalid_response(command, http_status, fallback_hash)
    message = envelope["message"]
    if not isinstance(message, Mapping):
        return _invalid_response(command, http_status, fallback_hash)
    payload = dict(message)
    signature = payload.pop("responseSignature", None)
    authenticated = _response_signature_is_valid(payload, signature, secret, now=now)
    if not authenticated:
        return _invalid_response(command, http_status, fallback_hash)
    expected_keys = {
        "contractVersion",
        "operation",
        "requestGlobalId",
        "attemptGlobalId",
        "attemptNumber",
        "targetIdempotencyKeyHash",
        "sourceHash",
        "httpStatus",
        "formalItemCode",
        "targetVersion",
        "mappingVersion",
        "exactReplay",
        "errorCode",
        "responseHash",
        "signatureVersion",
        "signedAt",
    }
    core = dict(payload)
    response_hash = core.pop("responseHash", None)
    core.pop("signatureVersion", None)
    core.pop("signedAt", None)
    valid = bool(
        set(payload) == expected_keys
        and payload["contractVersion"] == ITEM_ADAPTER_CONTRACT_VERSION
        and payload["operation"] == ITEM_PUBLISH_OPERATION
        and payload["requestGlobalId"] == str(command.request_global_id)
        and payload["attemptGlobalId"] == str(command.attempt_global_id)
        and payload["attemptNumber"] == command.attempt_number
        and payload["targetIdempotencyKeyHash"] == command.target_idempotency_key_hash
        and payload["sourceHash"] == command.source_hash
        and payload["httpStatus"] == http_status
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
    )
    success = 200 <= http_status < 300
    formal_item_code = payload.get("formalItemCode")
    target_version = payload.get("targetVersion")
    mapping_version = payload.get("mappingVersion")
    error_code = payload.get("errorCode")
    exact_replay = payload.get("exactReplay")
    if success:
        valid = bool(
            valid
            and isinstance(formal_item_code, str)
            and formal_item_code
            and len(formal_item_code) <= 140
            and isinstance(target_version, str)
            and target_version
            and len(target_version) <= 140
            and type(mapping_version) is int
            and mapping_version >= 1
            and type(exact_replay) is bool
            and error_code is None
        )
    else:
        valid = bool(
            valid
            and formal_item_code is None
            and target_version is None
            and mapping_version is None
            and exact_replay is False
            and isinstance(error_code, str)
            and _ERROR_CODE.fullmatch(error_code) is not None
        )
    return ItemAdapterResponse(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        target_idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        response_hash=(
            response_hash
            if isinstance(response_hash, str) and _HASH.fullmatch(response_hash)
            else fallback_hash
        ),
        http_status=http_status,
        response_authenticated=True,
        response_contract_valid=valid,
        business_validation_failed=bool(
            400 <= http_status < 500 and http_status != 429
        ),
        formal_item_code=formal_item_code if valid and success else None,
        target_version=target_version if valid and success else None,
    )


def _response_signature_is_valid(
    payload: Mapping[str, object],
    signature: object,
    secret: str,
    *,
    now: int,
) -> bool:
    if (
        not isinstance(signature, str)
        or _HASH.fullmatch(signature) is None
        or payload.get("signatureVersion") != SIGNATURE_VERSION
        or type(payload.get("signedAt")) is not int
        or abs(now - int(payload["signedAt"])) > MAX_CLOCK_SKEW_SECONDS
    ):
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _invalid_response(
    command: ItemAdapterCommand,
    http_status: int,
    response_hash: str,
) -> ItemAdapterResponse:
    return ItemAdapterResponse(
        request_global_id=command.request_global_id,
        attempt_global_id=command.attempt_global_id,
        attempt_number=command.attempt_number,
        target_idempotency_key_hash=command.target_idempotency_key_hash,
        source_hash=command.source_hash,
        response_hash=response_hash,
        http_status=http_status,
        response_authenticated=False,
        response_contract_valid=False,
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ItemPublishContractError("Sandbox Item JSON contains duplicate keys.")
        value[key] = item
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
