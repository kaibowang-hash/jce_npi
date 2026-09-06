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
    MbomAdapterCommand,
    MbomAdapterNodeResponse,
    MbomAdapterRegistration,
    MbomAdapterRegistry,
    MbomAdapterResponse,
)
from .config import MbomExecutionProfile
from .domain import (
    MBOM_PUBLISH_OPERATION,
    MbomPublishContractError,
    MbomTargetMode,
    MbomTargetSubmissionState,
    canonical_hash,
)
from .runtime_fixture import (
    resolve_adapter_registry as resolve_synthetic_adapter_registry,
)
from .runtime_fixture import resolve_profile as resolve_synthetic_profile
from npi_integration.project_publish.profile_inheritance import inherited_project_profile


SANDBOX_ENABLED_KEY = "npi_mbom_publish_sandbox_enabled"
SANDBOX_PROFILES_KEY = "npi_mbom_publish_sandbox_profiles"
SANDBOX_SECRETS_ENV = "NPI_MBOM_PUBLISH_SANDBOX_SECRETS"
SANDBOX_ADAPTER_PATH = (
    "npi_integration.mbom_publish.connector_runtime.sandbox_adapter"
)
MBOM_METHOD_PATH = "/api/method/npi_erpnext_connector.mbom_api.publish_mbom"
SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_RESPONSE_BYTES = 4_194_304
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
) -> MbomExecutionProfile | None:
    synthetic = resolve_synthetic_profile(tenant_id, project_global_id)
    if synthetic is not None:
        return synthetic
    import frappe

    return load_sandbox_profile(frappe.conf, tenant_id, project_global_id)


def resolve_adapter_registry() -> MbomAdapterRegistry | None:
    synthetic = resolve_synthetic_adapter_registry()
    if synthetic is not None:
        return synthetic
    import frappe

    if _sandbox_enabled(frappe.conf):
        return MbomAdapterRegistry(
            (
                MbomAdapterRegistration(
                    resolver_path=SANDBOX_ADAPTER_PATH,
                    target_mode=MbomTargetMode.SANDBOX,
                    operation=MBOM_PUBLISH_OPERATION,
                    adapter=sandbox_adapter,
                ),
            )
        )
    return None


def load_sandbox_profile(
    configuration: object,
    tenant_id: str,
    project_global_id: str,
) -> MbomExecutionProfile | None:
    if not _sandbox_enabled(configuration):
        return None
    if not hasattr(configuration, "get"):
        raise MbomPublishContractError("Sandbox MBOM configuration is unavailable.")
    values = configuration.get(SANDBOX_PROFILES_KEY)
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or not 1 <= len(values) <= 32
    ):
        raise MbomPublishContractError("Sandbox MBOM profiles are invalid.")
    matches: list[MbomExecutionProfile] = []
    for value in values:
        profile = _profile(value)
        if profile.tenant_id == tenant_id and profile.project_global_id == project_global_id:
            matches.append(profile)
    if len(matches) > 1:
        raise MbomPublishContractError("Sandbox MBOM profile resolution is ambiguous.")
    if matches:
        return matches[0]
    try:
        inherited = inherited_project_profile(
            values, tenant_id, project_global_id, family="mbom"
        )
    except ValueError as error:
        raise MbomPublishContractError(str(error)) from error
    return _profile(inherited) if inherited is not None else None


def sandbox_adapter(command: MbomAdapterCommand) -> MbomAdapterResponse:
    if not isinstance(command, MbomAdapterCommand):
        raise MbomPublishContractError("Sandbox MBOM command is invalid.")
    import frappe

    request = command.request_snapshot
    source = request.get("source") if isinstance(request, Mapping) else None
    if not isinstance(source, Mapping):
        raise MbomPublishContractError("Sandbox MBOM source is invalid.")
    profile = load_sandbox_profile(
        frappe.conf,
        str(source.get("tenantId", "")),
        str(source.get("projectGlobalId", "")),
    )
    if profile is None:
        raise MbomPublishContractError("Sandbox MBOM profile is unavailable.")
    actor = str(getattr(getattr(frappe, "session", None), "user", "") or "")
    if actor != profile.service_actor_user_id:
        raise MbomPublishContractError("Sandbox MBOM service actor drifted.")
    credential = load_sandbox_credential(
        profile.secret_reference,
        os.environ.get(SANDBOX_SECRETS_ENV, ""),
    )
    return execute_sandbox_mbom(command, profile, credential)


def load_sandbox_credential(
    secret_reference: str | None,
    serialized_secrets: str,
) -> SandboxCredential:
    if not isinstance(secret_reference, str) or not secret_reference:
        raise MbomPublishContractError("Sandbox MBOM credential reference is invalid.")
    if not isinstance(serialized_secrets, str) or len(serialized_secrets) > 65_536:
        raise MbomPublishContractError("Sandbox MBOM credentials are unavailable.")
    try:
        values = json.loads(serialized_secrets, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise MbomPublishContractError("Sandbox MBOM credentials are unavailable.") from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise MbomPublishContractError("Sandbox MBOM credentials are unavailable.")
    raw = values.get(secret_reference)
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise MbomPublishContractError("Sandbox MBOM credential is unavailable.")
    api_key = raw["apiKey"]
    api_secret = raw["apiSecret"]
    if (
        not isinstance(api_key, str)
        or _API_KEY.fullmatch(api_key) is None
        or not isinstance(api_secret, str)
        or _API_SECRET.fullmatch(api_secret) is None
        or len(f"{api_key}:{api_secret}") < 24
    ):
        raise MbomPublishContractError("Sandbox MBOM credential is invalid.")
    return SandboxCredential(api_key, api_secret)


def execute_sandbox_mbom(
    command: MbomAdapterCommand,
    profile: MbomExecutionProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> MbomAdapterResponse:
    if (
        not isinstance(command, MbomAdapterCommand)
        or not isinstance(profile, MbomExecutionProfile)
        or profile.target_mode is not MbomTargetMode.SANDBOX
        or profile.adapter_resolver != SANDBOX_ADAPTER_PATH
        or not isinstance(credential, SandboxCredential)
    ):
        raise MbomPublishContractError("Sandbox MBOM adapter inputs are invalid.")
    request = command.request_snapshot
    source = request.get("source") if isinstance(request, Mapping) else None
    if (
        not isinstance(source, Mapping)
        or source.get("tenantId") != profile.tenant_id
        or source.get("projectGlobalId") != profile.project_global_id
    ):
        raise MbomPublishContractError("Sandbox MBOM command scope does not match its profile.")
    body = _canonical_json(command.snapshot()).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _request_signature(
        credential.signing_secret,
        MBOM_METHOD_PATH,
        timestamp,
        body,
    )
    base_url = profile.base_url
    if not isinstance(base_url, str):
        raise MbomPublishContractError("Sandbox MBOM base URL is invalid.")
    endpoint = f"{base_url.rstrip('/')}{MBOM_METHOD_PATH}"
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
                "X-NPI-Trace-ID": f"mbom-{command.attempt_global_id}",
            },
            allow_redirects=False,
            timeout=(
                profile.connect_timeout_seconds,
                profile.read_timeout_seconds,
            ),
            stream=True,
        )
        body_bytes = _bounded_response(response)
        return _decode_response(
            command,
            response.status_code,
            response.headers,
            body_bytes,
            credential.signing_secret,
            now=int(clock()),
        )
    finally:
        if response is not None:
            response.close()
        session.close()


def _profile(value: object) -> MbomExecutionProfile:
    if not isinstance(value, Mapping) or set(value) != _PROFILE_KEYS:
        raise MbomPublishContractError("Sandbox MBOM profile shape is invalid.")
    return MbomExecutionProfile(
        profile_id=value["profileId"],
        profile_version=value["profileVersion"],
        tenant_id=value["tenantId"],
        project_global_id=value["projectGlobalId"],
        target_mode=MbomTargetMode.SANDBOX,
        environment_code=value["environmentCode"],
        requester_user_ids=_strings(value["requesterUserIds"], "requesters", 100),
        service_actor_user_id=value["serviceActorUserId"],
        projection_policy_id=value["projectionPolicyId"],
        projection_policy_version=value["projectionPolicyVersion"],
        projection_policy_hash=value["projectionPolicyHash"],
        allowed_operations=(MBOM_PUBLISH_OPERATION,),
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
        raise MbomPublishContractError(f"Sandbox MBOM {label} are invalid.")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise MbomPublishContractError(f"Sandbox MBOM {label} are invalid.")
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
            raise MbomPublishContractError("Sandbox MBOM response length is invalid.") from error
        if content_length < 0 or content_length > MAX_RESPONSE_BYTES:
            raise MbomPublishContractError("Sandbox MBOM response is too large.")
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise MbomPublishContractError("Sandbox MBOM response body is invalid.")
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise MbomPublishContractError("Sandbox MBOM response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(
    command: MbomAdapterCommand,
    http_status: object,
    headers: object,
    body: bytes,
    secret: str,
    *,
    now: int,
) -> MbomAdapterResponse:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise MbomPublishContractError("Sandbox MBOM HTTP status is invalid.")
    content_type = str(headers.get("Content-Type", "")) if hasattr(headers, "get") else ""
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
    if not _response_signature_is_valid(payload, response_signature, secret, now=now):
        return _invalid_response(command, fallback_hash)
    expected_keys = {
        "contractVersion",
        "operation",
        "requestGlobalId",
        "attemptGlobalId",
        "attemptNumber",
        "targetIdempotencyKeyHash",
        "sourceHash",
        "topologyHash",
        "nodeManifestHash",
        "nodes",
        "responseHash",
        "signatureVersion",
        "signedAt",
    }
    response_hash = payload.get("responseHash")
    core = dict(payload)
    core.pop("responseHash", None)
    core.pop("signatureVersion", None)
    core.pop("signedAt", None)
    raw_nodes = payload.get("nodes")
    binding_valid = bool(
        set(payload) == expected_keys
        and payload["contractVersion"] == 1
        and payload["operation"] == MBOM_PUBLISH_OPERATION
        and payload["requestGlobalId"] == str(command.request_global_id)
        and payload["attemptGlobalId"] == str(command.attempt_global_id)
        and payload["attemptNumber"] == command.attempt_number
        and payload["targetIdempotencyKeyHash"] == command.target_idempotency_key_hash
        and payload["sourceHash"] == command.source_hash
        and payload["topologyHash"] == command.topology_hash
        and payload["nodeManifestHash"] == command.node_manifest_hash
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
        and isinstance(raw_nodes, list)
        and len(raw_nodes) == len(command.nodes)
    )
    if not isinstance(raw_nodes, list):
        return _invalid_response(command, fallback_hash)
    nodes = tuple(
        _decode_node(command_node, raw_node, binding_valid)
        for command_node, raw_node in zip(command.nodes, raw_nodes)
    )
    if len(nodes) != len(command.nodes):
        return _invalid_response(command, fallback_hash)
    return MbomAdapterResponse(
        command.request_global_id,
        command.attempt_global_id,
        command.attempt_number,
        command.target_idempotency_key_hash,
        command.source_hash,
        command.topology_hash,
        command.node_manifest_hash,
        response_hash if binding_valid else fallback_hash,
        nodes,
    )


def _decode_node(
    command_node: object,
    raw: object,
    response_binding_valid: bool,
) -> MbomAdapterNodeResponse:
    keys = {
        "stableLineKey",
        "assemblySourceKey",
        "httpStatus",
        "formalBomId",
        "targetVersion",
        "targetSubmissionState",
        "mappingVersion",
        "errorCode",
        "exactReplay",
        "responseHash",
    }
    if not isinstance(raw, Mapping):
        return _invalid_node(command_node)
    value = dict(raw)
    node_hash = value.get("responseHash")
    core = dict(value)
    core.pop("responseHash", None)
    status = value.get("httpStatus")
    valid = bool(
        response_binding_valid
        and set(value) == keys
        and value.get("stableLineKey") == command_node.stable_line_key
        and value.get("assemblySourceKey") == command_node.assembly_source_key
        and type(status) is int
        and 100 <= status <= 599
        and type(value.get("exactReplay")) is bool
        and isinstance(node_hash, str)
        and _HASH.fullmatch(node_hash) is not None
        and canonical_hash(core) == node_hash
    )
    formal = value.get("formalBomId")
    target = value.get("targetVersion")
    submission = value.get("targetSubmissionState")
    mapping_version = value.get("mappingVersion")
    error = value.get("errorCode")
    if valid and 200 <= status < 300:
        valid = bool(
            isinstance(formal, str)
            and formal
            and len(formal) <= 140
            and isinstance(target, str)
            and target
            and len(target) <= 140
            and submission in {"editable_draft", "submitted_immutable"}
            and type(mapping_version) is int
            and mapping_version >= 1
            and error is None
        )
    elif valid:
        valid = bool(
            formal is None
            and target is None
            and submission is None
            and mapping_version is None
            and isinstance(error, str)
            and _ERROR_CODE.fullmatch(error) is not None
        )
    return MbomAdapterNodeResponse(
        command_node.stable_line_key,
        command_node.assembly_source_key,
        node_hash if valid else canonical_hash({"invalidNode": command_node.stable_line_key}),
        http_status=status if type(status) is int and 100 <= status <= 599 else None,
        response_authenticated=response_binding_valid,
        response_contract_valid=valid,
        business_validation_failed=bool(
            type(status) is int and 400 <= status < 500 and status != 429
        ),
        formal_bom_id=formal if valid and isinstance(formal, str) else None,
        target_version=target if valid and isinstance(target, str) else None,
        target_submission_state=(
            MbomTargetSubmissionState(submission)
            if valid and submission in {"editable_draft", "submitted_immutable"}
            else None
        ),
    )


def _invalid_node(command_node: object) -> MbomAdapterNodeResponse:
    return MbomAdapterNodeResponse(
        command_node.stable_line_key,
        command_node.assembly_source_key,
        canonical_hash({"invalidNode": command_node.stable_line_key}),
        response_contract_valid=False,
    )


def _invalid_response(
    command: MbomAdapterCommand,
    response_hash: str,
) -> MbomAdapterResponse:
    return MbomAdapterResponse(
        command.request_global_id,
        command.attempt_global_id,
        command.attempt_number,
        command.target_idempotency_key_hash,
        command.source_hash,
        command.topology_hash,
        command.node_manifest_hash,
        response_hash,
        tuple(_invalid_node(node) for node in command.nodes),
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
            raise MbomPublishContractError("Sandbox MBOM JSON contains duplicate keys.")
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
