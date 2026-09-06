from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .config import ProjectPublishProfile, SECRETS_ENV
from .domain import (
    CONTRACT_VERSION,
    OPERATION,
    RECONCILE_OPERATION,
    ProjectPublishError,
    PublishCommand,
    ReconcileCommand,
    TargetObservation,
    canonical_hash,
    canonical_json,
)

PUBLISH_PATH = "/api/method/npi_erpnext_connector.project_publish_api.publish_project"
RECONCILE_PATH = "/api/method/npi_erpnext_connector.project_publish_api.reconcile_project"
SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_RESPONSE_BYTES = 262_144
MAX_CLOCK_SKEW_SECONDS = 300
_CREDENTIAL_KEYS = {"apiKey", "apiSecret"}
_API_KEY = re.compile(r"^[A-Za-z0-9]{8,128}$")
_API_SECRET = re.compile(r"^[^\s\x00-\x1f\x7f]{8,512}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_ERROR = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


@dataclass(frozen=True, slots=True)
class Credential:
    api_key: str
    api_secret: str

    @property
    def authorization_value(self) -> str:
        return f"token {self.api_key}:{self.api_secret}"

    @property
    def signing_secret(self) -> str:
        return f"{self.api_key}:{self.api_secret}"


def load_credential(profile: ProjectPublishProfile) -> Credential:
    serialized = os.environ.get(SECRETS_ENV, "")
    if not isinstance(serialized, str) or len(serialized) > 65_536:
        raise ProjectPublishError("Project publication credentials are unavailable.")
    try:
        values = json.loads(serialized, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectPublishError("Project publication credentials are unavailable.") from error
    raw = values.get(profile.secret_reference) if isinstance(values, Mapping) else None
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise ProjectPublishError("Project publication credential is unavailable.")
    api_key, api_secret = raw["apiKey"], raw["apiSecret"]
    if not isinstance(api_key, str) or _API_KEY.fullmatch(api_key) is None or not isinstance(api_secret, str) or _API_SECRET.fullmatch(api_secret) is None or len(f"{api_key}:{api_secret}") < 24:
        raise ProjectPublishError("Project publication credential is invalid.")
    return Credential(api_key, api_secret)


def publish(command: PublishCommand, profile: ProjectPublishProfile, credential: Credential, *, session_factory: Any = None, clock: Any = time.time) -> TargetObservation:
    return _post(command.payload(), profile, credential, path=PUBLISH_PATH, expected_operation=OPERATION, expected={
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "attemptNumber": command.attempt_number,
        "targetIdempotencyKeyHash": command.source.target_idempotency_key_hash,
        "sourceHash": command.source.source_hash,
    }, session_factory=session_factory, clock=clock)


def reconcile(command: ReconcileCommand, profile: ProjectPublishProfile, credential: Credential, *, session_factory: Any = None, clock: Any = time.time) -> TargetObservation:
    return _post(command.payload(), profile, credential, path=RECONCILE_PATH, expected_operation=RECONCILE_OPERATION, expected={
        "requestGlobalId": command.request_global_id,
        "attemptGlobalId": command.attempt_global_id,
        "targetIdempotencyKeyHash": command.source.target_idempotency_key_hash,
        "sourceHash": command.source.source_hash,
    }, session_factory=session_factory, clock=clock)


def _post(payload: Mapping[str, object], profile: ProjectPublishProfile, credential: Credential, *, path: str, expected_operation: str, expected: Mapping[str, object], session_factory: Any, clock: Any) -> TargetObservation:
    body = canonical_json(payload).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _request_signature(credential.signing_secret, path, timestamp, body)
    if session_factory is None:
        import requests
        session_factory = requests.Session
    session = session_factory()
    session.trust_env = False
    response = None
    try:
        response = session.post(
            f"{profile.base_url}{path}",
            data=body,
            headers={"Accept": "application/json", "Authorization": credential.authorization_value, "Content-Type": "application/json; charset=utf-8", "X-NPI-Signature": signature, "X-NPI-Timestamp": timestamp, "X-NPI-Trace-ID": f"project-{payload['attemptGlobalId']}"},
            allow_redirects=False,
            timeout=(profile.connect_timeout_seconds, profile.read_timeout_seconds),
            stream=True,
        )
        response_body = _bounded_response(response)
        return _decode_response(response.status_code, response.headers, response_body, credential.signing_secret, expected_operation=expected_operation, expected=expected, now=int(clock()))
    finally:
        if response is not None:
            response.close()
        session.close()


def _decode_response(http_status: object, headers: object, body: bytes, secret: str, *, expected_operation: str, expected: Mapping[str, object], now: int) -> TargetObservation:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise ProjectPublishError("Project publication HTTP status is invalid.")
    if not str(headers.get("Content-Type", "")).casefold().startswith("application/json"):
        return _invalid(http_status, fallback_hash)
    try:
        envelope = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _invalid(http_status, fallback_hash)
    if not isinstance(envelope, Mapping) or set(envelope) != {"message"} or not isinstance(envelope["message"], Mapping):
        return _invalid(http_status, fallback_hash)
    signed = dict(envelope["message"])
    signature = signed.pop("responseSignature", None)
    if not _response_signature_is_valid(signed, signature, secret, now=now):
        return _invalid(http_status, fallback_hash)
    response_hash = signed.get("responseHash")
    core = dict(signed)
    for key in ("responseHash", "signatureVersion", "signedAt"):
        core.pop(key, None)
    common = bool(signed.get("contractVersion") == CONTRACT_VERSION and signed.get("operation") == expected_operation and signed.get("httpStatus") == http_status and all(signed.get(key) == value for key, value in expected.items()) and isinstance(response_hash, str) and _HASH.fullmatch(response_hash) is not None and canonical_hash(core) == response_hash)
    expected_keys = {"contractVersion", "operation", "requestGlobalId", "attemptGlobalId", "targetIdempotencyKeyHash", "sourceHash", "httpStatus", "formalProjectId", "targetVersion", "errorCode", "responseHash", "signatureVersion", "signedAt"}
    if expected_operation == OPERATION:
        expected_keys |= {"attemptNumber", "exactReplay"}
    else:
        expected_keys |= {"found"}
    common = common and set(signed) == expected_keys
    success = 200 <= http_status < 300
    formal = signed.get("formalProjectId")
    version = signed.get("targetVersion")
    error = signed.get("errorCode")
    exact = signed.get("exactReplay", False)
    found = signed.get("found") if expected_operation == RECONCILE_OPERATION else None
    if success and (expected_operation == OPERATION or found is True):
        common = bool(common and isinstance(formal, str) and 1 <= len(formal) <= 140 and isinstance(version, str) and 1 <= len(version) <= 140 and error is None and (expected_operation != OPERATION or type(exact) is bool))
    elif success:
        common = bool(common and found is False and formal is None and version is None and error is None)
    else:
        common = bool(common and formal is None and version is None and isinstance(error, str) and _ERROR.fullmatch(error) is not None and (expected_operation != OPERATION or exact is False))
    return TargetObservation(http_status, response_hash if common else fallback_hash, True, bool(common), formal if common and isinstance(formal, str) else None, version if common and isinstance(version, str) else None, bool(exact), error if common and isinstance(error, str) else None, found if common and type(found) is bool else None)


def _request_signature(secret: str, path: str, timestamp: str, body: bytes) -> str:
    message = "\n".join((SIGNATURE_VERSION, "POST", path, timestamp, hashlib.sha256(body).hexdigest())).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _response_signature_is_valid(payload: Mapping[str, object], signature: object, secret: str, *, now: int) -> bool:
    if not isinstance(signature, str) or _HASH.fullmatch(signature) is None or payload.get("signatureVersion") != SIGNATURE_VERSION or type(payload.get("signedAt")) is not int or abs(now - int(payload["signedAt"])) > MAX_CLOCK_SKEW_SECONDS:
        return False
    expected = hmac.new(secret.encode(), canonical_json(payload).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _bounded_response(response: Any) -> bytes:
    raw_length = response.headers.get("Content-Length")
    if raw_length is not None and (not str(raw_length).isdigit() or int(raw_length) > MAX_RESPONSE_BYTES):
        raise ProjectPublishError("Project publication response is too large.")
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise ProjectPublishError("Project publication response body is invalid.")
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise ProjectPublishError("Project publication response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _invalid(status: int, response_hash: str) -> TargetObservation:
    return TargetObservation(status, response_hash, False, False, None, None, False, None)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectPublishError("Project publication JSON contains duplicate keys.")
        result[key] = value
    return result
