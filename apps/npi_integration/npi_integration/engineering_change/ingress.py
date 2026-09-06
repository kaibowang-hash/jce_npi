from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .config import IntegrationProfile
from .domain import EngineeringChangeInboundEvent, EngineeringChangeIntegrationError, MAX_RAW_BODY_BYTES, TargetMode, parse_inbound_event
from .signature import SignatureError, SignatureHeaders, WEBHOOK_METHOD, WEBHOOK_PATH, verify_request_signature


ProfileResolver = Callable[[str, object], IntegrationProfile | None]
SecretResolver = Callable[[str], bytes]


class IngressProblem(Exception):
    def __init__(self, *, status: int, code: str, retryable: bool = False) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class AuthenticatedInboundRequest:
    profile: IntegrationProfile
    headers: SignatureHeaders
    event: EngineeringChangeInboundEvent
    raw_body: bytes
    received_at: datetime


def authenticate_inbound_request(
    *, method: str, path: str, content_type: str | None, content_encoding: str | None,
    raw_body: bytes, request_id: str | None, key_id: str | None, timestamp: str | None,
    signature: str | None, is_secure: bool, site_tenant_id: str, now: datetime,
    profile_resolver: ProfileResolver | None, secret_resolver: SecretResolver | None,
) -> AuthenticatedInboundRequest:
    if method != WEBHOOK_METHOD or path != WEBHOOK_PATH:
        raise _authentication()
    if content_type not in {"application/json", "application/json;charset=utf-8", "application/json; charset=utf-8"} or content_encoding not in (None, "", "identity"):
        raise IngressProblem(status=415, code="ENGINEERING_CHANGE_MEDIA_TYPE_UNSUPPORTED")
    if not isinstance(raw_body, bytes) or len(raw_body) > MAX_RAW_BODY_BYTES:
        raise IngressProblem(status=413, code="ENGINEERING_CHANGE_BODY_TOO_LARGE")
    try:
        headers = SignatureHeaders(request_id or "", key_id or "", timestamp or "", signature or "")
        event = parse_inbound_event(raw_body)
    except (SignatureError, EngineeringChangeIntegrationError) as error:
        raise _authentication() from error
    if not callable(profile_resolver):
        raise _unavailable()
    try:
        profile = profile_resolver(event.tenant_id, event.project_global_id)
    except Exception as error:
        raise _unavailable() from error
    if (
        not isinstance(profile, IntegrationProfile)
        or profile.target_mode is TargetMode.DISABLED
        or profile.tenant_id != site_tenant_id
        or profile.tenant_id != event.tenant_id
        or profile.project_global_id != str(event.project_global_id)
        or headers.key_id not in profile.signing_key_ids
        or not is_secure
        or not callable(secret_resolver)
    ):
        raise _unavailable()
    try:
        secret = secret_resolver(headers.key_id)
        verify_request_signature(secret=secret, method=method, path=path, headers=headers, raw_body=raw_body, now=now)
    except Exception as error:
        raise _authentication() from error
    return AuthenticatedInboundRequest(profile, headers, event, raw_body, _utc(now))


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise EngineeringChangeIntegrationError("Server time must be timezone-aware.")
    return value.astimezone(UTC)


def _authentication() -> IngressProblem:
    return IngressProblem(status=401, code="ENGINEERING_CHANGE_AUTHENTICATION_FAILED")


def _unavailable() -> IngressProblem:
    return IngressProblem(status=503, code="ENGINEERING_CHANGE_INGRESS_UNAVAILABLE", retryable=True)
