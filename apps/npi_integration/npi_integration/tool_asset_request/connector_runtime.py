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

from .adapters import (
    ToolAssetAdapterCommand,
    ToolAssetAdapterFieldResponse,
    ToolAssetAdapterRegistration,
    ToolAssetAdapterRegistry,
    ToolAssetAdapterResponse,
)
from .config import ToolAssetExecutionProfile
from .execution_domain import (
    TOOL_ASSET_OWNED_FIELDS,
    ToolAssetExecutionContractError,
    ToolAssetExecutionOperation,
    ToolAssetExecutionTargetMode,
    canonical_hash,
)
from .runtime_fixture import (
    resolve_adapter_registry as resolve_synthetic_adapter_registry,
)
from .runtime_fixture import resolve_profile as resolve_synthetic_profile
from npi_integration.project_publish.profile_inheritance import inherited_project_profile

SANDBOX_ENABLED_KEY = "npi_tool_asset_sandbox_enabled"
SANDBOX_PROFILES_KEY = "npi_tool_asset_sandbox_profiles"
SANDBOX_SECRETS_ENV = "NPI_TOOL_ASSET_SANDBOX_SECRETS"
SANDBOX_ADAPTER_PATH = (
    "npi_integration.tool_asset_request.connector_runtime.sandbox_adapter"
)
TOOL_ASSET_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.tool_asset_api.upsert_npi_tool_asset_v1"
)
SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_RESPONSE_BYTES = 1_048_576
MAX_CLOCK_SKEW_SECONDS = 300

_PROFILE_KEYS = {
    "profileId",
    "profileVersion",
    "tenantId",
    "projectGlobalId",
    "environmentCode",
    "requesterUserIds",
    "serviceActorUserId",
    "projectionPolicyId",
    "projectionPolicyVersion",
    "projectionPolicyHash",
    "allowedOperations",
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
) -> ToolAssetExecutionProfile | None:
    synthetic = resolve_synthetic_profile(tenant_id, project_global_id)
    if synthetic is not None:
        return synthetic
    import frappe

    return load_sandbox_profile(frappe.conf, tenant_id, project_global_id)


def resolve_adapter_registry() -> ToolAssetAdapterRegistry | None:
    synthetic = resolve_synthetic_adapter_registry()
    if synthetic is not None:
        return synthetic
    import frappe

    if not _sandbox_enabled(frappe.conf):
        return None
    return ToolAssetAdapterRegistry(
        tuple(
            ToolAssetAdapterRegistration(
                SANDBOX_ADAPTER_PATH,
                ToolAssetExecutionTargetMode.SANDBOX,
                operation,
                sandbox_adapter,
            )
            for operation in ToolAssetExecutionOperation
        )
    )


def load_sandbox_profile(
    configuration: object,
    tenant_id: str,
    project_global_id: str,
) -> ToolAssetExecutionProfile | None:
    if not _sandbox_enabled(configuration):
        return None
    if not hasattr(configuration, "get"):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset configuration is unavailable."
        )
    values = configuration.get(SANDBOX_PROFILES_KEY)
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or not 1 <= len(values) <= 32
    ):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset profiles are invalid."
        )
    matches: list[ToolAssetExecutionProfile] = []
    for value in values:
        profile = _profile(value)
        if (
            profile.tenant_id == tenant_id
            and profile.project_global_id == project_global_id
        ):
            matches.append(profile)
    if len(matches) > 1:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset profile resolution is ambiguous."
        )
    if matches:
        return matches[0]
    try:
        inherited = inherited_project_profile(
            values, tenant_id, project_global_id, family="tool-asset"
        )
    except ValueError as error:
        raise ToolAssetExecutionContractError(str(error)) from error
    return _profile(inherited) if inherited is not None else None


def sandbox_adapter(command: ToolAssetAdapterCommand) -> ToolAssetAdapterResponse:
    if not isinstance(command, ToolAssetAdapterCommand):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset command is invalid."
        )
    import frappe

    request = command.request_snapshot
    source = request.get("source") if isinstance(request, Mapping) else None
    if not isinstance(source, Mapping):
        raise ToolAssetExecutionContractError("Sandbox Tool Asset source is invalid.")
    profile = load_sandbox_profile(
        frappe.conf,
        str(source.get("tenantId", "")),
        str(source.get("projectGlobalId", "")),
    )
    if profile is None or command.operation.value not in profile.allowed_operations:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset profile is unavailable."
        )
    actor = str(getattr(getattr(frappe, "session", None), "user", "") or "")
    if actor != profile.service_actor_user_id:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset service actor drifted."
        )
    credential = load_sandbox_credential(
        profile.secret_reference,
        os.environ.get(SANDBOX_SECRETS_ENV, ""),
    )
    return execute_sandbox_tool_asset(command, profile, credential)


def load_sandbox_credential(
    secret_reference: str | None,
    serialized_secrets: str,
) -> SandboxCredential:
    if not isinstance(secret_reference, str) or not secret_reference:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credential reference is invalid."
        )
    if not isinstance(serialized_secrets, str) or len(serialized_secrets) > 65_536:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credentials are unavailable."
        )
    try:
        values = json.loads(serialized_secrets, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credentials are unavailable."
        ) from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credentials are unavailable."
        )
    raw = values.get(secret_reference)
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credential is unavailable."
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
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset credential is invalid."
        )
    return SandboxCredential(api_key, api_secret)


def execute_sandbox_tool_asset(
    command: ToolAssetAdapterCommand,
    profile: ToolAssetExecutionProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> ToolAssetAdapterResponse:
    if (
        not isinstance(command, ToolAssetAdapterCommand)
        or not isinstance(profile, ToolAssetExecutionProfile)
        or profile.target_mode is not ToolAssetExecutionTargetMode.SANDBOX
        or profile.adapter_resolver != SANDBOX_ADAPTER_PATH
        or command.operation.value not in profile.allowed_operations
        or not isinstance(credential, SandboxCredential)
    ):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset adapter inputs are invalid."
        )
    request = command.request_snapshot
    source = request.get("source") if isinstance(request, Mapping) else None
    if (
        not isinstance(source, Mapping)
        or source.get("tenantId") != profile.tenant_id
        or source.get("projectGlobalId") != profile.project_global_id
    ):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset command scope does not match its profile."
        )
    body = _canonical_json(command.snapshot).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _request_signature(
        credential.signing_secret,
        TOOL_ASSET_METHOD_PATH,
        timestamp,
        body,
    )
    base_url = profile.base_url
    if not isinstance(base_url, str):
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset base URL is invalid."
        )
    endpoint = f"{base_url.rstrip('/')}{TOOL_ASSET_METHOD_PATH}"
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
                "X-NPI-Trace-ID": f"tool-asset-{command.attempt_global_id}",
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


def _profile(value: object) -> ToolAssetExecutionProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset profile shape is invalid."
        )
    operations = _strings(value["allowedOperations"], "operations", 2)
    if not set(operations) <= {operation.value for operation in ToolAssetExecutionOperation}:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset operations are invalid."
        )
    return ToolAssetExecutionProfile(
        profile_id=value["profileId"],
        profile_version=value["profileVersion"],
        tenant_id=value["tenantId"],
        project_global_id=value["projectGlobalId"],
        target_mode=ToolAssetExecutionTargetMode.SANDBOX,
        environment_code=value["environmentCode"],
        requester_user_ids=_strings(value["requesterUserIds"], "requesters", 100),
        service_actor_user_id=value["serviceActorUserId"],
        projection_policy_id=value["projectionPolicyId"],
        projection_policy_version=value["projectionPolicyVersion"],
        projection_policy_hash=value["projectionPolicyHash"],
        allowed_operations=operations,
        adapter_resolver=SANDBOX_ADAPTER_PATH,
        base_url=value["baseUrl"],
        allowed_hostnames=_strings(value["allowedHostnames"], "hostnames", 8),
        secret_reference=value["secretReference"],
        response_authentication="hmac-sha256-v1",
        connect_timeout_seconds=value["connectTimeoutSeconds"],
        read_timeout_seconds=value["readTimeoutSeconds"],
        non_production_attested=True,
    )


def _sandbox_enabled(configuration: object) -> bool:
    return bool(
        hasattr(configuration, "get")
        and configuration.get(SANDBOX_ENABLED_KEY) is True
    )


def _strings(value: object, label: str, maximum: int) -> tuple[str, ...]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not 1 <= len(value) <= maximum
        or any(not isinstance(item, str) for item in value)
    ):
        raise ToolAssetExecutionContractError(
            f"Sandbox Tool Asset {label} are invalid."
        )
    result = tuple(value)
    if len(set(result)) != len(result):
        raise ToolAssetExecutionContractError(
            f"Sandbox Tool Asset {label} are invalid."
        )
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
            raise ToolAssetExecutionContractError(
                "Sandbox Tool Asset response length is invalid."
            ) from error
        if content_length < 0 or content_length > MAX_RESPONSE_BYTES:
            raise ToolAssetExecutionContractError(
                "Sandbox Tool Asset response is too large."
            )
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise ToolAssetExecutionContractError(
                "Sandbox Tool Asset response body is invalid."
            )
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise ToolAssetExecutionContractError(
                "Sandbox Tool Asset response is too large."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(
    command: ToolAssetAdapterCommand,
    http_status: object,
    headers: object,
    body: bytes,
    secret: str,
    *,
    now: int,
) -> ToolAssetAdapterResponse:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise ToolAssetExecutionContractError(
            "Sandbox Tool Asset HTTP status is invalid."
        )
    content_type = (
        str(headers.get("Content-Type", ""))
        if hasattr(headers, "get")
        else ""
    )
    try:
        envelope = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _invalid_response(command, fallback_hash)
    if (
        not content_type.casefold().startswith("application/json")
        or not isinstance(envelope, Mapping)
        or set(envelope) != {"message"}
        or not isinstance(envelope["message"], Mapping)
    ):
        return _invalid_response(command, fallback_hash)
    payload = dict(envelope["message"])
    response_signature = payload.pop("responseSignature", None)
    if not _response_signature_is_valid(
        payload,
        response_signature,
        secret,
        now=now,
    ):
        return _invalid_response(command, fallback_hash)
    expected_keys = {
        "contractVersion",
        "operation",
        "requestGlobalId",
        "attemptGlobalId",
        "attemptNumber",
        "targetIdempotencyKeyHash",
        "sourceHash",
        "httpStatus",
        "formalAssetId",
        "targetVersion",
        "mappingVersion",
        "errorCode",
        "exactReplay",
        "fields",
        "responseHash",
        "signatureVersion",
        "signedAt",
    }
    response_hash = payload.get("responseHash")
    core = dict(payload)
    core.pop("responseHash", None)
    core.pop("signatureVersion", None)
    core.pop("signedAt", None)
    raw_fields = payload.get("fields")
    binding_valid = bool(
        set(payload) == expected_keys
        and payload["contractVersion"] == 1
        and payload["operation"] == command.operation.value
        and payload["requestGlobalId"] == str(command.request_global_id)
        and payload["attemptGlobalId"] == str(command.attempt_global_id)
        and payload["attemptNumber"] == command.attempt_number
        and payload["targetIdempotencyKeyHash"]
        == command.target_idempotency_key_hash
        and payload["sourceHash"] == command.source_hash
        and payload["httpStatus"] == http_status
        and type(payload["exactReplay"]) is bool
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
        and isinstance(raw_fields, list)
        and len(raw_fields) == len(TOOL_ASSET_OWNED_FIELDS)
    )
    if not isinstance(raw_fields, list):
        return _invalid_response(command, fallback_hash)
    fields = tuple(
        _decode_field(code, raw, binding_valid)
        for code, raw in zip(TOOL_ASSET_OWNED_FIELDS, raw_fields)
    )
    if len(fields) != len(TOOL_ASSET_OWNED_FIELDS):
        return _invalid_response(command, fallback_hash)
    success = 200 <= http_status < 300
    formal_asset_id = payload.get("formalAssetId")
    target_version = payload.get("targetVersion")
    mapping_version = payload.get("mappingVersion")
    error_code = payload.get("errorCode")
    if success:
        binding_valid = bool(
            binding_valid
            and isinstance(formal_asset_id, str)
            and 1 <= len(formal_asset_id) <= 140
            and isinstance(target_version, str)
            and 1 <= len(target_version) <= 140
            and type(mapping_version) is int
            and mapping_version >= 1
            and error_code is None
            and all(
                value.http_status == http_status
                and value.response_contract_valid
                for value in fields
            )
        )
    else:
        binding_valid = bool(
            binding_valid
            and formal_asset_id is None
            and target_version is None
            and mapping_version is None
            and isinstance(error_code, str)
            and _ERROR_CODE.fullmatch(error_code) is not None
        )
    if not binding_valid:
        return _invalid_response(command, fallback_hash, authenticated=True)
    return ToolAssetAdapterResponse(
        command.request_global_id,
        command.attempt_global_id,
        command.attempt_number,
        command.operation,
        command.target_idempotency_key_hash,
        command.source_hash,
        response_hash,
        fields,
        formal_asset_id if success else None,
        target_version if success else None,
    )


def _decode_field(
    expected_code: str,
    raw: object,
    response_binding_valid: bool,
) -> ToolAssetAdapterFieldResponse:
    keys = {
        "fieldCode",
        "httpStatus",
        "errorCode",
        "exactReplay",
        "responseHash",
    }
    if not isinstance(raw, Mapping):
        return _invalid_field(expected_code)
    value = dict(raw)
    response_hash = value.get("responseHash")
    core = dict(value)
    core.pop("responseHash", None)
    status = value.get("httpStatus")
    error = value.get("errorCode")
    valid = bool(
        response_binding_valid
        and set(value) == keys
        and value.get("fieldCode") == expected_code
        and type(status) is int
        and 100 <= status <= 599
        and type(value.get("exactReplay")) is bool
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
    )
    if valid and 200 <= status < 300:
        valid = error is None
    elif valid:
        valid = isinstance(error, str) and _ERROR_CODE.fullmatch(error) is not None
    return ToolAssetAdapterFieldResponse(
        expected_code,
        response_hash
        if valid and isinstance(response_hash, str)
        else canonical_hash({"invalidField": expected_code}),
        http_status=status if type(status) is int and 100 <= status <= 599 else None,
        response_authenticated=response_binding_valid,
        response_contract_valid=valid,
        business_validation_failed=bool(
            type(status) is int and 400 <= status < 500 and status != 429
        ),
    )


def _invalid_field(code: str) -> ToolAssetAdapterFieldResponse:
    return ToolAssetAdapterFieldResponse(
        code,
        canonical_hash({"invalidField": code}),
        response_contract_valid=False,
    )


def _invalid_response(
    command: ToolAssetAdapterCommand,
    response_hash: str,
    *,
    authenticated: bool = False,
) -> ToolAssetAdapterResponse:
    fields = tuple(_invalid_field(code) for code in TOOL_ASSET_OWNED_FIELDS)
    if authenticated:
        fields = tuple(
            ToolAssetAdapterFieldResponse(
                value.field_code,
                value.response_hash,
                response_authenticated=True,
                response_contract_valid=False,
            )
            for value in fields
        )
    return ToolAssetAdapterResponse(
        command.request_global_id,
        command.attempt_global_id,
        command.attempt_number,
        command.operation,
        command.target_idempotency_key_hash,
        command.source_hash,
        response_hash,
        fields,
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
            raise ToolAssetExecutionContractError(
                "Sandbox Tool Asset JSON contains duplicate keys."
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
