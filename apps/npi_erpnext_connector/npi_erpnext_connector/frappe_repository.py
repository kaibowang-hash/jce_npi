from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import frappe

from npi_erpnext_connector.config import load_profile, sender_is_disabled
from npi_erpnext_connector.domain import (
    AuthorizationEvent,
    AuthorizationSenderError,
    SourcePermission,
    SourceUser,
    build_event,
    canonical_hash,
    canonical_json,
    project_source_user,
)
from npi_erpnext_connector.frappe_validation import (
    delivery_write,
    insert_delivery_document,
)


DOCTYPE = "NPI ERP Authorization Delivery"
MAX_RECONCILIATION_USERS = 500
DELIVERY_JOB = "npi_erpnext_connector.worker.deliver_pending"


def enqueue_user_authorization(target_user_id: str) -> str | None:
    if sender_is_disabled(frappe.conf):
        return None
    profile = load_profile(frappe.conf)
    source = _load_source_user(target_user_id)
    snapshot = project_source_user(source, profile.policy)
    now = datetime.now(UTC).replace(microsecond=0)
    for attempt in range(2):
        latest = _latest_delivery(snapshot.target_user_id)
        if latest and str(latest.get("source_snapshot_hash")) == snapshot.snapshot_hash:
            status = str(latest.get("status"))
            if status in {"pending", "retry"}:
                _enqueue_delivery(str(latest["name"]))
                return str(latest["name"])
            expires_at = _datetime(latest.get("expires_at"))
            refresh_margin = timedelta(
                seconds=min(3600, profile.policy.ttl_seconds // 4)
            )
            if status == "delivered" and expires_at > now + refresh_margin:
                return str(latest["name"])
            if status == "permanent_failure" and expires_at > now:
                return str(latest["name"])

        source_version = int(latest.get("source_version") or 0) + 1 if latest else 1
        event = build_event(
            snapshot,
            source_version=source_version,
            issued_at=now,
            ttl_seconds=profile.policy.ttl_seconds,
        )
        try:
            delivery = _insert_delivery(event, snapshot.target_user_id, source_version)
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            frappe.db.rollback()
            if attempt == 0:
                continue
            raise
        _enqueue_delivery(str(delivery.name))
        return str(delivery.name)
    raise RuntimeError("Authorization delivery concurrency recovery failed.")


def list_reconciliation_users() -> tuple[str, ...]:
    user_rows = frappe.get_all(
        "User",
        filters={
            "user_type": "System User",
            "name": ["not in", ["Administrator", "Guest"]],
        },
        fields=["name"],
        order_by="name asc",
        page_length=MAX_RECONCILIATION_USERS + 1,
    )
    delivery_rows = frappe.get_all(
        DOCTYPE,
        fields=["target_user_id"],
        group_by="target_user_id",
        order_by="target_user_id asc",
        page_length=MAX_RECONCILIATION_USERS + 1,
    )
    identities = {
        str(row[field])
        for rows, field in (
            (user_rows, "name"),
            (delivery_rows, "target_user_id"),
        )
        for row in rows
    }
    if (
        len(user_rows) > MAX_RECONCILIATION_USERS
        or len(delivery_rows) > MAX_RECONCILIATION_USERS
        or len(identities) > MAX_RECONCILIATION_USERS
    ):
        raise AuthorizationSenderError(
            "Authorization reconciliation identity count exceeds the fixed bound."
        )
    return tuple(sorted(identities))


def restore_event(delivery: object) -> AuthorizationEvent:
    raw = str(getattr(delivery, "event_json", "") or "")
    try:
        event = json.loads(raw)
        request_id = UUID(str(getattr(delivery, "request_id", "")))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AuthorizationSenderError("Stored authorization event is invalid.") from error
    source_version = event.get("sourceVersion") if isinstance(event, dict) else None
    if (
        not isinstance(event, dict)
        or type(source_version) is not int
        or canonical_json(event) != raw
        or canonical_hash(event) != str(getattr(delivery, "event_hash", ""))
        or str(event.get("eventId", "")) != str(getattr(delivery, "event_id", ""))
        or str(event.get("targetUserId", ""))
        != str(getattr(delivery, "target_user_id", ""))
        or source_version
        != int(getattr(delivery, "source_version", 0) or 0)
    ):
        raise AuthorizationSenderError("Stored authorization event binding is invalid.")
    return AuthorizationEvent(
        event=event,
        request_id=request_id,
        snapshot_hash=str(getattr(delivery, "source_snapshot_hash", "")),
    )


def get_delivery(delivery_id: str):
    return frappe.get_doc(DOCTYPE, delivery_id)


def _load_source_user(target_user_id: str) -> SourceUser:
    record = frappe.db.get_value(
        "User",
        target_user_id,
        ["name", "email", "enabled", "user_type"],
        as_dict=True,
    )
    if not record:
        return SourceUser(target_user_id, target_user_id, False, "System User", (), ())
    name = str(record.get("name") or "")
    email = str(record.get("email") or "")
    role_rows = frappe.get_all(
        "Has Role",
        filters={"parent": name, "parenttype": "User", "parentfield": "roles"},
        fields=["role"],
        order_by="role asc",
        page_length=129,
    )
    if len(role_rows) > 128:
        raise AuthorizationSenderError("ERPNext role count exceeds the fixed bound.")
    permission_rows = frappe.get_all(
        "User Permission",
        filters={
            "user": name,
            "allow": ["in", ["Project", "Company", "Customer", "Supplier"]],
        },
        fields=["allow", "for_value"],
        order_by="allow asc, for_value asc",
        page_length=513,
    )
    if len(permission_rows) > 512:
        raise AuthorizationSenderError(
            "ERPNext User Permission count exceeds the fixed bound."
        )
    permissions = tuple(
        sorted(
            {
                SourcePermission(row.get("allow"), row.get("for_value"))
                for row in permission_rows
            }
        )
    )
    enabled = record.get("enabled")
    if type(enabled) is not int or enabled not in {0, 1}:
        raise AuthorizationSenderError("ERPNext User enabled state is invalid.")
    raw_roles = tuple(row.get("role") for row in role_rows)
    if any(not isinstance(role, str) for role in raw_roles):
        raise AuthorizationSenderError("ERPNext role shape is invalid.")
    return SourceUser(
        source_subject_id=name,
        target_user_id=email,
        enabled=bool(enabled),
        user_type=str(record.get("user_type") or ""),
        roles=tuple(sorted(set(raw_roles))),
        permissions=permissions,
    )


def _latest_delivery(target_user_id: str) -> dict[str, object] | None:
    rows = frappe.get_all(
        DOCTYPE,
        filters={"target_user_id": target_user_id},
        fields=[
            "name",
            "source_version",
            "source_snapshot_hash",
            "status",
            "expires_at",
        ],
        order_by="source_version desc",
        page_length=1,
    )
    return dict(rows[0]) if rows else None


def _insert_delivery(
    event: AuthorizationEvent,
    target_user_id: str,
    source_version: int,
):
    stream_key = hashlib.sha256(
        f"{target_user_id}:{source_version}".encode()
    ).hexdigest()
    document = frappe.get_doc(
        {
            "doctype": DOCTYPE,
            "event_id": str(event.event_id),
            "stream_key": stream_key,
            "target_user_id": target_user_id,
            "source_version": source_version,
            "source_snapshot_hash": event.snapshot_hash,
            "event_hash": event.event_hash,
            "event_json": canonical_json(event.event),
            "request_id": str(event.request_id),
            "trace_id": event.trace_id,
            "expires_at": event.expires_at.replace(tzinfo=None),
            "status": "pending",
            "attempt_count": 0,
        }
    )
    with delivery_write(str(event.event_id)) as capability:
        return insert_delivery_document(document, capability=capability)


def _enqueue_delivery(delivery_id: str) -> None:
    frappe.enqueue(
        DELIVERY_JOB,
        queue="short",
        enqueue_after_commit=True,
        job_id=f"npi-erp-auth-{delivery_id}",
        delivery_id=delivery_id,
    )


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise AuthorizationSenderError("Stored authorization expiry is invalid.")
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)
