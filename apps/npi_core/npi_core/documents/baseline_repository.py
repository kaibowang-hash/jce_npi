from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import frappe
from frappe import _

from npi_core.documents.baseline_domain import (
    MAX_BASELINE_MEMBERS,
    BaselineGateDependency,
    BaselineImpactEvent,
    DocumentBaseline,
    DocumentBaselineIdempotencyConflict,
    DocumentBaselineInputUnavailable,
    DocumentBaselineMember,
    DocumentBaselineMemberPrecondition,
    DocumentBaselinePolicyReference,
    DocumentBaselinePolicyState,
    DocumentBaselinePolicyUnavailable,
    DocumentBaselinePolicyVersion,
    create_document_baseline,
    sha256_json,
)
from npi_core.documents.baseline_diagnostics import (
    baseline_workspace_server_step,
    record_baseline_workspace_server_failure,
    record_baseline_workspace_server_predicate,
)
from npi_core.documents.baseline_frappe import (
    baseline_dependency_value,
    baseline_impact_value,
    baseline_member_value,
    baseline_policy_value,
    document_baseline_command_write,
)
from npi_core.documents.domain import command_payload_hash
from npi_core.documents.frappe_repository import (
    DocumentCommandOutcome,
    _association_matches_live_file,
    _bounded_documents,
    _database_datetime,
    _datetime_value,
    _document_matches_project,
    _json_object,
    _record_value,
)
from npi_core.documents.release_domain import (
    DocumentLifecycleEventType,
    DocumentLifecycleState,
    DocumentReleaseFileEvidence,
    DocumentReleaseIntegrityBlocked,
    DocumentReviewEvidence,
)
from npi_core.documents.release_frappe import (
    lifecycle_event_value,
    lifecycle_value,
    review_cycle_value,
)
from npi_core.documents.release_repository import FrappeDocumentReleaseRepository
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project_controls.terminal_guard import require_mutable_project
from npi_core.request_security import document_baseline_routes_are_disabled


_MAX_BASELINES = 256
_MAX_BASELINE_IMPACTS = 50_000
_MAX_POLICIES = 64


def load_document_baseline(
    project,
    baseline_global_id: UUID,
    *,
    lock: bool,
) -> DocumentBaseline | None:
    """Load one exact immutable baseline within the supplied Project scope."""
    try:
        document = frappe.get_doc(
            "NPI Document Baseline",
            str(baseline_global_id),
            for_update=lock,
        )
    except frappe.DoesNotExistError:
        return None
    if (
        str(document.global_id) != str(baseline_global_id)
        or str(document.tenant_id) != str(project.tenant_id)
        or str(document.project_global_id) != str(project.global_id)
    ):
        return None
    return _validated_baseline_value(
        project,
        document,
        lock_members=lock,
    )


def document_baseline_response(value: DocumentBaseline) -> dict[str, Any]:
    """Return URL-free exact baseline metadata safe for normal-user APIs."""
    return {
        "globalId": str(value.global_id),
        "label": value.label,
        "version": value.version,
        "snapshotHash": value.snapshot_hash,
        "policy": value.policy_ref.canonical_dict(),
        "createdByUserId": value.created_by_user_id,
        "createdAt": value.created_at.isoformat().replace("+00:00", "Z"),
        "members": [
            {
                "globalId": str(member.global_id),
                "sequence": member.sequence,
                "documentGlobalId": str(member.document_global_id),
                "revisionGlobalId": str(member.revision_global_id),
                "major": member.major,
                "minor": member.minor,
                "revisionSnapshotHash": member.revision_snapshot_hash,
                "lifecycleVersion": member.lifecycle_version,
                "releaseEventGlobalId": str(member.release_event_global_id),
                "releaseSnapshotHash": member.release_snapshot_hash,
                "memberHash": member.member_hash,
                "files": [
                    {
                        "fileRevisionGlobalId": str(
                            file.file_revision_global_id
                        ),
                        "fileDocumentGlobalId": str(
                            file.file_document_global_id
                        ),
                        "fileName": file.file_name,
                        "mimeType": file.mime_type,
                        "sizeBytes": file.size_bytes,
                        "sha256": file.sha256,
                        "scanState": file.scan_state,
                    }
                    for file in member.release_evidence.files
                ],
            }
            for member in value.members
        ],
    }


def load_project_baseline_impacts(
    project,
    *,
    gate_global_id: UUID | None = None,
) -> tuple[BaselineImpactEvent, ...]:
    """Load validated append-only impact lineage for one Project or Gate."""
    filters: dict[str, object] = {
        "tenant_id": str(project.tenant_id),
        "project_global_id": str(project.global_id),
    }
    if gate_global_id is not None:
        filters["gate_global_id"] = str(gate_global_id)
    with baseline_workspace_server_step("P503_BASELINE_WORKSPACE_IMPACT_QUERY"):
        names = frappe.get_all(
            "NPI Baseline Impact Event",
            filters=filters,
            pluck="name",
            order_by="occurred_at desc, global_id desc",
            limit_page_length=_MAX_BASELINE_IMPACTS + 1,
        )
    if len(names) > _MAX_BASELINE_IMPACTS:
        raise DocumentBaselineInputUnavailable()
    impacts = []
    for name in names:
        with baseline_workspace_server_step(
            "P503_BASELINE_WORKSPACE_IMPACT_LOAD"
        ):
            impacts.append(
                _validated_baseline_impact(
                    project,
                    frappe.get_doc("NPI Baseline Impact Event", name),
                )
            )
    return tuple(impacts)


def document_baseline_impact_response(
    value: BaselineImpactEvent,
) -> dict[str, Any]:
    """Return visible exact impact lineage without request or trace metadata."""
    return {
        "globalId": str(value.global_id),
        "eventType": value.event_type.value,
        "dependencyGlobalId": str(value.dependency_global_id),
        "baselineGlobalId": str(value.baseline_global_id),
        "baselineSnapshotHash": value.baseline_snapshot_hash,
        "oldRevisionGlobalId": str(value.old_revision_global_id),
        "oldRevisionSnapshotHash": value.old_revision_snapshot_hash,
        "newRevisionGlobalId": str(value.new_revision_global_id),
        "newRevisionSnapshotHash": value.new_revision_snapshot_hash,
        "gateGlobalId": str(value.gate_global_id),
        "requirementGlobalId": str(value.requirement_global_id),
        "evidenceReferenceGlobalId": str(value.evidence_reference_global_id),
        "initiatedByUserId": value.initiated_by_user_id,
        "occurredAt": value.occurred_at.isoformat().replace("+00:00", "Z"),
        "eventHash": value.event_hash,
    }


def _validated_baseline_impact(
    project,
    document,
) -> BaselineImpactEvent:
    try:
        event = baseline_impact_value(document)
        dependency_document = frappe.get_doc(
            "NPI Baseline Gate Dependency",
            str(event.dependency_global_id),
        )
        dependency: BaselineGateDependency = baseline_dependency_value(
            dependency_document
        )
        baseline = load_document_baseline(
            project,
            dependency.baseline_global_id,
            lock=False,
        )
        evidence = frappe.get_doc(
            "NPI Gate Evidence Reference",
            str(dependency.evidence_reference_global_id),
        )
        gate = frappe.get_doc(
            "NPI Gate Shell",
            str(dependency.gate_global_id),
        )
        successor = frappe.get_doc(
            "NPI Document Revision",
            str(event.new_revision_global_id),
        )
    except Exception as error:
        raise DocumentBaselineInputUnavailable() from error
    member_matches = bool(
        baseline is not None
        and baseline.snapshot_hash == dependency.baseline_snapshot_hash
        and any(
            member.document_global_id == dependency.input_document_global_id
            and member.revision_global_id == dependency.input_revision_global_id
            and member.revision_snapshot_hash
            == dependency.input_revision_snapshot_hash
            for member in baseline.members
        )
    )
    if (
        str(event.tenant_id) != str(project.tenant_id)
        or event.project_global_id != UUID(str(project.global_id))
        or _json_object(document.event_snapshot) != event.event_payload()
        or str(document.event_hash) != event.event_hash
        or _json_object(dependency_document.dependency_snapshot)
        != dependency.snapshot_payload()
        or str(dependency_document.snapshot_hash) != dependency.snapshot_hash
        or dependency.tenant_id != event.tenant_id
        or dependency.project_global_id != event.project_global_id
        or event.dependency_global_id != dependency.global_id
        or event.baseline_global_id != dependency.baseline_global_id
        or event.baseline_snapshot_hash != dependency.baseline_snapshot_hash
        or event.old_revision_global_id != dependency.input_revision_global_id
        or event.old_revision_snapshot_hash
        != dependency.input_revision_snapshot_hash
        or event.gate_global_id != dependency.gate_global_id
        or event.requirement_global_id != dependency.requirement_global_id
        or event.evidence_reference_global_id
        != dependency.evidence_reference_global_id
        or not member_matches
        or str(evidence.tenant_id) != event.tenant_id
        or str(evidence.global_id)
        != str(dependency.evidence_reference_global_id)
        or str(evidence.project_global_id) != str(event.project_global_id)
        or str(evidence.gate_global_id) != str(event.gate_global_id)
        or str(evidence.requirement_global_id)
        != str(event.requirement_global_id)
        or str(evidence.requirement_key) != dependency.requirement_key
        or str(evidence.evidence_kind) != "release_baseline"
        or str(evidence.source_object_type) != "release_baseline"
        or str(evidence.source_global_id) != str(event.baseline_global_id)
        or int(evidence.source_version) != 1
        or str(evidence.source_hash) != event.baseline_snapshot_hash
        or str(gate.global_id) != str(event.gate_global_id)
        or str(gate.project_global_id) != str(event.project_global_id)
        or str(successor.global_id) != str(event.new_revision_global_id)
        or str(successor.tenant_id) != event.tenant_id
        or str(successor.project_global_id) != str(event.project_global_id)
        or str(successor.document_global_id)
        != str(dependency.input_document_global_id)
        or str(successor.predecessor_revision_global_id)
        != str(event.old_revision_global_id)
        or str(successor.snapshot_hash) != event.new_revision_snapshot_hash
    ):
        raise DocumentBaselineInputUnavailable()
    return event


class FrappeDocumentBaselineRepository(FrappeDocumentReleaseRepository):
    """Exact immutable baseline transactions over released P5 revisions."""

    def list_baselines(self, project_id: UUID) -> dict[str, Any] | None:
        project = self._authorized_project(project_id)
        if project is None:
            record_baseline_workspace_server_predicate(
                "P503_BASELINE_WORKSPACE_PROJECT_LOOKUP",
                exception_type="DocumentBaselineUnavailable",
            )
            return None
        policy_options = self._published_baseline_policy_options(project)
        with baseline_workspace_server_step(
            "P503_BASELINE_WORKSPACE_BASELINE_QUERY"
        ):
            names = frappe.get_all(
                "NPI Document Baseline",
                filters={
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                },
                pluck="name",
                order_by="created_at desc, global_id asc",
                limit_page_length=_MAX_BASELINES + 1,
            )
        if len(names) > _MAX_BASELINES:
            raise ValueError(
                "Persisted Document baseline collection exceeds its bound."
            )
        baselines = []
        for name in names:
            with baseline_workspace_server_step(
                "P503_BASELINE_WORKSPACE_BASELINE_LOAD"
            ):
                baselines.append(
                    self._validated_baseline(
                        project,
                        frappe.get_doc("NPI Document Baseline", name),
                    )
                )
        impacts = load_project_baseline_impacts(project)
        with baseline_workspace_server_step(
            "P503_BASELINE_WORKSPACE_REPOSITORY_RESPONSE"
        ):
            return {
                "project": {
                    "globalId": str(project.global_id),
                    "projectCode": str(project.business_code),
                    "projectName": str(project.title),
                },
                "permissions": {
                    "view": True,
                    "create": bool(
                        policy_options
                        and not document_baseline_routes_are_disabled()
                    ),
                },
                "policies": list(policy_options),
                "items": [self._baseline_response(value) for value in baselines],
                "impacts": [
                    document_baseline_impact_response(value) for value in impacts
                ],
            }

    def create_baseline(
        self,
        project_id: UUID,
        *,
        idempotency_key_hash: str,
        policy_global_id: UUID,
        policy_version: int,
        policy_snapshot_hash: str,
        label: str,
        members: Sequence[DocumentBaselineMemberPrecondition],
    ) -> DocumentCommandOutcome | None:
        project = self._locked_baseline_project(project_id)
        if project is None:
            return None
        if self._current_actor_member(project) is None:
            return None
        policy = self._load_exact_baseline_policy(
            project,
            policy_global_id=policy_global_id,
            policy_version=policy_version,
            snapshot_hash=policy_snapshot_hash,
            lock=True,
        )
        if not policy.permits_baseline(self.actor):
            from npi_core.documents.baseline_domain import (
                DocumentBaselineAuthorityUnavailable,
            )

            raise DocumentBaselineAuthorityUnavailable()
        payload = {
            "policyGlobalId": str(policy_global_id),
            "policyVersion": policy_version,
            "policySnapshotHash": policy_snapshot_hash,
            "label": label,
            "members": [
                {
                    "revisionId": str(value.revision_id),
                    "expectedRevisionSnapshotHash": (
                        value.expected_revision_snapshot_hash
                    ),
                    "expectedLifecycleVersion": value.expected_lifecycle_version,
                    "expectedReleaseSnapshotHash": (
                        value.expected_release_snapshot_hash
                    ),
                }
                for value in members
            ],
        }
        payload_hash = command_payload_hash(
            operation="baseline.create",
            actor=self.actor,
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            document_id=None,
            payload=payload,
        )
        receipt_key = self._receipt_key(
            project,
            idempotency_key_hash=idempotency_key_hash,
        )
        replay = self._baseline_replay(
            project,
            receipt_key=receipt_key,
            payload_hash=payload_hash,
        )
        if replay is not None:
            return DocumentCommandOutcome(replay, replayed=True)
        require_mutable_project(project)
        if (
            not members
            or len(members) > MAX_BASELINE_MEMBERS
            or len({value.revision_id for value in members}) != len(members)
        ):
            raise DocumentBaselineInputUnavailable()
        resolved = self._resolve_members(project, members)
        now = datetime.now(UTC)
        baseline = create_document_baseline(
            global_id=uuid4(),
            tenant_id=str(project.tenant_id),
            project_global_id=UUID(str(project.global_id)),
            label=label,
            policy=policy,
            members=resolved,
            actor=self.actor,
            now=now,
            request_id=self.request_id,
            trace_id=self.trace_id,
        )
        with _baseline_write_scope():
            receipt = self._insert_baseline_receipt(
                project,
                receipt_key=receipt_key,
                idempotency_key_hash=idempotency_key_hash,
                payload_hash=payload_hash,
                now=now,
            )
            baseline_document = self._insert_baseline(project, baseline)
            self._insert_members(project, baseline_document, baseline)
            self._append_audit(
                operation="document.baseline.create",
                global_id=baseline.global_id,
                object_version=1,
                result="created",
                summary={
                    "projectId": str(project_id),
                    "baselineId": str(baseline.global_id),
                    "baselineSnapshotHash": baseline.snapshot_hash,
                    "memberCount": len(baseline.members),
                    "policyGlobalId": str(policy.policy_global_id),
                    "policyVersion": policy.policy_version,
                    "requestId": self.request_id,
                },
            )
            response = {
                "projectId": str(project_id),
                "baseline": self._baseline_response(baseline),
            }
            self._seal_baseline_receipt(
                receipt,
                baseline_id=baseline.global_id,
                response=response,
                now=now,
            )
        return DocumentCommandOutcome(response)

    def _locked_baseline_project(self, project_id: UUID):
        try:
            project = frappe.get_doc(
                "NPI Engineering Project",
                str(project_id),
                for_update=True,
            )
        except frappe.DoesNotExistError:
            return None
        return (
            project
            if self._can_view_project(project, project_id)
            else None
        )

    def _published_baseline_policy_options(
        self,
        project,
    ) -> tuple[dict[str, Any], ...]:
        if (
            self.principal.is_external
            or "NPI API User" not in self.principal.roles
            or self._current_actor_member(project) is None
        ):
            return ()
        with baseline_workspace_server_step("P503_BASELINE_WORKSPACE_POLICY_QUERY"):
            rows = _bounded_documents(
                "NPI Document Baseline Policy Version",
                {
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "publication_state": DocumentBaselinePolicyState.PUBLISHED.value,
                },
                order_by="policy_key asc, policy_version desc, global_id asc",
                maximum=_MAX_POLICIES,
            )
        result = []
        for row in rows:
            try:
                with baseline_workspace_server_step(
                    "P503_BASELINE_WORKSPACE_POLICY_ROW"
                ):
                    policy_global_id = UUID(str(row.policy_global_id))
                    policy_version = int(row.policy_version)
                    snapshot_hash = str(row.snapshot_hash)
                policy = self._load_exact_baseline_policy(
                    project,
                    policy_global_id=policy_global_id,
                    policy_version=policy_version,
                    snapshot_hash=snapshot_hash,
                    lock=False,
                )
            except DocumentBaselinePolicyUnavailable:
                continue
            except Exception as error:
                record_baseline_workspace_server_failure(
                    "P503_BASELINE_WORKSPACE_POLICY_LOAD",
                    error,
                )
                raise
            if policy.permits_baseline(self.actor):
                result.append(
                    {
                        "globalId": str(policy.policy_global_id),
                        "version": policy.policy_version,
                        "snapshotHash": policy.snapshot_hash,
                        "key": policy.policy_key,
                        "title": policy.title,
                    }
                )
        return tuple(result)

    @staticmethod
    def _load_exact_baseline_policy(
        project,
        *,
        policy_global_id: UUID,
        policy_version: int,
        snapshot_hash: str,
        lock: bool,
    ) -> DocumentBaselinePolicyVersion:
        try:
            root = (
                frappe.get_doc(
                    "NPI Document Baseline Policy",
                    str(policy_global_id),
                    for_update=True,
                )
                if lock
                else frappe.get_doc(
                    "NPI Document Baseline Policy",
                    str(policy_global_id),
                )
            )
        except frappe.DoesNotExistError as error:
            raise DocumentBaselinePolicyUnavailable() from error
        version_name = frappe.db.get_value(
            "NPI Document Baseline Policy Version",
            {
                "policy_global_id": str(policy_global_id),
                "policy_version": policy_version,
            },
            "name",
        )
        if not version_name:
            raise DocumentBaselinePolicyUnavailable()
        try:
            row = (
                frappe.get_doc(
                    "NPI Document Baseline Policy Version",
                    str(version_name),
                    for_update=True,
                )
                if lock
                else frappe.get_doc(
                    "NPI Document Baseline Policy Version",
                    str(version_name),
                )
            )
            policy = baseline_policy_value(row)
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise DocumentBaselinePolicyUnavailable() from error
        if (
            str(root.global_id) != str(policy_global_id)
            or str(root.tenant_id) != str(project.tenant_id)
            or str(root.project_global_id) != str(project.global_id)
            or int(root.enabled or 0) != 1
            or policy.policy_global_id != policy_global_id
            or policy.policy_version != policy_version
            or policy.state is not DocumentBaselinePolicyState.PUBLISHED
            or policy.tenant_id != str(project.tenant_id)
            or str(policy.project_global_id) != str(project.global_id)
            or policy.snapshot_hash != snapshot_hash
        ):
            raise DocumentBaselinePolicyUnavailable()
        return policy

    def _resolve_members(
        self,
        project,
        preconditions: Sequence[DocumentBaselineMemberPrecondition],
    ) -> tuple[DocumentBaselineMember, ...]:
        by_id = {value.revision_id: value for value in preconditions}
        resolved: dict[UUID, tuple[Any, Any, DocumentReviewEvidence]] = {}
        for revision_id in sorted(by_id, key=str):
            precondition = by_id[revision_id]
            revision, document, lifecycle, evidence = self._resolve_member_input(
                project,
                precondition,
            )
            resolved[revision_id] = (revision, lifecycle, evidence)
            if not _document_matches_project(
                document,
                project,
                UUID(str(document.global_id)),
            ):
                raise DocumentBaselineInputUnavailable()
        members = []
        for sequence, precondition in enumerate(preconditions, start=1):
            revision, lifecycle, evidence = resolved[precondition.revision_id]
            members.append(
                DocumentBaselineMember(
                    global_id=uuid4(),
                    sequence=sequence,
                    document_global_id=UUID(str(revision.document_global_id)),
                    revision_global_id=UUID(str(revision.global_id)),
                    major=int(revision.major),
                    minor=int(revision.minor),
                    revision_snapshot_hash=str(revision.snapshot_hash),
                    lifecycle_version=lifecycle.version,
                    release_event_global_id=lifecycle.release_event_global_id,
                    release_snapshot_hash=lifecycle.release_snapshot_hash,
                    release_evidence=evidence,
                )
            )
        return tuple(members)

    def _resolve_member_input(
        self,
        project,
        precondition: DocumentBaselineMemberPrecondition,
    ) -> tuple[Any, Any, Any, DocumentReviewEvidence]:
        try:
            revision = frappe.get_doc(
                "NPI Document Revision",
                str(precondition.revision_id),
                for_update=True,
            )
            document = frappe.get_doc(
                "NPI Controlled Document",
                str(revision.document_global_id),
                for_update=True,
            )
            lifecycle_document = frappe.get_doc(
                "NPI Document Revision Lifecycle",
                str(precondition.revision_id),
                for_update=True,
            )
            lifecycle = lifecycle_value(lifecycle_document)
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise DocumentBaselineInputUnavailable() from error
        if (
            str(revision.global_id) != str(precondition.revision_id)
            or str(revision.tenant_id) != str(project.tenant_id)
            or str(revision.project_global_id) != str(project.global_id)
            or str(revision.snapshot_hash)
            != precondition.expected_revision_snapshot_hash
            or lifecycle.revision_global_id != precondition.revision_id
            or lifecycle.state is not DocumentLifecycleState.RELEASED
            or lifecycle.version != precondition.expected_lifecycle_version
            or lifecycle.release_snapshot_hash
            != precondition.expected_release_snapshot_hash
            or lifecycle.release_event_global_id is None
            or lifecycle.approved_cycle_global_id is None
        ):
            raise DocumentBaselineInputUnavailable()
        try:
            event_document = frappe.get_doc(
                "NPI Document Lifecycle Event",
                str(lifecycle.release_event_global_id),
                for_update=True,
            )
            event = lifecycle_event_value(event_document)
            cycle_document = frappe.get_doc(
                "NPI Document Review Cycle",
                str(lifecycle.approved_cycle_global_id),
                for_update=True,
            )
            cycle = review_cycle_value(cycle_document)
        except (
            frappe.DoesNotExistError,
            RequestValidationFailed,
            TypeError,
            ValueError,
        ) as error:
            raise DocumentBaselineInputUnavailable() from error
        if (
            event.event_type is not DocumentLifecycleEventType.RELEASED
            or event.revision_global_id != precondition.revision_id
            or event.cycle_global_id != cycle.global_id
            or event.evidence_snapshot_hash != cycle.evidence.snapshot_hash
            or cycle.revision_global_id != precondition.revision_id
            or cycle.evidence.revision_snapshot_hash != str(revision.snapshot_hash)
        ):
            raise DocumentBaselineInputUnavailable()
        self._validate_released_files(
            project,
            document,
            revision,
            cycle.evidence,
        )
        return revision, document, lifecycle, cycle.evidence

    def _validate_released_files(
        self,
        project,
        document,
        revision,
        evidence: DocumentReviewEvidence,
    ) -> None:
        names = frappe.get_all(
            "NPI Document Revision File",
            filters={
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "document_global_id": str(document.global_id),
                "document_revision_global_id": str(revision.global_id),
            },
            pluck="name",
            order_by="global_id asc",
            limit_page_length=MAX_BASELINE_MEMBERS + 1,
        )
        if not names or len(names) > MAX_BASELINE_MEMBERS:
            raise DocumentBaselineInputUnavailable()
        associations = [
            frappe.get_doc("NPI Document Revision File", name, for_update=True)
            for name in names
        ]
        evidence_by_association = {
            value.association_global_id: value for value in evidence.files
        }
        if len(evidence_by_association) != len(associations):
            raise DocumentBaselineInputUnavailable()
        for association in associations:
            expected = evidence_by_association.get(UUID(str(association.global_id)))
            if expected is None:
                raise DocumentBaselineInputUnavailable()
            try:
                file_revision = frappe.get_doc(
                    "NPI File Revision",
                    str(association.file_revision_global_id),
                    for_update=True,
                )
                observed = self._release_file_evidence(
                    association,
                    file_revision,
                )
            except (
                frappe.DoesNotExistError,
                DocumentReleaseIntegrityBlocked,
                RequestValidationFailed,
                TypeError,
                ValueError,
            ) as error:
                raise DocumentBaselineInputUnavailable() from error
            if (
                not _association_matches_live_file(
                    project,
                    document,
                    revision,
                    association,
                    file_revision,
                )
                or int(file_revision.released or 0) != 1
                or int(file_revision.optimistic_version)
                < expected.file_optimistic_version + 1
                or not _stable_file_evidence_matches(observed, expected)
            ):
                raise DocumentBaselineInputUnavailable()

    def _receipt_key(self, project, *, idempotency_key_hash: str) -> str:
        return sha256_json(
            {
                "tenantId": str(project.tenant_id),
                "projectGlobalId": str(project.global_id),
                "actorUserId": self.actor.casefold(),
                "operation": "baseline.create",
                "idempotencyKeyHash": idempotency_key_hash,
            }
        )

    def _baseline_replay(
        self,
        project,
        *,
        receipt_key: str,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        row = frappe.db.get_value(
            "NPI Baseline Command Idempotency",
            {"receipt_key": receipt_key},
            [
                "tenant_id",
                "project_global_id",
                "actor_user_id",
                "operation",
                "payload_hash",
                "response_payload",
                "response_hash",
                "sealed",
            ],
            as_dict=True,
            for_update=True,
        )
        if not row:
            return None
        response = _json_object(_record_value(row, "response_payload"))
        if (
            str(_record_value(row, "tenant_id")) != str(project.tenant_id)
            or str(_record_value(row, "project_global_id"))
            != str(project.global_id)
            or str(_record_value(row, "actor_user_id")) != self.actor
            or str(_record_value(row, "operation")) != "baseline.create"
            or str(_record_value(row, "payload_hash")) != payload_hash
            or int(_record_value(row, "sealed") or 0) != 1
            or str(_record_value(row, "response_hash")) != sha256_json(response)
        ):
            raise DocumentBaselineIdempotencyConflict()
        return response

    def _insert_baseline_receipt(
        self,
        project,
        *,
        receipt_key: str,
        idempotency_key_hash: str,
        payload_hash: str,
        now: datetime,
    ):
        try:
            return frappe.get_doc(
                {
                    "doctype": "NPI Baseline Command Idempotency",
                    "global_id": str(uuid4()),
                    "receipt_key": receipt_key,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "actor_user_id": self.actor,
                    "operation": "baseline.create",
                    "idempotency_key_hash": idempotency_key_hash,
                    "payload_hash": payload_hash,
                    "baseline_global_id": None,
                    "response_payload": {},
                    "response_hash": None,
                    "sealed": 0,
                    "created_at": _database_datetime(now),
                    "updated_at": _database_datetime(now),
                }
            ).insert()
        except (
            frappe.UniqueValidationError,
            frappe.DuplicateEntryError,
        ) as error:
            raise DocumentBaselineIdempotencyConflict() from error

    @staticmethod
    def _insert_baseline(project, value: DocumentBaseline):
        return frappe.get_doc(
            {
                "doctype": "NPI Document Baseline",
                "global_id": str(value.global_id),
                "tenant_id": str(project.tenant_id),
                "project_global_id": str(project.global_id),
                "label": value.label,
                "baseline_version": 1,
                "policy_global_id": str(value.policy_ref.global_id),
                "policy_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "member_count": len(value.members),
                "baseline_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
                "created_by_user_id": value.created_by_user_id,
                "created_at": _database_datetime(value.created_at),
                "request_id": value.request_id,
                "trace_id": value.trace_id,
            }
        ).insert()

    @staticmethod
    def _insert_members(project, baseline_document, value: DocumentBaseline) -> None:
        for member in value.members:
            frappe.get_doc(
                {
                    "doctype": "NPI Document Baseline Member",
                    "global_id": str(member.global_id),
                    "member_key": f"{value.global_id}:{member.sequence}",
                    "document_baseline": str(value.global_id),
                    "baseline_global_id": str(value.global_id),
                    "baseline_snapshot_hash": value.snapshot_hash,
                    "tenant_id": str(project.tenant_id),
                    "project_global_id": str(project.global_id),
                    "member_sequence": member.sequence,
                    "controlled_document": str(member.document_global_id),
                    "document_global_id": str(member.document_global_id),
                    "document_revision": str(member.revision_global_id),
                    "revision_global_id": str(member.revision_global_id),
                    "major": member.major,
                    "minor": member.minor,
                    "revision_snapshot_hash": member.revision_snapshot_hash,
                    "lifecycle_version": member.lifecycle_version,
                    "release_event_global_id": str(member.release_event_global_id),
                    "release_snapshot_hash": member.release_snapshot_hash,
                    "release_evidence": member.release_evidence.canonical_dict(),
                    "member_snapshot": member.canonical_dict(),
                    "member_hash": member.member_hash,
                    "created_at": baseline_document.created_at,
                }
            ).insert()

    @staticmethod
    def _seal_baseline_receipt(
        receipt,
        *,
        baseline_id: UUID,
        response: Mapping[str, object],
        now: datetime,
    ) -> None:
        receipt.baseline_global_id = str(baseline_id)
        receipt.response_payload = dict(response)
        receipt.response_hash = sha256_json(response)
        receipt.sealed = 1
        receipt.updated_at = _database_datetime(now)
        receipt.save()

    def _validated_baseline(self, project, document) -> DocumentBaseline:
        return _validated_baseline_value(
            project,
            document,
            lock_members=False,
        )

    @staticmethod
    def _baseline_response(value: DocumentBaseline) -> dict[str, Any]:
        return document_baseline_response(value)


def _validated_baseline_value(
    project,
    document,
    *,
    lock_members: bool,
) -> DocumentBaseline:
    names = frappe.get_all(
        "NPI Document Baseline Member",
        filters={"baseline_global_id": str(document.global_id)},
        pluck="name",
        order_by="member_sequence asc, global_id asc",
        limit_page_length=MAX_BASELINE_MEMBERS + 1,
    )
    if not names or len(names) > MAX_BASELINE_MEMBERS:
        raise DocumentBaselineInputUnavailable()
    member_rows = [
        frappe.get_doc(
            "NPI Document Baseline Member",
            name,
            for_update=lock_members,
        )
        for name in names
    ]
    try:
        members = tuple(baseline_member_value(row) for row in member_rows)
        value = DocumentBaseline(
            global_id=UUID(str(document.global_id)),
            tenant_id=str(document.tenant_id),
            project_global_id=UUID(str(document.project_global_id)),
            label=str(document.label),
            policy_ref=DocumentBaselinePolicyReference(
                UUID(str(document.policy_global_id)),
                int(document.policy_version),
                str(document.policy_snapshot_hash),
            ),
            members=members,
            created_by_user_id=str(document.created_by_user_id),
            created_at=_datetime_value(document.created_at),
            request_id=str(document.request_id),
            trace_id=str(document.trace_id),
            version=int(document.baseline_version),
            snapshot_hash=str(document.snapshot_hash),
        )
    except (RequestValidationFailed, TypeError, ValueError) as error:
        raise DocumentBaselineInputUnavailable() from error
    supplied_snapshot = _json_object(document.baseline_snapshot)
    if (
        str(document.tenant_id) != str(project.tenant_id)
        or str(document.project_global_id) != str(project.global_id)
        or int(document.member_count) != len(members)
        or supplied_snapshot != value.snapshot_payload()
        or any(
            str(row.tenant_id) != str(project.tenant_id)
            or str(row.project_global_id) != str(project.global_id)
            or str(row.document_baseline) != str(value.global_id)
            or str(row.baseline_global_id) != str(value.global_id)
            or _json_object(row.member_snapshot) != member.canonical_dict()
            or str(row.member_hash) != member.member_hash
            or str(row.baseline_snapshot_hash) != value.snapshot_hash
            for row, member in zip(member_rows, members, strict=True)
        )
    ):
        raise DocumentBaselineInputUnavailable()
    return value


def _stable_file_evidence_matches(
    observed: DocumentReleaseFileEvidence,
    expected: DocumentReleaseFileEvidence,
) -> bool:
    return bool(
        observed.association_global_id == expected.association_global_id
        and observed.association_snapshot_hash
        == expected.association_snapshot_hash
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


@contextmanager
def _baseline_write_scope() -> Iterator[None]:
    missing = object()
    previous = getattr(frappe.flags, "npi_audit_append", missing)
    frappe.flags.npi_audit_append = True
    try:
        with document_baseline_command_write():
            yield
    finally:
        if previous is missing:
            try:
                delattr(frappe.flags, "npi_audit_append")
            except AttributeError:
                pass
        else:
            frappe.flags.npi_audit_append = previous
