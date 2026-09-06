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

from .adapters import AdapterCommand, AdapterRegistration, AdapterRegistry
from .config import IntegrationProfile
from .domain import (
    AdapterResponse,
    EngineeringChangeIntegrationError,
    SUMMARY_OPERATION,
    TargetMode,
    canonical_hash,
)
from .runtime_fixture import (
    resolve_adapter_registry as resolve_synthetic_adapter_registry,
)
from .runtime_fixture import resolve_profile as resolve_synthetic_profile
from .runtime_fixture import resolve_secret as resolve_synthetic_secret
from npi_integration.project_publish.profile_inheritance import inherited_project_profile

SANDBOX_ENABLED_KEY = "npi_engineering_change_sandbox_enabled"
SANDBOX_PROFILES_KEY = "npi_engineering_change_sandbox_profiles"
SANDBOX_SECRETS_ENV = "NPI_ENGINEERING_CHANGE_SANDBOX_SECRETS"
INGRESS_SECRETS_ENV = "NPI_ENGINEERING_CHANGE_INGRESS_SECRETS"
SANDBOX_ADAPTER_PATH = (
    "npi_integration.engineering_change.connector_runtime.sandbox_adapter"
)
SUMMARY_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.engineering_change_api."
    "record_change_implementation_summary"
)
CONTRACT_VERSION = 1
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
    "signingKeyIds",
    "baseUrl",
    "allowedHostnames",
    "secretReference",
    "connectTimeoutSeconds",
    "readTimeoutSeconds",
}
_CREDENTIAL_KEYS = {"apiKey", "apiSecret"}
_API_KEY = re.compile(r"^[A-Za-z0-9]{8,128}$")
_API_SECRET = re.compile(r"^[^\s\x00-\x1f\x7f]{8,512}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_NON_PRODUCTION = frozenset(
    {"sandbox", "test", "testing", "dev", "development", "qa", "staging", "stage"}
)


@dataclass(frozen=True, slots=True)
class SandboxCredential:
    api_key: str
    api_secret: str

    @property
    def authorization_value(self) -> str:
        return f"token {self.api_key}:{self.api_secret}"

    @property
    def response_signing_secret(self) -> str:
        return f"{self.api_key}:{self.api_secret}"


def resolve_profile(
    tenant_id: str,
    project_global_id: object,
) -> IntegrationProfile | None:
    synthetic = resolve_synthetic_profile(tenant_id, project_global_id)
    if synthetic is not None:
        return synthetic
    import frappe

    return load_sandbox_profile(frappe.conf, tenant_id, str(project_global_id))


def resolve_secret(key_id: str) -> bytes:
    try:
        return resolve_synthetic_secret(key_id)
    except KeyError:
        return load_sandbox_signing_secret(
            key_id,
            os.environ.get(INGRESS_SECRETS_ENV, ""),
        )


def resolve_adapter_registry() -> AdapterRegistry | None:
    synthetic = resolve_synthetic_adapter_registry()
    if synthetic is not None:
        return synthetic
    import frappe

    if not _sandbox_enabled(frappe.conf):
        return None
    return AdapterRegistry(
        (
            AdapterRegistration(
                resolver_path=SANDBOX_ADAPTER_PATH,
                target_mode=TargetMode.SANDBOX,
                operation=SUMMARY_OPERATION,
                adapter=sandbox_adapter,
            ),
        )
    )


def load_sandbox_profile(
    configuration: object,
    tenant_id: str,
    project_global_id: str,
) -> IntegrationProfile | None:
    if not _sandbox_enabled(configuration):
        return None
    if not hasattr(configuration, "get"):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox configuration is unavailable."
        )
    raw_profiles = configuration.get(SANDBOX_PROFILES_KEY)
    if (
        isinstance(raw_profiles, (str, bytes))
        or not isinstance(raw_profiles, Sequence)
        or not 1 <= len(raw_profiles) <= 32
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox profiles are invalid."
        )
    profiles = tuple(_profile(value) for value in raw_profiles)
    matches = [
        profile
        for profile in profiles
        if profile.tenant_id == tenant_id
        and profile.project_global_id == project_global_id
    ]
    if len(matches) > 1:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox profile is ambiguous."
        )
    if matches:
        return matches[0]
    try:
        inherited = inherited_project_profile(
            raw_profiles, tenant_id, project_global_id, family="engineering-change"
        )
    except ValueError as error:
        raise EngineeringChangeIntegrationError(str(error)) from error
    return _profile(inherited) if inherited is not None else None


def sandbox_adapter(command: AdapterCommand) -> AdapterResponse:
    if not isinstance(command, AdapterCommand):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox command is invalid."
        )
    import frappe

    profile = load_sandbox_profile(
        frappe.conf,
        str(command.payload.get("tenant_id", "")),
        str(command.payload.get("project_global_id", "")),
    )
    if profile is None:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox profile is unavailable."
        )
    actor = str(getattr(getattr(frappe, "session", None), "user", "") or "")
    if actor != profile.service_actor_user_id:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox service actor drifted."
        )
    credential = load_sandbox_credential(
        profile.secret_reference,
        os.environ.get(SANDBOX_SECRETS_ENV, ""),
    )
    return execute_sandbox_summary(command, profile, credential)


def execute_sandbox_summary(
    command: AdapterCommand,
    profile: IntegrationProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> AdapterResponse:
    if (
        not isinstance(command, AdapterCommand)
        or not isinstance(profile, IntegrationProfile)
        or profile.target_mode is not TargetMode.SANDBOX
        or profile.adapter_resolver != SANDBOX_ADAPTER_PATH
        or not isinstance(credential, SandboxCredential)
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox adapter inputs are invalid."
        )
    source = dict(command.payload)
    actor = source.get("actor_user_id")
    if (
        source.get("tenant_id") != profile.tenant_id
        or source.get("project_global_id") != profile.project_global_id
        or not isinstance(actor, str)
        or not profile.permits(actor)
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox command scope does not match its profile."
        )
    body_value = {
        "contractVersion": CONTRACT_VERSION,
        "operation": SUMMARY_OPERATION,
        "requestGlobalId": str(command.request_global_id),
        "attemptGlobalId": str(command.attempt_global_id),
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
        "sourceHash": command.source_hash,
        "actorUserId": actor,
        "source": source,
    }
    body = _canonical_json(body_value).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _request_signature(
        credential.response_signing_secret,
        SUMMARY_METHOD_PATH,
        timestamp,
        body,
    )
    if session_factory is None:
        import requests

        session_factory = requests.Session
    session = session_factory()
    session.trust_env = False
    response = None
    try:
        response = session.post(
            f"{profile.base_url.rstrip('/')}{SUMMARY_METHOD_PATH}",
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": credential.authorization_value,
                "Content-Type": "application/json; charset=utf-8",
                "X-NPI-Signature": signature,
                "X-NPI-Timestamp": timestamp,
                "X-NPI-Trace-ID": f"change-summary-{command.attempt_global_id}",
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
            credential.response_signing_secret,
            now=int(clock()),
        )
    finally:
        if response is not None:
            response.close()
        session.close()


def load_sandbox_credential(
    secret_reference: str | None,
    serialized_secrets: str,
) -> SandboxCredential:
    values = _secret_values(serialized_secrets)
    raw = values.get(secret_reference)
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox credential is unavailable."
        )
    api_key = raw["apiKey"]
    api_secret = raw["apiSecret"]
    if (
        not isinstance(api_key, str)
        or _API_KEY.fullmatch(api_key) is None
        or not isinstance(api_secret, str)
        or _API_SECRET.fullmatch(api_secret) is None
        or len(f"{api_key}:{api_secret}") < 24
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox credential is invalid."
        )
    return SandboxCredential(api_key, api_secret)


def load_sandbox_signing_secret(key_id: str, serialized_secrets: str) -> bytes:
    if not isinstance(key_id, str) or _KEY_ID.fullmatch(key_id) is None:
        raise KeyError("Engineering Change signing key is unavailable.")
    values = _secret_values(serialized_secrets)
    secret = values.get(key_id)
    if (
        not isinstance(secret, str)
        or len(secret.encode("utf-8")) < 32
        or len(secret) > 1024
        or any(character in secret for character in "\r\n")
    ):
        raise KeyError("Engineering Change signing key is unavailable.")
    return secret.encode("utf-8")


def _profile(value: object) -> IntegrationProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox profile shape is invalid."
        )
    environment = value["environmentCode"]
    if (
        not isinstance(environment, str)
        or environment != environment.casefold()
        or environment not in _NON_PRODUCTION
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox environment is invalid."
        )
    try:
        return IntegrationProfile(
            profile_id=value["profileId"],
            profile_version=value["profileVersion"],
            tenant_id=value["tenantId"],
            project_global_id=value["projectGlobalId"],
            target_mode=TargetMode.SANDBOX,
            requester_user_ids=_strings(value["requesterUserIds"], 100),
            service_actor_user_id=value["serviceActorUserId"],
            signing_key_ids=_strings(value["signingKeyIds"], 8),
            adapter_resolver=SANDBOX_ADAPTER_PATH,
            base_url=value["baseUrl"],
            allowed_hostnames=_strings(value["allowedHostnames"], 8),
            secret_reference=value["secretReference"],
            response_authentication="hmac-sha256-v1",
            connect_timeout_seconds=value["connectTimeoutSeconds"],
            read_timeout_seconds=value["readTimeoutSeconds"],
        )
    except TypeError as error:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox profile is invalid."
        ) from error


def _sandbox_enabled(configuration: object) -> bool:
    return bool(
        hasattr(configuration, "get")
        and configuration.get(SANDBOX_ENABLED_KEY) is True
    )


def _strings(value: object, maximum: int) -> tuple[str, ...]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not 1 <= len(value) <= maximum
        or any(not isinstance(item, str) for item in value)
    ):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox list is invalid."
        )
    result = tuple(value)
    if len(set(result)) != len(result):
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox list is invalid."
        )
    return result


def _secret_values(serialized: str) -> Mapping[str, object]:
    if not isinstance(serialized, str) or not serialized or len(serialized) > 65_536:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox credentials are unavailable."
        )
    try:
        values = json.loads(serialized, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox credentials are unavailable."
        ) from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise EngineeringChangeIntegrationError(
            "Engineering Change Sandbox credentials are unavailable."
        )
    return values


def _request_signature(secret: str, path: str, timestamp: str, body: bytes) -> str:
    signing_input = "\n".join(
        (
            SIGNATURE_VERSION,
            "POST",
            path,
            timestamp,
            hashlib.sha256(body).hexdigest(),
        )
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()


def _bounded_response(response: Any) -> bytes:
    raw_length = response.headers.get("Content-Length")
    if raw_length is not None:
        try:
            length = int(raw_length)
        except (TypeError, ValueError) as error:
            raise EngineeringChangeIntegrationError(
                "Engineering Change response length is invalid."
            ) from error
        if length < 0 or length > MAX_RESPONSE_BYTES:
            raise EngineeringChangeIntegrationError(
                "Engineering Change response is too large."
            )
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise EngineeringChangeIntegrationError(
                "Engineering Change response body is invalid."
            )
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise EngineeringChangeIntegrationError(
                "Engineering Change response is too large."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(
    command: AdapterCommand,
    http_status: object,
    headers: object,
    body: bytes,
    secret: str,
    *,
    now: int,
) -> AdapterResponse:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise EngineeringChangeIntegrationError(
            "Engineering Change HTTP status is invalid."
        )
    content_type = (
        str(headers.get("Content-Type", "")) if hasattr(headers, "get") else ""
    )
    if not content_type.casefold().startswith("application/json"):
        return AdapterResponse(http_status, fallback_hash, False, False)
    try:
        envelope = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return AdapterResponse(http_status, fallback_hash, False, False)
    if not isinstance(envelope, Mapping) or set(envelope) != {"message"}:
        return AdapterResponse(http_status, fallback_hash, False, False)
    message = envelope["message"]
    if not isinstance(message, Mapping):
        return AdapterResponse(http_status, fallback_hash, False, False)
    payload = dict(message)
    response_signature = payload.pop("responseSignature", None)
    if not _response_signature_is_valid(
        payload, response_signature, secret, now=now
    ):
        return AdapterResponse(http_status, fallback_hash, False, False)
    expected_keys = {
        "contractVersion",
        "operation",
        "requestGlobalId",
        "attemptGlobalId",
        "attemptNumber",
        "targetIdempotencyKeyHash",
        "sourceHash",
        "httpStatus",
        "summaryProjectionId",
        "exactReplay",
        "partial",
        "retryAfterSeconds",
        "errorCode",
        "responseHash",
        "signatureVersion",
        "signedAt",
    }
    response_hash = payload.get("responseHash")
    core = dict(payload)
    core.pop("responseHash", None)
    core.pop("signatureVersion", None)
    core.pop("signedAt", None)
    valid = bool(
        set(payload) == expected_keys
        and payload.get("contractVersion") == CONTRACT_VERSION
        and payload.get("operation") == SUMMARY_OPERATION
        and payload.get("requestGlobalId") == str(command.request_global_id)
        and payload.get("attemptGlobalId") == str(command.attempt_global_id)
        and payload.get("attemptNumber") == command.attempt_number
        and payload.get("targetIdempotencyKeyHash")
        == command.target_idempotency_key_hash
        and payload.get("sourceHash") == command.source_hash
        and payload.get("httpStatus") == http_status
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
        and type(payload.get("exactReplay")) is bool
        and type(payload.get("partial")) is bool
        and (
            payload.get("retryAfterSeconds") is None
            or (
                type(payload.get("retryAfterSeconds")) is int
                and 1 <= payload["retryAfterSeconds"] <= 86_400
            )
        )
    )
    success = 200 <= http_status < 300
    projection_id = payload.get("summaryProjectionId")
    error_code = payload.get("errorCode")
    if success:
        valid = bool(
            valid
            and isinstance(projection_id, str)
            and projection_id == command.payload.get("revision_global_id")
            and error_code is None
        )
    else:
        valid = bool(
            valid
            and projection_id is None
            and payload.get("exactReplay") is False
            and isinstance(error_code, str)
            and _ERROR_CODE.fullmatch(error_code) is not None
        )
    return AdapterResponse(
        http_status=http_status,
        response_hash=(
            response_hash
            if isinstance(response_hash, str) and _HASH.fullmatch(response_hash)
            else fallback_hash
        ),
        authenticated=True,
        contract_valid=valid,
        partial=bool(payload.get("partial")) if valid else False,
        identity_conflict=http_status == 409,
        retry_after_seconds=(
            payload.get("retryAfterSeconds") if valid else None
        ),
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


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise EngineeringChangeIntegrationError(
                "Engineering Change JSON contains duplicate keys."
            )
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
