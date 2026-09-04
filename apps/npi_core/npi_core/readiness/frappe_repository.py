from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID, uuid4, uuid5

import frappe
from frappe import _

from npi_core.foundation.audit import create_audit_event
from npi_core.foundation.errors import NpiProblem, PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.project.domain import ProjectType
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.readiness.domain import (
    EXTERNAL_SOURCE_KINDS,
    ReadinessApplicabilitySelector,
    ReadinessBlockingLevel,
    ReadinessCategoryDefinition,
    ReadinessExactReference,
    ReadinessGateReference,
    ReadinessInstanceRevision,
    ReadinessItemDefinition,
    ReadinessItemState,
    ReadinessMemberReference,
    ReadinessProjectSnapshot,
    ReadinessPublicationState,
    ReadinessSourceKind,
    ReadinessSourceState,
    ReadinessTemplateVersion,
    ReadinessVersionConflict,
    initialize_readiness_instance,
    instance_from_snapshot,
    revise_readiness_item,
    template_from_snapshot,
    validate_readiness_successor,
)
from npi_core.readiness.frappe_validation import readiness_command_write
from npi_core.readiness.request_validation import ReadinessSourceRequest
from npi_core.readiness.source_resolver import (
    EXTERNAL_UNAVAILABLE_REASON_CODES,
    ExactSourceObservation,
    ExactSourceQuery,
    SourceResolutionContext,
    resolve_sources,
)
from npi_core.tooling.engineering_controls_domain import (
    capacity_scenario_from_snapshot,
)
from npi_core.tooling.revision_domain import tooling_revision_from_snapshot
from npi_core.trial.domain import trial_round_from_snapshot
from npi_core.trial.execution_domain import (
    actual_revision_from_snapshot,
    input_lock_from_snapshot,
    sample_batch_from_snapshot,
)
from npi_core.trial.quality_domain import (
    cavity_result_from_snapshot,
    trial_defect_from_snapshot,
    verification_from_snapshot,
)
from npi_core.trial.review_domain import (
    TrialReviewReferenceRevision,
    comparison_from_snapshot,
    conclusion_from_snapshot,
    review_reference_from_snapshot,
)


_MAX_TEMPLATES = 500
_MAX_REVISIONS = 1_000
_MAX_MEMBERS = 256
_MAX_GATES = 100
_MAX_SOURCE_OPTIONS = 1_000
_MAX_RELEASE_CONFIRMATIONS = 128
_MAX_RELEASE_FILES = 64
_HASH_LENGTH = 64
_DOCUMENT_REVISION_SNAPSHOT_KEYS = {
    "schemaVersion",
    "globalId",
    "documentGlobalId",
    "major",
    "minor",
    "reason",
    "effectiveDate",
    "predecessorRevisionId",
    "state",
    "documentPolicyRef",
    "lockRef",
    "file",
    "createdByUserId",
    "createdAt",
    "requestId",
    "traceId",
}


class ReadinessIdempotencyConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "READINESS_IDEMPOTENCY_CONFLICT",
            _("The idempotency key was already used for a different request."),
        )


@dataclass(frozen=True, slots=True)
class ReadinessCommandOutcome:
    response: dict[str, Any]
    replayed: bool = False


class FrappeReadinessRepository:
    """Project-first persistence and exact-source adapter for P7-05."""

    def __init__(
        self,
        *,
        principal: Principal,
        request_id: str,
        trace_id: str,
    ) -> None:
        self.principal = principal
        self.actor = principal.user_id
        self.request_id = str(UUID(request_id))
        self.trace_id = trace_id

    def template_catalog(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        project_type = ProjectType(str(project.project_type))
        customer_keys = _customer_reference_keys(project)
        versions: list[dict[str, Any]] = []
        names = frappe.get_all(
            "NPI Readiness Template Version",
            filters={"publication_state": ReadinessPublicationState.PUBLISHED.value},
            pluck="name",
            order_by="template_code asc, template_version asc, global_id asc",
            limit_page_length=_MAX_TEMPLATES + 1,
        )
        if len(names) > _MAX_TEMPLATES:
            raise RuntimeError("Persisted readiness template collection exceeds its safe bound.")
        for name in names:
            document = frappe.get_doc("NPI Readiness Template Version", str(name))
            value = _template_from_document(document)
            root = _optional_doc("NPI Readiness Template", str(value.template_global_id))
            if root is None or int(_value(root, "enabled") or 0) != 1:
                continue
            if _template_matches_project(value, project_type, customer_keys):
                versions.append(_template_response(value))
        return {"projectGlobalId": str(project_id), "templates": versions}

    def create_template(
        self,
        *,
        idempotency_key_hash: str,
        template_code: str,
        title: str,
        applicability: ReadinessApplicabilitySelector,
        categories: tuple[ReadinessCategoryDefinition, ...],
        items: tuple[ReadinessItemDefinition, ...],
    ) -> ReadinessCommandOutcome:
        tenant_id = self._require_template_administrator()
        payload = {
            "templateCode": template_code,
            "title": title,
            "applicability": applicability.snapshot_payload(),
            "categories": [value.snapshot_payload() for value in categories],
            "items": [value.snapshot_payload() for value in items],
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation="readiness_template.create",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ReadinessCommandOutcome(replay, replayed=True)
        if frappe.db.exists("NPI Readiness Template", {"template_code": template_code}):
            raise ReadinessVersionConflict()

        now = datetime.now(UTC)
        template_id = uuid4()
        value = ReadinessTemplateVersion.create_draft(
            template_global_id=template_id,
            template_code=template_code,
            template_version=1,
            title=title,
            applicability=applicability,
            categories=categories,
            items=items,
            changed_by_user_id=self.actor,
            changed_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = _template_response(value)
        with readiness_command_write():
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=None,
                operation="readiness_template.create",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return ReadinessCommandOutcome(receipt, replayed=True)
            frappe.get_doc(
                {
                    "doctype": "NPI Readiness Template",
                    "global_id": str(template_id),
                    "template_code": value.template_code,
                    "title": value.title,
                    "enabled": 1,
                    "optimistic_version": value.optimistic_version,
                }
            ).insert()
            self._insert_template_version(value)
            self._append_audit(
                operation="readiness_template.create",
                global_id=value.global_id,
                object_version=value.optimistic_version,
                summary={
                    "templateGlobalId": str(template_id),
                    "templateVersion": value.template_version,
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_object_type="readiness_template",
                target_global_id=template_id,
                response=response,
                updated_at=now,
            )
        return ReadinessCommandOutcome(response)

    def edit_template(
        self,
        template_id: UUID,
        template_version: int,
        *,
        idempotency_key_hash: str,
        expected_optimistic_version: int,
        title: str,
        applicability: ReadinessApplicabilitySelector,
        categories: tuple[ReadinessCategoryDefinition, ...],
        items: tuple[ReadinessItemDefinition, ...],
    ) -> ReadinessCommandOutcome | None:
        return self._change_template(
            template_id,
            template_version,
            operation="readiness_template.edit",
            idempotency_key_hash=idempotency_key_hash,
            payload={
                "expectedOptimisticVersion": expected_optimistic_version,
                "title": title,
                "applicability": applicability.snapshot_payload(),
                "categories": [value.snapshot_payload() for value in categories],
                "items": [value.snapshot_payload() for value in items],
            },
            transform=lambda current, now: current.edit_draft(
                expected_version=expected_optimistic_version,
                title=title,
                applicability=applicability,
                categories=categories,
                items=items,
                changed_by_user_id=self.actor,
                changed_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            ),
        )

    def publish_template(
        self,
        template_id: UUID,
        template_version: int,
        *,
        idempotency_key_hash: str,
        expected_optimistic_version: int,
    ) -> ReadinessCommandOutcome | None:
        return self._change_template(
            template_id,
            template_version,
            operation="readiness_template.publish",
            idempotency_key_hash=idempotency_key_hash,
            payload={"expectedOptimisticVersion": expected_optimistic_version},
            transform=lambda current, now: current.publish(
                expected_version=expected_optimistic_version,
                changed_by_user_id=self.actor,
                changed_at=now,
                request_id=UUID(self.request_id),
                trace_id=self.trace_id,
            ),
        )

    def readiness_workspace(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            return None
        return self._workspace_for(project, _project_revision_chain(project))

    def initialize_readiness(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        template_revision_global_id: UUID,
        template_version: int,
        template_snapshot_hash: str,
        industry_key: str,
        assignments: Mapping[str, tuple[UUID, date]],
    ) -> ReadinessCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "templateRevisionGlobalId": template_revision_global_id,
            "templateVersion": template_version,
            "templateSnapshotHash": template_snapshot_hash,
            "industryKey": industry_key,
            "assignments": [
                {
                    "itemKey": key,
                    "ownerMemberGlobalId": member_id,
                    "dueDate": due_date,
                }
                for key, (member_id, due_date) in sorted(assignments.items())
            ],
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation="readiness_instance.initialize",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ReadinessCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        if _project_revision_chain(project):
            raise ReadinessVersionConflict()
        template_document = _optional_doc(
            "NPI Readiness Template Version", str(template_revision_global_id)
        )
        if template_document is None:
            return None
        template = _template_from_document(template_document)
        if (
            template.global_id != template_revision_global_id
            or template.template_version != template_version
            or template.snapshot_hash != template_snapshot_hash
            or template.publication_state is not ReadinessPublicationState.PUBLISHED
        ):
            return None
        root = _optional_doc("NPI Readiness Template", str(template.template_global_id))
        if root is None or int(_value(root, "enabled") or 0) != 1:
            return None

        project_snapshot = _project_snapshot(project, industry_key)
        gates = self._gate_references(project, template)
        resolved_assignments = {
            item_key: (self._member_reference(project, member_id), due_date)
            for item_key, (member_id, due_date) in assignments.items()
        }
        now = datetime.now(UTC)
        revision = initialize_readiness_instance(
            global_id=uuid4(),
            instance_global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project=project_snapshot,
            template=template,
            gates=gates,
            assignments=resolved_assignments,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        response = self._workspace_for(project, (revision,))
        with readiness_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation="readiness_instance.initialize",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return ReadinessCommandOutcome(receipt, replayed=True)
            self._insert_instance_revision(revision)
            self._append_audit(
                operation="readiness_instance.initialize",
                global_id=revision.global_id,
                object_version=revision.instance_version,
                summary={
                    "instanceGlobalId": str(revision.instance_global_id),
                    "projectId": str(project_id),
                    "templateRevisionGlobalId": str(template.global_id),
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_object_type="readiness_instance_revision",
                target_global_id=revision.global_id,
                response=response,
                updated_at=now,
            )
        return ReadinessCommandOutcome(response)

    def revise_readiness(
        self,
        project_id: UUID,
        instance_id: UUID,
        *,
        idempotency_key_hash: str,
        expected_instance_version: int,
        expected_revision_global_id: UUID,
        expected_revision_snapshot_hash: str,
        item_key: str,
        owner_member_global_id: UUID,
        due_date: date,
        state: ReadinessItemState,
        confirmation_value: str | None,
        source_requests: tuple[ReadinessSourceRequest, ...],
    ) -> ReadinessCommandOutcome | None:
        project = self._locked_authorized_project(project_id)
        if project is None:
            return None
        payload = {
            "projectId": project_id,
            "instanceId": instance_id,
            "expectedInstanceVersion": expected_instance_version,
            "expectedRevisionGlobalId": expected_revision_global_id,
            "expectedRevisionSnapshotHash": expected_revision_snapshot_hash,
            "itemKey": item_key,
            "ownerMemberGlobalId": owner_member_global_id,
            "dueDate": due_date,
            "state": state,
            "confirmationValue": confirmation_value,
            "sources": [
                {
                    "requirementKey": value.requirement_key,
                    "kind": value.kind,
                    "globalId": value.global_id,
                    "sourceVersion": value.source_version,
                    "snapshotHash": value.snapshot_hash,
                }
                for value in source_requests
            ],
        }
        payload_hash = _payload_hash(payload)
        replay = self._idempotency_replay(
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            operation="readiness_instance.revise",
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ReadinessCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        revisions = _project_revision_chain(project)
        if not revisions:
            return None
        current = revisions[-1]
        if current.instance_global_id != instance_id:
            return None
        if (
            current.instance_version != expected_instance_version
            or current.global_id != expected_revision_global_id
            or current.snapshot_hash != expected_revision_snapshot_hash
        ):
            raise ReadinessVersionConflict()
        owner = self._member_reference(project, owner_member_global_id)
        sources = resolve_sources(
            source_requests,
            context=SourceResolutionContext(str(project.tenant_id), project_id),
            repository=self,
        )
        now = datetime.now(UTC)
        successor = revise_readiness_item(
            current,
            global_id=uuid4(),
            expected_instance_version=expected_instance_version,
            item_key=item_key,
            owner=owner,
            due_date=due_date,
            state=state,
            confirmation_value=confirmation_value,
            sources=sources,
            created_by_user_id=self.actor,
            created_at=now,
            request_id=UUID(self.request_id),
            trace_id=self.trace_id,
        )
        validate_readiness_successor(current, successor)
        response = self._workspace_for(project, revisions + (successor,))
        with readiness_command_write():
            receipt = self._insert_receipt(
                tenant_id=str(project.tenant_id),
                project_id=project_id,
                operation="readiness_instance.revise",
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return ReadinessCommandOutcome(receipt, replayed=True)
            self._insert_instance_revision(successor)
            self._append_audit(
                operation="readiness_instance.revise",
                global_id=successor.global_id,
                object_version=successor.instance_version,
                summary={
                    "instanceGlobalId": str(instance_id),
                    "itemKey": item_key,
                    "projectId": str(project_id),
                    "sourceCount": len(sources),
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_object_type="readiness_instance_revision",
                target_global_id=successor.global_id,
                response=response,
                updated_at=now,
            )
        return ReadinessCommandOutcome(response)

    def get_exact_source(
        self,
        context: SourceResolutionContext,
        query: ExactSourceQuery,
    ) -> ExactSourceObservation | None:
        """Resolve only the supplied exact row; no current/latest substitution."""

        if query.kind is ReadinessSourceKind.PROJECT:
            if query.global_id != context.project_global_id:
                return None
            project = _optional_doc("NPI Engineering Project", str(query.global_id))
            if (
                project is None
                or str(_value(project, "global_id")) != str(context.project_global_id)
                or str(_value(project, "tenant_id")) != context.tenant_id
            ):
                return None
            revisions = _project_revision_chain(project)
            if not revisions:
                return None
            frozen = revisions[-1].project
            if (
                frozen.global_id != context.project_global_id
                or frozen.optimistic_version != query.source_version
                or frozen.snapshot_hash != query.snapshot_hash
            ):
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.DOMAIN_WORK_ITEM:
            document = _source_document("NPI Domain Work Item", context, query)
            if document is None:
                return None
            value = _domain_work_item_value(document)
            if value is None:
                return None
            snapshot = _domain_work_item_source_snapshot(value)
            if (
                value.version != query.source_version
                or _payload_hash(snapshot) != query.snapshot_hash
            ):
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.RELEASED_DOCUMENT:
            revision = _source_document("NPI Document Revision", context, query)
            if revision is None or not _released_document_source_is_current(
                context,
                query,
                revision,
            ):
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.RELEASE_BASELINE:
            project = _optional_doc(
                "NPI Engineering Project", str(context.project_global_id)
            )
            if (
                project is None
                or str(_value(project, "tenant_id")) != context.tenant_id
                or str(_value(project, "global_id"))
                != str(context.project_global_id)
            ):
                return None
            try:
                from npi_core.documents.baseline_domain import (
                    DocumentBaselineInputUnavailable,
                )
                from npi_core.documents.baseline_repository import (
                    load_document_baseline,
                )

                value = load_document_baseline(project, query.global_id, lock=False)
            except (
                DocumentBaselineInputUnavailable,
                RequestValidationFailed,
                TypeError,
                ValueError,
            ):
                return None
            if (
                value is None
                or value.version != query.source_version
                or value.snapshot_hash != query.snapshot_hash
            ):
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.FILE_REVISION:
            document = _source_document("NPI File Revision", context, query)
            if (
                document is None
                or int(_value(document, "revision") or 0)
                != query.source_version
                or str(_value(document, "sha256")) != query.snapshot_hash
            ):
                return None
            try:
                from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
                    file_revision_source_snapshot,
                    has_live_private_file_identity,
                )

                snapshot = file_revision_source_snapshot(document)
            except (AttributeError, TypeError, ValueError, frappe.ValidationError):
                return None
            if (
                str(snapshot.get("globalId")) != str(query.global_id)
                or snapshot.get("revision") != query.source_version
                or snapshot.get("sha256") != query.snapshot_hash
                or snapshot.get("isPrivate") is not True
                or snapshot.get("scanState") != "clean"
                or not has_live_private_file_identity(document)
            ):
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.TOOLING_CAPACITY_SCENARIO:
            document = _source_document(
                "NPI Tooling Capacity Scenario Revision", context, query
            )
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="scenario_snapshot",
                parser=capacity_scenario_from_snapshot,
                document_version_field="scenario_version",
                parsed_version_attribute="scenario_version",
            )
            if value is None:
                return None
            try:
                disposition = (
                    ReadinessSourceState.SATISFIED
                    if Decimal(value.gap) <= 0
                    else ReadinessSourceState.FAILED
                )
            except (InvalidOperation, ValueError):
                return None
            return _observation(context, query, disposition)

        execution_specs = {
            ReadinessSourceKind.TRIAL_INPUT_LOCK: (
                "NPI Trial Input Lock Revision",
                "lock_version",
                "lock_snapshot",
                input_lock_from_snapshot,
            ),
            ReadinessSourceKind.TRIAL_ACTUAL: (
                "NPI Trial Actual Revision",
                "actual_version",
                "actual_snapshot",
                actual_revision_from_snapshot,
            ),
            ReadinessSourceKind.TRIAL_SAMPLE: (
                "NPI Trial Sample Batch Revision",
                "sample_version",
                "sample_snapshot",
                sample_batch_from_snapshot,
            ),
        }
        if query.kind in execution_specs:
            doctype, version_field, snapshot_field, parser = execution_specs[query.kind]
            document = _source_document(doctype, context, query)
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field=snapshot_field,
                parser=parser,
                document_version_field=version_field,
                parsed_version_attribute=version_field,
            )
            return (
                _observation(context, query, ReadinessSourceState.SATISFIED)
                if value is not None
                else None
            )

        if query.kind is ReadinessSourceKind.TRIAL_CAVITY_RESULT:
            document = _source_document("NPI Trial Cavity Result Revision", context, query)
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="cavity_result_snapshot",
                parser=cavity_result_from_snapshot,
                document_version_field="result_version",
                parsed_version_attribute="result_version",
            )
            if value is None:
                return None
            states = {item.comparison_state.value for item in value.measurements}
            if "out_of_spec" in states:
                return _observation(context, query, ReadinessSourceState.FAILED)
            if not states or states - {"within_spec"}:
                return None
            return _observation(context, query, ReadinessSourceState.SATISFIED)

        if query.kind is ReadinessSourceKind.TRIAL_DEFECT:
            document = _source_document("NPI Trial Defect Revision", context, query)
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="trial_defect_snapshot",
                parser=trial_defect_from_snapshot,
                document_version_field="defect_version",
                parsed_version_attribute="defect_version",
            )
            if value is None:
                return None
            return _observation(
                context,
                query,
                ReadinessSourceState.SATISFIED
                if value.state.value == "closed"
                else ReadinessSourceState.FAILED,
            )

        if query.kind is ReadinessSourceKind.TRIAL_DEFECT_VERIFICATION:
            document = _source_document(
                "NPI Trial Defect Verification Revision", context, query
            )
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="verification_snapshot",
                parser=verification_from_snapshot,
                document_version_field="attempt_sequence",
                parsed_version_attribute="attempt_sequence",
            )
            if value is None:
                return None
            result = value.result.value
            if result not in {"pass", "fail"}:
                return None
            return _observation(
                context,
                query,
                ReadinessSourceState.SATISFIED
                if result == "pass"
                else ReadinessSourceState.FAILED,
            )

        if query.kind is ReadinessSourceKind.TRIAL_COMPARISON:
            document = _source_document(
                "NPI Trial Round Comparison Snapshot", context, query
            )
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="comparison_snapshot",
                parser=comparison_from_snapshot,
                document_version_field=None,
                parsed_version_attribute=None,
            )
            return (
                _observation(context, query, ReadinessSourceState.SATISFIED)
                if value is not None
                else None
            )

        if query.kind is ReadinessSourceKind.TRIAL_REVIEW_REFERENCE:
            document = _source_document(
                "NPI Trial Review Reference Revision", context, query
            )
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="reference_snapshot",
                parser=review_reference_from_snapshot,
                document_version_field="reference_version",
                parsed_version_attribute="reference_version",
            )
            return (
                _observation(context, query, ReadinessSourceState.SATISFIED)
                if value is not None
                and _trial_review_reference_sources_are_current(context, value)
                else None
            )

        if query.kind is ReadinessSourceKind.TRIAL_CONCLUSION:
            document = _source_document("NPI Trial Conclusion Revision", context, query)
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="conclusion_snapshot",
                parser=conclusion_from_snapshot,
                document_version_field="conclusion_version",
                parsed_version_attribute="conclusion_version",
            )
            if value is None:
                return None
            state = value.state.value
            code = value.conclusion_code.value
            if state == "approved" and code in {"pass", "conditional_pass"}:
                return _observation(
                    context, query, ReadinessSourceState.SATISFIED
                )
            if state in {"approved", "rejected"}:
                return _observation(context, query, ReadinessSourceState.FAILED)
            return None

        if query.kind is ReadinessSourceKind.CONTROLLED_QUALITY_RESULT:
            document = _source_document(
                "NPI Trial Review Reference Revision", context, query
            )
            if document is None:
                return None
            value = _parsed_snapshot_source(
                context,
                query,
                document,
                snapshot_field="reference_snapshot",
                parser=review_reference_from_snapshot,
                document_version_field="reference_version",
                parsed_version_attribute="reference_version",
            )
            if value is None:
                return None
            return (
                _observation(context, query, ReadinessSourceState.SATISFIED)
                if value.reference_kind.value == "controlled_quality_report"
                and _trial_review_reference_sources_are_current(context, value)
                else None
            )
        return None

    def authorize_exact_source(
        self,
        context: SourceResolutionContext,
        source: ExactSourceObservation,
    ) -> None:
        project = self._authorized_project(context.project_global_id)
        if (
            project is None
            or str(project.tenant_id) != context.tenant_id
            or source.tenant_id != context.tenant_id
            or source.project_global_id != context.project_global_id
        ):
            raise PermissionDenied()

    def _change_template(
        self,
        template_id: UUID,
        template_version: int,
        *,
        operation: str,
        idempotency_key_hash: str,
        payload: Mapping[str, Any],
        transform,
    ) -> ReadinessCommandOutcome | None:
        tenant_id = self._require_template_administrator()
        command_payload = {
            "templateId": template_id,
            "templateVersion": template_version,
            **payload,
        }
        payload_hash = _payload_hash(command_payload)
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ReadinessCommandOutcome(replay, replayed=True)
        try:
            root = frappe.get_doc("NPI Readiness Template", str(template_id), for_update=True)
            version_id = uuid5(
                template_id, f"npi-readiness-template-version:{template_version}"
            )
            document = frappe.get_doc(
                "NPI Readiness Template Version", str(version_id), for_update=True
            )
        except frappe.DoesNotExistError:
            return None
        replay = self._idempotency_replay(
            tenant_id=tenant_id,
            project_id=None,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return ReadinessCommandOutcome(replay, replayed=True)
        current = _template_from_document(document)
        if (
            current.template_global_id != template_id
            or current.template_version != template_version
            or str(_value(root, "template_code")) != current.template_code
        ):
            return None
        now = datetime.now(UTC)
        successor = transform(current, now)
        response = _template_response(successor)
        with readiness_command_write():
            receipt = self._insert_receipt(
                tenant_id=tenant_id,
                project_id=None,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                created_at=now,
            )
            if _is_replay_response(receipt):
                return ReadinessCommandOutcome(receipt, replayed=True)
            _apply_template_version(document, successor)
            document.save()
            root.title = successor.title
            root.optimistic_version = successor.optimistic_version
            root.save()
            self._append_audit(
                operation=operation,
                global_id=successor.global_id,
                object_version=successor.optimistic_version,
                summary={
                    "templateGlobalId": str(template_id),
                    "templateVersion": template_version,
                    "requestId": self.request_id,
                },
            )
            self._seal_receipt(
                receipt,
                target_object_type="readiness_template_version",
                target_global_id=successor.global_id,
                response=response,
                updated_at=now,
            )
        return ReadinessCommandOutcome(response)

    def _authorized_project(self, project_id: UUID):
        project = _optional_doc("NPI Engineering Project", str(project_id))
        return project if project is not None and self._can_view_project(project, project_id) else None

    def _locked_authorized_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project", str(project_id), for_update=True
            )
        except frappe.DoesNotExistError:
            return None
        return project if self._can_administer_project(project, project_id) else None

    def _can_view_project(self, project, project_id: UUID) -> bool:
        if (
            self.principal.is_external
            or not self.principal.tenant_id
            or self.principal.tenant_id != str(project.tenant_id)
            or str(project.global_id) != str(project_id)
        ):
            return False
        if self._is_internal_system_manager() or str(project.owner_user_id).casefold() == self.actor.casefold():
            return True
        return self._current_actor_member(project) is not None

    def _can_administer_project(self, project, project_id: UUID) -> bool:
        return bool(
            not self.principal.is_external
            and self.principal.tenant_id == str(project.tenant_id)
            and str(project.global_id) == str(project_id)
            and self._is_internal_system_manager()
        )

    def _is_internal_system_manager(self) -> bool:
        return bool(
            not self.principal.is_external
            and "System Manager" in self.principal.roles
            and _enabled_system_user(self.actor)
        )

    def _require_template_administrator(self) -> str:
        if not self._is_internal_system_manager() or not self.principal.tenant_id:
            raise PermissionDenied()
        return self.principal.tenant_id

    def _current_actor_member(self, project):
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
            raise RuntimeError("Persisted Project member collection exceeds its safe bound.")
        today = datetime.now(UTC).date()
        matches = []
        for name in names:
            member = frappe.get_doc("NPI Project Member", str(name))
            if _member_effective(member, today) and _enabled_system_user(self.actor):
                matches.append(member)
        return matches[0] if len(matches) == 1 else None

    def _member_reference(self, project, member_id: UUID) -> ReadinessMemberReference:
        member = _optional_doc("NPI Project Member", str(member_id))
        today = datetime.now(UTC).date()
        if (
            member is None
            or str(member.global_id) != str(member_id)
            or str(member.tenant_id) != str(project.tenant_id)
            or str(member.project_global_id) != str(project.global_id)
            or not _member_effective(member, today)
            or not _enabled_system_user(str(member.user_id))
        ):
            raise RequestValidationFailed(
                [{"path": "ownerMemberGlobalId", "message": _("Select an enabled Project member.")}]
            )
        return ReadinessMemberReference(
            member_id,
            str(member.user_id),
            int(member.optimistic_version),
        )

    def _gate_references(
        self, project, template: ReadinessTemplateVersion
    ) -> dict[str, ReadinessGateReference]:
        keys = sorted({value.gate_key for value in template.items})
        if len(keys) > _MAX_GATES:
            raise RuntimeError("Readiness Gate collection exceeds its safe bound.")
        result: dict[str, ReadinessGateReference] = {}
        for key in keys:
            gate = _single_document(
                "NPI Gate Shell",
                {"project_global_id": str(project.global_id), "gate_key": key},
            )
            if (
                gate is None
                or str(gate.project_global_id) != str(project.global_id)
                or str(gate.gate_key) != key
            ):
                raise RequestValidationFailed(
                    [{"path": "templateRevisionGlobalId", "message": _("Resolve every configured Gate exactly once.")}]
                )
            snapshot = {
                "globalId": str(gate.global_id),
                "projectGlobalId": str(gate.project_global_id),
                "gateKey": str(gate.gate_key),
                "optimisticVersion": int(gate.optimistic_version),
                "templateGateSnapshot": _json_object(gate.template_gate_snapshot),
            }
            result[key] = ReadinessGateReference(
                UUID(str(gate.global_id)),
                key,
                int(gate.optimistic_version),
                _payload_hash(snapshot),
            )
        return result

    def _workspace_for(
        self,
        project,
        revisions: tuple[ReadinessInstanceRevision, ...],
    ) -> dict[str, Any]:
        current = _instance_response(revisions[-1]) if revisions else None
        allowed = self._is_internal_system_manager()
        return {
            "projectGlobalId": str(project.global_id),
            "currentRevision": current,
            "revisions": [_instance_response(value) for value in revisions],
            "sourceOptions": self._domain_work_item_source_options(project),
            "unavailableProjections": [
                {
                    "kind": kind.value,
                    "state": ReadinessSourceState.UNAVAILABLE.value,
                    "reasonCode": EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
                }
                for kind in sorted(EXTERNAL_SOURCE_KINDS, key=lambda value: value.value)
            ],
            "permissions": {
                "canManageTemplates": allowed,
                "canInitialize": allowed,
                "canRevise": allowed,
            },
        }

    @staticmethod
    def _domain_work_item_source_options(project) -> list[dict[str, object]]:
        names = frappe.get_all(
            "NPI Domain Work Item",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_SOURCE_OPTIONS + 1,
        )
        if len(names) > _MAX_SOURCE_OPTIONS:
            raise RuntimeError("Readiness source option collection exceeds its safe bound.")
        result: list[dict[str, object]] = []
        for name in names:
            value = _domain_work_item_value(
                frappe.get_doc("NPI Domain Work Item", str(name))
            )
            if value is None:
                raise RuntimeError("Persisted readiness Work Item source is invalid.")
            result.append(
                {
                    "kind": ReadinessSourceKind.DOMAIN_WORK_ITEM.value,
                    "globalId": str(value.global_id),
                    "sourceVersion": value.version,
                    "snapshotHash": _payload_hash(
                        _domain_work_item_source_snapshot(value)
                    ),
                    "label": value.title,
                    "stateLabelSource": value.state_label_source,
                    "stateTerminal": value.state_terminal,
                }
            )
        return result

    def _idempotency_replay(
        self,
        *,
        tenant_id: str,
        project_id: UUID | None,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        receipt_key = _receipt_key(
            tenant_id=tenant_id,
            project_id=project_id,
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        record = frappe.db.get_value(
            "NPI Readiness Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "idempotency_key_hash",
                "payload_hash",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not record:
            return None
        if str(_value(record, "payload_hash")) != payload_hash:
            raise ReadinessIdempotencyConflict()
        expected_project = str(project_id) if project_id else None
        if (
            str(_value(record, "tenant_id")) != tenant_id
            or (_value(record, "project_global_id") or None) != expected_project
            or str(_value(record, "actor_user_id")).casefold() != self.actor.casefold()
            or str(_value(record, "operation")) != operation
            or str(_value(record, "idempotency_key_hash")) != idempotency_key_hash
            or int(_value(record, "sealed") or 0) != 1
        ):
            raise RuntimeError("Persisted readiness idempotency receipt integrity failed.")
        response = _json_object(_value(record, "response_payload"))
        if _payload_hash(response) != str(_value(record, "response_hash")):
            raise RuntimeError("Persisted readiness idempotency response integrity failed.")
        return response

    def _insert_receipt(
        self,
        *,
        tenant_id: str,
        project_id: UUID | None,
        operation: str,
        idempotency_key_hash: str,
        payload_hash: str,
        created_at: datetime,
    ):
        receipt_key = _receipt_key(
            tenant_id=tenant_id,
            project_id=project_id,
            actor=self.actor,
            operation=operation,
            idempotency_key_hash=idempotency_key_hash,
        )
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Readiness Command Idempotency",
                    "global_id": str(uuid4()),
                    "receipt_key": receipt_key,
                    "tenant_id": tenant_id,
                    "project_global_id": str(project_id) if project_id else None,
                    "actor_user_id": self.actor,
                    "operation": operation,
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "target_object_type": None,
                    "target_global_id": None,
                    "response_payload": {},
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(created_at),
                    "updated_at": _database_datetime(created_at),
                }
            ).insert()
        except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
            frappe.db.rollback()
            replay = self._idempotency_replay(
                tenant_id=tenant_id,
                project_id=project_id,
                operation=operation,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
            )
            if replay is None:
                raise
            return replay

    @staticmethod
    def _seal_receipt(
        receipt,
        *,
        target_object_type: str,
        target_global_id: UUID,
        response: Mapping[str, Any],
        updated_at: datetime,
    ) -> None:
        receipt.target_object_type = target_object_type
        receipt.target_global_id = str(target_global_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = _payload_hash(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(updated_at)
        receipt.save()

    @staticmethod
    def _insert_template_version(value: ReadinessTemplateVersion) -> None:
        document = frappe.get_doc({"doctype": "NPI Readiness Template Version"})
        _apply_template_version(document, value)
        document.insert()

    @staticmethod
    def _insert_instance_revision(value: ReadinessInstanceRevision) -> None:
        frappe.get_doc(
            {
                "doctype": "NPI Readiness Instance Revision",
                "global_id": str(value.global_id),
                "instance_global_id": str(value.instance_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project": str(value.project.global_id),
                "project_global_id": str(value.project.global_id),
                "project_optimistic_version": value.project.optimistic_version,
                "project_snapshot_hash": value.project.snapshot_hash,
                "project_snapshot": value.project.snapshot_payload(),
                "template_revision": str(value.template_revision.global_id),
                "template_revision_global_id": str(value.template_revision.global_id),
                "template_version": value.template_revision.version,
                "template_snapshot_hash": value.template_revision.snapshot_hash,
                "instance_version": value.instance_version,
                "predecessor_revision": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_global_id": str(value.predecessor_global_id) if value.predecessor_global_id else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "category_snapshot": [item.snapshot_payload() for item in value.categories],
                "item_snapshot": [item.snapshot_payload() for item in value.items],
                "evaluation_snapshot": value.evaluation.snapshot_payload(),
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "instance_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            }
        ).insert()

    def _append_audit(
        self,
        *,
        operation: str,
        global_id: UUID,
        object_version: int,
        summary: Mapping[str, Any],
    ) -> None:
        event = create_audit_event(
            actor=self.actor,
            trace_id=self.trace_id,
            operation=operation,
            global_id=global_id,
            object_version=object_version,
            result="created",
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


def current_gate_readiness_input(
    *, project_id: UUID, gate_id: UUID
) -> dict[str, object]:
    """Return the closed current readiness projection consumed by Gate Review."""

    project = _optional_doc("NPI Engineering Project", str(project_id))
    if project is None or str(_value(project, "global_id")) != str(project_id):
        return {"blockers": (), "dependency": None}
    revisions = _project_revision_chain(project)
    if not revisions:
        return {"blockers": (), "dependency": None}
    current = revisions[-1]
    selected = tuple(item for item in current.items if item.gate.global_id == gate_id)
    if not selected:
        return {"blockers": (), "dependency": None}
    blockers = tuple(
        {
            "globalId": str(item.global_id),
            "version": item.item_version,
            "state": "readiness_incomplete_p0",
            "blocking": True,
            "terminal": False,
        }
        for item in selected
        if item.applicable
        and item.definition.blocking_level is ReadinessBlockingLevel.P0
        and item.state is not ReadinessItemState.COMPLETE
    )
    return {
        "blockers": blockers,
        "dependency": {
            "globalId": str(current.global_id),
            "version": current.instance_version,
            "snapshotHash": current.snapshot_hash,
        },
    }


def _project_revision_chain(project) -> tuple[ReadinessInstanceRevision, ...]:
    names = frappe.get_all(
        "NPI Readiness Instance Revision",
        filters={
            "tenant_id": str(project.tenant_id),
            "project_global_id": str(project.global_id),
        },
        pluck="name",
        order_by="instance_version asc, global_id asc",
        limit_page_length=_MAX_REVISIONS + 1,
    )
    if len(names) > _MAX_REVISIONS:
        raise RuntimeError("Persisted readiness revision collection exceeds its safe bound.")
    values = tuple(
        _instance_from_document(
            frappe.get_doc("NPI Readiness Instance Revision", str(name))
        )
        for name in names
    )
    if not values:
        return ()
    project_id = UUID(str(project.global_id))
    tenant_id = str(project.tenant_id)
    if any(
        value.tenant_id != tenant_id or value.project.global_id != project_id
        for value in values
    ):
        raise RuntimeError("Persisted readiness revision scope is invalid.")
    instance_ids = {value.instance_global_id for value in values}
    if len(instance_ids) != 1:
        raise RuntimeError("Persisted readiness instance stream is ambiguous.")
    by_version: dict[int, list[ReadinessInstanceRevision]] = {}
    for value in values:
        by_version.setdefault(value.instance_version, []).append(value)
    if set(by_version) != set(range(1, len(values) + 1)) or any(
        len(group) != 1 for group in by_version.values()
    ):
        raise RuntimeError("Persisted readiness revision lineage is ambiguous.")
    ordered = tuple(by_version[index][0] for index in range(1, len(values) + 1))
    for predecessor, successor in zip(ordered, ordered[1:]):
        validate_readiness_successor(predecessor, successor)
    return ordered


def _template_from_document(document) -> ReadinessTemplateVersion:
    value = template_from_snapshot(_json_object(_value(document, "template_snapshot")))
    if (
        str(value.global_id) != str(_value(document, "global_id"))
        or str(value.template_global_id) != str(_value(document, "template_global_id"))
        or value.template_version != int(_value(document, "template_version"))
        or value.optimistic_version != int(_value(document, "optimistic_version"))
        or value.snapshot_hash != str(_value(document, "snapshot_hash"))
        or value.version_key_hash != str(_value(document, "version_key_hash"))
    ):
        raise RuntimeError("Persisted readiness template integrity failed.")
    return value


def _instance_from_document(document) -> ReadinessInstanceRevision:
    value = instance_from_snapshot(_json_object(_value(document, "instance_snapshot")))
    if (
        str(value.global_id) != str(_value(document, "global_id"))
        or str(value.instance_global_id) != str(_value(document, "instance_global_id"))
        or value.instance_version != int(_value(document, "instance_version"))
        or value.snapshot_hash != str(_value(document, "snapshot_hash"))
        or value.version_key_hash != str(_value(document, "version_key_hash"))
        or value.evaluation.snapshot_payload()
        != _json_object(_value(document, "evaluation_snapshot"))
    ):
        raise RuntimeError("Persisted readiness instance integrity failed.")
    return value


def _apply_template_version(document, value: ReadinessTemplateVersion) -> None:
    document.global_id = str(value.global_id)
    document.template = str(value.template_global_id)
    document.template_global_id = str(value.template_global_id)
    document.template_code = value.template_code
    document.template_version = value.template_version
    document.version_key_hash = value.version_key_hash
    document.optimistic_version = value.optimistic_version
    document.title = value.title
    document.publication_state = value.publication_state.value
    document.applicability_snapshot = value.applicability.snapshot_payload()
    document.category_snapshot = [item.snapshot_payload() for item in value.categories]
    document.item_snapshot = [item.snapshot_payload() for item in value.items]
    document.changed_by_user_id = value.changed_by_user_id
    document.changed_at = _database_datetime(value.changed_at)
    document.request_id = str(value.request_id)
    document.trace_id = value.trace_id
    document.template_snapshot = value.snapshot_payload()
    document.snapshot_hash = value.snapshot_hash


def _project_snapshot(project, industry_key: str) -> ReadinessProjectSnapshot:
    project_id = UUID(str(project.global_id))
    version = int(project.optimistic_version)
    project_type = ProjectType(str(project.project_type))
    customer_keys = _customer_reference_keys(project)
    snapshot_hash = _payload_hash(
        {
            "globalId": str(project_id),
            "optimisticVersion": version,
            "projectType": project_type.value,
            "customerReferenceKeys": list(customer_keys),
            "industryKey": industry_key,
        }
    )
    return ReadinessProjectSnapshot(
        project_id,
        version,
        snapshot_hash,
        project_type,
        customer_keys,
        industry_key,
    )


def _customer_reference_keys(project) -> tuple[str, ...]:
    references = _value(project, "references") or ()
    keys = {
        f"{str(_value(value, 'source_system')).upper()}:{str(_value(value, 'source_object_id')).strip()}"
        for value in references
        if str(_value(value, "reference_type")) == "customer"
        and str(_value(value, "source_system")).strip()
        and str(_value(value, "source_object_id")).strip()
    }
    return tuple(sorted(keys))


def _template_matches_project(
    template: ReadinessTemplateVersion,
    project_type: ProjectType,
    customer_keys: tuple[str, ...],
) -> bool:
    selector = template.applicability
    return (
        (not selector.project_types or project_type in selector.project_types)
        and (
            not selector.customer_reference_keys
            or bool(set(selector.customer_reference_keys) & set(customer_keys))
        )
    )


def _template_response(value: ReadinessTemplateVersion) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _instance_response(value: ReadinessInstanceRevision) -> dict[str, Any]:
    return {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}


def _receipt_key(
    *,
    tenant_id: str,
    project_id: UUID | None,
    actor: str,
    operation: str,
    idempotency_key_hash: str,
) -> str:
    return _payload_hash(
        {
            "tenantId": tenant_id,
            "projectGlobalId": str(project_id) if project_id else None,
            "actorUserId": actor.casefold(),
            "operation": operation,
            "idempotencyKeyHash": idempotency_key_hash,
        }
    )


def _payload_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return getattr(value, "value", value)


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise RuntimeError("Persisted readiness JSON object is invalid.")
    return dict(value)


def _json_array(value: object) -> list[dict[str, Any]]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise RuntimeError("Persisted readiness JSON array is invalid.")
    return [dict(item) for item in value]


def _is_replay_response(value: object) -> bool:
    return isinstance(value, dict) and not callable(getattr(value, "save", None))


def _optional_doc(doctype: str, name: str):
    try:
        return frappe.get_doc(doctype, name)
    except frappe.DoesNotExistError:
        return None


def _single_document(doctype: str, filters: Mapping[str, Any]):
    names = frappe.get_all(
        doctype,
        filters=dict(filters),
        pluck="name",
        order_by="name asc",
        limit_page_length=2,
    )
    return frappe.get_doc(doctype, str(names[0])) if len(names) == 1 else None


def _value(record: object, fieldname: str) -> object:
    if isinstance(record, Mapping):
        return record.get(fieldname)
    getter = getattr(record, "get", None)
    if callable(getter):
        return getter(fieldname)
    return getattr(record, fieldname, None)


def _member_effective(member, today: date) -> bool:
    starts = _date_value(member.effective_from)
    ends = _date_value(member.effective_to) if member.effective_to else None
    return starts <= today and (ends is None or today <= ends)


def _enabled_system_user(user_id: str) -> bool:
    value = frappe.db.get_value("User", user_id, ["enabled", "user_type"], as_dict=True)
    return bool(
        value
        and int(_value(value, "enabled") or 0) == 1
        and str(_value(value, "user_type")) == "System User"
    )


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _database_datetime(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).isoformat(
        sep=" ", timespec="microseconds"
    )


def _source_document(
    doctype: str,
    context: SourceResolutionContext,
    query: ExactSourceQuery,
):
    document = _optional_doc(doctype, str(query.global_id))
    if document is None:
        return None
    return (
        document
        if str(_value(document, "global_id")) == str(query.global_id)
        and str(_value(document, "tenant_id")) == context.tenant_id
        and str(_value(document, "project_global_id"))
        == str(context.project_global_id)
        else None
    )


def _document_release_row_matches(
    document,
    context: SourceResolutionContext,
    *,
    document_id: UUID,
    revision_id: UUID,
) -> bool:
    return bool(
        str(_value(document, "tenant_id")) == context.tenant_id
        and str(_value(document, "project_global_id"))
        == str(context.project_global_id)
        and str(_value(document, "document_global_id")) == str(document_id)
        and str(_value(document, "document_revision")) == str(revision_id)
        and str(_value(document, "revision_global_id")) == str(revision_id)
    )


def _released_document_source_is_current(
    context: SourceResolutionContext,
    query: ExactSourceQuery,
    revision,
) -> bool:
    try:
        from npi_core.documents.domain import sha256_json
        from npi_core.documents.frappe_repository import (
            _association_matches_live_file,
        )
        from npi_core.documents.release_domain import (
            DocumentConfirmationType,
            DocumentLifecycleEventType,
            DocumentLifecycleState,
            DocumentReleaseIntegrityBlocked,
            DocumentReleasePolicyState,
        )
        from npi_core.documents.release_frappe import (
            confirmation_value,
            lifecycle_event_value,
            lifecycle_value,
            release_policy_value,
            review_cycle_value,
        )
        from npi_core.documents.release_repository import (
            FrappeDocumentReleaseRepository,
        )

        revision_snapshot = _json_object(_value(revision, "revision_snapshot"))
        revision_hash = str(_value(revision, "snapshot_hash"))
        document_id = UUID(str(_value(revision, "document_global_id")))
        parent = _optional_doc("NPI Controlled Document", str(document_id))
        project = _optional_doc(
            "NPI Engineering Project", str(context.project_global_id)
        )
        if (
            set(revision_snapshot) != _DOCUMENT_REVISION_SNAPSHOT_KEYS
            or _payload_hash(revision_snapshot) != revision_hash
            or revision_snapshot.get("schemaVersion") != 1
            or revision_snapshot.get("globalId") != str(query.global_id)
            or revision_snapshot.get("documentGlobalId") != str(document_id)
            or parent is None
            or project is None
            or str(_value(parent, "global_id")) != str(document_id)
            or str(_value(parent, "tenant_id")) != context.tenant_id
            or str(_value(parent, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(project, "global_id"))
            != str(context.project_global_id)
            or str(_value(project, "tenant_id")) != context.tenant_id
        ):
            return False

        lifecycle_document = _single_document(
            "NPI Document Revision Lifecycle",
            {
                "tenant_id": context.tenant_id,
                "project_global_id": str(context.project_global_id),
                "revision_global_id": str(query.global_id),
            },
        )
        if lifecycle_document is None:
            return False
        lifecycle = lifecycle_value(lifecycle_document)
        release_event_id = lifecycle.release_event_global_id
        approved_event_id = lifecycle.approved_event_global_id
        cycle_id = lifecycle.approved_cycle_global_id
        if (
            str(_value(lifecycle_document, "global_id")) != str(query.global_id)
            or not _document_release_row_matches(
                lifecycle_document,
                context,
                document_id=document_id,
                revision_id=query.global_id,
            )
            or lifecycle.revision_global_id != query.global_id
            or lifecycle.state is not DocumentLifecycleState.RELEASED
            or lifecycle.version != query.source_version
            or lifecycle.release_snapshot_hash != query.snapshot_hash
            or release_event_id is None
            or approved_event_id is None
            or approved_event_id == release_event_id
            or cycle_id is None
            or str(_value(lifecycle_document, "last_event_global_id"))
            != str(release_event_id)
        ):
            return False

        event_document = _optional_doc(
            "NPI Document Lifecycle Event", str(release_event_id)
        )
        approved_event_document = _optional_doc(
            "NPI Document Lifecycle Event", str(approved_event_id)
        )
        cycle_document = _optional_doc("NPI Document Review Cycle", str(cycle_id))
        if (
            event_document is None
            or approved_event_document is None
            or cycle_document is None
        ):
            return False
        event = lifecycle_event_value(event_document)
        approved_event = lifecycle_event_value(approved_event_document)
        cycle = review_cycle_value(cycle_document)
        if (
            not _document_release_row_matches(
                event_document,
                context,
                document_id=document_id,
                revision_id=query.global_id,
            )
            or not _document_release_row_matches(
                approved_event_document,
                context,
                document_id=document_id,
                revision_id=query.global_id,
            )
            or not _document_release_row_matches(
                cycle_document,
                context,
                document_id=document_id,
                revision_id=query.global_id,
            )
            or str(_value(event_document, "review_cycle")) != str(cycle_id)
            or str(_value(approved_event_document, "review_cycle"))
            != str(cycle_id)
            or event.global_id != release_event_id
            or event.revision_global_id != query.global_id
            or event.event_type is not DocumentLifecycleEventType.RELEASED
            or event.from_state is not DocumentLifecycleState.APPROVED
            or event.to_state is not DocumentLifecycleState.RELEASED
            or event.from_version != lifecycle.version - 1
            or event.to_version != lifecycle.version
            or event.cycle_global_id != cycle_id
            or event.evidence_snapshot_hash != query.snapshot_hash
            or _json_object(_value(event_document, "event_snapshot"))
            != event.event_payload()
            or approved_event.global_id != approved_event_id
            or approved_event.revision_global_id != query.global_id
            or approved_event.event_type
            is not DocumentLifecycleEventType.APPROVED
            or approved_event.from_state
            is not DocumentLifecycleState.IN_REVIEW
            or approved_event.to_state is not DocumentLifecycleState.APPROVED
            or approved_event.from_version != approved_event.to_version - 1
            or approved_event.to_version != event.from_version
            or approved_event.cycle_global_id != cycle_id
            or approved_event.evidence_snapshot_hash
            != cycle.evidence.snapshot_hash
            or approved_event.policy_ref != cycle.policy_ref
            or _json_object(_value(approved_event_document, "event_snapshot"))
            != approved_event.event_payload()
            or cycle.global_id != cycle_id
            or cycle.revision_global_id != query.global_id
            or cycle.evidence.revision_global_id != query.global_id
            or cycle.policy_ref != event.policy_ref
            or cycle.evidence.revision_snapshot_hash != revision_hash
            or _json_object(_value(cycle_document, "cycle_snapshot"))
            != cycle.snapshot_payload()
        ):
            return False

        policy_root = _optional_doc(
            "NPI Document Release Policy", str(cycle.policy_ref.global_id)
        )
        policy_document = _single_document(
            "NPI Document Release Policy Version",
            {
                "policy_global_id": str(cycle.policy_ref.global_id),
                "policy_version": cycle.policy_ref.version,
            },
        )
        if policy_root is None or policy_document is None:
            return False
        policy = release_policy_value(policy_document)
        if (
            str(_value(policy_root, "global_id"))
            != str(cycle.policy_ref.global_id)
            or str(_value(policy_root, "tenant_id")) != context.tenant_id
            or str(_value(policy_root, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(policy_document, "tenant_id")) != context.tenant_id
            or str(_value(policy_document, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(policy_document, "global_id"))
            != str(policy.global_id)
            or str(_value(policy_document, "policy_global_id"))
            != str(cycle.policy_ref.global_id)
            or policy.state is not DocumentReleasePolicyState.PUBLISHED
            or policy.reference != cycle.policy_ref
            or policy.reviewer_assignments != cycle.reviewer_assignments
            or policy.required_approval_count != cycle.required_approval_count
            or _json_object(_value(policy_document, "policy_snapshot"))
            != policy.snapshot_payload()
        ):
            return False

        confirmation_names = frappe.get_all(
            "NPI Document Confirmation",
            filters={
                "tenant_id": context.tenant_id,
                "project_global_id": str(context.project_global_id),
                "revision_global_id": str(query.global_id),
                "cycle_global_id": str(cycle_id),
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_RELEASE_CONFIRMATIONS + 1,
        )
        if len(confirmation_names) > _MAX_RELEASE_CONFIRMATIONS:
            return False
        approvals = []
        releases = []
        approval_slots: set[str] = set()
        for name in confirmation_names:
            confirmation_document = frappe.get_doc(
                "NPI Document Confirmation", str(name)
            )
            confirmation = confirmation_value(confirmation_document)
            if (
                not _document_release_row_matches(
                    confirmation_document,
                    context,
                    document_id=document_id,
                    revision_id=query.global_id,
                )
                or str(_value(confirmation_document, "global_id"))
                != str(confirmation.global_id)
                or confirmation.revision_global_id != query.global_id
                or confirmation.cycle_global_id != cycle_id
                or str(_value(confirmation_document, "review_cycle"))
                != str(cycle_id)
                or confirmation.policy_ref != cycle.policy_ref
                or confirmation.confirmed is not True
                or confirmation.confirmation_method
                != policy.confirmation_method
                or _json_object(
                    _value(confirmation_document, "confirmation_evidence")
                )
                != confirmation.evidence_payload()
            ):
                return False
            if (
                confirmation.confirmation_type
                is DocumentConfirmationType.REVIEW_APPROVE
                and confirmation.evidence_snapshot_hash
                == cycle.evidence.snapshot_hash
                and confirmation.confirmation_intent == "review_decision"
                and confirmation.authority_slot not in approval_slots
                and any(
                    assignment.slot_key == confirmation.authority_slot
                    and assignment.user_id.casefold()
                    == confirmation.actor_user_id.casefold()
                    for assignment in cycle.reviewer_assignments
                )
            ):
                approvals.append(confirmation)
                approval_slots.add(confirmation.authority_slot)
            elif (
                confirmation.confirmation_type is DocumentConfirmationType.RELEASE
                and confirmation.evidence_snapshot_hash == query.snapshot_hash
                and confirmation.confirmation_intent == "release_revision"
                and confirmation.authority_slot == "final_release_authority"
                and policy.permits_release(confirmation.actor_user_id)
            ):
                releases.append(confirmation)
            else:
                return False
        if len(approvals) < cycle.required_approval_count or len(releases) != 1:
            return False
        confirmation_hashes = tuple(
            item.evidence_hash for item in (*approvals, releases[0])
        )
        approval_hashes = tuple(item.evidence_hash for item in approvals)
        if (
            sorted(event.confirmation_hashes) != sorted(confirmation_hashes)
            or sorted(approved_event.confirmation_hashes)
            != sorted(approval_hashes)
        ):
            return False

        release_hash = sha256_json(
            {
                "schemaVersion": 1,
                "revisionGlobalId": str(query.global_id),
                "reviewEvidenceSnapshotHash": cycle.evidence.snapshot_hash,
                "releasePolicyRef": cycle.policy_ref.canonical_dict(),
                "approvalConfirmationHashes": sorted(
                    item.evidence_hash for item in approvals
                ),
                "files": [
                    {
                        "fileRevisionGlobalId": str(item.file_revision_global_id),
                        "fromOptimisticVersion": item.file_optimistic_version,
                        "toOptimisticVersion": item.file_optimistic_version + 1,
                        "sha256": item.sha256,
                    }
                    for item in sorted(
                        cycle.evidence.files,
                        key=lambda value: str(value.file_revision_global_id),
                    )
                ],
            }
        )
        if release_hash != query.snapshot_hash:
            return False

        association_names = frappe.get_all(
            "NPI Document Revision File",
            filters={
                "tenant_id": context.tenant_id,
                "project_global_id": str(context.project_global_id),
                "document_global_id": str(document_id),
                "document_revision_global_id": str(query.global_id),
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=_MAX_RELEASE_FILES + 1,
        )
        expected_files = {
            item.association_global_id: item for item in cycle.evidence.files
        }
        if (
            not association_names
            or len(association_names) > _MAX_RELEASE_FILES
            or len(association_names) != len(expected_files)
        ):
            return False
        for name in association_names:
            association = frappe.get_doc("NPI Document Revision File", str(name))
            expected = expected_files.get(UUID(str(_value(association, "global_id"))))
            if expected is None:
                return False
            file_revision = _optional_doc(
                "NPI File Revision", str(expected.file_revision_global_id)
            )
            if (
                file_revision is None
                or not _association_matches_live_file(
                    project,
                    parent,
                    revision,
                    association,
                    file_revision,
                )
                or int(_value(file_revision, "released") or 0) != 1
                or int(_value(file_revision, "optimistic_version") or 0)
                != expected.file_optimistic_version + 1
            ):
                return False
            observed = FrappeDocumentReleaseRepository._release_file_evidence(
                association, file_revision
            )
            if not _stable_release_file_matches(observed, expected):
                return False
        return True
    except (
        DocumentReleaseIntegrityBlocked,
        RequestValidationFailed,
        AttributeError,
        IndexError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
        frappe.DoesNotExistError,
        frappe.PermissionError,
    ):
        return False


def _stable_release_file_matches(observed, expected) -> bool:
    return bool(
        observed.association_global_id == expected.association_global_id
        and observed.association_snapshot_hash == expected.association_snapshot_hash
        and observed.file_revision_global_id == expected.file_revision_global_id
        and observed.file_document_global_id == expected.file_document_global_id
        and observed.frappe_file_id == expected.frappe_file_id
        and observed.frappe_content_hash == expected.frappe_content_hash
        and observed.file_name == expected.file_name
        and observed.mime_type == expected.mime_type
        and observed.size_bytes == expected.size_bytes
        and observed.sha256 == expected.sha256
        and observed.scan_state == "clean"
        and expected.scan_state == "clean"
        and observed.uploaded_by_user_id == expected.uploaded_by_user_id
        and observed.uploaded_at == expected.uploaded_at
    )


def _parsed_snapshot_source(
    context: SourceResolutionContext,
    query: ExactSourceQuery,
    document,
    *,
    snapshot_field: str,
    parser: Callable[[object], Any],
    document_version_field: str | None,
    parsed_version_attribute: str | None,
) -> Any | None:
    try:
        document_version = (
            int(_value(document, document_version_field) or 0)
            if document_version_field
            else 1
        )
        if (
            document_version != query.source_version
            or str(_value(document, "snapshot_hash")) != query.snapshot_hash
        ):
            return None
        snapshot = _json_object(_value(document, snapshot_field))
        value = parser(snapshot)
        canonical = value.snapshot_payload()
    except (
        RequestValidationFailed,
        AttributeError,
        IndexError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return None
    parsed_version = (
        getattr(value, parsed_version_attribute)
        if parsed_version_attribute is not None
        else 1
    )
    if (
        canonical != snapshot
        or value.global_id != query.global_id
        or value.tenant_id != context.tenant_id
        or value.project_global_id != context.project_global_id
        or parsed_version != query.source_version
        or value.snapshot_hash != query.snapshot_hash
    ):
        return None
    return value


def _trial_review_reference_sources_are_current(
    context: SourceResolutionContext,
    reference: TrialReviewReferenceRevision,
) -> bool:
    """Revalidate every exact source frozen by a Trial review reference."""

    try:
        from npi_core.tooling.frappe_repository import FrappeToolingRepository

        comparison_document = _optional_doc(
            "NPI Trial Round Comparison Snapshot",
            str(reference.comparison_snapshot.global_id),
        )
        if comparison_document is None:
            return False
        comparison_snapshot = _json_object(
            _value(comparison_document, "comparison_snapshot")
        )
        comparison = comparison_from_snapshot(comparison_snapshot)
        if (
            comparison.snapshot_payload() != comparison_snapshot
            or comparison.global_id != reference.comparison_snapshot.global_id
            or comparison.snapshot_hash != reference.comparison_snapshot.snapshot_hash
            or comparison.tenant_id != context.tenant_id
            or comparison.project_global_id != context.project_global_id
            or comparison.target_round_global_id != reference.trial_round_global_id
            or str(_value(comparison_document, "global_id"))
            != str(reference.comparison_snapshot.global_id)
            or str(_value(comparison_document, "tenant_id")) != context.tenant_id
            or str(_value(comparison_document, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(comparison_document, "target_round_global_id"))
            != str(reference.trial_round_global_id)
            or str(_value(comparison_document, "snapshot_hash"))
            != reference.comparison_snapshot.snapshot_hash
        ):
            return False

        target_source = comparison.sources[-1]
        trial_round_document = _optional_doc(
            "NPI Trial Round", str(reference.trial_round_global_id)
        )
        if trial_round_document is None:
            return False
        trial_round_snapshot = _json_object(
            _value(trial_round_document, "round_snapshot")
        )
        trial_round = trial_round_from_snapshot(trial_round_snapshot)
        if (
            trial_round.snapshot_payload() != trial_round_snapshot
            or target_source.trial_round_global_id != reference.trial_round_global_id
            or target_source.trial_round_optimistic_version
            != trial_round.optimistic_version
            or target_source.trial_round_snapshot_hash != trial_round.snapshot_hash
            or target_source.trial_plan_revision.global_id
            != trial_round.trial_plan_revision_global_id
            or target_source.trial_plan_revision.snapshot_hash
            != trial_round.trial_plan_revision_snapshot_hash
            or comparison.trial_plan_global_id != trial_round.trial_plan_global_id
            or trial_round.global_id != reference.trial_round_global_id
            or trial_round.tenant_id != context.tenant_id
            or trial_round.project_global_id != context.project_global_id
            or trial_round.tooling_master_global_id
            != reference.tooling_master_global_id
            or str(_value(trial_round_document, "global_id"))
            != str(reference.trial_round_global_id)
            or str(_value(trial_round_document, "tenant_id")) != context.tenant_id
            or str(_value(trial_round_document, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(trial_round_document, "tooling_master_global_id"))
            != str(reference.tooling_master_global_id)
            or int(_value(trial_round_document, "optimistic_version") or 0)
            != target_source.trial_round_optimistic_version
            or str(_value(trial_round_document, "snapshot_hash"))
            != target_source.trial_round_snapshot_hash
        ):
            return False

        part_document = _optional_doc(
            "NPI Engineering Part Revision",
            str(reference.part_revision.global_id),
        )
        master_document = _optional_doc(
            "NPI Tooling Master", str(reference.tooling_master_global_id)
        )
        revision_document = _optional_doc(
            "NPI Tooling Revision",
            str(reference.tooling_revision.global_id),
        )
        tooling_set_document = _optional_doc(
            "NPI Tooling Set",
            str(reference.tooling_set.global_id),
        )
        if any(
            document is None
            for document in (
                part_document,
                master_document,
                revision_document,
                tooling_set_document,
            )
        ):
            return False

        part_value = FrappeToolingRepository._revision_value(part_document)
        master_value = FrappeToolingRepository._master_value(master_document)
        tooling_set_value = FrappeToolingRepository._tooling_set_value(
            tooling_set_document
        )
        if (
            part_value.global_id != reference.part_revision.global_id
            or part_value.snapshot_hash != reference.part_revision.snapshot_hash
            or part_value.tenant_id != context.tenant_id
            or part_value.originating_project_global_id
            != context.project_global_id
            or master_value.global_id != reference.tooling_master_global_id
            or master_value.tenant_id != context.tenant_id
            or master_value.originating_project_global_id
            != context.project_global_id
            or tooling_set_value.global_id != reference.tooling_set.global_id
            or tooling_set_value.snapshot_hash
            != reference.tooling_set.snapshot_hash
            or tooling_set_value.tenant_id != context.tenant_id
            or tooling_set_value.project_global_id
            != context.project_global_id
            or tooling_set_value.tooling_master_global_id
            != reference.tooling_master_global_id
        ):
            return False

        revision_snapshot = _json_object(
            _value(revision_document, "revision_snapshot")
        )
        revision_value = tooling_revision_from_snapshot(revision_snapshot)
        if (
            revision_value.snapshot_payload() != revision_snapshot
            or revision_value.global_id != reference.tooling_revision.global_id
            or revision_value.snapshot_hash
            != reference.tooling_revision.snapshot_hash
            or revision_value.tenant_id != context.tenant_id
            or revision_value.project_global_id != context.project_global_id
            or revision_value.tooling_master_global_id
            != reference.tooling_master_global_id
            or str(_value(revision_document, "global_id"))
            != str(reference.tooling_revision.global_id)
            or str(_value(revision_document, "tenant_id"))
            != context.tenant_id
            or str(_value(revision_document, "project_global_id"))
            != str(context.project_global_id)
            or str(_value(revision_document, "snapshot_hash"))
            != reference.tooling_revision.snapshot_hash
            or str(_value(revision_document, "tooling_master_global_id"))
            != str(reference.tooling_master_global_id)
        ):
            return False

        file_revision = _optional_doc(
            "NPI File Revision", str(reference.file_revision.global_id)
        )
        if file_revision is None:
            return False
        from npi_core.npi_core.doctype.npi_file_revision.npi_file_revision import (
            file_revision_source_snapshot,
            has_live_private_file_identity,
        )

        file_snapshot = file_revision_source_snapshot(file_revision)
        return bool(
            str(_value(file_revision, "global_id"))
            == str(reference.file_revision.global_id)
            and str(_value(file_revision, "tenant_id")) == context.tenant_id
            and str(_value(file_revision, "project_global_id"))
            == str(context.project_global_id)
            and str(file_snapshot.get("globalId"))
            == str(reference.file_revision.global_id)
            and _payload_hash(file_snapshot) == reference.file_revision.snapshot_hash
            and file_snapshot.get("scanState") == "clean"
            and file_snapshot.get("isPrivate") is True
            and str(_value(file_revision, "scan_state")) == "clean"
            and int(_value(file_revision, "is_private") or 0) == 1
            and has_live_private_file_identity(file_revision)
        )
    except (
        RequestValidationFailed,
        AttributeError,
        IndexError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
        frappe.DoesNotExistError,
        frappe.PermissionError,
        frappe.ValidationError,
    ):
        return False


def _observation(
    context: SourceResolutionContext,
    query: ExactSourceQuery,
    disposition: ReadinessSourceState,
) -> ExactSourceObservation:
    return ExactSourceObservation(
        tenant_id=context.tenant_id,
        project_global_id=context.project_global_id,
        kind=query.kind,
        global_id=query.global_id,
        source_version=query.source_version,
        snapshot_hash=query.snapshot_hash,
        disposition=disposition,
    )


def _domain_work_item_value(document):
    if str(_value(document, "source_system")) != "NPI_ONE":
        return None
    try:
        from npi_core.project_work.frappe_repository import (
            _domain_work_item_from_document,
        )

        return _domain_work_item_from_document(document)
    except (
        RequestValidationFailed,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


def _domain_work_item_source_snapshot(value) -> dict[str, object]:
    return {
        "globalId": str(value.global_id),
        "tenantId": value.tenant_id,
        "projectGlobalId": str(value.project_global_id),
        "stageGlobalId": (
            str(value.stage_global_id) if value.stage_global_id else None
        ),
        "kind": value.kind.value,
        "title": value.title,
        "detail": value.detail or "",
        "wbsItemGlobalId": (
            str(value.wbs_item_global_id) if value.wbs_item_global_id else None
        ),
        "ownerUserId": value.owner_user_id,
        "dueAt": value.due_at,
        "severity": value.severity.value,
        "blocking": value.blocking,
        "stateKey": value.state_key,
        "stateLabelSource": value.state_label_source,
        "stateTerminal": value.state_terminal,
        "workPolicyRef": {
            "globalId": str(value.work_policy_global_id),
            "version": value.work_policy_version,
            "snapshotHash": value.work_policy_snapshot_hash,
        },
        "relations": [str(item) for item in value.related_work_item_ids],
        "evidenceReferences": [str(item) for item in value.evidence_references],
        "sourceSystem": "NPI_ONE",
        "optimisticVersion": value.version,
    }
