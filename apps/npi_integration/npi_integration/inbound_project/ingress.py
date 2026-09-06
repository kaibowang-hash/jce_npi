from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .config import InboundProjectProfile, ProjectIntakePolicy
from .domain import (
    MAX_RAW_BODY_BYTES,
    InboundProjectEvent,
    ProjectSourceContractError,
    parse_project_source_event,
)
from .signature import (
    WEBHOOK_METHOD,
    WEBHOOK_PATH,
    SignatureHeaders,
    WebhookAuthenticationError,
    verify_request_signature,
)


ProfileResolver = Callable[[], InboundProjectProfile | None]
SecretResolver = Callable[[str], bytes]


class InboundProjectIngressProblem(Exception):
    def __init__(self, *, status: int, code: str, retryable: bool = False) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class AuthenticatedProjectSourceRequest:
    profile: InboundProjectProfile
    policy: ProjectIntakePolicy
    headers: SignatureHeaders
    event: InboundProjectEvent
    raw_body: bytes
    received_at: datetime


def authenticate_project_source_request(
    *,
    method: str,
    path: str,
    content_type: str | None,
    content_encoding: str | None,
    raw_body: bytes,
    request_id: str | None,
    key_id: str | None,
    timestamp: str | None,
    signature: str | None,
    is_secure: bool,
    site_tenant_id: str,
    now: datetime,
    profile_resolver: ProfileResolver | None,
    secret_resolver: SecretResolver | None,
) -> AuthenticatedProjectSourceRequest:
    """Authenticate exact raw bytes before the closed event parser sees them."""
    if method != WEBHOOK_METHOD or path != WEBHOOK_PATH:
        raise _authentication_problem()
    if not _supported_media_type(content_type) or not _supported_encoding(
        content_encoding
    ):
        raise InboundProjectIngressProblem(
            status=415,
            code="INBOUND_PROJECT_MEDIA_TYPE_UNSUPPORTED",
        )
    if not isinstance(raw_body, bytes):
        raise TypeError("Raw webhook body must be bytes.")
    if len(raw_body) > MAX_RAW_BODY_BYTES:
        raise InboundProjectIngressProblem(
            status=413,
            code="INBOUND_PROJECT_BODY_TOO_LARGE",
        )
    try:
        headers = SignatureHeaders(
            request_id=request_id or "",
            key_id=key_id or "",
            timestamp=timestamp or "",
            signature=signature or "",
        )
    except WebhookAuthenticationError as error:
        raise _authentication_problem() from error

    profile = _resolve_profile(profile_resolver)
    if (
        not profile.enabled
        or not isinstance(site_tenant_id, str)
        or profile.tenant_id != site_tenant_id
    ):
        raise _unavailable_problem()
    if not is_secure and not profile.trusted_tls_termination:
        raise _authentication_problem()
    try:
        key = profile.key_at(headers.key_id, headers.signed_at)
    except (KeyError, ProjectSourceContractError, WebhookAuthenticationError) as error:
        raise _authentication_problem() from error
    if not callable(secret_resolver):
        raise _unavailable_problem()
    try:
        secret = secret_resolver(key.secret_reference)
    except Exception as error:
        raise _unavailable_problem() from error
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise _unavailable_problem()
    try:
        verify_request_signature(
            secret=secret,
            method=method,
            path=path,
            headers=headers,
            raw_body=raw_body,
            now=_utc(now),
        )
    except (ProjectSourceContractError, WebhookAuthenticationError) as error:
        raise _authentication_problem() from error
    try:
        event = parse_project_source_event(raw_body)
        policy = profile.policy_by_object_type[event.object_type]
    except (KeyError, ProjectSourceContractError) as error:
        raise InboundProjectIngressProblem(
            status=422,
            code="INBOUND_PROJECT_EVENT_INVALID",
        ) from error
    return AuthenticatedProjectSourceRequest(
        profile=profile,
        policy=policy,
        headers=headers,
        event=event,
        raw_body=raw_body,
        received_at=_utc(now),
    )


def _resolve_profile(
    resolver: ProfileResolver | None,
) -> InboundProjectProfile:
    if not callable(resolver):
        raise _unavailable_problem()
    try:
        profile = resolver()
    except Exception as error:
        raise _unavailable_problem() from error
    if not isinstance(profile, InboundProjectProfile):
        raise _unavailable_problem()
    return profile


def _supported_media_type(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    return normalized in {
        "application/json",
        "application/json;charset=utf-8",
        "application/json; charset=utf-8",
    }


def _supported_encoding(value: object) -> bool:
    return value in (None, "") or (
        isinstance(value, str) and value.strip().casefold() == "identity"
    )


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ProjectSourceContractError("Server time must be timezone-aware.")
    return value.astimezone(UTC)


def _authentication_problem() -> InboundProjectIngressProblem:
    return InboundProjectIngressProblem(
        status=401,
        code="INBOUND_PROJECT_AUTHENTICATION_FAILED",
    )


def _unavailable_problem() -> InboundProjectIngressProblem:
    return InboundProjectIngressProblem(
        status=503,
        code="INBOUND_PROJECT_INGRESS_UNAVAILABLE",
        retryable=True,
    )
