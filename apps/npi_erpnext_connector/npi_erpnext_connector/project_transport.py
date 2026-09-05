from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from .project_config import (
    EVENT_PATH,
    SIGNING_SECRET_ENV,
    STATUS_TOKEN_ENV,
    ProjectSenderProfile,
)
from .project_domain import ProjectSourceEvent, canonical_json


MAX_RESPONSE_BYTES = 65_536
_HASH = re.compile(r"^[a-f0-9]{64}$")
_STATES = {
    "pending",
    "processing",
    "succeeded",
    "failed_retryable",
    "failed_final",
    "quarantined",
    "superseded",
    "received_after_creation",
}


class ProjectDeliveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RetryableProjectDeliveryError(ProjectDeliveryError):
    pass


class PermanentProjectDeliveryError(ProjectDeliveryError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedProjectReceipt:
    receipt_id: UUID
    state: str
    exact_duplicate: bool


@dataclass(frozen=True, slots=True)
class ProjectReceiptStatus:
    receipt_id: UUID
    state: str
    terminal: bool
    disposition: str
    project_global_id: UUID | None
    error_code: str | None


def submit_project_event(
    profile: ProjectSenderProfile,
    event: ProjectSourceEvent,
    *,
    session: object | None = None,
    environment: Mapping[str, str] | None = None,
    clock: Callable[[], float] = time.time,
) -> AcceptedProjectReceipt:
    runtime = os.environ if environment is None else environment
    secret = _signing_secret(runtime.get(SIGNING_SECRET_ENV))
    body = canonical_json(event.event).encode("utf-8")
    timestamp = str(int(clock()))
    signature = _signature(
        secret,
        key_id=profile.signing_key_id,
        timestamp=timestamp,
        request_id=str(event.request_id),
        body=body,
    )
    client = session or _requests()
    response = None
    try:
        response = client.post(
            profile.event_endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "X-Request-ID": str(event.request_id),
                "X-NPI-Key-ID": profile.signing_key_id,
                "X-NPI-Timestamp": timestamp,
                "X-NPI-Signature": signature,
            },
            timeout=(3.05, 10.0),
            allow_redirects=False,
            stream=True,
        )
        status = int(getattr(response, "status_code", 0) or 0)
        payload = _bounded_json(response)
        if status != 202:
            _raise_http(status, payload)
        return _accepted_receipt(payload, event)
    except ProjectDeliveryError:
        raise
    except Exception as error:
        if _is_request_error(error):
            raise RetryableProjectDeliveryError("NETWORK_OR_TIMEOUT") from error
        raise
    finally:
        if response is not None:
            close = getattr(response, "close", None)
            if callable(close):
                close()


def get_project_receipt_status(
    profile: ProjectSenderProfile,
    receipt_id: UUID,
    *,
    session: object | None = None,
    environment: Mapping[str, str] | None = None,
) -> ProjectReceiptStatus:
    runtime = os.environ if environment is None else environment
    token = _service_token(runtime.get(STATUS_TOKEN_ENV))
    client = session or _requests()
    response = None
    try:
        response = client.get(
            profile.status_endpoint,
            params={"receiptId": str(receipt_id)},
            headers={"Accept": "application/json", "Authorization": token},
            timeout=(3.05, 10.0),
            allow_redirects=False,
            stream=True,
        )
        status = int(getattr(response, "status_code", 0) or 0)
        payload = _bounded_json(response)
        if status != 200:
            _raise_http(status, payload, missing_is_retryable=True)
        return _status_receipt(payload, receipt_id)
    except ProjectDeliveryError:
        raise
    except Exception as error:
        if _is_request_error(error):
            raise RetryableProjectDeliveryError("NETWORK_OR_TIMEOUT") from error
        raise
    finally:
        if response is not None:
            close = getattr(response, "close", None)
            if callable(close):
                close()


def _signature(
    secret: bytes,
    *,
    key_id: str,
    timestamp: str,
    request_id: str,
    body: bytes,
) -> str:
    signing_input = (
        f"npi-webhook-v1\nPOST\n{EVENT_PATH}\n{key_id}\n"
        f"{timestamp}\n{request_id}\n"
    ).encode("utf-8") + body
    return f"v1={hmac.new(secret, signing_input, hashlib.sha256).hexdigest()}"


def _accepted_receipt(
    value: object,
    event: ProjectSourceEvent,
) -> AcceptedProjectReceipt:
    keys = {
        "receiptId",
        "eventId",
        "state",
        "exactDuplicate",
        "requestId",
        "traceId",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RetryableProjectDeliveryError("INVALID_ACCEPTED_RESPONSE_SHAPE")
    try:
        receipt_id = UUID(str(value["receiptId"]))
    except (TypeError, ValueError) as error:
        raise RetryableProjectDeliveryError("INVALID_ACCEPTED_RESPONSE_BINDING") from error
    if (
        str(receipt_id) != value["receiptId"]
        or value["eventId"] != str(event.event_id)
        or value["requestId"] != str(event.request_id)
        or value["traceId"] != event.trace_id
        or value["state"] not in _STATES
        or type(value["exactDuplicate"]) is not bool
    ):
        raise RetryableProjectDeliveryError("INVALID_ACCEPTED_RESPONSE_BINDING")
    return AcceptedProjectReceipt(
        receipt_id=receipt_id,
        state=str(value["state"]),
        exact_duplicate=bool(value["exactDuplicate"]),
    )


def _status_receipt(value: object, receipt_id: UUID) -> ProjectReceiptStatus:
    keys = {
        "receiptId",
        "eventId",
        "state",
        "terminal",
        "disposition",
        "projectGlobalId",
        "errorCode",
        "traceId",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RetryableProjectDeliveryError("INVALID_STATUS_RESPONSE_SHAPE")
    project_id = value["projectGlobalId"]
    try:
        parsed_project_id = UUID(project_id) if project_id is not None else None
    except (TypeError, ValueError) as error:
        raise RetryableProjectDeliveryError("INVALID_STATUS_RESPONSE_BINDING") from error
    state = value["state"]
    terminal = value["terminal"]
    error_code = value["errorCode"]
    if (
        value["receiptId"] != str(receipt_id)
        or state not in _STATES
        or type(terminal) is not bool
        or terminal
        != (
            state
            in {
                "succeeded",
                "failed_final",
                "quarantined",
                "superseded",
                "received_after_creation",
            }
        )
        or not isinstance(value["eventId"], str)
        or not isinstance(value["traceId"], str)
        or not isinstance(value["disposition"], str)
        or (error_code is not None and not isinstance(error_code, str))
        or (state == "succeeded" and parsed_project_id is None)
        or (state != "succeeded" and parsed_project_id is not None)
    ):
        raise RetryableProjectDeliveryError("INVALID_STATUS_RESPONSE_BINDING")
    return ProjectReceiptStatus(
        receipt_id=receipt_id,
        state=str(state),
        terminal=terminal,
        disposition=str(value["disposition"]),
        project_global_id=parsed_project_id,
        error_code=error_code,
    )


def _bounded_json(response: object) -> object:
    iterator = getattr(response, "iter_content", None)
    if not callable(iterator):
        raise RetryableProjectDeliveryError("INVALID_RESPONSE_STREAM")
    body = bytearray()
    try:
        for chunk in iterator(chunk_size=8192):
            if not isinstance(chunk, bytes):
                raise RetryableProjectDeliveryError("INVALID_RESPONSE_STREAM")
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RetryableProjectDeliveryError("RESPONSE_TOO_LARGE")
        return json.loads(body.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise RetryableProjectDeliveryError("INVALID_RESPONSE_ENCODING") from error
    except json.JSONDecodeError as error:
        raise RetryableProjectDeliveryError("INVALID_RESPONSE_JSON") from error


def _raise_http(
    status: int,
    payload: object,
    *,
    missing_is_retryable: bool = False,
) -> None:
    code = None
    if isinstance(payload, Mapping) and isinstance(payload.get("code"), str):
        candidate = str(payload["code"])
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", candidate):
            code = candidate
    error_code = code or f"HTTP_{status or 0}"
    if (
        status in {408, 425, 429}
        or 500 <= status <= 599
        or (missing_is_retryable and status == 404)
    ):
        raise RetryableProjectDeliveryError(error_code)
    raise PermanentProjectDeliveryError(error_code)


def _signing_secret(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or not 32 <= len(value) <= 512
        or any(character in value for character in "\r\n\x00")
    ):
        raise PermanentProjectDeliveryError("SIGNING_SECRET_UNAVAILABLE")
    return value.encode("utf-8")


def _service_token(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 1024
        or not value.startswith("token ")
        or ":" not in value[6:]
        or any(character in value for character in "\r\n")
    ):
        raise PermanentProjectDeliveryError("SERVICE_TOKEN_UNAVAILABLE")
    return value


def _requests():
    import requests

    return requests


def _is_request_error(error: Exception) -> bool:
    try:
        import requests
    except ImportError:
        return False
    return isinstance(error, requests.RequestException)
