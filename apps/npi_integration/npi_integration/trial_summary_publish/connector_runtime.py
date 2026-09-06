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

from .config import SANDBOX_SECRETS_ENV, TrialSummaryProfile
from .domain import (
    CONTRACT_VERSION,
    OPERATION,
    RECONCILE_OPERATION,
    PublishCommand,
    ReconcileCommand,
    TargetObservation,
    TrialSummaryDeliveryError,
    canonical_hash,
    canonical_json,
)

PUBLISH_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.trial_summary_api.publish_trial_summary"
)
RECONCILE_METHOD_PATH = (
    "/api/method/npi_erpnext_connector.trial_summary_api.reconcile_trial_summary"
)
SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_RESPONSE_BYTES = 262_144
MAX_CLOCK_SKEW_SECONDS = 300

_CREDENTIAL_KEYS = {"apiKey", "apiSecret"}
_API_KEY = re.compile(r"^[A-Za-z0-9]{8,128}$")
_API_SECRET = re.compile(r"^[^\s\x00-\x1f\x7f]{8,512}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_ERROR = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


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


def load_credential(profile: TrialSummaryProfile) -> SandboxCredential:
    serialized = os.environ.get(SANDBOX_SECRETS_ENV, "")
    if not isinstance(serialized, str) or len(serialized) > 65_536:
        raise TrialSummaryDeliveryError("Trial Summary credentials are unavailable.")
    try:
        values = json.loads(serialized, object_pairs_hook=_unique_object)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TrialSummaryDeliveryError("Trial Summary credentials are unavailable.") from error
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise TrialSummaryDeliveryError("Trial Summary credentials are unavailable.")
    raw = values.get(profile.secret_reference)
    if not isinstance(raw, Mapping) or set(raw) != _CREDENTIAL_KEYS:
        raise TrialSummaryDeliveryError("Trial Summary credential is unavailable.")
    api_key = raw["apiKey"]
    api_secret = raw["apiSecret"]
    if (
        not isinstance(api_key, str)
        or _API_KEY.fullmatch(api_key) is None
        or not isinstance(api_secret, str)
        or _API_SECRET.fullmatch(api_secret) is None
        or len(f"{api_key}:{api_secret}") < 24
    ):
        raise TrialSummaryDeliveryError("Trial Summary credential is invalid.")
    return SandboxCredential(api_key, api_secret)


def publish(
    command: PublishCommand,
    profile: TrialSummaryProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> TargetObservation:
    return _post(
        command.payload(),
        profile,
        credential,
        path=PUBLISH_METHOD_PATH,
        trace_id=f"trial-summary-{command.attempt_global_id}",
        expected_operation=OPERATION,
        expected={
            "requestGlobalId": command.request_global_id,
            "attemptGlobalId": command.attempt_global_id,
            "attemptNumber": command.attempt_number,
            "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
            "sourceHash": command.source_hash,
        },
        expected_projection_id=command.expected_projection_id,
        expected_fact_count=command.expected_fact_count,
        session_factory=session_factory,
        clock=clock,
    )


def reconcile(
    command: ReconcileCommand,
    profile: TrialSummaryProfile,
    credential: SandboxCredential,
    *,
    session_factory: Any = None,
    clock: Any = time.time,
) -> TargetObservation:
    return _post(
        command.payload(),
        profile,
        credential,
        path=RECONCILE_METHOD_PATH,
        trace_id=f"trial-summary-reconcile-{command.attempt_global_id}",
        expected_operation=RECONCILE_OPERATION,
        expected={
            "requestGlobalId": command.request_global_id,
            "attemptGlobalId": command.attempt_global_id,
            "targetIdempotencyKeyHash": command.target_idempotency_key_hash,
            "sourceHash": command.source_hash,
        },
        expected_projection_id=command.expected_projection_id,
        expected_fact_count=command.expected_fact_count,
        session_factory=session_factory,
        clock=clock,
    )


def _post(
    payload: Mapping[str, object],
    profile: TrialSummaryProfile,
    credential: SandboxCredential,
    *,
    path: str,
    trace_id: str,
    expected_operation: str,
    expected: Mapping[str, object],
    expected_projection_id: str,
    expected_fact_count: int,
    session_factory: Any,
    clock: Any,
) -> TargetObservation:
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
            headers={
                "Accept": "application/json",
                "Authorization": credential.authorization_value,
                "Content-Type": "application/json; charset=utf-8",
                "X-NPI-Signature": signature,
                "X-NPI-Timestamp": timestamp,
                "X-NPI-Trace-ID": trace_id,
            },
            allow_redirects=False,
            timeout=(profile.connect_timeout_seconds, profile.read_timeout_seconds),
            stream=True,
        )
        response_body = _bounded_response(response)
        return _decode_response(
            response.status_code,
            response.headers,
            response_body,
            credential.signing_secret,
            expected_operation=expected_operation,
            expected=expected,
            expected_projection_id=expected_projection_id,
            expected_fact_count=expected_fact_count,
            now=int(clock()),
        )
    finally:
        if response is not None:
            response.close()
        session.close()


def _decode_response(
    http_status: object,
    headers: object,
    body: bytes,
    secret: str,
    *,
    expected_operation: str,
    expected: Mapping[str, object],
    expected_projection_id: str,
    expected_fact_count: int,
    now: int,
) -> TargetObservation:
    fallback_hash = hashlib.sha256(body).hexdigest()
    if type(http_status) is not int or not 100 <= http_status <= 599:
        raise TrialSummaryDeliveryError("Trial Summary HTTP status is invalid.")
    content_type = str(headers.get("Content-Type", "")) if hasattr(headers, "get") else ""
    if not content_type.casefold().startswith("application/json"):
        return _invalid(http_status, fallback_hash)
    try:
        envelope = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _invalid(http_status, fallback_hash)
    if not isinstance(envelope, Mapping) or set(envelope) != {"message"}:
        return _invalid(http_status, fallback_hash)
    message = envelope["message"]
    if not isinstance(message, Mapping):
        return _invalid(http_status, fallback_hash)
    signed = dict(message)
    signature = signed.pop("responseSignature", None)
    if not _response_signature_is_valid(signed, signature, secret, now=now):
        return _invalid(http_status, fallback_hash)
    response_hash = signed.get("responseHash")
    core = dict(signed)
    core.pop("responseHash", None)
    core.pop("signatureVersion", None)
    core.pop("signedAt", None)
    common_valid = bool(
        signed.get("contractVersion") == CONTRACT_VERSION
        and signed.get("operation") == expected_operation
        and signed.get("httpStatus") == http_status
        and all(signed.get(key) == value for key, value in expected.items())
        and isinstance(response_hash, str)
        and _HASH.fullmatch(response_hash) is not None
        and canonical_hash(core) == response_hash
    )
    success = 200 <= http_status < 300
    projection_id = signed.get("projectionId")
    fact_count = signed.get("factCount")
    error_code = signed.get("errorCode")
    found: bool | None = None
    exact_replay = False
    if expected_operation == OPERATION:
        exact_replay = signed.get("exactReplay")
        expected_keys = {
            "contractVersion", "operation", "requestGlobalId", "attemptGlobalId",
            "attemptNumber", "targetIdempotencyKeyHash", "sourceHash", "httpStatus",
            "projectionId", "factCount", "exactReplay", "errorCode", "responseHash",
            "signatureVersion", "signedAt",
        }
        common_valid = common_valid and set(signed) == expected_keys
    else:
        found = signed.get("found")
        expected_keys = {
            "contractVersion", "operation", "requestGlobalId", "attemptGlobalId",
            "targetIdempotencyKeyHash", "sourceHash", "httpStatus", "found",
            "projectionId", "factCount", "errorCode", "responseHash",
            "signatureVersion", "signedAt",
        }
        common_valid = common_valid and set(signed) == expected_keys and type(found) is bool
    if success:
        if expected_operation == OPERATION or found is True:
            common_valid = bool(
                common_valid
                and isinstance(projection_id, str)
                and projection_id == expected_projection_id
                and type(fact_count) is int
                and fact_count == expected_fact_count
                and error_code is None
            )
        else:
            common_valid = bool(
                common_valid
                and projection_id is None
                and fact_count is None
                and error_code is None
            )
        if expected_operation == OPERATION:
            common_valid = common_valid and type(exact_replay) is bool
    else:
        common_valid = bool(
            common_valid
            and projection_id is None
            and fact_count is None
            and isinstance(error_code, str)
            and _ERROR.fullmatch(error_code) is not None
        )
        if expected_operation == OPERATION:
            common_valid = common_valid and exact_replay is False
    return TargetObservation(
        http_status,
        response_hash if isinstance(response_hash, str) and _HASH.fullmatch(response_hash) else fallback_hash,
        True,
        bool(common_valid),
        projection_id if common_valid and isinstance(projection_id, str) else None,
        fact_count if common_valid and type(fact_count) is int else None,
        bool(exact_replay),
        error_code if common_valid and isinstance(error_code, str) else None,
        found if common_valid and type(found) is bool else None,
    )


def _request_signature(secret: str, path: str, timestamp: str, body: bytes) -> str:
    message = "\n".join(
        (SIGNATURE_VERSION, "POST", path, timestamp, hashlib.sha256(body).hexdigest())
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


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
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _bounded_response(response: Any) -> bytes:
    raw_length = response.headers.get("Content-Length")
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError) as error:
            raise TrialSummaryDeliveryError("Trial Summary response length is invalid.") from error
        if content_length < 0 or content_length > MAX_RESPONSE_BYTES:
            raise TrialSummaryDeliveryError("Trial Summary response is too large.")
    chunks: list[bytes] = []
    observed = 0
    for chunk in response.iter_content(chunk_size=65_536):
        if not isinstance(chunk, bytes):
            raise TrialSummaryDeliveryError("Trial Summary response body is invalid.")
        observed += len(chunk)
        if observed > MAX_RESPONSE_BYTES:
            raise TrialSummaryDeliveryError("Trial Summary response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _invalid(http_status: int, response_hash: str) -> TargetObservation:
    return TargetObservation(http_status, response_hash, False, False, None, None, False, None)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise TrialSummaryDeliveryError("Trial Summary JSON contains duplicate keys.")
        value[key] = item
    return value
