from __future__ import annotations

import re
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document

from npi_core.project_controls.frappe_validation import (
    canonical_datetime,
    canonicalize_json,
    deny_project_control_history_delete,
    normalize_uuid_fields,
    require_actor,
    require_project_control_write,
    require_request_id,
    require_snapshot_hash,
    require_trace_id,
)


_EVENT_TYPES = {
    "comment_added",
    "followed",
    "unfollowed",
    "health_assessed",
    "lifecycle_transition",
    "learning_created",
}
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_HEALTH_DIMENSIONS = {"progress", "cost", "quality", "risk"}
_HEALTH_RULE_MODES = {
    "manual",
    "higher_is_better",
    "lower_is_better",
    "unavailable",
}
_HEALTH_STATUSES = {"unassessed", "unavailable", "green", "yellow", "red"}
_LIFECYCLE_STATES = {
    "draft",
    "proposed",
    "active",
    "on_hold",
    "completed",
    "cancelled",
}
_PREREQUISITES = {"open_blockers", "controlled_files", "handover", "cost"}


class NPIProjectActivityEvent(Document):
    def before_insert(self) -> None:
        require_project_control_write()

    def before_save(self) -> None:
        require_project_control_write()
        if self.get_doc_before_save() is not None:
            frappe.throw(
                _("A Project Activity Event is immutable."),
                frappe.PermissionError,
            )

    def on_trash(self) -> None:
        deny_project_control_history_delete()

    def validate(self) -> None:
        normalize_uuid_fields(self, ("global_id", "project_global_id"))
        if not self.tenant_id:
            frappe.throw(_("Tenant ID is required."), frappe.ValidationError)
        if (
            not isinstance(self.event_key, str)
            or not self.event_key
            or len(self.event_key) > 280
        ):
            frappe.throw(
                _("Activity Event Key must be valid."),
                frappe.ValidationError,
            )
        if self.event_type not in _EVENT_TYPES:
            frappe.throw(
                _("Select a supported Project activity event type."),
                frappe.ValidationError,
            )
        self.actor_user_id = require_actor(
            self.actor_user_id,
            _("Actor User ID"),
        )
        self.request_id = require_request_id(self.request_id)
        self.trace_id = require_trace_id(self.trace_id)
        payload, self.payload = canonicalize_json(
            self.payload,
            expected_type=dict,
            label=_("Activity Payload"),
        )
        self.payload_hash = require_snapshot_hash(
            payload,
            self.payload_hash,
            _("Payload Hash"),
        )
        required = {
            "schemaVersion",
            "globalId",
            "eventKey",
            "tenantId",
            "projectGlobalId",
            "eventType",
            "actorUserId",
            "occurredAt",
            "requestId",
            "traceId",
            "detail",
        }
        if set(payload) != required or not isinstance(payload["detail"], dict):
            frappe.throw(
                _("Activity Payload has an invalid structure."),
                frappe.ValidationError,
            )
        if (
            payload["schemaVersion"] != 1
            or payload["globalId"] != self.global_id
            or payload["eventKey"] != self.event_key
            or payload["tenantId"] != self.tenant_id
            or payload["projectGlobalId"] != self.project_global_id
            or payload["eventType"] != self.event_type
            or require_actor(
                payload["actorUserId"],
                _("Actor User ID"),
            )
            != self.actor_user_id
            or canonical_datetime(
                payload["occurredAt"],
                _("Occurred At"),
            )
            != canonical_datetime(self.occurred_at, _("Occurred At"))
            or payload["requestId"] != self.request_id
            or payload["traceId"] != self.trace_id
        ):
            frappe.throw(
                _("Activity Payload does not match the event record."),
                frappe.ValidationError,
            )
        _validate_detail(self.event_type, payload["detail"])


def _validate_detail(event_type: str, detail: dict[str, object]) -> None:
    if event_type == "comment_added":
        if set(detail) != {"body", "mentions", "attachments", "objectLinks"}:
            _invalid_detail()
        body = detail["body"]
        if not isinstance(body, str) or not body.strip() or len(body.strip()) > 4000:
            _invalid_detail()
        _validate_mentions(detail["mentions"])
        _validate_attachments(detail["attachments"])
        _validate_object_links(detail["objectLinks"])
        return
    if event_type in {"followed", "unfollowed"}:
        expected = event_type == "followed"
        if set(detail) != {"active"} or detail["active"] is not expected:
            _invalid_detail()
        return
    if event_type == "health_assessed":
        if set(detail) != {
            "assessment",
            "policyRef",
            "bindingGlobalId",
            "projectVersion",
        }:
            _invalid_detail()
        if (
            not isinstance(detail["assessment"], dict)
            or type(detail["projectVersion"]) is not int
            or detail["projectVersion"] < 1
        ):
            _invalid_detail()
        _validate_uuid(detail["bindingGlobalId"])
        _validate_policy_ref(detail["policyRef"])
        _validate_health_evaluation(detail["assessment"], detail["policyRef"])
        return
    if event_type == "lifecycle_transition":
        if set(detail) != {
            "action",
            "fromState",
            "toState",
            "reason",
            "approvedBy",
            "policyRef",
            "bindingGlobalId",
            "prerequisites",
            "projectVersion",
        }:
            _invalid_detail()
        if (
            detail["action"] not in {"pause", "cancel", "resume", "complete"}
            or detail["fromState"] not in _LIFECYCLE_STATES
            or detail["toState"] not in _LIFECYCLE_STATES
            or not isinstance(detail["reason"], str)
            or not detail["reason"].strip()
            or len(detail["reason"].strip()) > 2000
            or not isinstance(detail["approvedBy"], dict)
            or not isinstance(detail["prerequisites"], list)
            or type(detail["projectVersion"]) is not int
            or detail["projectVersion"] < 1
        ):
            _invalid_detail()
        _validate_uuid(detail["bindingGlobalId"])
        _validate_authority(detail["approvedBy"])
        _validate_policy_ref(detail["policyRef"])
        _validate_prerequisites(detail["prerequisites"])
        return
    if event_type == "learning_created":
        if set(detail) != {"learningGlobalId", "kind", "title"}:
            _invalid_detail()
        _validate_uuid(detail["learningGlobalId"])
        if detail["kind"] not in {
            "retrospective",
            "lesson",
            "template_improvement",
        }:
            _invalid_detail()
        if (
            not isinstance(detail["title"], str)
            or not detail["title"].strip()
            or len(detail["title"].strip()) > 280
        ):
            _invalid_detail()
        return
    _invalid_detail()


def _validate_mentions(value: object) -> None:
    if not isinstance(value, list) or len(value) > 50:
        _invalid_detail()
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "memberGlobalId",
            "userId",
            "displayName",
        }:
            _invalid_detail()
        member_id = _validate_uuid(item["memberGlobalId"])
        if (
            member_id in seen
            or not _bounded_text(item["userId"], 254)
            or str(item["userId"]) != str(item["userId"]).casefold()
            or not _bounded_text(item["displayName"], 140)
        ):
            _invalid_detail()
        seen.add(member_id)


def _validate_attachments(value: object) -> None:
    if not isinstance(value, list) or len(value) > 20:
        _invalid_detail()
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "globalId",
            "version",
            "fileName",
            "mimeType",
            "sizeBytes",
            "sha256",
            "scanState",
        }:
            _invalid_detail()
        global_id = _validate_uuid(item["globalId"])
        if (
            global_id in seen
            or type(item["version"]) is not int
            or item["version"] < 1
            or type(item["sizeBytes"]) is not int
            or item["sizeBytes"] < 0
            or not _bounded_text(item["fileName"], 255)
            or not _bounded_text(item["mimeType"], 255)
            or not isinstance(item["sha256"], str)
            or _HASH_PATTERN.fullmatch(item["sha256"]) is None
            or item["scanState"] != "clean"
        ):
            _invalid_detail()
        seen.add(global_id)


def _validate_object_links(value: object) -> None:
    if not isinstance(value, list) or len(value) > 20:
        _invalid_detail()
    seen: set[tuple[object, str]] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "type",
            "globalId",
            "version",
            "code",
            "title",
        }:
            _invalid_detail()
        global_id = _validate_uuid(item["globalId"])
        identity = (item["type"], global_id)
        if (
            item["type"]
            not in {"project", "gate", "domain_work_item", "file_revision", "learning"}
            or identity in seen
            or type(item["version"]) is not int
            or item["version"] < 1
            or not _bounded_text(item["code"], 64)
            or not _bounded_text(item["title"], 280)
        ):
            _invalid_detail()
        seen.add(identity)


def _validate_uuid(value: object) -> str:
    try:
        canonical = str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        _invalid_detail()
    if not isinstance(value, str) or value != canonical:
        _invalid_detail()
    return canonical


def _validate_policy_ref(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"globalId", "version", "snapshotHash"}
        or type(value["version"]) is not int
        or value["version"] < 1
        or not isinstance(value["snapshotHash"], str)
        or _HASH_PATTERN.fullmatch(value["snapshotHash"]) is None
    ):
        _invalid_detail()
    _validate_uuid(value["globalId"])


def _validate_authority(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"slot", "memberGlobalId", "userId", "displayName"}
        or not _bounded_text(value["slot"], 64)
        or not _bounded_text(value["userId"], 254)
        or str(value["userId"]) != str(value["userId"]).casefold()
        or not _bounded_text(value["displayName"], 140)
    ):
        _invalid_detail()
    _validate_uuid(value["memberGlobalId"])


def _validate_health_evaluation(
    value: object,
    policy_ref: object,
) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "policyRef",
            "dimensionResults",
            "overallStatus",
            "reason",
            "recoveryPlan",
        }
        or value["policyRef"] != policy_ref
        or value["overallStatus"] not in _HEALTH_STATUSES
        or not isinstance(value["dimensionResults"], list)
        or len(value["dimensionResults"]) != 4
    ):
        _invalid_detail()
    dimensions: set[str] = set()
    red = value["overallStatus"] == "red"
    for result in value["dimensionResults"]:
        if (
            not isinstance(result, dict)
            or set(result)
            != {"dimension", "ruleMode", "status", "numericValue"}
            or result["dimension"] not in _HEALTH_DIMENSIONS
            or result["dimension"] in dimensions
            or result["ruleMode"] not in _HEALTH_RULE_MODES
            or result["status"] not in _HEALTH_STATUSES
            or (
                result["numericValue"] is not None
                and not isinstance(result["numericValue"], str)
            )
        ):
            _invalid_detail()
        dimensions.add(str(result["dimension"]))
        red = red or result["status"] == "red"
    if dimensions != _HEALTH_DIMENSIONS:
        _invalid_detail()
    if red and (
        not _bounded_text(value["reason"], 2000)
        or not _bounded_text(value["recoveryPlan"], 4000)
    ):
        _invalid_detail()
    if value["reason"] is not None and not _bounded_text(value["reason"], 2000):
        _invalid_detail()
    if value["recoveryPlan"] is not None and not _bounded_text(
        value["recoveryPlan"],
        4000,
    ):
        _invalid_detail()


def _validate_prerequisites(value: list[object]) -> None:
    if len(value) > 4:
        _invalid_detail()
    keys: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"key", "status"}
            or item["key"] not in _PREREQUISITES
            or item["key"] in keys
            or item["status"] not in {"satisfied", "blocked", "unavailable"}
        ):
            _invalid_detail()
        keys.add(str(item["key"]))


def _bounded_text(value: object, maximum: int) -> bool:
    return bool(
        isinstance(value, str)
        and value.strip()
        and len(value.strip()) <= maximum
    )


def _invalid_detail() -> None:
    frappe.throw(
        _("Project activity detail has an invalid structure."),
        frappe.ValidationError,
    )
