from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable, Iterator
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.change_control.domain import (
    EngineeringChangeEvent,
    EngineeringChangeEventType,
    EngineeringChangeRevision,
    EngineeringChangeState,
    FormalChangeObservation,
    sha256_json,
)
from npi_core.change_control.frappe_validation import (
    change_command_write,
    change_observation_write,
    save_change_support_document,
)
from npi_core.change_control.request_validation import (
    parse_formal_observation,
    parse_revision_content,
)
from npi_core.change_control.response_validation import validate_receipt_response
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import (
    NpiProblem,
    PermissionDenied,
    RequestValidationFailed,
    VersionConflict,
)
from npi_core.foundation.security import Principal


_MAX_CHANGES = 1_000
_MAX_MEMBERS = 1_000
_OPERATIONS = frozenset(
    {
        "engineering_change.create",
        "engineering_change.revise",
        "engineering_change.link_formal_observation",
        "engineering_change.close",
    }
)
ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES = frozenset(
    {
        "P901_CHANGE_REVISE_API_CALL",
        "P901_CHANGE_REVISE_API_ROUTES",
        "P901_CHANGE_REVISE_API_USER",
        "P901_CHANGE_REVISE_API_CSRF",
        "P901_CHANGE_REVISE_API_PRINCIPAL",
        "P901_CHANGE_REVISE_API_ROLE",
        "P901_CHANGE_REVISE_API_FIELDS",
        "P901_CHANGE_REVISE_API_REPOSITORY_INIT",
        "P901_CHANGE_REVISE_API_IDEMPOTENCY",
        "P901_CHANGE_REVISE_API_REPOSITORY_CALL",
        "P901_CHANGE_REVISE_API_OUTCOME",
        "P901_CHANGE_REVISE_API_RESPONSE",
        "P901_CHANGE_REVISE_REPOSITORY_PROJECT_LOCK",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_LOCK",
        "P901_CHANGE_REVISE_REPOSITORY_PAYLOAD",
        "P901_CHANGE_REVISE_REPOSITORY_REPLAY",
        "P901_CHANGE_REVISE_REPOSITORY_CURRENT",
        "P901_CHANGE_REVISE_REPOSITORY_PREDECESSOR",
        "P901_CHANGE_REVISE_REPOSITORY_STATE",
        "P901_CHANGE_REVISE_REPOSITORY_TRANSFORM",
        "P901_CHANGE_REVISE_REPOSITORY_EVENT",
        "P901_CHANGE_REVISE_REPOSITORY_RESPONSE",
        "P901_CHANGE_REVISE_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_REPLAY",
        "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT",
        "P901_CHANGE_REVISE_REPOSITORY_EVENT_INSERT",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_APPLY",
        "P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE",
        "P901_CHANGE_REVISE_REPOSITORY_AUDIT",
        "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_SEAL",
        "P901_CHANGE_REVISE_REPOSITORY_OUTCOME",
        "P901_CHANGE_INBOUND_API_CALL",
        "P901_CHANGE_INBOUND_API_FIELDS",
        "P901_CHANGE_INBOUND_API_REQUEST",
        "P901_CHANGE_INBOUND_API_AUTHENTICATE",
        "P901_CHANGE_INBOUND_API_PRINCIPAL",
        "P901_CHANGE_INBOUND_API_REPOSITORY_INIT",
        "P901_CHANGE_INBOUND_API_REPOSITORY_CALL",
        "P901_CHANGE_INBOUND_API_COMMIT",
        "P901_CHANGE_INBOUND_API_ENQUEUE",
        "P901_CHANGE_INBOUND_API_OUTCOME",
        "P901_CHANGE_INBOUND_API_RESPONSE",
        "P901_CHANGE_INBOUND_REPOSITORY_INPUT",
        "P901_CHANGE_INBOUND_REPOSITORY_EVENT",
        "P901_CHANGE_INBOUND_REPOSITORY_HASHES",
        "P901_CHANGE_INBOUND_REPOSITORY_REPLAY",
        "P901_CHANGE_INBOUND_REPOSITORY_SOURCE_KEY",
        "P901_CHANGE_INBOUND_REPOSITORY_LATEST",
        "P901_CHANGE_INBOUND_REPOSITORY_VERSION",
        "P901_CHANGE_INBOUND_REPOSITORY_RESPONSE",
        "P901_CHANGE_INBOUND_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_INSERT",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_NULL",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_COLUMN",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DUPLICATE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_TABLE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_LOCK",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_DATETIME",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_MISSING_DEFAULT",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_INVALID_VALUE",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_TOO_LONG",
        "P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_OTHER",
        "P901_CHANGE_INBOUND_REPOSITORY_AUDIT",
        "P901_CHANGE_INBOUND_REPOSITORY_OUTCOME",
        "P901_CHANGE_SUMMARY_API_CALL",
        "P901_CHANGE_SUMMARY_API_USER",
        "P901_CHANGE_SUMMARY_API_CSRF",
        "P901_CHANGE_SUMMARY_API_PRINCIPAL",
        "P901_CHANGE_SUMMARY_API_ROUTES",
        "P901_CHANGE_SUMMARY_API_REPOSITORY_INIT",
        "P901_CHANGE_SUMMARY_API_SCOPE",
        "P901_CHANGE_SUMMARY_API_FIELDS",
        "P901_CHANGE_SUMMARY_API_REPOSITORY_CALL",
        "P901_CHANGE_SUMMARY_API_COMMIT",
        "P901_CHANGE_SUMMARY_API_ENQUEUE",
        "P901_CHANGE_SUMMARY_API_OUTCOME",
        "P901_CHANGE_SUMMARY_API_RESPONSE",
        "P901_CHANGE_SUMMARY_REPOSITORY_PROJECT_LOCK",
        "P901_CHANGE_SUMMARY_REPOSITORY_PROFILE",
        "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY_LOOKUP",
        "P901_CHANGE_SUMMARY_REPOSITORY_REPLAY",
        "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL",
        "P901_CHANGE_SUMMARY_REPOSITORY_DETAIL_VALIDATE",
        "P901_CHANGE_SUMMARY_REPOSITORY_CURRENT",
        "P901_CHANGE_SUMMARY_REPOSITORY_SUMMARY",
        "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_VALUE",
        "P901_CHANGE_SUMMARY_REPOSITORY_RESPONSE",
        "P901_CHANGE_SUMMARY_REPOSITORY_WRITE_SCOPE",
        "P901_CHANGE_SUMMARY_REPOSITORY_REQUEST_INSERT",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_PAYLOAD",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTBOX_INSERT",
        "P901_CHANGE_SUMMARY_REPOSITORY_AUDIT",
        "P901_CHANGE_SUMMARY_REPOSITORY_OUTCOME",
    }
)
_REVISE_SERVER_DIAGNOSTIC_FLAG = "npi_p901_change_revise_server_diagnostic"
_DIAGNOSTIC_PATH_ENV = "NPI_P9_01_RUNTIME_DIAGNOSTIC_PATH"
_DIAGNOSTIC_PATH_NAME = "p9-01-engineering-change-runtime-diagnostic.json"
_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_DIAGNOSTIC_TYPE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,127}$")


@contextmanager
def engineering_change_revise_server_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    try:
        state = None
        if (
            active
            and isinstance(trace_id, str)
            and _DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        ):
            state = {"trace_id": trace_id, "recorded": False}
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _REVISE_SERVER_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _REVISE_SERVER_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _REVISE_SERVER_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _REVISE_SERVER_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def engineering_change_revise_server_step(code: str) -> Iterator[None]:
    try:
        yield
    except Exception as error:
        _record_engineering_change_revise_server_failure(code, error)
        raise


def _record_engineering_change_revise_server_failure(
    code: str,
    error: Exception,
) -> None:
    try:
        state = getattr(frappe.flags, _REVISE_SERVER_DIAGNOSTIC_FLAG, None)
        exception_type = type(error).__name__
        if (
            not isinstance(state, dict)
            or set(state) != {"trace_id", "recorded"}
            or state.get("recorded") is True
            or type(state.get("recorded")) is not bool
            or code not in ENGINEERING_CHANGE_REVISE_SERVER_DIAGNOSTIC_CODES
            or not isinstance(state.get("trace_id"), str)
            or _DIAGNOSTIC_TRACE_PATTERN.fullmatch(str(state["trace_id"])) is None
            or _DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        _write_engineering_change_revise_server_diagnostic(
            {
                "code": code,
                "exceptionType": exception_type,
                "traceId": str(state["trace_id"]),
            }
        )
        state["recorded"] = True
    except Exception:
        # Diagnostics must never replace the original exception or transaction.
        pass


def _write_engineering_change_revise_server_diagnostic(
    record: dict[str, str],
) -> None:
    path_value = os.environ.get(_DIAGNOSTIC_PATH_ENV)
    if not isinstance(path_value, str) or not path_value:
        return
    path = os.path.abspath(path_value)
    if path != path_value or os.path.basename(path) != _DIAGNOSTIC_PATH_NAME:
        return
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(payload)


class ChangeControlIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "ENGINEERING_CHANGE_IDEMPOTENCY_CONFLICT",
            _("This idempotency key was already used for a different engineering change command."),
        )


class ChangeControlNotCloseable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "ENGINEERING_CHANGE_NOT_CLOSEABLE",
            _("Complete every engineering change closeout requirement before closing the change."),
        )


@dataclass(frozen=True, slots=True)
class ChangeCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeChangeControlRepository:
    """Project-contained append-only engineering change repository."""

    def __init__(self, *, principal: Principal, request_id: str, trace_id: str) -> None:
        if principal.is_external or not principal.tenant_id:
            raise PermissionDenied()
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = request_id
        self.trace_id = trace_id

    def list_changes(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        names = frappe.get_all(
            "NPI Engineering Change",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project_id),
            },
            pluck="name",
            order_by="modified desc, global_id asc",
            limit_page_length=_MAX_CHANGES + 1,
        )
        if len(names) > _MAX_CHANGES:
            raise RuntimeError("Engineering change collection exceeds its safe bound.")
        items = []
        for name in names:
            root = frappe.get_doc("NPI Engineering Change", str(name))
            current = self._revision_document(root.current_revision_global_id)
            if current is None:
                raise RuntimeError("Engineering change current revision is unavailable.")
            items.append({"change": _change_response(current), "currentRevision": _revision_response(current)})
        return {
            "projectGlobalId": str(project_id),
            "items": items,
            "permissions": self._permissions(project),
        }

    def get_change(self, project_id: UUID, change_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        root = self._change_root(project, change_id)
        return None if root is None else self._detail(project, root)

    def create_change(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        content: Mapping[str, object],
    ) -> ChangeCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        tenant_id = str(project.tenant_id)
        operation = "engineering_change.create"
        payload_hash = _payload_hash({"projectGlobalId": str(project_id), "content": _content_payload(content)})
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=project_id,
            change_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ChangeCommandOutcome(replay, True)
        now = datetime.now(UTC)
        change_id = uuid4()
        revision = EngineeringChangeRevision(
            global_id=uuid4(),
            change_global_id=change_id,
            tenant_id=tenant_id,
            project_global_id=project_id,
            revision=1,
            predecessor_global_id=None,
            predecessor_snapshot_hash=None,
            state=EngineeringChangeState.DRAFT,
            formal_change=None,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
            **content,
        )
        event = self._event(revision, EngineeringChangeEventType.CREATED, now)
        response = _command_response(operation, revision)
        with change_command_write(
            service_actor_user_id=self.actor,
            scope=operation,
        ):
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=project_id,
                change_id=change_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
            if isinstance(receipt, dict):
                return ChangeCommandOutcome(receipt, True)
            self._insert_revision(revision)
            self._insert_event(event)
            self._insert_root(revision)
            self._append_audit(operation, revision)
            self._seal_receipt(receipt, response)
        return ChangeCommandOutcome(response)

    def revise_change(
        self,
        project_id: UUID,
        change_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_revision: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        content: Mapping[str, object],
    ) -> ChangeCommandOutcome | None:
        return self._successor_command(
            project_id,
            change_id,
            operation="engineering_change.revise",
            event_type=EngineeringChangeEventType.REVISED,
            idempotency_key_hash=idempotency_key_hash,
            expected_revision=expected_revision,
            expected_revision_global_id=expected_revision_global_id,
            expected_revision_snapshot_hash=expected_revision_snapshot_hash,
            payload={"content": _content_payload(content)},
            transform=lambda current, now: current.successor(
                global_id=uuid4(),
                state=(
                    EngineeringChangeState.READY_TO_CLOSE
                    if _content_successor(current, content).ready_to_close
                    else EngineeringChangeState.ACTIVE
                ),
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                **_successor_content(current, content),
            ),
        )

    def link_formal_observation(
        self,
        project_id: UUID,
        change_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_revision: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        formal_change: FormalChangeObservation,
    ) -> ChangeCommandOutcome | None:
        return self._successor_command(
            project_id,
            change_id,
            operation="engineering_change.link_formal_observation",
            event_type=EngineeringChangeEventType.FORMAL_OBSERVATION_LINKED,
            idempotency_key_hash=idempotency_key_hash,
            expected_revision=expected_revision,
            expected_revision_global_id=expected_revision_global_id,
            expected_revision_snapshot_hash=expected_revision_snapshot_hash,
            payload={"formalChange": formal_change.payload()},
            transform=lambda current, now: current.successor(
                global_id=uuid4(),
                state=(
                    EngineeringChangeState.READY_TO_CLOSE
                    if current.successor(
                        global_id=uuid4(), reason="Link the formal ERP engineering change observation.",
                        created_by_user_id=self.actor, created_at=now,
                        request_id=UUID(self.request_id), trace_id=self.trace_id,
                        formal_change=formal_change,
                    ).ready_to_close
                    else EngineeringChangeState.ACTIVE
                ),
                reason="Link the formal ERP engineering change observation.",
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
                formal_change=formal_change,
            ),
            observation=True,
        )

    def close_change(
        self,
        project_id: UUID,
        change_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_revision: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
    ) -> ChangeCommandOutcome | None:
        def close(current: EngineeringChangeRevision, now: datetime) -> EngineeringChangeRevision:
            if not current.ready_to_close:
                raise ChangeControlNotCloseable()
            return current.successor(
                global_id=uuid4(),
                state=EngineeringChangeState.CLOSED,
                reason="Close the fully evidenced engineering change.",
                created_by_user_id=self.actor,
                created_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            )

        return self._successor_command(
            project_id,
            change_id,
            operation="engineering_change.close",
            event_type=EngineeringChangeEventType.CLOSED,
            idempotency_key_hash=idempotency_key_hash,
            expected_revision=expected_revision,
            expected_revision_global_id=expected_revision_global_id,
            expected_revision_snapshot_hash=expected_revision_snapshot_hash,
            payload={},
            transform=close,
        )

    def _successor_command(
        self,
        project_id: UUID,
        change_id: UUID,
        *,
        operation: str,
        event_type: EngineeringChangeEventType,
        idempotency_key_hash: str,
        expected_revision: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        payload: Mapping[str, object],
        transform: Callable[[EngineeringChangeRevision, datetime], EngineeringChangeRevision],
        observation: bool = False,
    ) -> ChangeCommandOutcome | None:
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_PROJECT_LOCK"
        ):
            project = self._locked_authorized_project(project_id)
            if project is None:
                return None
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_ROOT_LOCK"
        ):
            root = self._locked_change_root(project, change_id)
            if root is None:
                return None
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_PAYLOAD"
        ):
            tenant_id = str(project.tenant_id)
            full_payload = {
                "projectGlobalId": str(project_id),
                "changeGlobalId": str(change_id),
                "predecessor": {
                    "expectedRevision": expected_revision,
                    "expectedRevisionGlobalId": str(expected_revision_global_id),
                    "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
                },
                **payload,
            }
            payload_hash = _payload_hash(full_payload)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_REPLAY"
        ):
            replay = self._idempotency_replay(
                tenant_id=tenant_id,
                project_id=project_id,
                change_id=change_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
        if replay is not None:
            return ChangeCommandOutcome(replay, True)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_CURRENT"
        ):
            current = self._revision_document(
                root.current_revision_global_id,
                for_update=True,
            )
            if current is None:
                return None
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_PREDECESSOR"
        ):
            if (
                current.revision != expected_revision
                or current.global_id != expected_revision_global_id
                or current.snapshot_hash != expected_revision_snapshot_hash
                or current.change_global_id != change_id
            ):
                raise VersionConflict()
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_STATE"
        ):
            if current.state in {
                EngineeringChangeState.CLOSED,
                EngineeringChangeState.CANCELLED,
            }:
                raise VersionConflict()
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_TRANSFORM"
        ):
            now = datetime.now(UTC)
            successor = transform(current, now)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_EVENT"
        ):
            resolved_event_type = (
                EngineeringChangeEventType.READY_TO_CLOSE
                if successor.state is EngineeringChangeState.READY_TO_CLOSE
                and current.state is not EngineeringChangeState.READY_TO_CLOSE
                else event_type
            )
            event = self._event(successor, resolved_event_type, now)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_RESPONSE"
        ):
            response = _command_response(operation, successor)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_WRITE_SCOPE"
        ):
            scope = (
                change_observation_write(
                    service_actor_user_id=self.actor,
                    scope=operation,
                )
                if observation
                else change_command_write(
                    service_actor_user_id=self.actor,
                    scope=operation,
                )
            )
            with scope as capability:
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_RECEIPT"
                ):
                    receipt = self._insert_receipt(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        change_id=change_id,
                        operation=operation,
                        idempotency_key_hash=idempotency_key_hash,
                        payload_hash=payload_hash,
                    )
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_REPLAY"
                ):
                    if isinstance(receipt, dict):
                        return ChangeCommandOutcome(receipt, True)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_REVISION_INSERT"
                ):
                    self._insert_revision(successor)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_EVENT_INSERT"
                ):
                    self._insert_event(event)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_ROOT_APPLY"
                ):
                    self._apply_root(root, successor)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE"
                ):
                    save_change_support_document(root, capability=capability)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_AUDIT"
                ):
                    self._append_audit(operation, successor)
                with engineering_change_revise_server_step(
                    "P901_CHANGE_REVISE_REPOSITORY_RECEIPT_SEAL"
                ):
                    self._seal_receipt(receipt, response)
        with engineering_change_revise_server_step(
            "P901_CHANGE_REVISE_REPOSITORY_OUTCOME"
        ):
            return ChangeCommandOutcome(response)

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        return project if project is not None and self._can_access_project(project, project_id) else None

    def _locked_authorized_project(self, project_id: UUID):
        try:
            project = frappe.get_doc("NPI Engineering Project", str(project_id), for_update=True)
        except frappe.DoesNotExistError:
            return None
        return project if self._can_access_project(project, project_id) else None

    def _can_access_project(self, project, project_id: UUID) -> bool:
        if (
            self.principal.is_external
            or self.principal.tenant_id != str(project.tenant_id)
            or str(project.global_id) != str(project_id)
            or not _enabled_system_user(self.actor)
        ):
            return False
        if "System Manager" in self.principal.roles or str(project.owner_user_id).casefold() == self.actor.casefold():
            return True
        return self._current_actor_member(project)

    def _current_actor_member(self, project) -> bool:
        names = frappe.get_all(
            "NPI Project Member",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "user_id": self.actor,
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_MEMBERS + 1,
        )
        if len(names) > _MAX_MEMBERS:
            raise RuntimeError("Project member collection exceeds its safe bound.")
        today = datetime.now(UTC).date()
        return len(
            [member for name in names if _member_effective((member := frappe.get_doc("NPI Project Member", str(name))), today)]
        ) == 1

    def _permissions(self, project) -> dict[str, bool]:
        allowed = self._can_access_project(project, UUID(str(project.global_id)))
        return {
            "canView": allowed,
            "canCreate": allowed,
            "canRevise": allowed,
            "canLinkFormalObservation": allowed and "System Manager" in self.principal.roles,
            "canClose": allowed,
        }

    @staticmethod
    def _change_root(project, change_id: UUID):
        root = _optional_doc("NPI Engineering Change", str(change_id))
        if root is None or str(root.global_id) != str(change_id) or str(root.project_global_id) != str(project.global_id) or str(root.tenant_id) != str(project.tenant_id):
            return None
        return root

    @staticmethod
    def _locked_change_root(project, change_id: UUID):
        try:
            root = frappe.get_doc("NPI Engineering Change", str(change_id), for_update=True)
        except frappe.DoesNotExistError:
            return None
        if str(root.global_id) != str(change_id) or str(root.project_global_id) != str(project.global_id) or str(root.tenant_id) != str(project.tenant_id):
            return None
        return root

    def _detail(self, project, root) -> dict[str, Any]:
        names = frappe.get_all(
            "NPI Engineering Change Revision",
            filters={"tenant_id": str(project.tenant_id), "change_global_id": str(root.global_id)},
            pluck="name",
            order_by="revision asc",
            limit_page_length=_MAX_CHANGES + 1,
        )
        event_names = frappe.get_all(
            "NPI Engineering Change Event",
            filters={"tenant_id": str(project.tenant_id), "change_global_id": str(root.global_id)},
            pluck="name",
            order_by="revision asc, occurred_at asc, global_id asc",
            limit_page_length=_MAX_CHANGES + 1,
        )
        if not names or len(names) > _MAX_CHANGES or not event_names or len(event_names) > _MAX_CHANGES:
            raise RuntimeError("Engineering change history is invalid or exceeds its safe bound.")
        revisions = [self._revision_document(name) for name in names]
        if any(item is None for item in revisions):
            raise RuntimeError("Engineering change revision history is unavailable.")
        events = [_event_from_document(frappe.get_doc("NPI Engineering Change Event", str(name))) for name in event_names]
        current = revisions[-1]
        assert current is not None
        return {
            "projectGlobalId": str(project.global_id),
            "change": _change_response(current),
            "currentRevision": _revision_response(current),
            "revisions": [_revision_response(item) for item in revisions if item is not None],
            "events": [_event_response(item) for item in events],
            "permissions": self._permissions(project),
        }

    @staticmethod
    def _revision_document(name: object, for_update: bool = False) -> EngineeringChangeRevision | None:
        try:
            document = frappe.get_doc("NPI Engineering Change Revision", str(name), for_update=for_update)
        except frappe.DoesNotExistError:
            return None
        return _revision_from_document(document)

    def _idempotency_replay(
        self,
        *,
        tenant_id: str,
        project_id: UUID,
        change_id: UUID | None,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        actor_key_hash = _actor_key_hash(tenant_id, project_id, self.actor, operation, idempotency_key_hash)
        records = frappe.get_all(
            "NPI Engineering Change Idempotency",
            filters={"actor_key_hash": actor_key_hash},
            fields=["name", "record_id", "actor_user_id", "tenant_id", "project_global_id", "change_global_id", "operation", "actor_key_hash", "payload_hash", "response_json", "response_sealed"],
            limit_page_length=2,
        )
        if not records:
            return None
        if len(records) != 1:
            raise RuntimeError("Engineering change idempotency identity is not unique.")
        record = records[0]
        if (
            str(_value(record, "payload_hash")) != payload_hash
            or str(_value(record, "tenant_id")) != tenant_id
            or str(_value(record, "project_global_id")) != str(project_id)
            or str(_value(record, "actor_user_id")).casefold() != self.actor.casefold()
            or str(_value(record, "operation")) != operation
            or str(_value(record, "actor_key_hash")) != actor_key_hash
            or int(_value(record, "response_sealed") or 0) != 1
        ):
            raise ChangeControlIdempotencyConflict()
        persisted_change = _value(record, "change_global_id") or None
        if change_id is not None and persisted_change != str(change_id):
            raise ChangeControlIdempotencyConflict()
        response = _json_object(_value(record, "response_json"))
        return validate_receipt_response(
            operation,
            response,
            project_global_id=str(project_id),
            change_global_id=str(change_id) if change_id else persisted_change,
        )

    def _insert_receipt(
        self,
        *,
        tenant_id: str,
        project_id: UUID,
        change_id: UUID,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ):
        if operation not in _OPERATIONS:
            raise RuntimeError("Unsupported engineering change operation.")
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Engineering Change Idempotency",
                    "record_id": str(uuid4()),
                    "actor_user_id": self.actor,
                    "tenant_id": tenant_id,
                    "project_global_id": str(project_id),
                    "change_global_id": str(change_id),
                    "operation": operation,
                    "actor_key_hash": _actor_key_hash(tenant_id, project_id, self.actor, operation, idempotency_key_hash),
                    "payload_hash": payload_hash,
                    "response_json": {},
                    "response_sealed": 0,
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(
                tenant_id=tenant_id,
                project_id=project_id,
                change_id=None if operation == "engineering_change.create" else change_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_receipt(receipt, response: Mapping[str, Any]) -> None:
        receipt.response_json = dict(response)
        receipt.response_sealed = 1
        receipt.save()

    @staticmethod
    def _insert_revision(value: EngineeringChangeRevision) -> None:
        payload = value.revision_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Engineering Change Revision",
                "global_id": str(value.global_id),
                "change_global_id": str(value.change_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "revision": value.revision,
                "predecessor_global_id": None if value.predecessor_global_id is None else str(value.predecessor_global_id),
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "internal_state": value.state.value,
                "title": value.title,
                "formal_change_snapshot": payload["formalChange"] or {},
                "impact_assessment_snapshot": payload["impactAssessments"],
                "affected_object_snapshot": payload["affectedObjects"],
                "implementation_task_snapshot": payload["implementationTasks"],
                "effectivity_snapshot": payload["effectivityRules"],
                "disposition_snapshot": payload["dispositions"],
                "revalidation_snapshot": payload["revalidationRequirements"],
                "cost_summary_snapshot": payload["costSummary"],
                "closure_evidence_snapshot": payload["closureEvidence"] or {},
                "revision_reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "revision_snapshot": payload,
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    @staticmethod
    def _insert_event(value: EngineeringChangeEvent) -> None:
        payload = value.event_payload()
        frappe.get_doc(
            {
                "doctype": "NPI Engineering Change Event",
                "global_id": str(value.global_id),
                "change_global_id": str(value.change_global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "revision_global_id": str(value.revision_global_id),
                "revision": value.revision,
                "revision_snapshot_hash": value.revision_snapshot_hash,
                "event_type": value.event_type.value,
                "actor_user_id": value.actor_user_id,
                "occurred_at": _database_datetime(value.occurred_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "event_snapshot": payload,
                "event_hash": value.event_hash,
            }
        ).insert()

    @staticmethod
    def _insert_root(value: EngineeringChangeRevision) -> None:
        document = frappe.get_doc({"doctype": "NPI Engineering Change", "global_id": str(value.change_global_id), "tenant_id": value.tenant_id, "project_global_id": str(value.project_global_id)})
        FrappeChangeControlRepository._apply_root(document, value)
        document.insert()

    @staticmethod
    def _apply_root(document, value: EngineeringChangeRevision) -> None:
        document.title = value.title
        document.internal_state = value.state.value
        document.optimistic_version = value.revision
        document.current_revision = str(value.global_id)
        document.current_revision_global_id = str(value.global_id)
        document.current_revision_number = value.revision
        document.current_revision_snapshot_hash = value.snapshot_hash
        formal = value.formal_change
        document.formal_change_doctype = None if formal is None else formal.doctype
        document.formal_change_document_id = None if formal is None else formal.document_name
        document.formal_change_raw_status = None if formal is None else formal.raw_status
        document.formal_change_source_version = None if formal is None else formal.source_version
        document.formal_change_source_modified_at = None if formal is None else _database_datetime(formal.source_modified_at)
        document.formal_change_source_hash = None if formal is None else formal.source_hash
        document.formal_change_observed_at = None if formal is None else _database_datetime(formal.observed_at)

    def _event(self, revision: EngineeringChangeRevision, event_type: EngineeringChangeEventType, now: datetime) -> EngineeringChangeEvent:
        return EngineeringChangeEvent(
            global_id=uuid4(),
            change_global_id=revision.change_global_id,
            tenant_id=revision.tenant_id,
            project_global_id=revision.project_global_id,
            revision_global_id=revision.global_id,
            revision=revision.revision,
            revision_snapshot_hash=revision.snapshot_hash,
            event_type=event_type,
            actor_user_id=self.actor,
            occurred_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )

    def _append_audit(self, operation: str, revision: EngineeringChangeRevision) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=revision.change_global_id,
            object_version=revision.revision,
            result="created",
            input_summary={
                "projectGlobalId": str(revision.project_global_id),
                "changeGlobalId": str(revision.change_global_id),
                "revisionGlobalId": str(revision.global_id),
                "requestId": self.request_id,
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


def _content_successor(current: EngineeringChangeRevision, content: Mapping[str, object]) -> EngineeringChangeRevision:
    return current.successor(
        global_id=uuid4(),
        created_by_user_id=current.created_by_user_id,
        created_at=current.created_at,
        request_id=current.request_id,
        trace_id=current.trace_id,
        **_successor_content(current, content),
    )


def _successor_content(
    current: EngineeringChangeRevision,
    content: Mapping[str, object],
) -> dict[str, object]:
    if content["title"] != current.title:
        raise RequestValidationFailed(
            [
                {
                    "path": "content.title",
                    "message": _("The engineering change title cannot be changed."),
                }
            ]
        )
    return {key: value for key, value in content.items() if key != "title"}


def _content_payload(content: Mapping[str, object]) -> dict[str, object]:
    return {
        "title": content["title"],
        "reason": content["reason"],
        "impactAssessments": [item.payload() for item in content["impact_assessments"]],
        "affectedObjects": [item.payload() for item in content["affected_objects"]],
        "implementationTasks": [item.payload() for item in content["implementation_tasks"]],
        "effectivityRules": [item.payload() for item in content["effectivity_rules"]],
        "dispositions": [item.payload() for item in content["dispositions"]],
        "revalidationRequirements": [item.payload() for item in content["revalidation_requirements"]],
        "costSummary": content["cost_summary"].payload(),
        "closureEvidence": None if content["closure_evidence"] is None else content["closure_evidence"].payload(),
    }


def _revision_from_document(document) -> EngineeringChangeRevision:
    snapshot = _json_object(document.revision_snapshot)
    content = parse_revision_content(
        {
            "title": snapshot["title"], "reason": snapshot["reason"],
            "impactAssessments": snapshot["impactAssessments"],
            "affectedObjects": snapshot["affectedObjects"],
            "implementationTasks": snapshot["implementationTasks"],
            "effectivityRules": snapshot["effectivityRules"],
            "dispositions": snapshot["dispositions"],
            "revalidationRequirements": snapshot["revalidationRequirements"],
            "costSummary": snapshot["costSummary"],
            "closureEvidence": snapshot["closureEvidence"],
        }
    )
    result = EngineeringChangeRevision(
        global_id=UUID(snapshot["globalId"]),
        change_global_id=UUID(snapshot["changeGlobalId"]),
        tenant_id=str(snapshot["tenantId"]),
        project_global_id=UUID(snapshot["projectGlobalId"]),
        revision=int(snapshot["revision"]),
        predecessor_global_id=None if snapshot["predecessorGlobalId"] is None else UUID(snapshot["predecessorGlobalId"]),
        predecessor_snapshot_hash=snapshot["predecessorSnapshotHash"],
        state=EngineeringChangeState(snapshot["state"]),
        formal_change=None if snapshot["formalChange"] is None else parse_formal_observation(snapshot["formalChange"]),
        created_by_user_id=str(snapshot["createdByUserId"]),
        created_at=_datetime(snapshot["createdAt"]),
        request_id=UUID(snapshot["requestId"]),
        trace_id=str(snapshot["traceId"]),
        **content,
    )
    if result.snapshot_hash != str(document.snapshot_hash) or result.revision_payload() != snapshot:
        raise RuntimeError("Persisted engineering change revision integrity failed.")
    return result


def _event_from_document(document) -> EngineeringChangeEvent:
    snapshot = _json_object(document.event_snapshot)
    result = EngineeringChangeEvent(
        global_id=UUID(snapshot["globalId"]), change_global_id=UUID(snapshot["changeGlobalId"]),
        tenant_id=str(snapshot["tenantId"]), project_global_id=UUID(snapshot["projectGlobalId"]),
        revision_global_id=UUID(snapshot["revisionGlobalId"]), revision=int(snapshot["revision"]),
        revision_snapshot_hash=str(snapshot["revisionSnapshotHash"]),
        event_type=EngineeringChangeEventType(snapshot["eventType"]), actor_user_id=str(snapshot["actorUserId"]),
        occurred_at=_datetime(snapshot["occurredAt"]), request_id=UUID(snapshot["requestId"]),
        trace_id=str(snapshot["traceId"]),
    )
    if result.event_hash != str(document.event_hash) or result.event_payload() != snapshot:
        raise RuntimeError("Persisted engineering change event integrity failed.")
    return result


def _revision_response(value: EngineeringChangeRevision) -> dict[str, Any]:
    return {**value.revision_payload(), "snapshotHash": value.snapshot_hash}


def _event_response(value: EngineeringChangeEvent) -> dict[str, Any]:
    return {**value.event_payload(), "eventHash": value.event_hash}


def _change_response(value: EngineeringChangeRevision) -> dict[str, Any]:
    return {
        "globalId": str(value.change_global_id), "projectGlobalId": str(value.project_global_id),
        "title": value.title, "state": value.state.value, "optimisticVersion": value.revision,
        "currentRevisionGlobalId": str(value.global_id), "currentRevisionNumber": value.revision,
        "currentRevisionSnapshotHash": value.snapshot_hash,
        "formalChange": None if value.formal_change is None else value.formal_change.payload(),
        "readyToClose": value.ready_to_close,
    }


def _command_response(operation: str, value: EngineeringChangeRevision) -> dict[str, Any]:
    return {"operation": operation, "change": _change_response(value), "currentRevision": _revision_response(value)}


def _actor_key_hash(tenant_id: str, project_id: UUID, actor: str, operation: str, idempotency_key_hash: str) -> str:
    return sha256_json({"tenantId": tenant_id, "projectGlobalId": str(project_id), "actorUserId": actor.casefold(), "operation": operation, "idempotencyKeyHash": idempotency_key_hash})


def _payload_hash(value: Mapping[str, object]) -> str:
    return sha256_json(dict(value))


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _enabled_system_user(user_id: str) -> bool:
    record = frappe.db.get_value("User", user_id, ["enabled", "user_type"], as_dict=True)
    return bool(record and int(_value(record, "enabled") or 0) == 1 and _value(record, "user_type") == "System User")


def _member_effective(member, today) -> bool:
    valid_from = _date_value(getattr(member, "effective_from", None))
    valid_to = (
        _date_value(member.effective_to)
        if getattr(member, "effective_to", None)
        else None
    )
    return valid_from <= today and (valid_to is None or today <= valid_to)


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _json_object(value: object) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise RuntimeError("Persisted engineering change JSON is invalid.")
    return dict(parsed)


def _datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")


def _value(record: object, name: str):
    return record.get(name) if hasattr(record, "get") else getattr(record, name, None)
