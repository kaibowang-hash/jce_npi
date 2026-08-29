from __future__ import annotations

import base64
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterator
from uuid import UUID, uuid4

import frappe

from npi_core.documents.frappe_repository import (
    FrappeDocumentRepository,
    _database_datetime,
)
from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.security import Principal
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_integration.inbound_project.frappe_validation import (
    inbound_project_manual_replay_write,
    save_inbound_project_replay_document,
)
from npi_integration.item_publish.frappe_validation import (
    item_manual_replay_write,
    item_service_actor_scope,
    save_item_support_document,
)
from npi_integration.mbom_publish.frappe_validation import (
    mbom_manual_replay_write,
    mbom_service_actor_scope,
    save_mbom_support_document,
)
from npi_integration.tool_asset_request.execution_frappe_validation import (
    save_tool_asset_support_document,
    tool_asset_manual_replay_write,
    tool_asset_service_actor_scope,
)

from .domain import (
    INTEGRATION_OPERATIONS_SCHEMA_VERSION,
    IntegrationActionKind,
    IntegrationActionOutcome,
    IntegrationActionReceipt,
    IntegrationOperationKind,
    IntegrationOperationReference,
    IntegrationViewState,
    canonical_hash,
    classify_operation_state,
    evaluate_replay_eligibility,
)
from .frappe_validation import (
    INTEGRATION_OPERATIONS_SUPPORT_WRITES,
    insert_integration_operations_support_document,
    integration_operations_write_capability,
)
from .problems import IntegrationOperationConflict


_MAX_OPERATIONS = 500
_MAX_HISTORY = 256
_CURSOR_VERSION = 1
_ACTION_RECEIPT_INSERT = frozenset(
    {("NPI Integration Action Receipt", "insert")}
)
INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_CODES = frozenset(
    {
        "P807_COLLECTION_API_DOMAIN_CALL",
        "P807_COLLECTION_API_FIELDS",
        "P807_COLLECTION_API_CONTEXT",
        "P807_COLLECTION_API_ARGUMENTS",
        "P807_COLLECTION_API_REPOSITORY",
        "P807_COLLECTION_API_OUTCOME",
        "P807_COLLECTION_API_RESPONSE",
        "P807_COLLECTION_REPOSITORY_PROJECT",
        "P807_COLLECTION_REPOSITORY_CURSOR",
        "P807_COLLECTION_REPOSITORY_VALUES",
        "P807_COLLECTION_REPOSITORY_FILTER",
        "P807_COLLECTION_REPOSITORY_ITEM",
        "P807_COLLECTION_REPOSITORY_SORT",
        "P807_COLLECTION_REPOSITORY_PAGE",
        "P807_COLLECTION_REPOSITORY_CURSOR_ENCODE",
        "P807_COLLECTION_REPOSITORY_RESPONSE",
        "P807_COLLECTION_INBOUND_QUERY",
        "P807_COLLECTION_ITEM_QUERY",
        "P807_COLLECTION_MBOM_QUERY",
        "P807_COLLECTION_TOOL_CREATE_QUERY",
        "P807_COLLECTION_TOOL_UPDATE_QUERY",
        "P807_COLLECTION_INBOUND_ROW",
        "P807_COLLECTION_ITEM_ROW",
        "P807_COLLECTION_MBOM_ROW",
        "P807_COLLECTION_TOOL_CREATE_ROW",
        "P807_COLLECTION_TOOL_UPDATE_ROW",
        "P807_COLLECTION_INBOUND_VALUE",
        "P807_COLLECTION_ITEM_VALUE",
        "P807_COLLECTION_MBOM_VALUE",
        "P807_COLLECTION_TOOL_CREATE_VALUE",
        "P807_COLLECTION_TOOL_UPDATE_VALUE",
        "P807_COLLECTION_INBOUND_TIME",
        "P807_COLLECTION_ITEM_TIME",
        "P807_COLLECTION_MBOM_TIME",
        "P807_COLLECTION_TOOL_CREATE_TIME",
        "P807_COLLECTION_TOOL_UPDATE_TIME",
        "P807_COLLECTION_INBOUND_BOUNDARIES",
        "P807_COLLECTION_ITEM_BOUNDARIES",
        "P807_COLLECTION_MBOM_BOUNDARIES",
        "P807_COLLECTION_TOOL_CREATE_BOUNDARIES",
        "P807_COLLECTION_TOOL_UPDATE_BOUNDARIES",
        "P807_COLLECTION_INBOUND_SHAPE",
        "P807_COLLECTION_ITEM_SHAPE",
        "P807_COLLECTION_MBOM_SHAPE",
        "P807_COLLECTION_TOOL_CREATE_SHAPE",
        "P807_COLLECTION_TOOL_UPDATE_SHAPE",
    }
)
INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_CODES = frozenset(
    {
        "P807_ACTION_API_DOMAIN_CALL",
        "P807_ACTION_API_CSRF",
        "P807_ACTION_API_FIELDS",
        "P807_ACTION_API_CONTEXT",
        "P807_ACTION_API_REPOSITORY",
        "P807_ACTION_API_OUTCOME",
        "P807_ACTION_API_RESPONSE",
        "P807_ACTION_API_COMMIT",
        "P807_ACTION_API_HEADERS",
        "P807_ACTION_REPOSITORY_PROJECT",
        "P807_ACTION_REPOSITORY_REQUEST",
        "P807_ACTION_REPOSITORY_REPLAY_LOOKUP",
        "P807_ACTION_REPOSITORY_MUTABLE",
        "P807_ACTION_REPOSITORY_OPERATION",
        "P807_ACTION_REPOSITORY_EXPECTATION",
        "P807_ACTION_REPOSITORY_REQUEUE",
        "P807_ACTION_REPOSITORY_RESPONSE",
        "P807_ACTION_REPOSITORY_RECEIPT",
        "P807_ACTION_REPOSITORY_RECEIPT_INSERT",
        "P807_ACTION_REPOSITORY_AUDIT",
        "P807_ACTION_REPOSITORY_ENQUEUE",
        "P807_ACTION_REPOSITORY_OUTCOME",
    }
)
_COLLECTION_DIAGNOSTIC_FLAG = "npi_p807_collection_diagnostic"
_ACTION_DIAGNOSTIC_FLAG = "npi_p807_action_diagnostic"
_COLLECTION_DIAGNOSTIC_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")
_COLLECTION_DIAGNOSTIC_TYPE_PATTERN = re.compile(
    r"^[A-Za-z][A-Za-z0-9_.]{0,127}$"
)


@contextmanager
def integration_operations_collection_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    """Enable one exact collection diagnostic scope without changing behavior."""

    try:
        state = None
        if (
            active
            and isinstance(trace_id, str)
            and _COLLECTION_DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        ):
            state = {"trace_id": trace_id, "recorded": False}
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _COLLECTION_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _COLLECTION_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _COLLECTION_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _COLLECTION_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def integration_operations_collection_step(code: str) -> Iterator[None]:
    """Record one innermost allowlisted collection stage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_integration_operations_collection_failure(code, error)
        raise


@contextmanager
def integration_operations_action_diagnostics(
    trace_id: str | None,
    *,
    active: bool,
) -> Iterator[None]:
    """Enable one exact action diagnostic scope without changing behavior."""

    try:
        state = None
        if (
            active
            and isinstance(trace_id, str)
            and _COLLECTION_DIAGNOSTIC_TRACE_PATTERN.fullmatch(trace_id) is not None
        ):
            state = {"trace_id": trace_id, "recorded": False}
        flags = frappe.flags
        missing = object()
        previous = getattr(flags, _ACTION_DIAGNOSTIC_FLAG, missing)
        setattr(flags, _ACTION_DIAGNOSTIC_FLAG, state)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if previous is missing:
                delattr(flags, _ACTION_DIAGNOSTIC_FLAG)
            else:
                setattr(flags, _ACTION_DIAGNOSTIC_FLAG, previous)
        except Exception:
            pass


@contextmanager
def integration_operations_action_step(code: str) -> Iterator[None]:
    """Record one innermost allowlisted action stage and re-raise unchanged."""

    try:
        yield
    except Exception as error:
        _record_integration_operations_action_failure(code, error)
        raise


def _record_integration_operations_collection_failure(
    code: str,
    error: Exception,
) -> None:
    try:
        state = getattr(frappe.flags, _COLLECTION_DIAGNOSTIC_FLAG, None)
        exception_type = type(error).__name__
        if (
            not isinstance(state, dict)
            or set(state) != {"trace_id", "recorded"}
            or state.get("recorded") is True
            or type(state.get("recorded")) is not bool
            or code not in INTEGRATION_OPERATIONS_COLLECTION_DIAGNOSTIC_CODES
            or not isinstance(state.get("trace_id"), str)
            or _COLLECTION_DIAGNOSTIC_TRACE_PATTERN.fullmatch(
                str(state["trace_id"])
            )
            is None
            or _COLLECTION_DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI integration operations collection stage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics must never alter the original response or transaction.
        pass


def _record_integration_operations_action_failure(
    code: str,
    error: Exception,
) -> None:
    try:
        state = getattr(frappe.flags, _ACTION_DIAGNOSTIC_FLAG, None)
        exception_type = type(error).__name__
        if (
            not isinstance(state, dict)
            or set(state) != {"trace_id", "recorded"}
            or state.get("recorded") is True
            or type(state.get("recorded")) is not bool
            or code not in INTEGRATION_OPERATIONS_ACTION_DIAGNOSTIC_CODES
            or not isinstance(state.get("trace_id"), str)
            or _COLLECTION_DIAGNOSTIC_TRACE_PATTERN.fullmatch(
                str(state["trace_id"])
            )
            is None
            or _COLLECTION_DIAGNOSTIC_TYPE_PATTERN.fullmatch(exception_type) is None
        ):
            return
        state["recorded"] = True
        from npi_core.api import record_safe_diagnostic

        record_safe_diagnostic(
            code=code,
            title="NPI integration operation action stage failed",
            exception_type=exception_type,
            trace_id=str(state["trace_id"]),
        )
    except Exception:
        # Diagnostics must never alter the original response or transaction.
        pass


@dataclass(frozen=True, slots=True)
class IntegrationActionCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class _OperationSpec:
    kind: IntegrationOperationKind
    doctype: str
    state_field: str
    version_field: str
    source_id_field: str
    source_hash_field: str
    updated_field: str
    result_field: str | None
    outbox_link_field: str | None


_SPECS = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: _OperationSpec(
        IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION,
        "NPI Inbox Message",
        "state",
        "attempt_count",
        "event_id",
        "canonical_event_hash",
        "last_error_at",
        None,
        None,
    ),
    IntegrationOperationKind.PUBLISH_ITEM: _OperationSpec(
        IntegrationOperationKind.PUBLISH_ITEM,
        "NPI Item Publish Request",
        "state",
        "optimistic_version",
        "selected_publish_node_global_id",
        "source_hash",
        "updated_at",
        "result_global_id",
        "outbox_event_id",
    ),
    IntegrationOperationKind.PUBLISH_MBOM: _OperationSpec(
        IntegrationOperationKind.PUBLISH_MBOM,
        "NPI MBOM Publish Request",
        "state",
        "optimistic_version",
        "ebom_global_id",
        "source_hash",
        "updated_at",
        "result_global_id",
        "outbox_event_id",
    ),
    IntegrationOperationKind.CREATE_TOOL_ASSET: _OperationSpec(
        IntegrationOperationKind.CREATE_TOOL_ASSET,
        "NPI Tool Asset Request",
        "execution_state",
        "optimistic_version",
        "tooling_set_global_id",
        "source_hash",
        "updated_at",
        "result_global_id",
        "outbox_event_id",
    ),
    IntegrationOperationKind.UPDATE_TOOL_ASSET: _OperationSpec(
        IntegrationOperationKind.UPDATE_TOOL_ASSET,
        "NPI Tool Asset Request",
        "execution_state",
        "optimistic_version",
        "tooling_set_global_id",
        "source_hash",
        "updated_at",
        "result_global_id",
        "outbox_event_id",
    ),
}
_COLLECTION_QUERY_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_QUERY",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_QUERY",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_QUERY",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_QUERY",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_QUERY",
}
_COLLECTION_ROW_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_ROW",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_ROW",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_ROW",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_ROW",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_ROW",
}
_COLLECTION_VALUE_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_VALUE",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_VALUE",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_VALUE",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_VALUE",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_VALUE",
}
_COLLECTION_TIME_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_TIME",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_TIME",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_TIME",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_TIME",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_TIME",
}
_COLLECTION_BOUNDARY_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_BOUNDARIES",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_BOUNDARIES",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_BOUNDARIES",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_BOUNDARIES",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_BOUNDARIES",
}
_COLLECTION_SHAPE_CODES = {
    IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: "P807_COLLECTION_INBOUND_SHAPE",
    IntegrationOperationKind.PUBLISH_ITEM: "P807_COLLECTION_ITEM_SHAPE",
    IntegrationOperationKind.PUBLISH_MBOM: "P807_COLLECTION_MBOM_SHAPE",
    IntegrationOperationKind.CREATE_TOOL_ASSET: "P807_COLLECTION_TOOL_CREATE_SHAPE",
    IntegrationOperationKind.UPDATE_TOOL_ASSET: "P807_COLLECTION_TOOL_UPDATE_SHAPE",
}


class FrappeIntegrationOperationsRepository(FrappeDocumentRepository):
    """Project-first derived operations view with fixed owning replay commands."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        super().__init__(principal=principal, request_id=request_id, trace_id=trace_id)

    def authorize_scope(self, project_id: UUID, *, administer: bool = False) -> bool:
        project = self._authorized_project(project_id)
        if project is None:
            return False
        return not administer or self._can_act_on_project(project, project_id)

    def list_operations(
        self,
        project_id: UUID,
        *,
        operation_kind: IntegrationOperationKind | None,
        shared_state: IntegrationViewState | None,
        cursor: str | None,
        limit: int,
        logical_dlq: bool = False,
    ) -> dict[str, Any] | None:
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_PROJECT"
        ):
            project = self._authorized_project(project_id)
        if project is None:
            return None
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_CURSOR"
        ):
            marker = _decode_cursor(cursor, project_id) if cursor else None
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_VALUES"
        ):
            values = self._project_operations(project, operation_kind=operation_kind)
        items = []
        for value, row, updated_at in values:
            with integration_operations_collection_step(
                "P807_COLLECTION_REPOSITORY_FILTER"
            ):
                classification = value.classification
                if (
                    shared_state is not None
                    and classification.shared_state is not shared_state
                ):
                    continue
                if logical_dlq and not classification.logical_dlq:
                    continue
                sort_key = (updated_at, str(value.operation_global_id))
                if marker is not None and sort_key >= marker:
                    continue
            with integration_operations_collection_step(
                "P807_COLLECTION_REPOSITORY_ITEM"
            ):
                items.append(self._operation_item(value, row, updated_at))
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_SORT"
        ):
            items.sort(
                key=lambda item: (
                    str(item["updatedAt"]),
                    str(item["operationGlobalId"]),
                ),
                reverse=True,
            )
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_PAGE"
        ):
            page = items[: limit + 1]
            has_more = len(page) > limit
            page = page[:limit]
        next_cursor = None
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_CURSOR_ENCODE"
        ):
            if has_more and page:
                last = page[-1]
                next_cursor = _encode_cursor(
                    project_id,
                    str(last["updatedAt"]),
                    str(last["operationGlobalId"]),
                )
        with integration_operations_collection_step(
            "P807_COLLECTION_REPOSITORY_RESPONSE"
        ):
            return {
                "projectGlobalId": str(project.global_id),
                "permissions": {
                    "view": True,
                    "act": self._can_act_on_project(project, project_id),
                },
                "items": page,
                "nextCursor": next_cursor,
            }

    def operation_detail(
        self,
        project_id: UUID,
        *,
        operation_kind: IntegrationOperationKind,
        operation_id: UUID,
    ) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        resolved = self._operation_for_project(
            project,
            operation_kind=operation_kind,
            operation_id=operation_id,
            lock=False,
        )
        if resolved is None:
            return None
        value, row, updated_at = resolved
        attempts, results = self._history(value, row)
        actions = self._action_history(value)
        item = self._operation_item(value, row, updated_at)
        item.update(
            {
                "attempts": attempts,
                "results": results,
                "actions": actions,
            }
        )
        return {
            "projectGlobalId": str(project.global_id),
            "permissions": {
                "view": True,
                "act": self._can_act_on_project(project, project_id),
            },
            "operation": item,
        }

    def request_action(
        self,
        project_id: UUID,
        *,
        operation_kind: IntegrationOperationKind,
        operation_id: UUID,
        action_kind: IntegrationActionKind,
        expected_raw_state: str,
        expected_version: int,
        action_idempotency_key_hash: str,
    ) -> IntegrationActionCommandOutcome | None:
        with integration_operations_action_step("P807_ACTION_REPOSITORY_PROJECT"):
            project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        with integration_operations_action_step("P807_ACTION_REPOSITORY_REQUEST"):
            request_payload = {
                "projectGlobalId": str(project_id),
                "operationKind": operation_kind.value,
                "operationGlobalId": str(operation_id),
                "actionKind": action_kind.value,
                "expectedRawState": expected_raw_state,
                "expectedVersion": expected_version,
            }
            request_hash = canonical_hash(request_payload)
        with integration_operations_action_step(
            "P807_ACTION_REPOSITORY_REPLAY_LOOKUP"
        ):
            prior = self._action_replay(
                project,
                operation_kind=operation_kind,
                operation_id=operation_id,
                action_kind=action_kind,
                action_idempotency_key_hash=action_idempotency_key_hash,
                request_hash=request_hash,
            )
        if prior is not None:
            return IntegrationActionCommandOutcome(prior, replayed=True)
        with integration_operations_action_step("P807_ACTION_REPOSITORY_MUTABLE"):
            require_mutable_project(project)
        with integration_operations_action_step("P807_ACTION_REPOSITORY_OPERATION"):
            resolved = self._operation_for_project(
                project,
                operation_kind=operation_kind,
                operation_id=operation_id,
                lock=True,
            )
        if resolved is None:
            return None
        operation, row, _updated_at = resolved
        with integration_operations_action_step("P807_ACTION_REPOSITORY_EXPECTATION"):
            if (
                operation.raw_state != expected_raw_state
                or operation.operation_version != expected_version
            ):
                raise IntegrationOperationConflict()
        outcome_reference = None
        if action_kind is IntegrationActionKind.REPLAY:
            with integration_operations_action_step("P807_ACTION_REPOSITORY_REQUEUE"):
                outcome_reference = self._requeue_failed_retryable(operation, row)
        with integration_operations_action_step("P807_ACTION_REPOSITORY_RESPONSE"):
            action_id = uuid4()
            outcome_state = (
                IntegrationActionOutcome.REPLAY_REQUESTED
                if action_kind is IntegrationActionKind.REPLAY
                else IntegrationActionOutcome.RECONCILIATION_REQUESTED
            )
            response = {
                "actionGlobalId": str(action_id),
                "operationGlobalId": str(operation.operation_global_id),
                "outcomeState": outcome_state.value,
                "outcomeReferenceGlobalId": (
                    str(outcome_reference) if outcome_reference is not None else None
                ),
            }
        with integration_operations_action_step("P807_ACTION_REPOSITORY_RECEIPT"):
            receipt = IntegrationActionReceipt(
                global_id=action_id,
                operation=operation,
                action_kind=action_kind,
                action_idempotency_key_hash=action_idempotency_key_hash,
                expected_raw_state=expected_raw_state,
                expected_version=expected_version,
                request_hash=request_hash,
                outcome_state=outcome_state,
                outcome_reference_global_id=outcome_reference,
                response_snapshot=response,
                response_hash=canonical_hash(response),
                actor_user_id=self.actor,
                trace_id=self.trace_id,
                created_at=datetime.now(UTC),
            )
        with integration_operations_action_step(
            "P807_ACTION_REPOSITORY_RECEIPT_INSERT"
        ):
            self._insert_action_receipt(receipt)
        with integration_operations_action_step("P807_ACTION_REPOSITORY_AUDIT"):
            self._append_action_audit(receipt)
        if action_kind is IntegrationActionKind.REPLAY:
            with integration_operations_action_step("P807_ACTION_REPOSITORY_ENQUEUE"):
                self._enqueue_replay(operation_kind, outcome_reference, action_id)
        with integration_operations_action_step("P807_ACTION_REPOSITORY_OUTCOME"):
            return IntegrationActionCommandOutcome(response)

    def _can_act_on_project(self, project: Any, project_id: UUID) -> bool:
        return bool(
            "NPI API User" in self.principal.roles
            and self._can_administer_project(project, project_id)
        )

    def _project_operations(
        self,
        project: Any,
        *,
        operation_kind: IntegrationOperationKind | None,
    ) -> list[tuple[IntegrationOperationReference, Any, str]]:
        kinds = (operation_kind,) if operation_kind is not None else tuple(_SPECS)
        values: list[tuple[IntegrationOperationReference, Any, str]] = []
        for kind in kinds:
            spec = _SPECS[kind]
            filters: dict[str, Any] = {
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            }
            if kind in {
                IntegrationOperationKind.CREATE_TOOL_ASSET,
                IntegrationOperationKind.UPDATE_TOOL_ASSET,
            }:
                filters["operation"] = kind.value
                filters["schema_version"] = 2
            with integration_operations_collection_step(
                _COLLECTION_QUERY_CODES[kind]
            ):
                names = frappe.get_all(
                    spec.doctype,
                    filters=filters,
                    pluck="name",
                    order_by=f"{spec.updated_field} desc, name desc",
                    limit_page_length=_MAX_OPERATIONS + 1,
                )
                if len(names) > _MAX_OPERATIONS:
                    raise RuntimeError(
                        "Persisted integration operation collection exceeds its safe bound."
                    )
            for name in names:
                with integration_operations_collection_step(
                    _COLLECTION_ROW_CODES[kind]
                ):
                    row = frappe.get_doc(spec.doctype, str(name))
                with integration_operations_collection_step(
                    _COLLECTION_VALUE_CODES[kind]
                ):
                    value = self._operation_value(project, spec, row)
                if value is not None:
                    with integration_operations_collection_step(
                        _COLLECTION_TIME_CODES[kind]
                    ):
                        updated_at = _utc_text(_row_datetime(row, spec))
                    values.append((value, row, updated_at))
        return values

    def _operation_for_project(
        self,
        project: Any,
        *,
        operation_kind: IntegrationOperationKind,
        operation_id: UUID,
        lock: bool,
    ) -> tuple[IntegrationOperationReference, Any, str] | None:
        spec = _SPECS[operation_kind]
        try:
            row = frappe.get_doc(spec.doctype, str(operation_id), for_update=lock)
        except frappe.DoesNotExistError:
            return None
        value = self._operation_value(project, spec, row)
        if value is None or value.operation_global_id != operation_id:
            return None
        return value, row, _utc_text(_row_datetime(row, spec))

    def _operation_value(
        self,
        project: Any,
        spec: _OperationSpec,
        row: Any,
    ) -> IntegrationOperationReference | None:
        if (
            str(_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_value(row, "project_global_id")) != str(project.global_id)
        ):
            return None
        if spec.kind in {
            IntegrationOperationKind.CREATE_TOOL_ASSET,
            IntegrationOperationKind.UPDATE_TOOL_ASSET,
        } and str(_value(row, "operation")) != spec.kind.value:
            return None
        raw_state = str(_value(row, spec.state_field))
        target_key = (
            _value(row, "source_key_hash")
            if spec.kind is IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION
            else _value(row, "target_idempotency_key_hash")
        )
        if (
            spec.kind is IntegrationOperationKind.PUBLISH_ITEM
            and raw_state == "validated_mock"
            and not target_key
        ):
            return None
        classification = classify_operation_state(spec.kind, raw_state)
        operation_id = _uuid(_value(row, "name") or _value(row, "global_id"))
        source_id = _uuid(_value(row, spec.source_id_field))
        version = max(1, int(_value(row, spec.version_field) or 0))
        return IntegrationOperationReference(
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            operation_kind=spec.kind,
            operation_global_id=operation_id,
            source_global_id=source_id,
            operation_version=version,
            raw_state=raw_state,
            shared_state=classification.shared_state,
            source_snapshot_hash=str(_value(row, spec.source_hash_field)),
            target_idempotency_key_hash=str(target_key),
        )

    def _operation_item(
        self,
        operation: IntegrationOperationReference,
        row: Any,
        updated_at: str,
    ) -> dict[str, Any]:
        classification = operation.classification
        with integration_operations_collection_step(
            _COLLECTION_BOUNDARY_CODES[operation.operation_kind]
        ):
            uncertain_boundary, reconciliation_required, partial_result = (
                self._replay_boundaries(operation, row)
            )
        with integration_operations_collection_step(
            _COLLECTION_SHAPE_CODES[operation.operation_kind]
        ):
            eligibility = evaluate_replay_eligibility(
                classification,
                uncertain_boundary=uncertain_boundary,
                reconciliation_required=reconciliation_required,
                partial_result=partial_result,
            )
            return {
                **operation.payload(),
                "logicalDlq": classification.logical_dlq,
                "faultClass": classification.fault_class.value,
                "replayEligible": eligibility.eligible,
                "replayEligibilityReason": eligibility.reason.value,
                "reconciliationRequired": reconciliation_required,
                "updatedAt": updated_at,
            }

    def _replay_boundaries(
        self,
        operation: IntegrationOperationReference,
        row: Any,
    ) -> tuple[bool, bool, bool]:
        if operation.operation_kind is IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION:
            return False, False, False
        outbox = self._outbox(operation.operation_kind, row, lock=False)
        boundary = bool(_value(outbox, "adapter_boundary_crossed")) if outbox else True
        result_id = _value(row, _SPECS[operation.operation_kind].result_field or "")
        result = self._result(operation.operation_kind, result_id, lock=False)
        result_state = str(_value(result, "state")) if result else ""
        reconciliation = result_state in {"uncertain_after_timeout", "mapping_conflict"}
        partial = result_state == "partially_succeeded"
        return boundary, reconciliation, partial

    def _history(
        self,
        operation: IntegrationOperationReference,
        row: Any,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if operation.operation_kind is IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION:
            attempt_count = int(_value(row, "attempt_count") or 0)
            attempts = (
                [
                    {
                        "attemptNumber": attempt_count,
                        "state": operation.raw_state,
                        "adapterBoundaryCrossed": False,
                        "reconciliationRequired": False,
                        "safeErrorCode": _value(row, "last_error_code") or None,
                    }
                ]
                if attempt_count
                else []
            )
            return attempts, []
        attempt_doctype, result_doctype, request_field = {
            IntegrationOperationKind.PUBLISH_ITEM: (
                "NPI Item Publish Attempt",
                "NPI Item Publish Result",
                "request_global_id",
            ),
            IntegrationOperationKind.PUBLISH_MBOM: (
                "NPI MBOM Publish Attempt",
                "NPI MBOM Publish Result",
                "request_global_id",
            ),
            IntegrationOperationKind.CREATE_TOOL_ASSET: (
                "NPI Tool Asset Attempt",
                "NPI Tool Asset Result",
                "request_global_id",
            ),
            IntegrationOperationKind.UPDATE_TOOL_ASSET: (
                "NPI Tool Asset Attempt",
                "NPI Tool Asset Result",
                "request_global_id",
            ),
        }[operation.operation_kind]
        attempt_names = frappe.get_all(
            attempt_doctype,
            filters={request_field: str(operation.operation_global_id)},
            pluck="name",
            order_by="attempt_number asc, name asc",
            limit_page_length=_MAX_HISTORY + 1,
        )
        result_names = frappe.get_all(
            result_doctype,
            filters={request_field: str(operation.operation_global_id)},
            pluck="name",
            order_by="attempt_number asc, name asc",
            limit_page_length=_MAX_HISTORY + 1,
        )
        if len(attempt_names) > _MAX_HISTORY or len(result_names) > _MAX_HISTORY:
            raise RuntimeError("Persisted integration operation history exceeds its safe bound.")
        attempts = []
        for name in attempt_names:
            value = frappe.get_doc(attempt_doctype, str(name))
            attempts.append(
                {
                    "attemptGlobalId": str(_value(value, "global_id")),
                    "attemptNumber": int(_value(value, "attempt_number")),
                    "state": str(_value(value, "state")),
                    "adapterBoundaryCrossed": bool(_value(value, "adapter_boundary_crossed")),
                    "reconciliationRequired": bool(_value(value, "reconciliation_required")),
                    "safeErrorCode": _value(value, "safe_error_code") or None,
                    "startedAt": _optional_utc_text(_value(value, "started_at")),
                    "finishedAt": _optional_utc_text(_value(value, "finished_at")),
                }
            )
        results = []
        for name in result_names:
            value = frappe.get_doc(result_doctype, str(name))
            results.append(
                {
                    "resultGlobalId": str(_value(value, "global_id")),
                    "attemptGlobalId": str(_value(value, "attempt_global_id")),
                    "attemptNumber": int(_value(value, "attempt_number")),
                    "state": str(_value(value, "state")),
                    "authority": str(_value(value, "authority")),
                    "responseAuthenticated": bool(_value(value, "response_authenticated")),
                    "faultKind": _value(value, "fault_kind") or None,
                    "observedAt": _optional_utc_text(_value(value, "observed_at")),
                }
            )
        return attempts, results

    def _action_history(
        self,
        operation: IntegrationOperationReference,
    ) -> list[dict[str, Any]]:
        names = frappe.get_all(
            "NPI Integration Action Receipt",
            filters={
                "tenant_id": operation.tenant_id,
                "project_global_id": str(operation.project_global_id),
                "operation_kind": operation.operation_kind.value,
                "operation_global_id": str(operation.operation_global_id),
            },
            pluck="name",
            order_by="created_at asc, name asc",
            limit_page_length=_MAX_HISTORY + 1,
        )
        if len(names) > _MAX_HISTORY:
            raise RuntimeError("Persisted integration action history exceeds its safe bound.")
        values = []
        for name in names:
            row = frappe.get_doc("NPI Integration Action Receipt", str(name))
            values.append(
                {
                    "actionGlobalId": str(_value(row, "global_id")),
                    "actionKind": str(_value(row, "action_kind")),
                    "outcomeState": str(_value(row, "outcome_state")),
                    "outcomeReferenceGlobalId": _value(row, "outcome_reference_global_id") or None,
                    "actorUserId": str(_value(row, "actor_user_id")),
                    "traceId": str(_value(row, "trace_id")),
                    "createdAt": _optional_utc_text(_value(row, "created_at")),
                }
            )
        return values

    def _action_replay(
        self,
        project: Any,
        *,
        operation_kind: IntegrationOperationKind,
        operation_id: UUID,
        action_kind: IntegrationActionKind,
        action_idempotency_key_hash: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        names = frappe.get_all(
            "NPI Integration Action Receipt",
            filters={"action_idempotency_key_hash": action_idempotency_key_hash},
            pluck="name",
            order_by="name asc",
            limit_page_length=2,
        )
        if not names:
            return None
        if len(names) != 1:
            raise IntegrationOperationConflict()
        row = frappe.get_doc("NPI Integration Action Receipt", str(names[0]), for_update=True)
        if (
            str(_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_value(row, "project_global_id")) != str(project.global_id)
            or str(_value(row, "operation_kind")) != operation_kind.value
            or str(_value(row, "operation_global_id")) != str(operation_id)
            or str(_value(row, "action_kind")) != action_kind.value
            or str(_value(row, "actor_user_id")).casefold() != self.actor.casefold()
            or str(_value(row, "request_hash")) != request_hash
        ):
            raise IntegrationOperationConflict()
        response = _json_object(_value(row, "response_snapshot"))
        if canonical_hash(response) != str(_value(row, "response_hash")):
            raise RuntimeError("Persisted integration action response integrity failed.")
        return response

    def _requeue_failed_retryable(
        self,
        operation: IntegrationOperationReference,
        row: Any,
    ) -> UUID:
        if operation.raw_state != "failed_retryable":
            raise IntegrationOperationConflict()
        if operation.operation_kind is IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION:
            return self._requeue_inbound(operation, row)
        if operation.operation_kind is IntegrationOperationKind.PUBLISH_ITEM:
            return self._requeue_item(operation, row)
        if operation.operation_kind is IntegrationOperationKind.PUBLISH_MBOM:
            return self._requeue_mbom(operation, row)
        return self._requeue_tool_asset(operation, row)

    def _requeue_inbound(self, operation: IntegrationOperationReference, row: Any) -> UUID:
        if not _value(row, "last_error_code") or _value(row, "project_result_hash"):
            raise IntegrationOperationConflict()
        receipt_id = str(_value(row, "name"))
        with inbound_project_manual_replay_write(
            actor_user_id=self.actor,
            receipt_id=receipt_id,
        ) as capability:
            row.state = "pending"
            row.disposition = "pending"
            row.claim_token = None
            row.claimed_at = None
            row.lease_expires_at = None
            row.last_error_code = None
            row.last_error_at = None
            row.project_result_hash = None
            save_inbound_project_replay_document(row, capability=capability)
        return UUID(receipt_id)

    def _requeue_item(self, operation: IntegrationOperationReference, row: Any) -> UUID:
        outbox = self._outbox(operation.operation_kind, row, lock=True)
        if outbox is None or str(_value(outbox, "state")) != "failed_retryable":
            raise IntegrationOperationConflict()
        attempt = self._last_attempt(operation.operation_kind, outbox, lock=True)
        result = self._result(operation.operation_kind, _value(row, "result_global_id"), lock=True)
        if not _safe_retryable_boundary(outbox, attempt, result):
            raise IntegrationOperationConflict()
        actor = str(_value(row, "service_actor_user_id"))
        guard = self._stream_guard(
            "NPI Item Publish Stream Guard",
            row,
            lock=True,
            active_retryable=True,
        )
        with item_service_actor_scope(actor), item_manual_replay_write(actor) as capability:
            _activate_guard(guard, row, "queued")
            save_item_support_document(guard, capability=capability)
            _reset_outbox(outbox, result_field="result_global_id")
            save_item_support_document(outbox, capability=capability)
            row.state = "queued"
            row.result_global_id = None
            row.optimistic_version = int(_value(row, "optimistic_version")) + 1
            row.updated_at = _database_datetime(datetime.now(UTC))
            save_item_support_document(row, capability=capability)
        return UUID(str(_value(outbox, "event_id")))

    def _requeue_mbom(self, operation: IntegrationOperationReference, row: Any) -> UUID:
        outbox = self._outbox(operation.operation_kind, row, lock=True)
        if outbox is None or str(_value(outbox, "state")) != "failed_retryable":
            raise IntegrationOperationConflict()
        attempt = self._last_attempt(operation.operation_kind, outbox, lock=True)
        result = self._result(operation.operation_kind, _value(row, "result_global_id"), lock=True)
        if not _safe_retryable_boundary(outbox, attempt, result):
            raise IntegrationOperationConflict()
        nodes = self._mbom_nodes(operation.operation_global_id)
        if not nodes or any(str(_value(node, "state")) != "failed_retryable" for node in nodes):
            raise IntegrationOperationConflict()
        actor = str(_value(row, "service_actor_user_id"))
        guard = self._stream_guard("NPI MBOM Publish Stream Guard", row, lock=True)
        with mbom_service_actor_scope(actor), mbom_manual_replay_write(actor) as capability:
            _activate_guard(guard, row, "queued")
            save_mbom_support_document(guard, capability=capability)
            for node in nodes:
                node.state = "queued"
                node.result_global_id = None
                node.optimistic_version = int(_value(node, "optimistic_version")) + 1
                node.updated_at = _database_datetime(datetime.now(UTC))
                save_mbom_support_document(node, capability=capability)
            _reset_outbox(outbox, result_field="mbom_result_global_id")
            save_mbom_support_document(outbox, capability=capability)
            row.state = "queued"
            row.result_global_id = None
            row.optimistic_version = int(_value(row, "optimistic_version")) + 1
            row.updated_at = _database_datetime(datetime.now(UTC))
            save_mbom_support_document(row, capability=capability)
        return UUID(str(_value(outbox, "event_id")))

    def _requeue_tool_asset(
        self,
        operation: IntegrationOperationReference,
        row: Any,
    ) -> UUID:
        outbox = self._outbox(operation.operation_kind, row, lock=True)
        if outbox is None or str(_value(outbox, "state")) != "failed_retryable":
            raise IntegrationOperationConflict()
        attempt = self._last_attempt(operation.operation_kind, outbox, lock=True)
        result = self._result(operation.operation_kind, _value(row, "result_global_id"), lock=True)
        if not _safe_retryable_boundary(outbox, attempt, result):
            raise IntegrationOperationConflict()
        actor = str(_value(outbox, "service_actor_user_id"))
        guard = self._stream_guard("NPI Tool Asset Stream Guard", row, lock=True)
        with tool_asset_service_actor_scope(actor), tool_asset_manual_replay_write(
            actor,
            operation_kind=operation.operation_kind.value,
        ) as capability:
            _activate_guard(guard, row, "queued")
            save_tool_asset_support_document(guard, capability=capability)
            _reset_outbox(outbox, result_field="tool_asset_result_global_id")
            save_tool_asset_support_document(outbox, capability=capability)
            row.execution_state = "queued"
            row.result_global_id = None
            row.optimistic_version = int(_value(row, "optimistic_version")) + 1
            row.updated_at = _database_datetime(datetime.now(UTC))
            save_tool_asset_support_document(row, capability=capability)
        return UUID(str(_value(outbox, "event_id")))

    def _outbox(
        self,
        kind: IntegrationOperationKind,
        row: Any,
        *,
        lock: bool,
    ) -> Any | None:
        field = _SPECS[kind].outbox_link_field
        name = _value(row, field or "")
        if not name:
            return None
        try:
            outbox = frappe.get_doc("NPI Outbox Message", str(name), for_update=lock)
        except frappe.DoesNotExistError:
            return None
        request_field = {
            IntegrationOperationKind.PUBLISH_ITEM: "request_global_id",
            IntegrationOperationKind.PUBLISH_MBOM: "mbom_request_global_id",
            IntegrationOperationKind.CREATE_TOOL_ASSET: "tool_asset_request_global_id",
            IntegrationOperationKind.UPDATE_TOOL_ASSET: "tool_asset_request_global_id",
        }.get(kind)
        if request_field is None or str(_value(outbox, request_field)) != str(_value(row, "name")):
            return None
        return outbox

    def _last_attempt(
        self,
        kind: IntegrationOperationKind,
        outbox: Any,
        *,
        lock: bool,
    ) -> Any | None:
        doctype, field = {
            IntegrationOperationKind.PUBLISH_ITEM: ("NPI Item Publish Attempt", "last_attempt_global_id"),
            IntegrationOperationKind.PUBLISH_MBOM: ("NPI MBOM Publish Attempt", "mbom_last_attempt_global_id"),
            IntegrationOperationKind.CREATE_TOOL_ASSET: ("NPI Tool Asset Attempt", "tool_asset_last_attempt_global_id"),
            IntegrationOperationKind.UPDATE_TOOL_ASSET: ("NPI Tool Asset Attempt", "tool_asset_last_attempt_global_id"),
        }[kind]
        name = _value(outbox, field)
        if not name:
            return None
        try:
            return frappe.get_doc(doctype, str(name), for_update=lock)
        except frappe.DoesNotExistError:
            return None

    def _result(
        self,
        kind: IntegrationOperationKind,
        name: Any,
        *,
        lock: bool,
    ) -> Any | None:
        if not name:
            return None
        doctype = {
            IntegrationOperationKind.PUBLISH_ITEM: "NPI Item Publish Result",
            IntegrationOperationKind.PUBLISH_MBOM: "NPI MBOM Publish Result",
            IntegrationOperationKind.CREATE_TOOL_ASSET: "NPI Tool Asset Result",
            IntegrationOperationKind.UPDATE_TOOL_ASSET: "NPI Tool Asset Result",
        }.get(kind)
        if doctype is None:
            return None
        try:
            return frappe.get_doc(doctype, str(name), for_update=lock)
        except frappe.DoesNotExistError:
            return None

    def _stream_guard(
        self,
        doctype: str,
        row: Any,
        *,
        lock: bool,
        active_retryable: bool = False,
    ) -> Any:
        name = frappe.db.get_value(
            doctype,
            {"source_stream_key_hash": str(_value(row, "source_stream_key_hash"))},
            "name",
        )
        if not name:
            raise IntegrationOperationConflict()
        try:
            guard = frappe.get_doc(doctype, str(name), for_update=lock)
        except frappe.DoesNotExistError as error:
            raise IntegrationOperationConflict() from error
        request_id = str(_value(row, "name"))
        target_key = str(_value(row, "target_idempotency_key_hash"))
        active_binding = bool(
            str(_value(guard, "active_request_global_id")) == request_id
            and str(_value(guard, "active_target_idempotency_key_hash"))
            == target_key
            and str(_value(guard, "active_state")) == "failed_retryable"
        )
        retained_binding = bool(
            not _value(guard, "active_request_global_id")
            and not _value(guard, "active_target_idempotency_key_hash")
            and not _value(guard, "active_state")
            and str(_value(guard, "last_request_global_id")) == request_id
            and str(_value(guard, "last_target_idempotency_key_hash"))
            == target_key
            and str(_value(guard, "last_state")) == "failed_retryable"
        )
        expected_binding = active_binding if active_retryable else retained_binding
        if not expected_binding:
            raise IntegrationOperationConflict()
        return guard

    def _mbom_nodes(self, request_id: UUID) -> list[Any]:
        names = frappe.get_all(
            "NPI MBOM Publish Node",
            filters={"request_global_id": str(request_id), "source_role": "assembly"},
            pluck="name",
            order_by="stable_line_key asc, name asc",
            limit_page_length=_MAX_HISTORY + 1,
        )
        if len(names) > _MAX_HISTORY:
            raise RuntimeError("Persisted MBOM node collection exceeds its safe bound.")
        return [
            frappe.get_doc("NPI MBOM Publish Node", str(name), for_update=True)
            for name in names
        ]

    def _insert_action_receipt(self, receipt: IntegrationActionReceipt) -> None:
        payload = receipt.payload()
        operation = receipt.operation
        values = {
            "doctype": "NPI Integration Action Receipt",
            "global_id": str(receipt.global_id),
            "schema_version": INTEGRATION_OPERATIONS_SCHEMA_VERSION,
            "tenant_id": operation.tenant_id,
            "project_global_id": str(operation.project_global_id),
            "operation_kind": operation.operation_kind.value,
            "operation_global_id": str(operation.operation_global_id),
            "source_global_id": str(operation.source_global_id),
            "operation_version": operation.operation_version,
            "raw_state": operation.raw_state,
            "shared_state": operation.shared_state.value,
            "source_snapshot_hash": operation.source_snapshot_hash,
            "target_idempotency_key_hash": operation.target_idempotency_key_hash,
            "action_kind": receipt.action_kind.value,
            "action_idempotency_key_hash": receipt.action_idempotency_key_hash,
            "expected_raw_state": receipt.expected_raw_state,
            "expected_version": receipt.expected_version,
            "request_hash": receipt.request_hash,
            "outcome_state": receipt.outcome_state.value,
            "outcome_reference_global_id": (
                str(receipt.outcome_reference_global_id)
                if receipt.outcome_reference_global_id
                else None
            ),
            "response_snapshot": dict(receipt.response_snapshot),
            "response_hash": receipt.response_hash,
            "receipt_snapshot": payload,
            "receipt_hash": receipt.receipt_hash,
            "actor_user_id": receipt.actor_user_id,
            "trace_id": receipt.trace_id,
            "created_at": _database_datetime(receipt.created_at),
        }
        with integration_operations_write_capability(
            service_actor_user_id=self.actor,
            scope=f"{receipt.action_kind.value}:{receipt.operation.operation_global_id}",
            allowed=_ACTION_RECEIPT_INSERT,
        ) as capability:
            if not _ACTION_RECEIPT_INSERT.issubset(INTEGRATION_OPERATIONS_SUPPORT_WRITES):
                raise RuntimeError("Integration action receipt support scope is unavailable.")
            insert_integration_operations_support_document(
                frappe.get_doc(values),
                capability=capability,
            )

    def _append_action_audit(self, receipt: IntegrationActionReceipt) -> None:
        event = create_audit_event(
            actor=receipt.actor_user_id,
            trace_id=receipt.trace_id,
            operation=f"integration_operations.{receipt.action_kind.value}",
            global_id=receipt.operation.operation_global_id,
            object_version=receipt.operation.operation_version,
            result=receipt.outcome_state.value,
            input_summary={
                "actionGlobalId": str(receipt.global_id),
                "operationKind": receipt.operation.operation_kind.value,
                "projectGlobalId": str(receipt.operation.project_global_id),
            },
        )
        with integration_operations_write_capability(
            service_actor_user_id=self.actor,
            scope=f"audit:{receipt.global_id}",
            allowed=_ACTION_RECEIPT_INSERT,
        ):
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

    def _enqueue_replay(
        self,
        kind: IntegrationOperationKind,
        reference: UUID | None,
        action_id: UUID,
    ) -> None:
        if reference is None:
            raise RuntimeError("Integration replay has no owning work reference.")
        job_path, argument = {
            IntegrationOperationKind.RECEIVE_PROJECT_SUBMISSION: (
                "npi_integration.inbound_project.worker.process_inbox_message",
                "receipt_id",
            ),
            IntegrationOperationKind.PUBLISH_ITEM: (
                "npi_integration.item_publish.worker.process_outbox_message",
                "outbox_event_id",
            ),
            IntegrationOperationKind.PUBLISH_MBOM: (
                "npi_integration.mbom_publish.worker.process_outbox_message",
                "outbox_event_id",
            ),
            IntegrationOperationKind.CREATE_TOOL_ASSET: (
                "npi_integration.tool_asset_request.worker.process_outbox_message",
                "outbox_event_id",
            ),
            IntegrationOperationKind.UPDATE_TOOL_ASSET: (
                "npi_integration.tool_asset_request.worker.process_outbox_message",
                "outbox_event_id",
            ),
        }[kind]
        frappe.enqueue(
            job_path,
            queue="short",
            enqueue_after_commit=True,
            deduplicate=True,
            job_id=f"integration-replay-{action_id}",
            **{argument: str(reference)},
        )


def _safe_retryable_boundary(outbox: Any, attempt: Any, result: Any) -> bool:
    return bool(
        outbox is not None
        and attempt is not None
        and result is not None
        and not bool(_value(outbox, "adapter_boundary_crossed"))
        and not bool(_value(attempt, "adapter_boundary_crossed"))
        and not bool(_value(attempt, "reconciliation_required"))
        and str(_value(result, "state")) == "failed_retryable"
        and str(_value(result, "authority")) == "none"
        and not bool(_value(result, "response_authenticated"))
    )


def _activate_guard(guard: Any, row: Any, state: str) -> None:
    guard.active_request_global_id = str(_value(row, "name"))
    guard.active_target_idempotency_key_hash = str(
        _value(row, "target_idempotency_key_hash")
    )
    guard.active_state = state
    guard.optimistic_version = int(_value(guard, "optimistic_version") or 0) + 1
    guard.updated_at = _database_datetime(datetime.now(UTC))


def _reset_outbox(outbox: Any, *, result_field: str) -> None:
    outbox.state = "pending"
    outbox.disposition = "pending"
    outbox.claim_token = None
    outbox.claimed_at = None
    outbox.lease_expires_at = None
    outbox.adapter_boundary_crossed = 0
    outbox.last_error_code = None
    outbox.last_error_at = None
    setattr(outbox, result_field, None)


def _encode_cursor(project_id: UUID, updated_at: str, operation_id: str) -> str:
    payload = {
        "v": _CURSOR_VERSION,
        "projectGlobalId": str(project_id),
        "updatedAt": updated_at,
        "operationGlobalId": operation_id,
    }
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, project_id: UUID) -> tuple[str, str]:
    if not isinstance(cursor, str) or not cursor or len(cursor) > 512:
        raise ValueError("Integration operation cursor is invalid.")
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Integration operation cursor is invalid.") from error
    if (
        not isinstance(payload, dict)
        or set(payload) != {"v", "projectGlobalId", "updatedAt", "operationGlobalId"}
        or payload["v"] != _CURSOR_VERSION
        or payload["projectGlobalId"] != str(project_id)
    ):
        raise ValueError("Integration operation cursor is invalid.")
    _uuid(payload["operationGlobalId"])
    _datetime(payload["updatedAt"])
    return str(payload["updatedAt"]), str(payload["operationGlobalId"])


def _row_datetime(row: Any, spec: _OperationSpec) -> datetime:
    value = _value(row, spec.updated_field) or _value(row, "created_at") or _value(row, "received_at")
    return _datetime(value)


def _datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RuntimeError("Persisted integration operation time is invalid.") from error
    if not isinstance(value, datetime):
        raise RuntimeError("Persisted integration operation time is invalid.")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _datetime(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _optional_utc_text(value: Any) -> str | None:
    return _utc_text(_datetime(value)) if value not in (None, "") else None


def _uuid(value: Any) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("Persisted integration operation identity is invalid.") from error


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("Persisted integration operation snapshot is invalid.")
    return dict(value)


def _value(row: Any, fieldname: str) -> Any:
    return row.get(fieldname) if isinstance(row, dict) else getattr(row, fieldname, None)
