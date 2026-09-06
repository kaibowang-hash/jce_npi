from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import frappe
from frappe import _

from npi_core.collaboration.domain import (
    MAX_NOTIFICATION_ROWS,
    EmailDeliveryState,
    MeetingDraft,
    NotificationKind,
    NOTIFICATION_TITLE_SOURCES,
    canonical_hash,
    notification_bucket,
    notification_kind,
    preference_email_kinds,
    utc_text,
)
from npi_core.collaboration.frappe_validation import collaboration_write_scope
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import CursorSigningUnavailable, PermissionDenied, VersionConflict
from npi_core.foundation.security import Principal, authorize_tenant
from npi_core.project.domain import IdempotencyConflict
from npi_core.project_work.frappe_repository import FrappeProjectWorkRepository
from npi_core.reporting.domain import PageCursor, decode_cursor, encode_cursor, query_fingerprint


MAX_MEETINGS = 500
MAX_FEED_PAGE = 100
_CURSOR_CONTEXT = b"npi-one:p9-02:notification-feed:v1"
_DEFAULT_EMAIL_KINDS = (
    NotificationKind.DUE_REMINDER,
    NotificationKind.GATE_ATTENTION,
    NotificationKind.OVERDUE_ESCALATION,
)
@dataclass(frozen=True, slots=True)
class CollaborationOutcome:
    response: dict[str, object]
    replayed: bool = False


class FrappeCollaborationRepository:
    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if principal.tenant_id is None:
            raise PermissionDenied()
        authorize_tenant(principal, principal.tenant_id)
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id
        self.clock = clock or (lambda: datetime.now(UTC))

    def list_meetings(self, project_id: UUID) -> dict[str, object] | None:
        project = self._project_work().work_context(project_id)
        if project is None:
            return None
        rows = frappe.get_all(
            "NPI Meeting Minute",
            filters={"tenant_id": self.principal.tenant_id, "project_global_id": str(project_id)},
            fields=[
                "global_id",
                "template_global_id",
                "template_version",
                "template_snapshot_hash",
                "title",
                "occurred_at",
                "attendee_user_ids",
                "sections",
                "content_hash",
                "created_by",
                "optimistic_version",
                "creation",
            ],
            order_by="occurred_at desc, global_id desc",
            limit_page_length=MAX_MEETINGS + 1,
        )
        if len(rows) > MAX_MEETINGS:
            raise RuntimeError("The meeting scope exceeds its safe bound.")
        return {
            "schemaVersion": 1,
            "projectId": str(project_id),
            "projectVersion": int(project["projectVersion"]),
            "items": [self._meeting_response(row) for row in rows],
            "permissions": project["permissions"],
        }

    def create_meeting(
        self,
        project_id: UUID,
        *,
        expected_project_version: int,
        idempotency_key: str,
        draft: MeetingDraft,
    ) -> CollaborationOutcome | None:
        work_repository = self._project_work()
        project = work_repository.locked_project_for_parent_command(project_id)
        if project is None:
            return None
        payload_hash = canonical_hash(
            {
                "expectedProjectVersion": expected_project_version,
                "meeting": draft.snapshot(),
                "projectId": str(project_id),
            }
        )
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return CollaborationOutcome(replay, replayed=True)
        if int(project.optimistic_version) != expected_project_version:
            raise VersionConflict()
        self._require_attendees(project, draft.attendee_user_ids)
        meeting_id = uuid4()
        content = draft.minute_content()
        with collaboration_write_scope(audit=True):
            receipt = self._insert_idempotency(
                idempotency_key,
                payload_hash,
                "meeting_minute.create",
            )
            if isinstance(receipt, dict):
                return CollaborationOutcome(receipt, replayed=True)
            meeting = frappe.get_doc(
                {
                    "doctype": "NPI Meeting Minute",
                    "global_id": str(meeting_id),
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project_id),
                    "template_global_id": str(draft.template_ref["globalId"]),
                    "template_version": int(draft.template_ref["version"]),
                    "template_snapshot_hash": str(draft.template_ref["snapshotHash"]),
                    "title": draft.title,
                    "occurred_at": draft.occurred_at.replace(tzinfo=None),
                    "attendee_user_ids": list(draft.attendee_user_ids),
                    "sections": dict(draft.sections),
                    "content_hash": canonical_hash(content),
                    "created_by": self.actor,
                    "optimistic_version": 1,
                }
            ).insert()
            created = []
            if draft.items:
                created = work_repository.create_domain_work_items_in_parent_command(
                    project,
                    items=[item.parent_input() for item in draft.items],
                )
                if created is None:
                    return None
            links = []
            for item, value in zip(draft.items, created, strict=True):
                work_item = value["response"]
                link_id = uuid5(NAMESPACE_URL, f"npi-meeting:{meeting_id}:{work_item['globalId']}")
                frappe.get_doc(
                    {
                        "doctype": "NPI Meeting Work Link",
                        "link_id": str(link_id),
                        "tenant_id": str(project.tenant_id),
                        "project_global_id": str(project_id),
                        "meeting_global_id": str(meeting_id),
                        "work_item_global_id": work_item["globalId"],
                        "item_key": item.item_key,
                        "kind": item.kind.value,
                    }
                ).insert()
                links.append(self._link_response(item.item_key, item.kind.value, work_item))
            self._append_audit(
                operation="meeting_minute.create",
                global_id=meeting_id,
                version=1,
                result="created",
                summary={
                    "actionCount": sum(item.kind.value == "action" for item in draft.items),
                    "decisionCount": sum(item.kind.value == "decision_request" for item in draft.items),
                    "projectId": str(project_id),
                    "requestId": self.request_id,
                    "contentHash": canonical_hash(content),
                },
            )
            response = self._meeting_response(meeting, linked_items=links)
            response["projectVersion"] = int(project.optimistic_version)
            self._seal_idempotency(receipt, response)
        return CollaborationOutcome(response)

    def notification_feed(
        self,
        *,
        unread_only: bool,
        cursor: object | None,
        limit: int,
    ) -> dict[str, object]:
        filters: dict[str, object] = {
            "tenant_id": self.principal.tenant_id,
            "recipient_user_id": self.actor,
        }
        rows = frappe.get_all(
            "NPI Internal Notification",
            filters=filters,
            fields=[
                "global_id",
                "project_global_id",
                "source_type",
                "source_global_id",
                "source_version",
                "notification_kind",
                "critical_audit",
                "title_source",
                "message_parameters",
                "target_route",
                "source_due_at",
                "email_delivery_state",
                "failure_code",
                "read_at",
                "optimistic_version",
                "creation",
            ],
            order_by="creation desc, global_id desc",
            limit_page_length=MAX_NOTIFICATION_ROWS + 1,
        )
        if len(rows) > MAX_NOTIFICATION_ROWS:
            raise RuntimeError("The notification feed exceeds its safe bound.")
        if unread_only:
            rows = [row for row in rows if not _value(row, "read_at", None)]
        fingerprint = query_fingerprint(
            "notification_feed",
            {"actor": self.actor.casefold(), "tenantId": self.principal.tenant_id, "unreadOnly": unread_only},
        )
        position = None if cursor is None else decode_cursor(cursor, self._cursor_key(), fingerprint)
        if position is not None:
            rows = [
                row
                for row in rows
                if (_datetime(_value(row, "creation")), str(_value(row, "global_id")))
                < (_datetime(position.sort_value), position.global_id)
            ]
        selected = rows[: limit + 1]
        has_more = len(selected) > limit
        selected = selected[:limit]
        next_cursor = None
        if has_more and selected:
            last = selected[-1]
            next_cursor = encode_cursor(
                PageCursor(fingerprint, utc_text(_datetime(_value(last, "creation"))), str(_value(last, "global_id"))),
                self._cursor_key(),
            )
        return {
            "schemaVersion": 1,
            "items": [self._notification_response(row) for row in selected],
            "page": {"limit": limit, "hasMore": has_more, "nextCursor": next_cursor},
            "permissions": {"serverFiltered": True},
        }

    def mark_notification_read(
        self,
        notification_id: UUID,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> CollaborationOutcome | None:
        document = _optional_doc("NPI Internal Notification", str(notification_id), for_update=True)
        if (
            document is None
            or str(document.tenant_id) != self.principal.tenant_id
            or str(document.recipient_user_id).casefold() != self.actor.casefold()
        ):
            return None
        payload_hash = canonical_hash(
            {"expectedVersion": expected_version, "notificationId": str(notification_id)}
        )
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return CollaborationOutcome(replay, replayed=True)
        if int(document.optimistic_version) != expected_version:
            raise VersionConflict()
        with collaboration_write_scope(audit=True):
            receipt = self._insert_idempotency(idempotency_key, payload_hash, "notification.mark_read")
            if isinstance(receipt, dict):
                return CollaborationOutcome(receipt, replayed=True)
            document.read_at = self.clock().astimezone(UTC).replace(tzinfo=None)
            document.save()
            response = self._notification_response(document)
            self._seal_idempotency(receipt, response)
        return CollaborationOutcome(response)

    def notification_preference(self) -> dict[str, object]:
        document = _optional_doc("NPI Notification Preference", self._preference_id())
        return self._preference_response(document)

    def set_notification_preference(
        self,
        *,
        expected_version: int,
        email_kinds: tuple[NotificationKind, ...],
        idempotency_key: str,
    ) -> CollaborationOutcome:
        payload_hash = canonical_hash(
            {
                "emailKinds": [item.value for item in email_kinds],
                "expectedVersion": expected_version,
            }
        )
        replay = self._idempotency_replay(idempotency_key, payload_hash)
        if replay is not None:
            return CollaborationOutcome(replay, replayed=True)
        document = _optional_doc("NPI Notification Preference", self._preference_id(), for_update=True)
        current_version = 0 if document is None else int(document.optimistic_version)
        if current_version != expected_version:
            raise VersionConflict()
        with collaboration_write_scope(audit=True):
            receipt = self._insert_idempotency(idempotency_key, payload_hash, "notification_preference.set")
            if isinstance(receipt, dict):
                return CollaborationOutcome(receipt, replayed=True)
            values = [item.value for item in email_kinds]
            if document is None:
                document = frappe.get_doc(
                    {
                        "doctype": "NPI Notification Preference",
                        "global_id": self._preference_id(),
                        "tenant_id": self.principal.tenant_id,
                        "user_id": self.actor,
                        "email_kinds": values,
                        "critical_audit_email": 1,
                        "optimistic_version": 1,
                    }
                ).insert()
            else:
                document.email_kinds = values
                document.save()
            response = self._preference_response(document)
            self._append_audit(
                operation="notification_preference.set",
                global_id=UUID(self._preference_id()),
                version=int(document.optimistic_version),
                result="updated",
                summary={"emailKindCount": len(values), "requestId": self.request_id},
            )
            self._seal_idempotency(receipt, response)
        return CollaborationOutcome(response)

    def _project_work(self) -> FrappeProjectWorkRepository:
        return FrappeProjectWorkRepository(
            principal=self.principal,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )

    def _require_attendees(self, project, attendees: tuple[str, ...]) -> None:
        members = frappe.get_all(
            "NPI Project Member",
            filters={"tenant_id": project.tenant_id, "project_global_id": project.global_id},
            fields=["user_id"],
            limit_page_length=501,
        )
        if len(members) > 500:
            raise RuntimeError("The Project membership scope exceeds its safe bound.")
        eligible = {str(project.owner_user_id).casefold(), self.actor.casefold()}
        eligible.update(str(_value(row, "user_id")).casefold() for row in members)
        for attendee in attendees:
            if attendee not in eligible or frappe.db.get_value("User", attendee, "enabled") != 1:
                raise PermissionDenied()

    def _meeting_response(self, document, *, linked_items=None) -> dict[str, object]:
        links = linked_items
        if links is None:
            rows = frappe.get_all(
                "NPI Meeting Work Link",
                filters={
                    "tenant_id": self.principal.tenant_id,
                    "meeting_global_id": str(_value(document, "global_id")),
                },
                fields=["item_key", "kind", "work_item_global_id"],
                order_by="item_key asc",
                limit_page_length=51,
            )
            if len(rows) > 50:
                raise RuntimeError("The meeting Work Item link scope exceeds its safe bound.")
            links = []
            for row in rows:
                work = _optional_doc("NPI Domain Work Item", str(_value(row, "work_item_global_id")))
                if work is None or str(work.project_global_id) != str(_value(document, "project_global_id")):
                    raise RuntimeError("A meeting Work Item link is invalid.")
                links.append(
                    self._link_response(str(_value(row, "item_key")), str(_value(row, "kind")), work)
                )
        return {
            "schemaVersion": 1,
            "globalId": str(_value(document, "global_id")),
            "projectId": str(_value(document, "project_global_id")),
            "templateRef": {
                "globalId": str(_value(document, "template_global_id")),
                "version": int(_value(document, "template_version")),
                "snapshotHash": str(_value(document, "template_snapshot_hash")),
            },
            "title": str(_value(document, "title")),
            "occurredAt": utc_text(_datetime(_value(document, "occurred_at"))),
            "attendeeUserIds": _json(_value(document, "attendee_user_ids"), list),
            "sections": _json(_value(document, "sections"), dict),
            "linkedItems": links,
            "contentHash": str(_value(document, "content_hash")),
            "createdBy": str(_value(document, "created_by")),
            "createdAt": utc_text(_datetime(_value(document, "creation"))),
            "version": int(_value(document, "optimistic_version")),
        }

    @staticmethod
    def _link_response(item_key: str, kind: str, work) -> dict[str, object]:
        get = work.get if isinstance(work, Mapping) else lambda name, default=None: getattr(work, name, default)
        project_id = str(get("projectId") or get("project_global_id"))
        work_id = str(get("globalId") or get("global_id"))
        return {
            "itemKey": item_key,
            "kind": kind,
            "workItemId": work_id,
            "title": str(get("title")),
            "ownerUserId": str(get("ownerUserId") or get("owner_user_id")),
            "dueAt": str(get("dueAt") or utc_text(_datetime(get("due_at")))),
            "targetRoute": f"/projects/{project_id}/work?workItemId={work_id}",
        }

    def _notification_response(self, document) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "globalId": str(_value(document, "global_id")),
            "projectId": str(_value(document, "project_global_id")),
            "source": {
                "type": str(_value(document, "source_type")),
                "globalId": str(_value(document, "source_global_id")),
                "version": int(_value(document, "source_version")),
            },
            "kind": str(_value(document, "notification_kind")),
            "criticalAudit": bool(_value(document, "critical_audit")),
            "titleSource": str(_value(document, "title_source")),
            "messageParameters": _json(_value(document, "message_parameters"), dict),
            "targetRoute": str(_value(document, "target_route")),
            "sourceDueAt": utc_text(_datetime(_value(document, "source_due_at"))),
            "emailDeliveryState": str(_value(document, "email_delivery_state")),
            "failureCode": _value(document, "failure_code", None) or None,
            "readAt": None
            if not _value(document, "read_at", None)
            else utc_text(_datetime(_value(document, "read_at"))),
            "createdAt": utc_text(_datetime(_value(document, "creation"))),
            "version": int(_value(document, "optimistic_version")),
        }

    def _preference_response(self, document) -> dict[str, object]:
        if document is None:
            kinds = [item.value for item in _DEFAULT_EMAIL_KINDS]
            version = 0
        else:
            kinds = [item.value for item in preference_email_kinds(_json(document.email_kinds, list))]
            version = int(document.optimistic_version)
        return {
            "schemaVersion": 1,
            "emailKinds": kinds,
            "criticalAuditEmail": True,
            "criticalAuditMutable": False,
            "version": version,
        }

    def _preference_id(self) -> str:
        return str(uuid5(NAMESPACE_URL, f"npi-notification-preference:{self.principal.tenant_id}:{self.actor.casefold()}"))

    def _idempotency_replay(self, actor_key_hash: str, payload_hash: str) -> dict[str, object] | None:
        value = frappe.db.get_value(
            "NPI Collaboration Idempotency",
            {"actor_key_hash": actor_key_hash},
            ["payload_hash", "response_json", "response_sealed"],
            as_dict=True,
            for_update=True,
        )
        if not value:
            return None
        if str(value.payload_hash) != payload_hash or int(value.response_sealed or 0) != 1:
            raise IdempotencyConflict()
        return _json(value.response_json, dict)

    def _insert_idempotency(self, actor_key_hash: str, payload_hash: str, operation: str):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Collaboration Idempotency",
                    "record_id": str(uuid4()),
                    "actor": self.actor,
                    "tenant_id": self.principal.tenant_id,
                    "operation": operation,
                    "actor_key_hash": actor_key_hash,
                    "payload_hash": payload_hash,
                    "response_json": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(actor_key_hash, payload_hash)
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_idempotency(document, response: Mapping[str, object]) -> None:
        document.response_json = dict(response)
        document.response_sealed = 1
        document.save()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        version: int,
        result: str,
        summary: Mapping[str, object],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=version,
            result=result,
            input_summary=summary,
        )
        frappe.get_doc(
            {
                "doctype": "NPI Audit Event",
                "event_id": str(event.event_id),
                "global_id": str(event.global_id),
                "object_version": event.object_version,
                "actor": event.actor,
                "trace_id": event.trace_id,
                "operation": event.operation,
                "result": event.result,
                "input_summary": dict(event.input_summary),
            }
        ).insert()

    def _cursor_key(self) -> bytes:
        try:
            configuration = getattr(getattr(frappe, "local", None), "conf", None) or frappe.conf
            persisted = configuration.get("encryption_key")
            decoded = base64.b64decode(persisted.encode("ascii"), altchars=b"-_", validate=True)
            if len(decoded) != 32:
                raise ValueError
        except Exception as error:
            raise CursorSigningUnavailable() from error
        return hmac.new(decoded, _CURSOR_CONTEXT, hashlib.sha256).digest()


def refresh_due_notifications(now: datetime | None = None) -> dict[str, int]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    rows = frappe.get_all(
        "NPI My Work Assignment",
        filters={"active": 1},
        fields=[
            "tenant_id",
            "actor_user_id",
            "project_global_id",
            "source_type",
            "source_global_id",
            "source_version",
            "category",
            "due_at",
            "priority_value",
            "blocking",
        ],
        order_by="due_at asc, global_id asc",
        limit_page_length=MAX_NOTIFICATION_ROWS + 1,
    )
    if len(rows) > MAX_NOTIFICATION_ROWS:
        raise RuntimeError("The notification source scope exceeds its safe bound.")
    created = queued = failed = 0
    for row in rows:
        classification = notification_kind(row, current)
        if classification is None:
            continue
        kind, critical = classification
        due_at = _datetime(_value(row, "due_at"))
        raw_key = "\x00".join(
            (
                str(_value(row, "tenant_id")),
                str(_value(row, "actor_user_id")).casefold(),
                str(_value(row, "source_type")),
                str(_value(row, "source_global_id")),
                str(_value(row, "source_version")),
                kind.value,
                notification_bucket(kind, current, due_at),
            )
        )
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        if frappe.db.exists("NPI Internal Notification", {"delivery_key_hash": key_hash}):
            continue
        identity = uuid5(NAMESPACE_URL, f"npi-notification:{key_hash}")
        email_requested = critical or kind in _email_kinds_for_user(
            str(_value(row, "tenant_id")),
            str(_value(row, "actor_user_id")),
        )
        with collaboration_write_scope(audit=critical):
            document = frappe.get_doc(
                {
                    "doctype": "NPI Internal Notification",
                    "global_id": str(identity),
                    "delivery_key_hash": key_hash,
                    "tenant_id": str(_value(row, "tenant_id")),
                    "recipient_user_id": str(_value(row, "actor_user_id")),
                    "project_global_id": str(_value(row, "project_global_id")),
                    "source_type": str(_value(row, "source_type")),
                    "source_global_id": str(_value(row, "source_global_id")),
                    "source_version": int(_value(row, "source_version")),
                    "notification_kind": kind.value,
                    "critical_audit": int(critical),
                    "title_source": NOTIFICATION_TITLE_SOURCES[kind],
                    "message_parameters": {"dueAt": utc_text(due_at)},
                    "target_route": f"/projects/{_value(row, 'project_global_id')}",
                    "source_due_at": due_at.replace(tzinfo=None),
                    "email_delivery_state": (
                        EmailDeliveryState.NOT_REQUESTED.value
                        if not email_requested
                        else EmailDeliveryState.UNAVAILABLE.value
                    ),
                    "optimistic_version": 1,
                }
            ).insert()
            created += 1
            if email_requested:
                try:
                    _queue_notification_email(document)
                except Exception:
                    document.email_delivery_state = EmailDeliveryState.FAILED.value
                    document.failure_code = "email_queue_failed"
                    failed += 1
                else:
                    document.email_delivery_state = EmailDeliveryState.QUEUED.value
                    document.failure_code = None
                    queued += 1
                document.save()
            if critical:
                event = create_audit_event(
                    actor="scheduler",
                    trace_id=f"notify-{str(identity)}",
                    operation="notification.critical_blocker.created",
                    global_id=identity,
                    object_version=int(document.optimistic_version),
                    result="created",
                    input_summary={
                        "projectId": str(_value(row, "project_global_id")),
                        "emailState": str(document.email_delivery_state),
                    },
                )
                frappe.get_doc(
                    {
                        "doctype": "NPI Audit Event",
                        "event_id": str(event.event_id),
                        "global_id": str(event.global_id),
                        "object_version": event.object_version,
                        "actor": event.actor,
                        "trace_id": event.trace_id,
                        "operation": event.operation,
                        "result": event.result,
                        "input_summary": dict(event.input_summary),
                    }
                ).insert()
    return {"created": created, "emailQueued": queued, "emailFailed": failed}


def _queue_notification_email(document) -> None:
    language = frappe.db.get_value("User", document.recipient_user_id, "language") or "en"
    subject = _translated_notification_title(
        NotificationKind(str(document.notification_kind)),
        language,
    )
    message = _("Notification: {title}. Due at {due_at}.", lang=language).format(
        title=subject,
        due_at=utc_text(_datetime(document.source_due_at))
    )
    frappe.sendmail(
        recipients=[document.recipient_user_id],
        subject=subject,
        message=message,
        now=False,
        reference_doctype="NPI Internal Notification",
        reference_name=document.global_id,
    )


def _translated_notification_title(kind: NotificationKind, language: str) -> str:
    if kind is NotificationKind.DUE_REMINDER:
        return _("Work item due soon", lang=language)
    if kind is NotificationKind.OVERDUE_ESCALATION:
        return _("Work item overdue", lang=language)
    if kind is NotificationKind.CRITICAL_BLOCKER:
        return _("Critical blocker requires attention", lang=language)
    if kind is NotificationKind.GATE_ATTENTION:
        return _("Gate review requires attention", lang=language)
    raise ValueError("Unsupported notification kind.")


def _email_kinds_for_user(tenant_id: str, user_id: str) -> frozenset[NotificationKind]:
    preference_id = str(
        uuid5(
            NAMESPACE_URL,
            f"npi-notification-preference:{tenant_id}:{user_id.casefold()}",
        )
    )
    document = _optional_doc("NPI Notification Preference", preference_id)
    if document is None:
        return frozenset(_DEFAULT_EMAIL_KINDS)
    return frozenset(preference_email_kinds(_json(document.email_kinds, list)))


def _optional_doc(doctype: str, name: str, *, for_update: bool = False):
    try:
        return frappe.get_doc(doctype, name, for_update=for_update)
    except frappe.DoesNotExistError:
        return None


def _value(record: Any, field: str, default: Any = ...):
    if isinstance(record, Mapping) and field in record:
        return record[field]
    if hasattr(record, field):
        return getattr(record, field)
    if default is not ...:
        return default
    raise RuntimeError(f"Persisted collaboration field is missing: {field}")


def _json(value: object, expected: type):
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, expected):
        raise RuntimeError("Persisted collaboration JSON has an invalid structure.")
    return parsed


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
