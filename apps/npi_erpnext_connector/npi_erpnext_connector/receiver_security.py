from __future__ import annotations

import hashlib
import hmac
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

from npi_erpnext_connector.item_contract import canonical_json

SIGNATURE_VERSION = "npi-hmac-sha256-v1"
MAX_CLOCK_SKEW_SECONDS = 300
_SIGNATURE = re.compile(r"^[a-f0-9]{64}$")
_PATH = re.compile(r"^/api/method/npi_erpnext_connector\.[A-Za-z0-9_.]{1,180}$")
_ACTOR = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReceiverAuthenticationError(ValueError):
    """Raised when an operation request cannot be authenticated exactly."""


def business_actor_is_enabled(actor_user_id: object, *, service_user: object) -> bool:
    """Return whether an ERP-synchronised business actor can own target documents."""

    if (
        not isinstance(actor_user_id, str)
        or actor_user_id != actor_user_id.casefold()
        or len(actor_user_id) > 254
        or _ACTOR.fullmatch(actor_user_id) is None
        or actor_user_id in {"guest", "administrator"}
        or not isinstance(service_user, str)
        or actor_user_id == service_user.casefold()
    ):
        return False
    import frappe

    user = frappe.db.get_value(
        "User",
        actor_user_id,
        ["enabled", "user_type"],
        as_dict=True,
    )
    return bool(
        user and user.get("enabled") == 1 and user.get("user_type") == "System User"
    )


@contextmanager
def business_actor_context(actor_user_id: str) -> Iterator[None]:
    """Attribute one bounded target create to its validated business actor."""

    import frappe

    previous_user = str(getattr(frappe.session, "user", "") or "Guest")
    frappe.set_user(actor_user_id)
    try:
        yield
    finally:
        frappe.set_user(previous_user)


def request_signature(secret: str, path: str, timestamp: str, body: bytes) -> str:
    key = _secret(secret)
    normalized_path = _path(path)
    normalized_timestamp = _timestamp(timestamp)
    message = "\n".join(
        (
            SIGNATURE_VERSION,
            "POST",
            normalized_path,
            normalized_timestamp,
            hashlib.sha256(body).hexdigest(),
        )
    ).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_request(
    *,
    secret: str,
    path: str,
    timestamp: str,
    signature: str,
    body: bytes,
    now: int | None = None,
) -> None:
    observed_at = int(time.time()) if now is None else now
    signed_at = int(_timestamp(timestamp))
    if abs(observed_at - signed_at) > MAX_CLOCK_SKEW_SECONDS:
        raise ReceiverAuthenticationError(
            "Integration request timestamp is outside the allowed window."
        )
    if not isinstance(signature, str) or _SIGNATURE.fullmatch(signature) is None:
        raise ReceiverAuthenticationError("Integration request signature is invalid.")
    expected = request_signature(secret, path, timestamp, body)
    if not hmac.compare_digest(expected, signature):
        raise ReceiverAuthenticationError("Integration request signature is invalid.")


def signed_response(
    payload: dict[str, object], secret: str, *, now: int | None = None
) -> dict[str, object]:
    signed_at = int(time.time()) if now is None else now
    value = {**payload, "signatureVersion": SIGNATURE_VERSION, "signedAt": signed_at}
    signature = hmac.new(
        _secret(secret),
        canonical_json(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**value, "responseSignature": signature}


def verify_response(
    value: object, secret: str, *, now: int | None = None
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReceiverAuthenticationError("Integration response shape is invalid.")
    payload = dict(value)
    signature = payload.pop("responseSignature", None)
    if not isinstance(signature, str) or _SIGNATURE.fullmatch(signature) is None:
        raise ReceiverAuthenticationError("Integration response signature is invalid.")
    if payload.get("signatureVersion") != SIGNATURE_VERSION:
        raise ReceiverAuthenticationError(
            "Integration response signature version is unsupported."
        )
    signed_at = payload.get("signedAt")
    if type(signed_at) is not int:
        raise ReceiverAuthenticationError("Integration response timestamp is invalid.")
    observed_at = int(time.time()) if now is None else now
    if abs(observed_at - signed_at) > MAX_CLOCK_SKEW_SECONDS:
        raise ReceiverAuthenticationError(
            "Integration response timestamp is outside the allowed window."
        )
    expected = hmac.new(
        _secret(secret),
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ReceiverAuthenticationError("Integration response signature is invalid.")
    return payload


def _secret(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or not 24 <= len(value) <= 1024
        or any(character in value for character in "\r\n")
    ):
        raise ReceiverAuthenticationError("Integration service secret is unavailable.")
    return value.encode("utf-8")


def _path(value: object) -> str:
    if not isinstance(value, str) or _PATH.fullmatch(value) is None:
        raise ReceiverAuthenticationError("Integration request path is invalid.")
    return value


def _timestamp(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or len(value) > 12
    ):
        raise ReceiverAuthenticationError("Integration request timestamp is invalid.")
    parsed = int(value)
    if parsed < 1:
        raise ReceiverAuthenticationError("Integration request timestamp is invalid.")
    return str(parsed)
