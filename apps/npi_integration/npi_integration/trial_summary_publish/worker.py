from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import frappe

from .config import TrialSummaryProfile, load_profile
from .connector_runtime import load_credential, publish, reconcile
from .domain import (
    MAX_ATTEMPTS,
    MAX_AUTOMATIC_ATTEMPTS,
    PublishCommand,
    ReconcileCommand,
    TargetObservation,
    TrialSummaryDeliveryError,
    canonical_hash,
    parse_uuid,
    source_fact_count,
    validate_persisted_source,
)
from .frappe_validation import (
    delivery_write,
    insert_support_document,
    save_support_document,
)
from .service import ATTEMPT_DOCTYPE, DELIVERY_DOCTYPE, JOB_PATH

LEASE_MINUTES = 5
RECONCILE_JOB_PATH = "npi_integration.trial_summary_publish.worker.reconcile_delivery"


@dataclass(frozen=True, slots=True)
class Claim:
    delivery_global_id: str
    attempt_global_id: str
    attempt_number: int
    claim_token: str
    kind: str
    tenant_id: str
    project_global_id: str
    actor_user_id: str
    source_hash: str
    target_idempotency_key_hash: str
    source: object


def process_delivery(delivery_global_id: str) -> dict[str, object]:
    delivery_id = parse_uuid(delivery_global_id, "deliveryGlobalId")
    claim = _claim(delivery_id, kind="publish")
    if claim is None:
        return _status(delivery_id, "not_claimed")
    try:
        profile = _profile(claim)
        credential = load_credential(profile)
    except Exception as error:
        _complete_before_boundary(claim, _configuration_error(error))
        return _status(delivery_id)
    try:
        _mark_adapter_boundary(claim, profile)
    except Exception:
        _complete_before_boundary(claim, "TRIAL_SUMMARY_EXECUTION_ROUTE_CONFLICT", final=True)
        return _status(delivery_id)
    command = PublishCommand(
        claim.delivery_global_id,
        claim.attempt_global_id,
        claim.attempt_number,
        claim.target_idempotency_key_hash,
        claim.source_hash,
        claim.actor_user_id,
        claim.source,
    )
    try:
        observation = publish(command, profile, credential)
    except Exception as error:
        _complete_uncertain(claim, error)
    else:
        _complete_publish_observation(claim, observation)
    return _status(delivery_id)


def reconcile_delivery(delivery_global_id: str) -> dict[str, object]:
    delivery_id = parse_uuid(delivery_global_id, "deliveryGlobalId")
    claim = _claim(delivery_id, kind="reconcile")
    if claim is None:
        return _status(delivery_id, "not_claimed")
    try:
        profile = _profile(claim)
        credential = load_credential(profile)
    except Exception as error:
        _complete_reconcile_unavailable(claim, _configuration_error(error))
        return _status(delivery_id)
    try:
        _mark_adapter_boundary(claim, profile)
    except Exception:
        _complete_reconcile_unavailable(
            claim,
            "TRIAL_SUMMARY_EXECUTION_ROUTE_CONFLICT",
            final=True,
        )
        return _status(delivery_id)
    command = ReconcileCommand(
        claim.delivery_global_id,
        claim.attempt_global_id,
        claim.target_idempotency_key_hash,
        claim.source_hash,
        parse_uuid(
            claim.source.get("summaryRevisionGlobalId"),
            "summaryRevisionGlobalId",
        ),
        source_fact_count(claim.source),
    )
    try:
        observation = reconcile(command, profile, credential)
    except Exception as error:
        _complete_reconcile_uncertain(claim, error)
    else:
        _complete_reconcile_observation(claim, observation)
    return _status(delivery_id)


def recover_trial_summary_deliveries() -> int:
    """Queue bounded pending/retryable work and recover expired leases."""

    now = datetime.now(UTC).replace(tzinfo=None)
    names: list[str] = []
    for state in ("pending", "failed_retryable", "processing"):
        rows = frappe.get_all(
            DELIVERY_DOCTYPE,
            filters={"state": state},
            fields=["name", "next_retry_at", "lease_expires_at"],
            order_by="updated_at asc, name asc",
            page_length=101,
        )
        for row in rows:
            due = row.next_retry_at if state == "failed_retryable" else row.lease_expires_at
            if state == "pending" or due is None or due <= now:
                names.append(str(row.name))
            if len(names) >= 100:
                break
        if len(names) >= 100:
            break
    queued = 0
    for name in names:
        frappe.enqueue(
            JOB_PATH,
            queue="short",
            job_name=f"trial-summary-delivery-{name}",
            delivery_global_id=name,
        )
        queued += 1
    return queued


def _claim(delivery_id: str, *, kind: str) -> Claim | None:
    now = datetime.now(UTC).replace(tzinfo=None)
    delivery = frappe.get_doc(DELIVERY_DOCTYPE, delivery_id, for_update=True)
    if delivery.state == "processing":
        lease = delivery.lease_expires_at
        if lease is not None and lease > now:
            frappe.db.rollback()
            return None
        _recover_expired_claim(delivery, now=now)
        frappe.db.commit()
        return None
    if kind == "publish":
        if delivery.state not in {"pending", "failed_retryable"}:
            frappe.db.rollback()
            return None
        if delivery.state == "failed_retryable" and delivery.next_retry_at and delivery.next_retry_at > now:
            frappe.db.rollback()
            return None
        if (
            delivery.state == "failed_retryable"
            and int(delivery.attempt_count or 0) >= MAX_AUTOMATIC_ATTEMPTS
        ):
            with delivery_write(delivery_id) as capability:
                delivery.state = "failed_final"
                delivery.last_error_code = "TRIAL_SUMMARY_AUTOMATIC_RETRY_LIMIT_REACHED"
                delivery.updated_at = now
                save_support_document(delivery, capability=capability)
            frappe.db.commit()
            return None
    elif kind == "reconcile":
        if delivery.state != "uncertain":
            frappe.db.rollback()
            return None
    else:
        raise ValueError("Trial Summary attempt kind is invalid.")
    attempt_number = int(delivery.attempt_count or 0) + 1
    if attempt_number > MAX_ATTEMPTS:
        frappe.db.rollback()
        return None
    attempt_id = str(uuid4())
    claim_token = str(uuid4())
    with delivery_write(delivery_id) as capability:
        attempt = frappe.get_doc(
            {
                "doctype": ATTEMPT_DOCTYPE,
                "global_id": attempt_id,
                "delivery_global_id": delivery_id,
                "attempt_number": attempt_number,
                "attempt_key_hash": canonical_hash(
                    {
                        "deliveryGlobalId": delivery_id,
                        "attemptKind": kind,
                        "attemptNumber": attempt_number,
                    }
                ),
                "attempt_kind": kind,
                "state": "started",
                "adapter_boundary_crossed": 0,
                "response_authenticated": 0,
                "response_contract_valid": 0,
                "trace_id": f"trial-summary-{kind}-{attempt_id}",
                "started_at": now,
            }
        )
        insert_support_document(attempt, capability=capability)
        delivery.state = "processing"
        delivery.attempt_count = attempt_number
        delivery.claim_token = claim_token
        delivery.claimed_at = now
        delivery.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
        delivery.adapter_boundary_crossed = 0
        delivery.last_attempt_global_id = attempt_id
        delivery.next_retry_at = None
        delivery.updated_at = now
        save_support_document(delivery, capability=capability)
    source = validate_persisted_source(
        delivery.source_snapshot,
        source_hash=str(delivery.source_hash),
        summary_revision_global_id=str(delivery.summary_revision_global_id),
    )
    claim = Claim(
        delivery_id,
        attempt_id,
        attempt_number,
        claim_token,
        kind,
        str(delivery.tenant_id),
        str(delivery.project_global_id),
        str(delivery.actor_user_id),
        str(delivery.source_hash),
        str(delivery.target_idempotency_key_hash),
        source,
    )
    frappe.db.commit()
    return claim


def _profile(claim: Claim) -> TrialSummaryProfile:
    profile = load_profile(frappe.conf, claim.tenant_id, claim.project_global_id)
    if profile is None:
        raise TrialSummaryDeliveryError("Trial Summary Sandbox profile is unavailable.")
    return profile


def _mark_adapter_boundary(claim: Claim, profile: TrialSummaryProfile) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    delivery, attempt = _locked_claim(claim)
    bound = (
        str(delivery.profile_id or ""),
        int(delivery.profile_version or 0),
        str(delivery.profile_snapshot_hash or ""),
        str(delivery.environment_code or ""),
        str(delivery.service_actor_user_id or ""),
    )
    current = (
        profile.profile_id,
        profile.profile_version,
        profile.snapshot_hash,
        profile.environment_code,
        profile.service_actor_user_id,
    )
    if bound[2] and bound != current:
        raise TrialSummaryDeliveryError("Trial Summary execution route drifted.")
    with delivery_write(claim.delivery_global_id) as capability:
        if not bound[2]:
            delivery.profile_id = profile.profile_id
            delivery.profile_version = profile.profile_version
            delivery.profile_snapshot_hash = profile.snapshot_hash
            delivery.environment_code = profile.environment_code
            delivery.service_actor_user_id = profile.service_actor_user_id
        delivery.adapter_boundary_crossed = 1
        delivery.updated_at = now
        attempt.adapter_boundary_crossed = 1
        save_support_document(attempt, capability=capability)
        save_support_document(delivery, capability=capability)
    frappe.db.commit()


def _complete_publish_observation(claim: Claim, observation: TargetObservation) -> None:
    if not observation.authenticated or not observation.contract_valid:
        _complete(
            claim,
            attempt_state="uncertain",
            delivery_state="uncertain",
            observation=observation,
            error_code="TRIAL_SUMMARY_RESPONSE_UNVERIFIED",
        )
    elif 200 <= observation.http_status < 300:
        _complete(
            claim,
            attempt_state="succeeded",
            delivery_state="succeeded",
            observation=observation,
            error_code=None,
        )
    elif observation.http_status == 429 or observation.http_status >= 500:
        final = claim.attempt_number >= MAX_AUTOMATIC_ATTEMPTS
        _complete(
            claim,
            attempt_state="failed_final" if final else "failed_retryable",
            delivery_state="failed_final" if final else "failed_retryable",
            observation=observation,
            error_code=observation.error_code or "TRIAL_SUMMARY_TARGET_RETRYABLE_FAILURE",
        )
    else:
        _complete(
            claim,
            attempt_state="failed_final",
            delivery_state="failed_final",
            observation=observation,
            error_code=observation.error_code or "TRIAL_SUMMARY_TARGET_REJECTED",
        )


def _complete_reconcile_observation(claim: Claim, observation: TargetObservation) -> None:
    if not observation.authenticated or not observation.contract_valid:
        _complete(
            claim,
            attempt_state="uncertain",
            delivery_state="uncertain",
            observation=observation,
            error_code="TRIAL_SUMMARY_RECONCILIATION_UNVERIFIED",
        )
    elif 200 <= observation.http_status < 300 and observation.found is True:
        _complete(
            claim,
            attempt_state="reconciled_present",
            delivery_state="succeeded",
            observation=observation,
            error_code=None,
        )
    elif 200 <= observation.http_status < 300 and observation.found is False:
        _complete(
            claim,
            attempt_state="reconciled_absent",
            delivery_state="pending",
            observation=observation,
            error_code=None,
        )
        frappe.enqueue(
            JOB_PATH,
            queue="short",
            job_name=f"trial-summary-delivery-{claim.delivery_global_id}",
            delivery_global_id=claim.delivery_global_id,
        )
    elif observation.http_status == 409:
        _complete(
            claim,
            attempt_state="failed_final",
            delivery_state="failed_final",
            observation=observation,
            error_code=observation.error_code or "TRIAL_SUMMARY_RECONCILIATION_CONFLICT",
        )
    else:
        _complete(
            claim,
            attempt_state="failed_final",
            delivery_state="uncertain",
            observation=observation,
            error_code=observation.error_code or "TRIAL_SUMMARY_RECONCILIATION_UNAVAILABLE",
        )


def _complete_before_boundary(claim: Claim, error_code: str, *, final: bool = False) -> None:
    final = final or claim.attempt_number >= MAX_AUTOMATIC_ATTEMPTS
    _complete(
        claim,
        attempt_state="failed_final" if final else "failed_retryable",
        delivery_state="failed_final" if final else "failed_retryable",
        observation=None,
        error_code=error_code,
    )


def _complete_reconcile_unavailable(claim: Claim, error_code: str, *, final: bool = False) -> None:
    _complete(
        claim,
        attempt_state="failed_final" if final else "failed_retryable",
        delivery_state="uncertain",
        observation=None,
        error_code=error_code,
    )


def _complete_uncertain(claim: Claim, error: Exception) -> None:
    _complete(
        claim,
        attempt_state="uncertain",
        delivery_state="uncertain",
        observation=None,
        error_code="TRIAL_SUMMARY_ADAPTER_OUTCOME_UNCERTAIN",
        fallback_hash=_safe_exception_hash(error),
    )


def _complete_reconcile_uncertain(claim: Claim, error: Exception) -> None:
    _complete(
        claim,
        attempt_state="uncertain",
        delivery_state="uncertain",
        observation=None,
        error_code="TRIAL_SUMMARY_RECONCILIATION_OUTCOME_UNCERTAIN",
        fallback_hash=_safe_exception_hash(error),
    )


def _complete(
    claim: Claim,
    *,
    attempt_state: str,
    delivery_state: str,
    observation: TargetObservation | None,
    error_code: str | None,
    fallback_hash: str | None = None,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    delivery, attempt = _locked_claim(claim)
    response_hash = observation.response_hash if observation else fallback_hash
    with delivery_write(claim.delivery_global_id) as capability:
        attempt.state = attempt_state
        attempt.response_authenticated = int(bool(observation and observation.authenticated))
        attempt.response_contract_valid = int(bool(observation and observation.contract_valid))
        attempt.http_status = observation.http_status if observation else None
        attempt.response_hash = response_hash
        attempt.error_code = error_code
        attempt.completed_at = now
        save_support_document(attempt, capability=capability)
        delivery.state = delivery_state
        delivery.claim_token = None
        delivery.claimed_at = None
        delivery.lease_expires_at = None
        delivery.last_http_status = observation.http_status if observation else None
        delivery.response_hash = response_hash
        delivery.last_error_code = error_code
        delivery.next_retry_at = (
            now + timedelta(minutes=min(60, 2 ** min(claim.attempt_number, 6)))
            if delivery_state == "failed_retryable"
            else None
        )
        if delivery_state == "succeeded" and observation is not None:
            delivery.projection_id = observation.projection_id
            delivery.fact_count = observation.fact_count
        if delivery_state == "pending":
            delivery.adapter_boundary_crossed = 0
        delivery.updated_at = now
        save_support_document(delivery, capability=capability)
    frappe.db.commit()


def _recover_expired_claim(delivery: object, *, now: datetime) -> None:
    delivery_id = str(delivery.global_id)
    attempt_id = str(delivery.last_attempt_global_id or "")
    with delivery_write(delivery_id) as capability:
        if attempt_id:
            attempt = frappe.get_doc(ATTEMPT_DOCTYPE, attempt_id, for_update=True)
            if attempt.state == "started":
                crossed = bool(delivery.adapter_boundary_crossed)
                attempt.state = "uncertain" if crossed else "failed_retryable"
                attempt.error_code = (
                    "TRIAL_SUMMARY_EXPIRED_AFTER_ADAPTER_BOUNDARY"
                    if crossed
                    else "TRIAL_SUMMARY_EXPIRED_BEFORE_ADAPTER_BOUNDARY"
                )
                attempt.completed_at = now
                save_support_document(attempt, capability=capability)
        crossed = bool(delivery.adapter_boundary_crossed)
        delivery.state = "uncertain" if crossed else "failed_retryable"
        delivery.last_error_code = (
            "TRIAL_SUMMARY_EXPIRED_AFTER_ADAPTER_BOUNDARY"
            if crossed
            else "TRIAL_SUMMARY_EXPIRED_BEFORE_ADAPTER_BOUNDARY"
        )
        delivery.claim_token = None
        delivery.claimed_at = None
        delivery.lease_expires_at = None
        delivery.next_retry_at = None if crossed else now
        delivery.updated_at = now
        save_support_document(delivery, capability=capability)


def _locked_claim(claim: Claim) -> tuple[object, object]:
    delivery = frappe.get_doc(
        DELIVERY_DOCTYPE,
        claim.delivery_global_id,
        for_update=True,
    )
    attempt = frappe.get_doc(
        ATTEMPT_DOCTYPE,
        claim.attempt_global_id,
        for_update=True,
    )
    if (
        delivery.state != "processing"
        or str(delivery.claim_token or "") != claim.claim_token
        or str(delivery.last_attempt_global_id or "") != claim.attempt_global_id
        or attempt.state != "started"
    ):
        frappe.db.rollback()
        raise RuntimeError("Trial Summary delivery claim was lost.")
    return delivery, attempt


def _status(delivery_id: str, fallback: str | None = None) -> dict[str, object]:
    values = frappe.db.get_value(
        DELIVERY_DOCTYPE,
        delivery_id,
        [
            "state",
            "attempt_count",
            "projection_id",
            "fact_count",
            "last_error_code",
        ],
        as_dict=True,
    )
    if not values:
        return {"deliveryGlobalId": delivery_id, "state": fallback or "unavailable"}
    return {
        "deliveryGlobalId": delivery_id,
        "state": fallback or str(values.state),
        "attemptCount": int(values.attempt_count or 0),
        "projectionId": values.projection_id,
        "factCount": values.fact_count,
        "lastErrorCode": values.last_error_code,
    }


def _configuration_error(error: Exception) -> str:
    if isinstance(error, TrialSummaryDeliveryError):
        return "TRIAL_SUMMARY_EXECUTION_CONFIGURATION_UNAVAILABLE"
    return "TRIAL_SUMMARY_EXECUTION_CONFIGURATION_INVALID"


def _safe_exception_hash(error: Exception) -> str:
    return hashlib.sha256(type(error).__name__.encode("utf-8")).hexdigest()
