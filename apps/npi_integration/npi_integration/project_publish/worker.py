from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import frappe

from .config import ProjectPublishProfile, load_profile
from .connector_runtime import load_credential, publish, reconcile
from .domain import (
    MAX_ATTEMPTS,
    MAX_AUTOMATIC_ATTEMPTS,
    ProjectPublishError,
    ProjectSource,
    PublishCommand,
    ReconcileCommand,
    TargetObservation,
    canonical_hash,
    parse_uuid,
    restore_source,
)
from .frappe_validation import (
    insert_support_document,
    project_publish_write,
    save_support_document,
)
from .service import ATTEMPT_DOCTYPE, JOB_PATH, REQUEST_DOCTYPE, RESULT_DOCTYPE


LEASE_MINUTES = 5
RECOVERY_LIMIT = 100


@dataclass(frozen=True, slots=True)
class Claim:
    request_global_id: str
    attempt_global_id: str
    attempt_number: int
    claim_token: str
    kind: str
    source: ProjectSource


def process_request(request_global_id: str) -> dict[str, object]:
    request_id = parse_uuid(request_global_id, "requestGlobalId")
    request = frappe.get_doc(REQUEST_DOCTYPE, request_id)
    kind = "reconcile" if str(request.state) == "uncertain" else "publish"
    claim = _claim(request_id, kind=kind)
    if claim is None:
        return _status(request_id, "not_claimed")
    try:
        profile = _profile(claim)
        credential = load_credential(profile)
    except Exception as error:
        _complete_before_boundary(claim, _configuration_error(error))
        return _status(request_id)
    try:
        _mark_adapter_boundary(claim, profile)
    except Exception:
        _complete_before_boundary(claim, "PROJECT_PUBLISH_EXECUTION_ROUTE_CONFLICT", final=True)
        return _status(request_id)
    try:
        if claim.kind == "reconcile":
            observation = reconcile(
                ReconcileCommand(claim.request_global_id, claim.attempt_global_id, claim.source),
                profile,
                credential,
            )
            _complete_reconcile(claim, observation)
        else:
            observation = publish(
                PublishCommand(claim.request_global_id, claim.attempt_global_id, claim.attempt_number, claim.source),
                profile,
                credential,
            )
            _complete_publish(claim, observation)
    except Exception as error:
        _complete_uncertain(claim, error)
    return _status(request_id)


def recover_project_publish_requests() -> int:
    now = datetime.now(UTC).replace(tzinfo=None)
    names: list[str] = []
    for state in ("pending", "failed_retryable", "processing", "uncertain"):
        rows = frappe.get_all(
            REQUEST_DOCTYPE,
            filters={"state": state},
            fields=["name", "next_retry_at", "lease_expires_at"],
            order_by="updated_at asc, name asc",
            page_length=RECOVERY_LIMIT + 1,
        )
        for row in rows[:RECOVERY_LIMIT]:
            due = row.get("lease_expires_at") if state == "processing" else row.get("next_retry_at")
            if state == "pending" or due is None or due <= now:
                names.append(str(row["name"]))
            if len(names) >= RECOVERY_LIMIT:
                break
        if len(names) >= RECOVERY_LIMIT:
            break
    for name in names:
        frappe.enqueue(
            JOB_PATH,
            queue="short",
            job_id=f"npi-erp-project-publish-{name}",
            request_global_id=name,
        )
    return len(names)


def _claim(request_id: str, *, kind: str) -> Claim | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    request = frappe.get_doc(REQUEST_DOCTYPE, request_id, for_update=True)
    source = restore_source(request.source_snapshot, expected_hash=request.source_hash)
    if request.state == "processing":
        if request.lease_expires_at and request.lease_expires_at > now:
            frappe.db.rollback()
            return None
        _recover_expired_claim(request, now)
        frappe.db.commit()
        return None
    allowed = {"uncertain"} if kind == "reconcile" else {"pending", "failed_retryable"}
    if request.state not in allowed:
        frappe.db.rollback()
        return None
    if request.next_retry_at and request.next_retry_at > now:
        frappe.db.rollback()
        return None
    if kind == "publish" and request.state == "failed_retryable" and int(request.attempt_count or 0) >= MAX_AUTOMATIC_ATTEMPTS:
        with project_publish_write(request_id) as capability:
            request.state = "failed_final"
            request.last_error_code = "PROJECT_PUBLISH_AUTOMATIC_RETRY_LIMIT_REACHED"
            request.updated_at = now
            save_support_document(request, capability=capability)
        frappe.db.commit()
        return None
    attempt_number = int(request.attempt_count or 0) + 1
    if attempt_number > MAX_ATTEMPTS:
        with project_publish_write(request_id) as capability:
            request.state = "failed_final"
            request.last_error_code = "PROJECT_PUBLISH_ATTEMPT_LIMIT_REACHED"
            request.next_retry_at = None
            request.updated_at = now
            save_support_document(request, capability=capability)
        frappe.db.commit()
        return None
    attempt_id, claim_token = str(uuid4()), str(uuid4())
    with project_publish_write(request_id) as capability:
        attempt = frappe.get_doc({
            "doctype": ATTEMPT_DOCTYPE,
            "global_id": attempt_id,
            "request_global_id": request_id,
            "attempt_number": attempt_number,
            "attempt_kind": kind,
            "attempt_key_hash": canonical_hash({"requestGlobalId": request_id, "attemptKind": kind, "attemptNumber": attempt_number}),
            "state": "started",
            "adapter_boundary_crossed": 0,
            "response_authenticated": 0,
            "response_contract_valid": 0,
            "trace_id": f"project-publish-{kind}-{attempt_id}",
            "started_at": now,
        })
        insert_support_document(attempt, capability=capability)
        request.state = "processing"
        request.attempt_count = attempt_number
        request.claim_token = claim_token
        request.claimed_at = now
        request.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
        request.adapter_boundary_crossed = 0
        request.last_attempt_global_id = attempt_id
        request.next_retry_at = None
        request.updated_at = now
        save_support_document(request, capability=capability)
    frappe.db.commit()
    return Claim(request_id, attempt_id, attempt_number, claim_token, kind, source)


def _profile(claim: Claim) -> ProjectPublishProfile:
    profile = load_profile(frappe.conf, claim.source.tenant_id)
    if profile is None:
        raise ProjectPublishError("Project publication profile is unavailable.")
    return profile


def _mark_adapter_boundary(claim: Claim, profile: ProjectPublishProfile) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    request, attempt = _locked_claim(claim)
    bound = (str(request.profile_id or ""), int(request.profile_version or 0), str(request.profile_snapshot_hash or ""), str(request.environment_code or ""), str(request.service_actor_user_id or ""))
    current = (profile.profile_id, profile.profile_version, profile.snapshot_hash, profile.environment_code, profile.service_actor_user_id)
    if bound[2] and bound != current:
        raise ProjectPublishError("Project publication execution route drifted.")
    with project_publish_write(claim.request_global_id) as capability:
        if not bound[2]:
            request.profile_id, request.profile_version, request.profile_snapshot_hash, request.environment_code, request.service_actor_user_id = current
        request.adapter_boundary_crossed = 1
        request.updated_at = now
        attempt.adapter_boundary_crossed = 1
        save_support_document(attempt, capability=capability)
        save_support_document(request, capability=capability)
    frappe.db.commit()


def _complete_publish(claim: Claim, observation: TargetObservation) -> None:
    if not observation.authenticated or not observation.contract_valid:
        _complete(claim, "uncertain", "uncertain", observation, "PROJECT_PUBLISH_RESPONSE_UNVERIFIED")
    elif 200 <= observation.http_status < 300 and observation.formal_project_id and observation.target_version:
        _complete(claim, "succeeded", "succeeded", observation, None)
    elif observation.http_status == 429 or observation.http_status >= 500:
        final = claim.attempt_number >= MAX_AUTOMATIC_ATTEMPTS
        state = "failed_final" if final else "failed_retryable"
        _complete(claim, state, state, observation, observation.error_code or "PROJECT_PUBLISH_TARGET_RETRYABLE_FAILURE")
    else:
        _complete(claim, "failed_final", "failed_final", observation, observation.error_code or "PROJECT_PUBLISH_TARGET_REJECTED")


def _complete_reconcile(claim: Claim, observation: TargetObservation) -> None:
    if not observation.authenticated or not observation.contract_valid:
        _complete(claim, "uncertain", "uncertain", observation, "PROJECT_PUBLISH_RECONCILIATION_UNVERIFIED")
    elif 200 <= observation.http_status < 300 and observation.found is True and observation.formal_project_id and observation.target_version:
        _complete(claim, "reconciled_present", "succeeded", observation, None)
    elif 200 <= observation.http_status < 300 and observation.found is False:
        _complete(claim, "reconciled_absent", "pending", observation, None)
        frappe.enqueue(JOB_PATH, queue="short", job_id=f"npi-erp-project-publish-{claim.request_global_id}", request_global_id=claim.request_global_id)
    else:
        _complete(claim, "failed_final", "uncertain", observation, observation.error_code or "PROJECT_PUBLISH_RECONCILIATION_UNAVAILABLE")


def _complete_before_boundary(claim: Claim, error_code: str, *, final: bool = False) -> None:
    final = final or claim.attempt_number >= MAX_AUTOMATIC_ATTEMPTS
    state = "failed_final" if final else "failed_retryable"
    _complete(claim, state, state, None, error_code)


def _complete_uncertain(claim: Claim, error: Exception) -> None:
    _complete(claim, "uncertain", "uncertain", None, "PROJECT_PUBLISH_ADAPTER_OUTCOME_UNCERTAIN", fallback_hash=hashlib.sha256(type(error).__name__.encode()).hexdigest())


def _complete(claim: Claim, attempt_state: str, request_state: str, observation: TargetObservation | None, error_code: str | None, *, fallback_hash: str | None = None) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    request, attempt = _locked_claim(claim)
    response_hash = observation.response_hash if observation else fallback_hash
    result_id = str(uuid4())
    with project_publish_write(claim.request_global_id) as capability:
        result = frappe.get_doc({
            "doctype": RESULT_DOCTYPE,
            "global_id": result_id,
            "request_global_id": claim.request_global_id,
            "attempt_global_id": claim.attempt_global_id,
            "state": request_state,
            "response_authenticated": int(bool(observation and observation.authenticated)),
            "response_contract_valid": int(bool(observation and observation.contract_valid)),
            "http_status": observation.http_status if observation else None,
            "response_hash": response_hash,
            "formal_erp_project_id": observation.formal_project_id if observation else None,
            "target_version": observation.target_version if observation else None,
            "exact_replay": int(bool(observation and observation.exact_replay)),
            "error_code": error_code,
            "observed_at": now,
        })
        insert_support_document(result, capability=capability)
        attempt.state = attempt_state
        attempt.response_authenticated = int(bool(observation and observation.authenticated))
        attempt.response_contract_valid = int(bool(observation and observation.contract_valid))
        attempt.http_status = observation.http_status if observation else None
        attempt.response_hash = response_hash
        attempt.error_code = error_code
        attempt.completed_at = now
        save_support_document(attempt, capability=capability)
        request.state = request_state
        request.claim_token = None
        request.claimed_at = None
        request.lease_expires_at = None
        request.last_http_status = observation.http_status if observation else None
        request.response_hash = response_hash
        request.last_error_code = error_code
        request.result_global_id = result_id
        request.next_retry_at = (
            now + timedelta(minutes=min(60, 2 ** min(claim.attempt_number, 6)))
            if request_state in {"failed_retryable", "uncertain"}
            else None
        )
        if request_state == "succeeded" and observation:
            request.formal_erp_project_id = observation.formal_project_id
            request.target_version = observation.target_version
            request.exact_replay = int(observation.exact_replay)
            request.completed_at = now
        if request_state == "pending":
            request.adapter_boundary_crossed = 0
        request.updated_at = now
        save_support_document(request, capability=capability)
    frappe.db.commit()


def _recover_expired_claim(request: object, now: datetime) -> None:
    request_id = str(request.global_id)
    attempt_id = str(request.last_attempt_global_id or "")
    crossed = bool(request.adapter_boundary_crossed)
    with project_publish_write(request_id) as capability:
        if attempt_id:
            attempt = frappe.get_doc(ATTEMPT_DOCTYPE, attempt_id, for_update=True)
            if attempt.state == "started":
                attempt.state = "uncertain" if crossed else "failed_retryable"
                attempt.error_code = "PROJECT_PUBLISH_EXPIRED_AFTER_ADAPTER_BOUNDARY" if crossed else "PROJECT_PUBLISH_EXPIRED_BEFORE_ADAPTER_BOUNDARY"
                attempt.completed_at = now
                save_support_document(attempt, capability=capability)
        request.state = "uncertain" if crossed else "failed_retryable"
        request.last_error_code = "PROJECT_PUBLISH_EXPIRED_AFTER_ADAPTER_BOUNDARY" if crossed else "PROJECT_PUBLISH_EXPIRED_BEFORE_ADAPTER_BOUNDARY"
        request.claim_token = request.claimed_at = request.lease_expires_at = None
        request.next_retry_at = None if crossed else now
        request.updated_at = now
        save_support_document(request, capability=capability)


def _locked_claim(claim: Claim) -> tuple[object, object]:
    request = frappe.get_doc(REQUEST_DOCTYPE, claim.request_global_id, for_update=True)
    attempt = frappe.get_doc(ATTEMPT_DOCTYPE, claim.attempt_global_id, for_update=True)
    if request.state != "processing" or str(request.claim_token or "") != claim.claim_token or str(request.last_attempt_global_id or "") != claim.attempt_global_id or attempt.state != "started":
        frappe.db.rollback()
        raise RuntimeError("ERP Project publication claim was lost.")
    return request, attempt


def _status(request_id: str, fallback: str | None = None) -> dict[str, object]:
    values = frappe.db.get_value(REQUEST_DOCTYPE, request_id, ["state", "attempt_count", "formal_erp_project_id", "target_version", "last_error_code"], as_dict=True)
    if not values:
        return {"requestGlobalId": request_id, "state": fallback or "unavailable"}
    return {"requestGlobalId": request_id, "state": fallback or str(values.state), "attemptCount": int(values.attempt_count or 0), "formalErpProjectId": values.formal_erp_project_id, "targetVersion": values.target_version, "lastErrorCode": values.last_error_code}


def _configuration_error(error: Exception) -> str:
    return "PROJECT_PUBLISH_EXECUTION_CONFIGURATION_UNAVAILABLE" if isinstance(error, ProjectPublishError) else "PROJECT_PUBLISH_EXECUTION_CONFIGURATION_INVALID"
