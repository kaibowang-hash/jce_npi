from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from npi_erpnext_connector.master_data_config import (
    TOKEN_ENV,
    MasterDataSenderProfile,
)
from npi_erpnext_connector.master_data_domain import MasterSnapshotEvent


MAX_RESPONSE_BYTES = 65_536
_HASH = re.compile(r"^[a-f0-9]{64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class MasterDataDeliveryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RetryableMasterDataDeliveryError(MasterDataDeliveryError):
    pass


class PermanentMasterDataDeliveryError(MasterDataDeliveryError):
    pass


@dataclass(frozen=True, slots=True)
class MasterDataReceipt:
    snapshot_id: str
    payload_hash: str
    exact_replay: bool


def deliver_master_snapshot(
    profile: MasterDataSenderProfile,
    event: MasterSnapshotEvent,
    *,
    session: object | None = None,
    environment: Mapping[str, str] | None = None,
) -> MasterDataReceipt:
    runtime = os.environ if environment is None else environment
    token = _token(runtime.get(TOKEN_ENV))
    client = session or _requests()
    response = None
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
            timeout=(3.05, 30.0),
            allow_redirects=False,
            stream=True,
        )
        status = int(getattr(response, "status_code", 0) or 0)
        payload = _bounded_json(response)
        if status != 200:
            code = _error_code(status, payload)
            if status in {408, 425, 429} or 500 <= status <= 599:
                raise RetryableMasterDataDeliveryError(code)
            raise PermanentMasterDataDeliveryError(code)
        return _receipt(payload, event)
    except MasterDataDeliveryError:
        raise
    except Exception as error:
        if _is_request_error(error):
            raise RetryableMasterDataDeliveryError("NETWORK_OR_TIMEOUT") from error
        raise
    finally:
        if response is not None:
            close = getattr(response, "close", None)
            if callable(close):
                close()


def _receipt(value: object, event: MasterSnapshotEvent) -> MasterDataReceipt:
    keys = {
        "snapshotId",
        "catalogKind",
        "sourceVersion",
        "recordCount",
        "payloadHash",
        "exactReplay",
        "requestId",
        "traceId",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_SHAPE")
    if (
        not isinstance(value["snapshotId"], str)
        or _UUID.fullmatch(value["snapshotId"]) is None
        or value["catalogKind"] != event.kind.value
        or value["sourceVersion"] != event.source_version
        or value["recordCount"] != len(event.event["records"])
        or value["payloadHash"] != event.payload_hash
        or not isinstance(value["payloadHash"], str)
        or _HASH.fullmatch(value["payloadHash"]) is None
        or type(value["exactReplay"]) is not bool
        or value["requestId"] != str(event.request_id)
        or value["traceId"] != event.trace_id
    ):
        raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_BINDING")
    return MasterDataReceipt(
        str(value["snapshotId"]),
        str(value["payloadHash"]),
        bool(value["exactReplay"]),
    )


def _bounded_json(response: object) -> object:
    iterator = getattr(response, "iter_content", None)
    if not callable(iterator):
        raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_STREAM")
    body = bytearray()
    try:
        for chunk in iterator(chunk_size=8192):
            if not isinstance(chunk, bytes):
                raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_STREAM")
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise RetryableMasterDataDeliveryError("RESPONSE_TOO_LARGE")
        return json.loads(body.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_ENCODING") from error
    except json.JSONDecodeError as error:
        raise RetryableMasterDataDeliveryError("INVALID_RESPONSE_JSON") from error


def _token(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 1024
        or not value.startswith("token ")
        or ":" not in value[6:]
        or any(character in value for character in "\r\n")
    ):
        raise PermanentMasterDataDeliveryError("SERVICE_TOKEN_UNAVAILABLE")
    return value


def _error_code(status: int, value: object) -> str:
    candidate = value.get("code") if isinstance(value, Mapping) else None
    if isinstance(candidate, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", candidate):
        return candidate
    return f"HTTP_{status or 0}"


def _requests():
    import requests

    return requests


def _is_request_error(error: Exception) -> bool:
    try:
        import requests
    except ImportError:
        return False
    return isinstance(error, requests.RequestException)
