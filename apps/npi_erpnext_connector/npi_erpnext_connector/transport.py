from __future__ import annotations

import os
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from npi_erpnext_connector.config import TOKEN_ENV, SenderProfile
from npi_erpnext_connector.domain import AuthorizationEvent


_HASH = re.compile(r"^[a-f0-9]{64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_LOCAL_USER_STATES = {"enabled", "disabled", "absent_disabled"}
_LOCAL_USER_DISPOSITIONS = {
    "created",
    "enabled",
    "retained",
    "disabled",
    "absent_disabled",
    "exact_replay",
}
MAX_RESPONSE_BYTES = 65_536


class DeliveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RetryableDeliveryError(DeliveryError):
    pass


class PermanentDeliveryError(DeliveryError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    projection_hash: str
    state: str
    local_user_state: str
    local_user_disposition: str
    exact_replay: bool


def deliver(
    profile: SenderProfile,
    event: AuthorizationEvent,
    *,
    session: object | None = None,
    environment: Mapping[str, str] | None = None,
) -> DeliveryReceipt:
    runtime_environment = os.environ if environment is None else environment
    token = _token(runtime_environment.get(TOKEN_ENV))
    client = session or _requests()
    try:
        response = client.put(
            profile.endpoint,
            json=dict(event.event),
            headers={
                "Accept": "application/json",
                "Authorization": token,
                "Content-Type": "application/json",
                "X-Request-ID": str(event.request_id),
            },
            timeout=(3.05, 10.0),
            allow_redirects=False,
            stream=True,
        )
    except Exception as error:
        if _is_request_error(error):
            raise RetryableDeliveryError("NETWORK_OR_TIMEOUT") from error
        raise
    try:
        status = int(getattr(response, "status_code", 0) or 0)
        if status != 200:
            if status in {408, 425, 429} or 500 <= status <= 599:
                raise RetryableDeliveryError(f"HTTP_{status or 0}")
            raise PermanentDeliveryError(f"HTTP_{status or 0}")
        payload = _bounded_json(response)
        return _receipt(payload, event)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _receipt(value: object, event: AuthorizationEvent) -> DeliveryReceipt:
    keys = {
        "projectionId",
        "sourceVersion",
        "state",
        "projectionHash",
        "exactReplay",
        "localUserState",
        "localUserDisposition",
        "requestId",
        "traceId",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RetryableDeliveryError("INVALID_RESPONSE_SHAPE")
    expected_state = "enabled" if event.event["enabled"] else "disabled"
    if (
        type(value["sourceVersion"]) is not int
        or value["sourceVersion"] != event.event["sourceVersion"]
        or not isinstance(value["state"], str)
        or value["state"] != expected_state
        or value["traceId"] != event.trace_id
        or value["requestId"] != str(event.request_id)
        or not isinstance(value["exactReplay"], bool)
        or not isinstance(value["localUserState"], str)
        or value["localUserState"] not in _LOCAL_USER_STATES
        or not isinstance(value["localUserDisposition"], str)
        or value["localUserDisposition"] not in _LOCAL_USER_DISPOSITIONS
        or not isinstance(value["projectionHash"], str)
        or _HASH.fullmatch(value["projectionHash"]) is None
        or not isinstance(value["projectionId"], str)
        or _UUID.fullmatch(value["projectionId"]) is None
    ):
        raise RetryableDeliveryError("INVALID_RESPONSE_BINDING")
    return DeliveryReceipt(
        projection_hash=value["projectionHash"],
        state=value["state"],
        local_user_state=value["localUserState"],
        local_user_disposition=value["localUserDisposition"],
        exact_replay=value["exactReplay"],
    )


def _bounded_json(response: object) -> object:
    iterator = getattr(response, "iter_content", None)
    if not callable(iterator):
        raise RetryableDeliveryError("INVALID_RESPONSE_STREAM")
    body = bytearray()
    try:
        for chunk in iterator(chunk_size=8192):
            if not isinstance(chunk, bytes):
                raise RetryableDeliveryError("INVALID_RESPONSE_STREAM")
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RetryableDeliveryError("RESPONSE_TOO_LARGE")
        return json.loads(body.decode("utf-8"))
    except (TypeError, UnicodeDecodeError) as error:
        raise RetryableDeliveryError("INVALID_RESPONSE_ENCODING") from error
    except json.JSONDecodeError as error:
        raise RetryableDeliveryError("INVALID_RESPONSE_JSON") from error


def _token(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 1024
        or not value.startswith("token ")
        or ":" not in value[6:]
        or any(character in value for character in "\r\n")
    ):
        raise PermanentDeliveryError("SERVICE_TOKEN_UNAVAILABLE")
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
