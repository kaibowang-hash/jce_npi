from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from .domain import EngineeringChangeIntegrationError


WEBHOOK_METHOD = "POST"
WEBHOOK_PATH = "/api/npi/v1/integration/erpnext/engineering-change-events"
REPLAY_WINDOW_SECONDS = 300
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SIGNATURE = re.compile(r"^v1=[a-f0-9]{64}$")
_TIMESTAMP = re.compile(r"^(?:0|[1-9][0-9]{0,11})$")


class SignatureError(ValueError):
    """Generic signature failure that intentionally hides its cause."""


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
            raise SignatureError("Webhook authentication failed.") from error
        if (
            request_id != self.request_id
            or _KEY_ID.fullmatch(self.key_id) is None
            or _TIMESTAMP.fullmatch(self.timestamp) is None
            or _SIGNATURE.fullmatch(self.signature) is None
        ):
            raise SignatureError("Webhook authentication failed.")

    @property
    def signed_at(self) -> datetime:
        try:
            return datetime.fromtimestamp(int(self.timestamp), tz=UTC)
        except (OverflowError, OSError, ValueError) as error:
            raise SignatureError("Webhook authentication failed.") from error


def signing_input(*, method: str, path: str, headers: SignatureHeaders, raw_body: bytes) -> bytes:
    if method != WEBHOOK_METHOD or path != WEBHOOK_PATH or not isinstance(raw_body, bytes):
        raise SignatureError("Webhook authentication failed.")
    return (
        f"npi-change-webhook-v1\n{method}\n{path}\n{headers.key_id}\n"
        f"{headers.timestamp}\n{headers.request_id}\n"
    ).encode("utf-8") + raw_body


def sign_request(*, secret: bytes, method: str, path: str, headers: SignatureHeaders, raw_body: bytes) -> str:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise EngineeringChangeIntegrationError("Webhook secret reference is unavailable.")
    digest = hmac.new(secret, signing_input(method=method, path=path, headers=headers, raw_body=raw_body), sha256).hexdigest()
    return f"v1={digest}"


def verify_request_signature(*, secret: bytes, method: str, path: str, headers: SignatureHeaders, raw_body: bytes, now: datetime) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise EngineeringChangeIntegrationError("Server time must be timezone-aware.")
    if abs((now.astimezone(UTC) - headers.signed_at).total_seconds()) > REPLAY_WINDOW_SECONDS:
        raise SignatureError("Webhook authentication failed.")
    expected = sign_request(secret=secret, method=method, path=path, headers=headers, raw_body=raw_body)
    if not hmac.compare_digest(expected, headers.signature):
        raise SignatureError("Webhook authentication failed.")
