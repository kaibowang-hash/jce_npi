from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from .domain import ProjectSourceContractError


WEBHOOK_METHOD = "POST"
WEBHOOK_PATH = "/api/npi/v1/integration/erpnext/project-source-events"
SIGNATURE_VERSION = "v1"
REPLAY_WINDOW_SECONDS = 300
_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SIGNATURE_PATTERN = re.compile(r"^v1=[a-f0-9]{64}$")
_TIMESTAMP_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,11})$")


class WebhookAuthenticationError(ValueError):
    """Generic authentication failure that intentionally hides its cause."""


@dataclass(frozen=True, slots=True)
class SignatureHeaders:
    request_id: str
    key_id: str
    timestamp: str
    signature: str

    def __post_init__(self) -> None:
        try:
            request_id = str(UUID(self.request_id))
        except (AttributeError, TypeError, ValueError) as error:
            raise WebhookAuthenticationError("Webhook authentication failed.") from error
        if request_id != self.request_id:
            raise WebhookAuthenticationError("Webhook authentication failed.")
        if (
            not isinstance(self.key_id, str)
            or _KEY_ID_PATTERN.fullmatch(self.key_id) is None
            or not isinstance(self.timestamp, str)
            or _TIMESTAMP_PATTERN.fullmatch(self.timestamp) is None
            or not isinstance(self.signature, str)
            or _SIGNATURE_PATTERN.fullmatch(self.signature) is None
        ):
            raise WebhookAuthenticationError("Webhook authentication failed.")

    @property
    def unix_seconds(self) -> int:
        return int(self.timestamp)

    @property
    def signed_at(self) -> datetime:
        try:
            return datetime.fromtimestamp(self.unix_seconds, tz=UTC)
        except (OverflowError, OSError, ValueError) as error:
            raise WebhookAuthenticationError("Webhook authentication failed.") from error


def signing_input(
    *,
    method: str,
    path: str,
    headers: SignatureHeaders,
    raw_body: bytes,
) -> bytes:
    if method != WEBHOOK_METHOD or path != WEBHOOK_PATH:
        raise WebhookAuthenticationError("Webhook authentication failed.")
    if not isinstance(headers, SignatureHeaders) or not isinstance(raw_body, bytes):
        raise WebhookAuthenticationError("Webhook authentication failed.")
    prefix = (
        f"npi-webhook-v1\n{WEBHOOK_METHOD}\n{WEBHOOK_PATH}\n"
        f"{headers.key_id}\n{headers.timestamp}\n{headers.request_id}\n"
    ).encode("utf-8")
    return prefix + raw_body


def sign_request(
    *,
    secret: bytes,
    method: str,
    path: str,
    headers: SignatureHeaders,
    raw_body: bytes,
) -> str:
    key = _secret_bytes(secret)
    digest = hmac.new(
        key,
        signing_input(method=method, path=path, headers=headers, raw_body=raw_body),
        sha256,
    ).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def verify_request_signature(
    *,
    secret: bytes,
    method: str,
    path: str,
    headers: SignatureHeaders,
    raw_body: bytes,
    now: datetime,
) -> None:
    server_time = _aware_utc(now)
    signed_at = headers.signed_at
    if abs((server_time - signed_at).total_seconds()) > REPLAY_WINDOW_SECONDS:
        raise WebhookAuthenticationError("Webhook authentication failed.")
    expected = sign_request(
        secret=secret,
        method=method,
        path=path,
        headers=headers,
        raw_body=raw_body,
    )
    if not hmac.compare_digest(expected, headers.signature):
        raise WebhookAuthenticationError("Webhook authentication failed.")


def _secret_bytes(value: object) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ProjectSourceContractError("Resolved webhook secret is invalid.")
    return value


def _aware_utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSourceContractError("Server time must be timezone-aware.")
    return value.astimezone(UTC)
