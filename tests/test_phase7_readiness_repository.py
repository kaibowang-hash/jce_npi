from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4, uuid5


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
OTHER_PROJECT_ID = UUID("3e96f421-5872-4c96-a0dd-718d5c970a21")
MEMBER_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
OTHER_MEMBER_ID = UUID("39e933a3-3954-4a96-9400-2be1987ae370")
GATE_G6_ID = UUID("49e933a3-3954-4a96-9400-2be1987ae370")
GATE_G7_ID = UUID("59e933a3-3954-4a96-9400-2be1987ae370")
OTHER_GATE_G6_ID = UUID("69e933a3-3954-4a96-9400-2be1987ae370")
REQUEST_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
SHA = "a" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(self, owner: "Phase7ReadinessRepositoryTest", values: dict[str, Any]):
        super().__init__(values)
        object.__setattr__(self, "_owner", owner)

    def insert(self):
        name = self.get("name") or self.get("event_id") or self.get("global_id")
        if name is None:
            raise AssertionError(f"Fake {self.get('doctype')} document has no identity")
        self.name = str(name)
        event = ("insert", str(self.doctype), self.name)
        self._owner.events.append(event)
        if self._owner.fail_on == event[:2]:
            raise RuntimeError(f"Injected failure at {event[0]} {event[1]}")
        bucket = self._owner.documents.setdefault(str(self.doctype), {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        bucket[self.name] = self
        return self

    def save(self):
        event = ("save", str(self.doctype), str(self.name))
        self._owner.events.append(event)
        if self._owner.fail_on == event[:2]:
            raise RuntimeError(f"Injected failure at {event[0]} {event[1]}")
        self._owner.documents.setdefault(str(self.doctype), {})[str(self.name)] = self
        return self


class FakeDatabase:
    def __init__(self, owner: "Phase7ReadinessRepositoryTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def exists(self, doctype: str, filters: dict[str, Any]) -> bool:
        return bool(self.owner.matching(doctype, filters))

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fields: object,
        *,
        as_dict: bool = False,
        for_update: bool = False,
    ):
        del for_update
        if isinstance(name_or_filters, dict):
            matches = self.owner.matching(doctype, name_or_filters)
            document = matches[0] if matches else None
        else:
            document = self.owner.documents.get(doctype, {}).get(str(name_or_filters))
        if document is None:
            return None
        if isinstance(fields, list):
            values = AttrDict({field: document.get(field) for field in fields})
            return values if as_dict else tuple(values.values())
        return document.get(str(fields))

    def rollback(self) -> None:
        self.rollback_count += 1


class Phase7ReadinessRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.readiness.frappe_validation",
        "npi_core.readiness.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.events: list[tuple[str, str, str]] = []
        self.fail_on: tuple[str, str] | None = None
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        self.frappe.PermissionError = type("PermissionError", (Exception,), {})
        self.frappe.ValidationError = type("ValidationError", (Exception,), {})
        self.frappe.db = FakeDatabase(self)
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = self.get_all
        self.frappe.throw = self.frappe_throw
        sys.modules["frappe"] = self.frappe

        self.module = importlib.import_module("npi_core.readiness.frappe_repository")
        self.domain = importlib.import_module("npi_core.readiness.domain")
        self.security = importlib.import_module("npi_core.foundation.security")
        self.errors = importlib.import_module("npi_core.foundation.errors")
        self.source_validation = importlib.import_module(
            "npi_core.readiness.request_validation"
        )
        self.source_resolver = importlib.import_module(
            "npi_core.readiness.source_resolver"
        )
        self.add(
            "User",
            {
                "name": "admin@example.invalid",
                "enabled": 1,
                "user_type": "System User",
            },
        )
        self.repository = self.repository_for()
        self.project = self.seed_project(PROJECT_ID)
        self.member = self.seed_member(PROJECT_ID, MEMBER_ID)
        self.seed_gate(PROJECT_ID, "G6", GATE_G6_ID)
        self.seed_gate(PROJECT_ID, "G7", GATE_G7_ID)

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved_modules[name] is not None:
                sys.modules[name] = self.saved_modules[name]

    @staticmethod
    def frappe_throw(message: str, exception_type: type[Exception] = Exception):
        raise exception_type(message)

    def repository_for(
        self,
        *,
        user_id: str = "admin@example.invalid",
        roles: frozenset[str] = frozenset({"NPI API User", "System Manager"}),
        tenant_id: str | None = "TENANT-A",
        external: bool = False,
        request_id: str = REQUEST_ID,
    ):
        return self.module.FrappeReadinessRepository(
            principal=self.security.Principal(
                user_id=user_id,
                roles=roles,
                is_external=external,
                tenant_id=tenant_id,
            ),
            request_id=request_id,
            trace_id="trace-p7-05-repository",
        )

    def add(self, doctype: str, values: dict[str, Any]) -> FakeDocument:
        return FakeDocument(self, {"doctype": doctype, **values}).insert()

    def get_doc(self, doctype_or_values, name: str | None = None, **_kwargs: Any):
        if isinstance(doctype_or_values, dict):
            return FakeDocument(self, dict(doctype_or_values))
        document = self.documents.get(str(doctype_or_values), {}).get(str(name))
        if document is None:
            raise self.frappe.DoesNotExistError()
        return document

    def matching(self, doctype: str, filters: dict[str, Any]) -> list[FakeDocument]:
        return [
            document
            for document in self.documents.get(doctype, {}).values()
            if all(
                self._matches(document.get(field), expected)
                for field, expected in filters.items()
            )
        ]

    @staticmethod
    def _matches(actual: object, expected: object) -> bool:
        if isinstance(expected, list) and len(expected) == 2:
            operator, value = expected
            if operator == "=":
                return str(actual) == str(value)
            if operator == "!=":
                return str(actual) != str(value)
        return str(actual) == str(expected)

    def get_all(
        self,
        doctype: str,
        *,
        filters: dict[str, Any],
        pluck: str | None = None,
        fields: list[str] | None = None,
        order_by: str | None = None,
        limit_page_length: int | None = None,
    ):
        documents = self.matching(doctype, filters)
        if order_by:
            clauses = [part.strip().split() for part in order_by.split(",")]
            for clause in reversed(clauses):
                field = clause[0]
                reverse = len(clause) > 1 and clause[1].casefold() == "desc"
                documents.sort(
                    key=lambda item: (item.get(field) is None, str(item.get(field))),
                    reverse=reverse,
                )
        if limit_page_length is not None:
            documents = documents[:limit_page_length]
        if pluck:
            return [document.get(pluck) for document in documents]
        if fields:
            return [
                AttrDict({field: document.get(field) for field in fields})
                for document in documents
            ]
        return documents

    def seed_project(
        self,
        project_id: UUID,
        *,
        tenant_id: str = "TENANT-A",
        owner: str = "owner@example.invalid",
    ) -> FakeDocument:
        return self.add(
            "NPI Engineering Project",
            {
                "global_id": str(project_id),
                "tenant_id": tenant_id,
                "owner_user_id": owner,
                "lifecycle_state": "active",
                "optimistic_version": 3,
                "project_type": "new_tool",
                "references": [],
            },
        )

    def seed_member(
        self,
        project_id: UUID,
        member_id: UUID,
        *,
        user_id: str = "member@example.invalid",
        tenant_id: str = "TENANT-A",
    ) -> FakeDocument:
        member = self.add(
            "NPI Project Member",
            {
                "global_id": str(member_id),
                "tenant_id": tenant_id,
                "project_global_id": str(project_id),
                "user_id": user_id,
                "effective_from": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
                "effective_to": None,
                "optimistic_version": 2,
            },
        )
        if user_id not in self.documents.get("User", {}):
            self.add(
                "User",
                {
                    "name": user_id,
                    "enabled": 1,
                    "user_type": "System User",
                },
            )
        return member

    def seed_gate(
        self,
        project_id: UUID,
        gate_key: str,
        gate_id: UUID,
    ) -> FakeDocument:
        return self.add(
            "NPI Gate Shell",
            {
                "global_id": str(gate_id),
                "project_global_id": str(project_id),
                "gate_key": gate_key,
                "optimistic_version": 2,
                "template_gate_snapshot": {"gateKey": gate_key},
            },
        )

    def seed_released_document_source(self) -> AttrDict:
        from npi_core.documents.release_domain import (
            DocumentReleaseFileEvidence,
            DocumentReleasePolicyState,
            DocumentReleasePolicyVersion,
            DocumentReviewDecision,
            DocumentReviewEvidence,
            DocumentReviewerAssignment,
            confirm_document_review,
            release_document_revision,
            sha256_json,
            submit_document_review,
        )

        now = datetime(2026, 8, 12, 4, 0, tzinfo=UTC)
        document_id = uuid4()
        revision_id = uuid4()
        association_id = uuid4()
        file_revision_id = uuid4()
        file_document_id = uuid4()
        policy_id = uuid4()
        policy_revision_id = uuid4()
        cycle_id = uuid4()
        submitted_event_id = uuid4()
        approved_event_id = uuid4()
        release_event_id = uuid4()

        revision_snapshot = {
            "schemaVersion": 1,
            "globalId": str(revision_id),
            "documentGlobalId": str(document_id),
            "major": 1,
            "minor": 0,
            "reason": "Freeze the exact released readiness source.",
            "effectiveDate": None,
            "predecessorRevisionId": None,
            "state": "draft",
            "documentPolicyRef": {
                "globalId": str(uuid4()),
                "version": 1,
                "snapshotHash": "1" * 64,
            },
            "lockRef": {
                "globalId": str(uuid4()),
                "version": 1,
                "holderUserId": "author@example.invalid",
            },
            "file": {"globalId": str(file_revision_id)},
            "createdByUserId": "author@example.invalid",
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "requestId": "request-readiness-release-revision",
            "traceId": "trace-readiness-release-revision",
        }
        revision_hash = self.module._payload_hash(revision_snapshot)
        file_evidence = DocumentReleaseFileEvidence(
            association_global_id=association_id,
            association_snapshot_hash="2" * 64,
            file_revision_global_id=file_revision_id,
            file_document_global_id=file_document_id,
            file_optimistic_version=2,
            frappe_file_id="released-file-identity",
            frappe_content_hash="3" * 32,
            file_name="released-drawing.pdf",
            mime_type="application/pdf",
            size_bytes=512,
            sha256="4" * 64,
            scan_state="clean",
            scan_observed_at=now,
            uploaded_by_user_id="author@example.invalid",
            uploaded_at=now,
        )
        evidence = DocumentReviewEvidence(
            revision_global_id=revision_id,
            revision_snapshot_hash=revision_hash,
            files=(file_evidence,),
        )
        policy = DocumentReleasePolicyVersion(
            global_id=policy_revision_id,
            policy_global_id=policy_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            policy_key="readiness_release_policy",
            policy_version=1,
            title="Readiness release policy",
            state=DocumentReleasePolicyState.PUBLISHED,
            submitter_user_ids=("submitter@example.invalid",),
            reviewer_assignments=(
                DocumentReviewerAssignment(
                    "reviewer_one",
                    "reviewer@example.invalid",
                ),
            ),
            required_approval_count=1,
            release_authority_user_ids=("releaser@example.invalid",),
            supersede_authority_user_ids=("superseder@example.invalid",),
            obsolete_authority_user_ids=("obsoleter@example.invalid",),
        )
        submitted = submit_document_review(
            lifecycle=None,
            policy=policy,
            evidence=evidence,
            cycle_global_id=cycle_id,
            event_global_id=submitted_event_id,
            cycle_number=1,
            prior_rejected_cycle_global_id=None,
            actor="submitter@example.invalid",
            now=now,
            request_id="request-readiness-release-submit",
            trace_id="trace-readiness-release-submit",
        )
        approved = confirm_document_review(
            lifecycle=submitted.lifecycle,
            cycle=submitted.cycle,
            policy=policy,
            decision=DocumentReviewDecision.APPROVE,
            existing_approval_hashes=(),
            confirmation_global_id=uuid4(),
            event_global_id=approved_event_id,
            actor="reviewer@example.invalid",
            reason=None,
            now=now,
            request_id="request-readiness-release-approve",
            trace_id="trace-readiness-release-approve",
        )
        release_hash = sha256_json(
            {
                "schemaVersion": 1,
                "revisionGlobalId": str(revision_id),
                "reviewEvidenceSnapshotHash": evidence.snapshot_hash,
                "releasePolicyRef": policy.reference.canonical_dict(),
                "approvalConfirmationHashes": [
                    approved.confirmation.evidence_hash
                ],
                "files": [
                    {
                        "fileRevisionGlobalId": str(file_revision_id),
                        "fromOptimisticVersion": 2,
                        "toOptimisticVersion": 3,
                        "sha256": file_evidence.sha256,
                    }
                ],
            }
        )
        released = release_document_revision(
            lifecycle=approved.lifecycle,
            cycle=submitted.cycle,
            policy=policy,
            release_snapshot_hash=release_hash,
            approval_confirmation_hashes=(approved.confirmation.evidence_hash,),
            confirmation_global_id=uuid4(),
            event_global_id=release_event_id,
            actor="releaser@example.invalid",
            now=now,
            request_id="request-readiness-release-final",
            trace_id="trace-readiness-release-final",
        )

        parent = self.add(
            "NPI Controlled Document",
            {
                "global_id": str(document_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
            },
        )
        revision = self.add(
            "NPI Document Revision",
            {
                "global_id": str(revision_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "controlled_document": str(document_id),
                "document_global_id": str(document_id),
                "major": 1,
                "minor": 0,
                "revision_key": f"{document_id}:1.0",
                "reason": revision_snapshot["reason"],
                "effective_date": None,
                "predecessor_revision_global_id": None,
                "revision_state": "draft",
                "revision_snapshot": revision_snapshot,
                "snapshot_hash": revision_hash,
                "optimistic_version": 1,
            },
        )
        lifecycle = self.add(
            "NPI Document Revision Lifecycle",
            {
                "global_id": str(revision_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(document_id),
                "document_revision": str(revision_id),
                "revision_global_id": str(revision_id),
                "current_state": released.lifecycle.state.value,
                "lifecycle_version": released.lifecycle.version,
                "active_cycle_global_id": None,
                "approved_cycle_global_id": str(cycle_id),
                "approved_event_global_id": str(approved_event_id),
                "release_event_global_id": str(release_event_id),
                "release_snapshot_hash": release_hash,
                "replacement_revision_global_id": None,
                "replacement_effective_date": None,
                "terminal_event_global_id": None,
                "last_event_global_id": str(release_event_id),
            },
        )

        def add_event(value):
            return self.add(
                "NPI Document Lifecycle Event",
                {
                    "global_id": str(value.global_id),
                    "tenant_id": "TENANT-A",
                    "project_global_id": str(PROJECT_ID),
                    "document_global_id": str(document_id),
                    "document_revision": str(revision_id),
                    "revision_global_id": str(revision_id),
                    "event_type": value.event_type.value,
                    "from_state": value.from_state.value,
                    "to_state": value.to_state.value,
                    "from_version": value.from_version,
                    "to_version": value.to_version,
                    "review_cycle": str(cycle_id),
                    "cycle_global_id": str(cycle_id),
                    "policy_global_id": str(policy_id),
                    "policy_version": policy.policy_version,
                    "policy_snapshot_hash": policy.snapshot_hash,
                    "evidence_snapshot_hash": value.evidence_snapshot_hash,
                    "confirmation_hashes": list(value.confirmation_hashes),
                    "replacement_revision_global_id": None,
                    "replacement_effective_date": None,
                    "actor_user_id": value.actor_user_id,
                    "occurred_at": value.occurred_at,
                    "request_id": value.request_id,
                    "trace_id": value.trace_id,
                    "event_snapshot": value.event_payload(),
                    "event_hash": value.event_hash,
                },
            )

        approved_event = add_event(approved.event)
        release_event = add_event(released.event)
        cycle = self.add(
            "NPI Document Review Cycle",
            {
                "global_id": str(cycle_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(document_id),
                "document_revision": str(revision_id),
                "revision_global_id": str(revision_id),
                "cycle_number": submitted.cycle.cycle_number,
                "policy_global_id": str(policy_id),
                "policy_version": policy.policy_version,
                "policy_snapshot_hash": policy.snapshot_hash,
                "review_evidence": evidence.canonical_dict(),
                "evidence_snapshot_hash": evidence.snapshot_hash,
                "reviewer_assignments": [
                    value.canonical_dict()
                    for value in submitted.cycle.reviewer_assignments
                ],
                "required_approval_count": 1,
                "prior_rejected_cycle_global_id": None,
                "submitted_by_user_id": submitted.cycle.submitted_by_user_id,
                "submitted_at": submitted.cycle.submitted_at,
                "request_id": submitted.cycle.request_id,
                "trace_id": submitted.cycle.trace_id,
                "cycle_snapshot": submitted.cycle.snapshot_payload(),
                "snapshot_hash": submitted.cycle.snapshot_hash,
            },
        )
        self.add(
            "NPI Document Release Policy",
            {
                "global_id": str(policy_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "enabled": 1,
            },
        )
        policy_document = self.add(
            "NPI Document Release Policy Version",
            {
                "global_id": str(policy.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "policy_global_id": str(policy.policy_global_id),
                "policy_key": policy.policy_key,
                "policy_version": policy.policy_version,
                "title": policy.title,
                "publication_state": policy.state.value,
                "submitter_user_ids": list(policy.submitter_user_ids),
                "reviewer_assignments": [
                    value.canonical_dict()
                    for value in policy.reviewer_assignments
                ],
                "required_approval_count": policy.required_approval_count,
                "release_authority_user_ids": list(
                    policy.release_authority_user_ids
                ),
                "supersede_authority_user_ids": list(
                    policy.supersede_authority_user_ids
                ),
                "obsolete_authority_user_ids": list(
                    policy.obsolete_authority_user_ids
                ),
                "confirmation_method": policy.confirmation_method,
                "required_scan_state": policy.required_scan_state,
                "require_live_private_identity": 1,
                "require_sha256_match": 1,
                "supersede_requires_released_successor": 1,
                "supersede_requires_later_revision": 1,
                "supersede_requires_successor_effective_date": 1,
                "policy_snapshot": policy.snapshot_payload(),
                "snapshot_hash": policy.snapshot_hash,
            },
        )

        def add_confirmation(value):
            return self.add(
                "NPI Document Confirmation",
                {
                    "global_id": str(value.global_id),
                    "confirmation_key": value.confirmation_key,
                    "tenant_id": "TENANT-A",
                    "project_global_id": str(PROJECT_ID),
                    "document_global_id": str(document_id),
                    "document_revision": str(revision_id),
                    "revision_global_id": str(revision_id),
                    "review_cycle": str(cycle_id),
                    "cycle_global_id": str(cycle_id),
                    "policy_global_id": str(policy_id),
                    "policy_version": policy.policy_version,
                    "policy_snapshot_hash": policy.snapshot_hash,
                    "evidence_snapshot_hash": value.evidence_snapshot_hash,
                    "confirmation_type": value.confirmation_type.value,
                    "actor_user_id": value.actor_user_id,
                    "authority_slot": value.authority_slot,
                    "confirmation_method": value.confirmation_method,
                    "confirmation_intent": value.confirmation_intent,
                    "confirmed": 1,
                    "reason": value.reason,
                    "confirmed_at": value.confirmed_at,
                    "request_id": value.request_id,
                    "trace_id": value.trace_id,
                    "confirmation_evidence": value.evidence_payload(),
                    "evidence_hash": value.evidence_hash,
                },
            )

        approval_confirmation = add_confirmation(approved.confirmation)
        release_confirmation = add_confirmation(released.confirmation)
        association = self.add(
            "NPI Document Revision File",
            {
                "global_id": str(association_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(document_id),
                "document_revision": str(revision_id),
                "document_revision_global_id": str(revision_id),
                "file_revision_global_id": str(file_revision_id),
                "live_identity_matches": True,
                "observed_evidence": file_evidence,
            },
        )
        file_revision = self.add(
            "NPI File Revision",
            {
                "global_id": str(file_revision_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(file_document_id),
                "released": 1,
                "optimistic_version": 3,
            },
        )

        document_module = types.ModuleType("npi_core.documents.frappe_repository")
        document_module._association_matches_live_file = (
            lambda _project, _parent, _revision, selected, _file: bool(
                selected.get("live_identity_matches")
            )
        )
        release_module = types.ModuleType("npi_core.documents.release_repository")

        class ReleaseRepositoryStub:
            @staticmethod
            def _release_file_evidence(selected, _file):
                return selected.observed_evidence

        release_module.FrappeDocumentReleaseRepository = ReleaseRepositoryStub
        query = self.source_resolver.ExactSourceQuery(
            kind=self.domain.ReadinessSourceKind.RELEASED_DOCUMENT,
            global_id=revision_id,
            source_version=released.lifecycle.version,
            snapshot_hash=release_hash,
        )
        return AttrDict(
            context=self.source_resolver.SourceResolutionContext(
                "TENANT-A", PROJECT_ID
            ),
            query=query,
            revision=revision,
            lifecycle=lifecycle,
            approved_event=approved_event,
            release_event=release_event,
            cycle=cycle,
            policy_document=policy_document,
            approval_confirmation=approval_confirmation,
            release_confirmation=release_confirmation,
            association=association,
            file_revision=file_revision,
            file_evidence=file_evidence,
            parent=parent,
            modules={
                "npi_core.documents.frappe_repository": document_module,
                "npi_core.documents.release_repository": release_module,
            },
        )

    def seed_trial_review_reference_dependencies(
        self,
        *,
        reference_global_id: UUID | None = None,
    ) -> AttrDict:
        from npi_core.tooling.domain import ToolingMaster
        from npi_core.trial.domain import TrialPurpose, TrialRound, TrialRoundState
        from npi_core.trial.review_domain import TrialExactReference
        from tests import test_phase6_tooling_domain as tooling_core
        from tests import test_phase6_tooling_revision_domain as tooling
        from tests import test_phase7_trial_review_domain as review

        base_comparison = review.comparison()
        base_reference = review.reference(base_comparison)
        target_source = base_comparison.sources[-1]
        trial_round = TrialRound(
            global_id=target_source.trial_round_global_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            trial_plan_global_id=base_comparison.trial_plan_global_id,
            trial_plan_revision_global_id=(
                target_source.trial_plan_revision.global_id
            ),
            trial_plan_revision_snapshot_hash=(
                target_source.trial_plan_revision.snapshot_hash
            ),
            tooling_master_global_id=base_reference.tooling_master_global_id,
            round_sequence=2,
            display_label="T2",
            purpose=TrialPurpose.FIRST_TRIAL,
            planned_start_at=review.NOW,
            planned_end_at=review.NOW + timedelta(hours=6),
            current_state=TrialRoundState.PLANNED,
            current_event_global_id=uuid4(),
            optimistic_version=target_source.trial_round_optimistic_version,
            created_by_user_id="trial-engineer@example.invalid",
            created_at=review.NOW,
            request_id=review.REQUEST,
            trace_id="trace-readiness-reference-round",
        )
        target_source = replace(
            target_source,
            trial_round_snapshot_hash=trial_round.snapshot_hash,
        )
        comparison = replace(
            base_comparison,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            sources=(*base_comparison.sources[:-1], target_source),
            snapshot_hash="",
        )

        part_value = replace(
            tooling_core.part_revision(),
            global_id=base_reference.part_revision.global_id,
            tenant_id="TENANT-A",
            originating_project_global_id=PROJECT_ID,
            snapshot_hash="",
        )
        master_value = ToolingMaster(
            global_id=base_reference.tooling_master_global_id,
            tenant_id="TENANT-A",
            originating_project_global_id=PROJECT_ID,
            title="Readiness reference Tooling Master",
            created_by_user_id="tooling.owner@example.invalid",
            created_at=tooling_core.NOW,
            request_id=tooling_core.REQUEST,
            trace_id="trace-readiness-reference-master",
        )
        tooling_revision = replace(
            tooling.tooling_revision(),
            global_id=base_reference.tooling_revision.global_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            tooling_master_global_id=base_reference.tooling_master_global_id,
            revision_key_hash="",
            snapshot_hash="",
        )
        tooling_set_value = replace(
            tooling_core.tooling_set(),
            global_id=base_reference.tooling_set.global_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            tooling_master_global_id=base_reference.tooling_master_global_id,
            snapshot_hash="",
        )

        file_module_name = (
            "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision"
        )
        file_module = types.ModuleType(file_module_name)

        def canonical_file_snapshot(document: FakeDocument) -> dict[str, object]:
            if int(document.get("is_private") or 0) != 1 or not str(
                document.get("file")
            ).startswith("/private/files/"):
                raise self.frappe.ValidationError("not private")
            observed_at = document.get("scan_observed_at")
            return {
                "documentGlobalId": str(document.get("document_global_id")),
                "fileContentHash": str(document.get("frappe_content_hash")),
                "fileId": str(document.get("frappe_file_id")),
                "fileName": str(document.get("file_name")),
                "fileOptimisticVersion": int(document.get("optimistic_version")),
                "globalId": str(document.get("global_id")),
                "isPrivate": True,
                "mimeType": str(document.get("mime_type")),
                "released": bool(document.get("released")),
                "revision": int(document.get("revision")),
                "scanObservedAt": str(observed_at) if observed_at else None,
                "scanState": str(document.get("scan_state")),
                "sha256": str(document.get("sha256")),
                "sizeBytes": int(document.get("size_bytes")),
            }

        file_module.file_revision_source_snapshot = canonical_file_snapshot
        file_module.has_live_private_file_identity = lambda document: (
            int(document.get("is_private") or 0) == 1
            and str(document.get("file") or "").startswith("/private/files/")
            and document.get("live_identity_matches", True) is True
        )
        file_document_id = uuid4()
        file_revision = self.add(
            "NPI File Revision",
            {
                "global_id": str(base_reference.file_revision.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(file_document_id),
                "revision": 1,
                "revision_key": f"{file_document_id}:1",
                "frappe_file_id": "trial-reference-evidence",
                "frappe_content_hash": "b" * 32,
                "file": "/private/files/trial-reference-evidence.pdf",
                "file_name": "trial-reference-evidence.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 256,
                "sha256": "c" * 64,
                "is_private": 1,
                "scan_state": "clean",
                "scan_observed_at": "2026-08-12 08:00:00",
                "released": 0,
                "optimistic_version": 2,
                "live_identity_matches": True,
            },
        )
        file_hash = self.module._payload_hash(
            canonical_file_snapshot(file_revision)
        )
        reference = replace(
            base_reference,
            global_id=reference_global_id or base_reference.global_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            comparison_snapshot=TrialExactReference(
                comparison.global_id,
                comparison.snapshot_hash,
            ),
            part_revision=TrialExactReference(
                part_value.global_id,
                part_value.snapshot_hash,
            ),
            tooling_revision=TrialExactReference(
                tooling_revision.global_id,
                tooling_revision.snapshot_hash,
            ),
            tooling_set=TrialExactReference(
                tooling_set_value.global_id,
                tooling_set_value.snapshot_hash,
            ),
            file_revision=TrialExactReference(
                base_reference.file_revision.global_id,
                file_hash,
            ),
            snapshot_hash="",
        )

        comparison_document = self.add(
            "NPI Trial Round Comparison Snapshot",
            {
                "global_id": str(comparison.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "target_round_global_id": str(
                    comparison.target_round_global_id
                ),
                "comparison_snapshot": comparison.snapshot_payload(),
                "snapshot_hash": comparison.snapshot_hash,
            },
        )
        trial_round_document = self.add(
            "NPI Trial Round",
            {
                "global_id": str(trial_round.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "tooling_master_global_id": str(
                    trial_round.tooling_master_global_id
                ),
                "optimistic_version": trial_round.optimistic_version,
                "round_snapshot": trial_round.snapshot_payload(),
                "snapshot_hash": trial_round.snapshot_hash,
            },
        )
        part_revision = self.add(
            "NPI Engineering Part Revision",
            {
                "global_id": str(part_value.global_id),
                "engineering_part": str(part_value.part_global_id),
                "part_global_id": str(part_value.part_global_id),
                "tenant_id": part_value.tenant_id,
                "originating_project_global_id": str(
                    part_value.originating_project_global_id
                ),
                "revision_number": part_value.revision_number,
                "revision_label": part_value.revision_label,
                "predecessor_global_id": None,
                "predecessor_snapshot_hash": None,
                "title": part_value.title,
                "reason": part_value.reason,
                "created_by_user_id": part_value.created_by_user_id,
                "created_at": part_value.created_at,
                "request_id": str(part_value.request_id),
                "trace_id": part_value.trace_id,
                "revision_snapshot": part_value.snapshot_payload(),
                "snapshot_hash": part_value.snapshot_hash,
            },
        )
        tooling_master = self.add(
            "NPI Tooling Master",
            {
                "global_id": str(master_value.global_id),
                "tenant_id": master_value.tenant_id,
                "originating_project_global_id": str(
                    master_value.originating_project_global_id
                ),
                "title": master_value.title,
                "created_by_user_id": master_value.created_by_user_id,
                "created_at": master_value.created_at,
                "request_id": str(master_value.request_id),
                "trace_id": master_value.trace_id,
                "master_snapshot": master_value.snapshot_payload(),
                "snapshot_hash": master_value.snapshot_hash,
            },
        )
        tooling_revision_document = self.add(
            "NPI Tooling Revision",
            {
                "global_id": str(tooling_revision.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "tooling_master_global_id": str(
                    base_reference.tooling_master_global_id
                ),
                "revision_snapshot": tooling_revision.snapshot_payload(),
                "snapshot_hash": tooling_revision.snapshot_hash,
            },
        )
        tooling_set = self.add(
            "NPI Tooling Set",
            {
                "global_id": str(tooling_set_value.global_id),
                "tenant_id": tooling_set_value.tenant_id,
                "project_global_id": str(tooling_set_value.project_global_id),
                "tooling_master": str(
                    tooling_set_value.tooling_master_global_id
                ),
                "tooling_master_global_id": str(
                    tooling_set_value.tooling_master_global_id
                ),
                "tooling_requirement": str(
                    tooling_set_value.tooling_requirement_global_id
                ),
                "tooling_requirement_global_id": str(
                    tooling_set_value.tooling_requirement_global_id
                ),
                "requirement_kind": tooling_set_value.requirement_kind.value,
                "physical_serial": tooling_set_value.physical_serial,
                "customer_source_system": (
                    tooling_set_value.customer_source_system
                ),
                "customer_source_object_id": (
                    tooling_set_value.customer_source_object_id
                ),
                "custody_responsibility": (
                    tooling_set_value.custody_responsibility
                ),
                "repair_authorization_reference": (
                    tooling_set_value.repair_authorization_reference
                ),
                "return_conditions": tooling_set_value.return_conditions,
                "created_by_user_id": tooling_set_value.created_by_user_id,
                "created_at": tooling_set_value.created_at,
                "request_id": str(tooling_set_value.request_id),
                "trace_id": tooling_set_value.trace_id,
                "set_snapshot": tooling_set_value.snapshot_payload(),
                "snapshot_hash": tooling_set_value.snapshot_hash,
            },
        )
        return AttrDict(
            reference=reference,
            comparison=comparison,
            trial_round=trial_round,
            comparison_document=comparison_document,
            trial_round_document=trial_round_document,
            part_revision=part_revision,
            tooling_master=tooling_master,
            tooling_revision=tooling_revision_document,
            tooling_set=tooling_set,
            file_revision=file_revision,
            file_module_name=file_module_name,
            modules={file_module_name: file_module},
        )

    def template_parts(self):
        selector = self.domain.ReadinessApplicabilitySelector(
            project_types=(self.domain.ProjectType.NEW_TOOL,)
        )
        nonapplicable = self.domain.ReadinessApplicabilitySelector(
            project_types=(self.domain.ProjectType.NEW_TOOL,),
            industry_keys=("medical",),
        )

        def item(
            key: str,
            gate: str,
            blocking,
            *,
            applicability=selector,
        ):
            return self.domain.ReadinessItemDefinition(
                key=key,
                title=key.replace("_", " ").title(),
                category_key="launch",
                weight=10,
                required=True,
                blocking_level=blocking,
                gate_key=gate,
                completion_rule=self.domain.ReadinessCompletionRule.CONFIRMATION,
                applicability=applicability,
            )

        return {
            "applicability": selector,
            "categories": (self.domain.ReadinessCategoryDefinition("launch", "Launch"),),
            "items": (
                item("p0_g6", "G6", self.domain.ReadinessBlockingLevel.P0),
                item("p1_g6", "G6", self.domain.ReadinessBlockingLevel.P1),
                item("done_g6", "G6", self.domain.ReadinessBlockingLevel.P0),
                item("p0_g7", "G7", self.domain.ReadinessBlockingLevel.P0),
                item(
                    "not_applicable_g6",
                    "G6",
                    self.domain.ReadinessBlockingLevel.P0,
                    applicability=nonapplicable,
                ),
            ),
        }

    def create_template(
        self,
        *,
        repository=None,
        key: str = "1" * 64,
        code: str = "P7-05",
        title: str = "Readiness",
    ):
        return (repository or self.repository).create_template(
            idempotency_key_hash=key,
            template_code=code,
            title=title,
            **self.template_parts(),
        )

    def create_published_template(self):
        created = self.create_template()
        template_id = UUID(created.response["templateGlobalId"])
        published = self.repository.publish_template(
            template_id,
            1,
            idempotency_key_hash="2" * 64,
            expected_optimistic_version=1,
        )
        assert published is not None
        return published

    def initialize_project(
        self,
        project_id: UUID = PROJECT_ID,
        *,
        member_id: UUID = MEMBER_ID,
        repository=None,
        key: str = "3" * 64,
        published=None,
    ):
        published = published or self.create_published_template()
        due = date(2026, 9, 1)
        return (repository or self.repository).initialize_readiness(
            project_id,
            idempotency_key_hash=key,
            template_revision_global_id=UUID(published.response["globalId"]),
            template_version=published.response["templateVersion"],
            template_snapshot_hash=published.response["snapshotHash"],
            industry_key="automotive",
            assignments={
                key: (member_id, due)
                for key in ("p0_g6", "p1_g6", "done_g6", "p0_g7")
            },
        )

    def test_project_first_visibility_and_mutation_authorization_are_scoped(self) -> None:
        member_repository = self.repository_for(
            user_id="member@example.invalid",
            roles=frozenset({"NPI API User"}),
        )
        self.assertIsNotNone(member_repository.template_catalog(PROJECT_ID))

        outsider = self.repository_for(
            user_id="outsider@example.invalid",
            roles=frozenset({"NPI API User"}),
        )
        self.assertIsNone(outsider.template_catalog(PROJECT_ID))
        self.assertIsNone(outsider.readiness_workspace(PROJECT_ID))
        self.assertIsNone(
            member_repository.initialize_readiness(
                PROJECT_ID,
                idempotency_key_hash="9" * 64,
                template_revision_global_id=uuid4(),
                template_version=1,
                template_snapshot_hash=SHA,
                industry_key="automotive",
                assignments={},
            )
        )
        with self.assertRaises(self.errors.PermissionDenied):
            member_repository.create_template(
                idempotency_key_hash="8" * 64,
                template_code="DENIED",
                title="Denied",
                **self.template_parts(),
            )

        cross_tenant = self.repository_for(tenant_id="TENANT-B")
        external = self.repository_for(external=True)
        self.assertIsNone(cross_tenant.template_catalog(PROJECT_ID))
        self.assertIsNone(external.template_catalog(PROJECT_ID))
        self.assertIsNone(
            cross_tenant.initialize_readiness(
                PROJECT_ID,
                idempotency_key_hash="7" * 64,
                template_revision_global_id=uuid4(),
                template_version=1,
                template_snapshot_hash=SHA,
                industry_key="automotive",
                assignments={},
            )
        )
        with self.assertRaises(self.errors.PermissionDenied):
            external.create_template(
                idempotency_key_hash="6" * 64,
                template_code="EXTERNAL-DENIED",
                title="External denied",
                **self.template_parts(),
            )
        self.assertFalse(self.documents.get("NPI Readiness Instance Revision"))

    def test_ambiguous_or_disabled_member_visibility_fails_closed(self) -> None:
        member_repository = self.repository_for(
            user_id="member@example.invalid",
            roles=frozenset({"NPI API User"}),
        )
        self.seed_member(PROJECT_ID, OTHER_MEMBER_ID)
        self.assertIsNone(member_repository.template_catalog(PROJECT_ID))
        del self.documents["NPI Project Member"][str(OTHER_MEMBER_ID)]
        self.documents["User"]["member@example.invalid"].enabled = 0
        self.assertIsNone(member_repository.template_catalog(PROJECT_ID))

    def test_template_create_edit_publish_is_exact_versioned_and_immutable(self) -> None:
        created = self.create_template()
        template_id = UUID(created.response["templateGlobalId"])
        version_id = uuid5(template_id, "npi-readiness-template-version:1")
        self.assertEqual(UUID(created.response["globalId"]), version_id)
        self.assertEqual(created.response["optimisticVersion"], 1)
        self.assertEqual(created.response["publicationState"], "draft")
        first_hash = created.response["snapshotHash"]

        edited = self.repository.edit_template(
            template_id,
            1,
            idempotency_key_hash="2" * 64,
            expected_optimistic_version=1,
            title="Readiness revised",
            **self.template_parts(),
        )
        assert edited is not None
        self.assertEqual(edited.response["globalId"], str(version_id))
        self.assertEqual(edited.response["optimisticVersion"], 2)
        self.assertNotEqual(edited.response["snapshotHash"], first_hash)

        with self.assertRaises(self.domain.ReadinessVersionConflict):
            self.repository.edit_template(
                template_id,
                1,
                idempotency_key_hash="3" * 64,
                expected_optimistic_version=1,
                title="Stale edit",
                **self.template_parts(),
            )

        published = self.repository.publish_template(
            template_id,
            1,
            idempotency_key_hash="4" * 64,
            expected_optimistic_version=2,
        )
        assert published is not None
        self.assertEqual(published.response["publicationState"], "published")
        self.assertEqual(published.response["optimisticVersion"], 3)
        self.assertNotEqual(published.response["snapshotHash"], edited.response["snapshotHash"])

        with self.assertRaises(self.domain.ReadinessTemplateImmutable):
            self.repository.edit_template(
                template_id,
                1,
                idempotency_key_hash="5" * 64,
                expected_optimistic_version=3,
                title="Forbidden overwrite",
                **self.template_parts(),
            )
        with self.assertRaises(self.domain.ReadinessTemplateImmutable):
            self.repository.publish_template(
                template_id,
                1,
                idempotency_key_hash="6" * 64,
                expected_optimistic_version=3,
            )
        self.assertEqual(len(self.documents["NPI Readiness Template Version"]), 1)

    def test_template_change_replays_receipt_found_after_root_and_version_locks(
        self,
    ) -> None:
        created = self.create_template()
        template_id = UUID(created.response["templateGlobalId"])

        cases = (
            ("edit", "readiness_template.edit", "edit_draft"),
            ("publish", "readiness_template.publish", "publish"),
        )
        for action, operation, transform_name in cases:
            with self.subTest(action=action):
                sequence: list[tuple[str, str]] = []
                replay_response = copy.deepcopy(created.response)
                original_get_doc = self.frappe.get_doc
                replay_count = 0

                def observing_get_doc(doctype_or_values, name=None, **kwargs):
                    if kwargs.get("for_update"):
                        sequence.append(("lock", str(doctype_or_values)))
                    return original_get_doc(doctype_or_values, name, **kwargs)

                def replay_after_locks(**kwargs):
                    nonlocal replay_count
                    replay_count += 1
                    sequence.append(("replay", str(kwargs["operation"])))
                    return None if replay_count == 1 else copy.deepcopy(replay_response)

                self.events.clear()
                with (
                    patch.object(
                        self.frappe,
                        "get_doc",
                        side_effect=observing_get_doc,
                    ),
                    patch.object(
                        self.repository,
                        "_idempotency_replay",
                        side_effect=replay_after_locks,
                    ) as replay_mock,
                    patch.object(
                        self.domain.ReadinessTemplateVersion,
                        transform_name,
                        side_effect=AssertionError("template transform must not run"),
                    ) as transform_mock,
                    patch.object(
                        FakeDocument,
                        "save",
                        side_effect=AssertionError("template documents must not be saved"),
                    ) as save_mock,
                    patch.object(
                        self.repository,
                        "_insert_receipt",
                        side_effect=AssertionError("receipt must not be inserted"),
                    ) as receipt_mock,
                    patch.object(
                        self.repository,
                        "_append_audit",
                        side_effect=AssertionError("audit must not be appended"),
                    ) as audit_mock,
                    patch.object(
                        self.repository,
                        "_seal_receipt",
                        side_effect=AssertionError("receipt must not be resealed"),
                    ) as seal_mock,
                ):
                    if action == "edit":
                        outcome = self.repository.edit_template(
                            template_id,
                            1,
                            idempotency_key_hash="a" * 64,
                            expected_optimistic_version=1,
                            title="Concurrent edit",
                            **self.template_parts(),
                        )
                    else:
                        outcome = self.repository.publish_template(
                            template_id,
                            1,
                            idempotency_key_hash="b" * 64,
                            expected_optimistic_version=1,
                        )

                assert outcome is not None
                self.assertTrue(outcome.replayed)
                self.assertEqual(outcome.response, replay_response)
                self.assertEqual(
                    sequence,
                    [
                        ("replay", operation),
                        ("lock", "NPI Readiness Template"),
                        ("lock", "NPI Readiness Template Version"),
                        ("replay", operation),
                    ],
                )
                self.assertEqual(replay_mock.call_count, 2)
                transform_mock.assert_not_called()
                save_mock.assert_not_called()
                receipt_mock.assert_not_called()
                audit_mock.assert_not_called()
                seal_mock.assert_not_called()
                self.assertEqual(self.events, [])

    def test_nullable_project_receipt_is_actor_bound_and_payload_sealed(self) -> None:
        created = self.create_template()
        replay = self.create_template()
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.response, created.response)
        with self.assertRaises(self.module.ReadinessIdempotencyConflict):
            self.create_template(title="Different request")

        other_actor = self.repository_for(
            user_id="other-admin@example.invalid",
            request_id="fb233de2-5d4d-4556-ad16-9476d8f0776f",
        )
        self.add(
            "User",
            {
                "name": "other-admin@example.invalid",
                "enabled": 1,
                "user_type": "System User",
            },
        )
        self.create_template(
            repository=other_actor,
            code="P7-05-OTHER",
            title="Other actor",
        )
        receipts = tuple(self.documents["NPI Readiness Command Idempotency"].values())
        self.assertEqual(len(receipts), 2)
        self.assertEqual({item.project_global_id for item in receipts}, {None})
        self.assertEqual(
            {item.actor_user_id for item in receipts},
            {"admin@example.invalid", "other-admin@example.invalid"},
        )
        self.assertTrue(all(item.sealed == 1 for item in receipts))
        self.assertTrue(all(item.response_hash for item in receipts))

    def test_single_instance_and_exact_linear_current_tip_reject_stale_predecessor(self) -> None:
        initialized = self.initialize_project()
        assert initialized is not None
        first = initialized.response["currentRevision"]
        with self.assertRaises(self.domain.ReadinessVersionConflict):
            self.initialize_project(
                key="4" * 64,
                published=types.SimpleNamespace(response={
                    "globalId": first["templateRevision"]["globalId"],
                    "templateVersion": first["templateRevision"]["version"],
                    "snapshotHash": first["templateRevision"]["snapshotHash"],
                }),
            )

        revised = self.repository.revise_readiness(
            PROJECT_ID,
            UUID(first["instanceGlobalId"]),
            idempotency_key_hash="5" * 64,
            expected_instance_version=1,
            expected_revision_global_id=UUID(first["globalId"]),
            expected_revision_snapshot_hash=first["snapshotHash"],
            item_key="p0_g6",
            owner_member_global_id=MEMBER_ID,
            due_date=date(2026, 9, 2),
            state=self.domain.ReadinessItemState.IN_PROGRESS,
            confirmation_value=None,
            source_requests=(),
        )
        assert revised is not None
        self.assertEqual(revised.response["currentRevision"]["instanceVersion"], 2)
        self.assertEqual(
            [item["instanceVersion"] for item in revised.response["revisions"]],
            [1, 2],
        )

        stale_values = {
            "project_id": PROJECT_ID,
            "instance_id": UUID(first["instanceGlobalId"]),
            "expected_instance_version": 1,
            "expected_revision_global_id": UUID(first["globalId"]),
            "expected_revision_snapshot_hash": first["snapshotHash"],
            "item_key": "p0_g6",
            "owner_member_global_id": MEMBER_ID,
            "due_date": date(2026, 9, 3),
            "state": self.domain.ReadinessItemState.IN_PROGRESS,
            "confirmation_value": None,
            "source_requests": (),
        }
        with self.assertRaises(self.domain.ReadinessVersionConflict):
            self.repository.revise_readiness(
                idempotency_key_hash="6" * 64,
                **stale_values,
            )
        with self.assertRaises(self.domain.ReadinessVersionConflict):
            self.repository.revise_readiness(
                idempotency_key_hash="7" * 64,
                **{
                    **stale_values,
                    "expected_instance_version": 2,
                    "expected_revision_global_id": UUID(
                        revised.response["currentRevision"]["globalId"]
                    ),
                    "expected_revision_snapshot_hash": "f" * 64,
                },
            )

    def test_multiple_active_streams_and_duplicate_tip_fail_closed(self) -> None:
        initialized = self.initialize_project()
        assert initialized is not None
        document = next(iter(self.documents["NPI Readiness Instance Revision"].values()))
        duplicate = FakeDocument(self, dict(document))
        duplicate.name = "duplicate-row"
        self.documents["NPI Readiness Instance Revision"][duplicate.name] = duplicate
        with self.assertRaisesRegex(RuntimeError, "lineage is ambiguous"):
            self.repository.readiness_workspace(PROJECT_ID)

        del self.documents["NPI Readiness Instance Revision"][duplicate.name]
        current = self.module._instance_from_document(document)
        template_document = self.documents["NPI Readiness Template Version"][
            str(current.template_revision.global_id)
        ]
        template = self.module._template_from_document(template_document)
        other = self.domain.initialize_readiness_instance(
            global_id=uuid4(),
            instance_global_id=uuid4(),
            tenant_id=current.tenant_id,
            project=current.project,
            template=template,
            gates={item.gate.gate_key: item.gate for item in current.items},
            assignments={
                item.definition.key: (item.owner, item.due_date)
                for item in current.items
                if item.applicable
            },
            created_by_user_id="admin@example.invalid",
            created_at=datetime.now(UTC),
            request_id=UUID(REQUEST_ID),
            trace_id="trace-p7-05-other-stream",
        )
        self.module.FrappeReadinessRepository._insert_instance_revision(other)
        with self.assertRaisesRegex(RuntimeError, "instance stream is ambiguous"):
            self.repository.readiness_workspace(PROJECT_ID)

    def test_persisted_revision_hash_corruption_fails_closed(self) -> None:
        self.initialize_project()
        document = next(iter(self.documents["NPI Readiness Instance Revision"].values()))
        document.snapshot_hash = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "instance integrity failed"):
            self.repository.readiness_workspace(PROJECT_ID)

    def test_persisted_revision_scope_cannot_disagree_with_its_project_index(self) -> None:
        self.initialize_project()
        document = next(iter(self.documents["NPI Readiness Instance Revision"].values()))
        payload = copy.deepcopy(document.instance_snapshot)
        payload["project"]["globalId"] = str(OTHER_PROJECT_ID)
        value = self.domain.instance_from_snapshot(payload)
        document.instance_snapshot = value.snapshot_payload()
        document.snapshot_hash = value.snapshot_hash
        with self.assertRaisesRegex(RuntimeError, "revision scope is invalid"):
            self.repository.readiness_workspace(PROJECT_ID)

    def test_receipt_revision_audit_and_seal_order_is_observable(self) -> None:
        published = self.create_published_template()
        self.events.clear()
        outcome = self.initialize_project(published=published)
        self.assertIsNotNone(outcome)
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Readiness Command Idempotency"),
                ("insert", "NPI Readiness Instance Revision"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Readiness Command Idempotency"),
            ],
        )
        receipt = next(
            item
            for item in self.documents["NPI Readiness Command Idempotency"].values()
            if item.operation == "readiness_instance.initialize"
        )
        self.assertEqual(receipt.sealed, 1)

    def test_failure_before_audit_never_seals_or_replays_fake_success(self) -> None:
        published = self.create_published_template()
        self.events.clear()
        self.fail_on = ("insert", "NPI Audit Event")
        with self.assertRaisesRegex(RuntimeError, "Injected failure"):
            self.initialize_project(published=published)
        receipt = next(
            item
            for item in self.documents["NPI Readiness Command Idempotency"].values()
            if item.operation == "readiness_instance.initialize"
        )
        self.assertEqual(receipt.sealed, 0)
        self.assertNotIn(
            ("save", "NPI Readiness Command Idempotency"),
            [(action, doctype) for action, doctype, _name in self.events],
        )
        self.fail_on = None
        with self.assertRaisesRegex(RuntimeError, "receipt integrity failed"):
            self.initialize_project(published=published)

    def test_released_document_uses_lifecycle_tuple_and_full_release_closure(
        self,
    ) -> None:
        fixture = self.seed_released_document_source()

        def resolve(query=None):
            with patch.dict(sys.modules, fixture.modules):
                return self.repository.get_exact_source(
                    fixture.context,
                    query or fixture.query,
                )

        observed = resolve()
        self.assertIsNotNone(observed)
        self.assertIs(
            observed.disposition,
            self.domain.ReadinessSourceState.SATISFIED,
        )

        self.assertIsNone(
            resolve(
                replace(
                    fixture.query,
                    source_version=int(fixture.revision.optimistic_version),
                    snapshot_hash=str(fixture.revision.snapshot_hash),
                )
            )
        )
        self.assertIsNone(
            resolve(
                replace(
                    fixture.query,
                    source_version=fixture.query.source_version + 1,
                )
            )
        )
        self.assertIsNone(
            resolve(replace(fixture.query, snapshot_hash="f" * 64))
        )

        def rejects_drift(document, fieldname: str, value: object) -> None:
            original = copy.deepcopy(document.get(fieldname))
            document[fieldname] = value
            try:
                self.assertIsNone(resolve(), fieldname)
            finally:
                document[fieldname] = original

        rejects_drift(fixture.revision, "revision_snapshot", {
            **fixture.revision.revision_snapshot,
            "reason": "Tampered after release.",
        })
        rejects_drift(fixture.lifecycle, "current_state", "superseded")
        rejects_drift(
            fixture.lifecycle,
            "release_snapshot_hash",
            "e" * 64,
        )
        rejects_drift(
            fixture.lifecycle,
            "last_event_global_id",
            str(uuid4()),
        )
        rejects_drift(
            fixture.release_event,
            "to_version",
            fixture.query.source_version + 1,
        )
        rejects_drift(
            fixture.release_event,
            "evidence_snapshot_hash",
            "d" * 64,
        )
        rejects_drift(
            fixture.release_event,
            "document_global_id",
            str(uuid4()),
        )
        rejects_drift(
            fixture.approved_event,
            "confirmation_hashes",
            [],
        )
        rejects_drift(
            fixture.cycle,
            "review_evidence",
            {
                **fixture.cycle.review_evidence,
                "revisionSnapshotHash": "c" * 64,
            },
        )
        rejects_drift(
            fixture.policy_document,
            "policy_snapshot",
            {
                **fixture.policy_document.policy_snapshot,
                "title": "Tampered release policy",
            },
        )
        rejects_drift(
            fixture.release_confirmation,
            "confirmation_evidence",
            {
                **fixture.release_confirmation.confirmation_evidence,
                "traceId": "tampered-release-confirmation",
            },
        )

        approved_name = str(fixture.approved_event.name)
        approved_document = self.documents["NPI Document Lifecycle Event"].pop(
            approved_name
        )
        try:
            self.assertIsNone(resolve())
        finally:
            self.documents["NPI Document Lifecycle Event"][approved_name] = (
                approved_document
            )

        fixture.association.live_identity_matches = False
        self.assertIsNone(resolve())
        fixture.association.live_identity_matches = True
        fixture.association.observed_evidence = replace(
            fixture.file_evidence,
            sha256="b" * 64,
        )
        self.assertIsNone(resolve())

    def test_release_baseline_loader_seam_is_exact_and_fails_closed(self) -> None:
        from npi_core.documents.baseline_domain import (
            DocumentBaselineInputUnavailable,
        )

        baseline_id = uuid4()
        baseline = AttrDict(
            global_id=baseline_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            version=3,
            snapshot_hash="6" * 64,
        )
        result: list[object | None] = [baseline]
        calls: list[tuple[object, UUID, bool]] = []

        def load_document_baseline(project, global_id: UUID, *, lock: bool):
            calls.append((project, global_id, lock))
            selected = result[0]
            if isinstance(selected, Exception):
                raise selected
            return selected

        baseline_module = types.ModuleType(
            "npi_core.documents.baseline_repository"
        )
        baseline_module.load_document_baseline = load_document_baseline
        context = self.source_resolver.SourceResolutionContext(
            "TENANT-A", PROJECT_ID
        )
        query = self.source_resolver.ExactSourceQuery(
            kind=self.domain.ReadinessSourceKind.RELEASE_BASELINE,
            global_id=baseline_id,
            source_version=baseline.version,
            snapshot_hash=baseline.snapshot_hash,
        )
        with patch.dict(
            sys.modules,
            {"npi_core.documents.baseline_repository": baseline_module},
        ):
            observed = self.repository.get_exact_source(context, query)
            self.assertIsNotNone(observed)
            self.assertIs(
                observed.disposition,
                self.domain.ReadinessSourceState.SATISFIED,
            )
            self.assertEqual(calls[-1], (self.project, baseline_id, False))
            self.assertIsNone(
                self.repository.get_exact_source(
                    context,
                    replace(query, source_version=query.source_version + 1),
                )
            )
            self.assertIsNone(
                self.repository.get_exact_source(
                    context,
                    replace(query, snapshot_hash="7" * 64),
                )
            )
            result[0] = None
            self.assertIsNone(self.repository.get_exact_source(context, query))
            result[0] = DocumentBaselineInputUnavailable()
            self.assertIsNone(self.repository.get_exact_source(context, query))

    def test_formal_external_sources_do_zero_lookup_and_controlled_report_is_evidence_only(self) -> None:
        context = self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID)
        with patch.object(
            self.module,
            "_optional_doc",
            side_effect=AssertionError("external source lookup is forbidden"),
        ):
            for kind in self.domain.EXTERNAL_SOURCE_KINDS:
                query = self.source_resolver.ExactSourceQuery(
                    kind=kind,
                    global_id=uuid4(),
                    source_version=1,
                    snapshot_hash=SHA,
                )
                self.assertIsNone(self.repository.get_exact_source(context, query))

        report_id = uuid4()
        self.add(
            "NPI Document Revision",
            {
                "global_id": str(report_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "optimistic_version": 1,
                "snapshot_hash": SHA,
                "revision_snapshot": {"disposition": "pass"},
            },
        )
        self.assertIsNone(
            self.repository.get_exact_source(
                context,
                self.source_resolver.ExactSourceQuery(
                    kind=self.domain.ReadinessSourceKind.CONTROLLED_QUALITY_RESULT,
                    global_id=report_id,
                    source_version=1,
                    snapshot_hash=SHA,
                ),
            )
        )

        reference_id = uuid4()
        fixture = self.seed_trial_review_reference_dependencies(
            reference_global_id=reference_id,
        )
        reference_value = fixture.reference
        reference_snapshot = reference_value.snapshot_payload()
        reference_hash = reference_value.snapshot_hash
        self.add(
            "NPI Trial Review Reference Revision",
            {
                "global_id": str(reference_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "reference_version": reference_value.reference_version,
                "reference_snapshot": reference_snapshot,
                "snapshot_hash": reference_hash,
            },
        )
        with patch.dict(sys.modules, fixture.modules):
            report = self.repository.get_exact_source(
                context,
                self.source_resolver.ExactSourceQuery(
                    kind=(
                        self.domain.ReadinessSourceKind.CONTROLLED_QUALITY_RESULT
                    ),
                    global_id=reference_id,
                    source_version=reference_value.reference_version,
                    snapshot_hash=reference_hash,
                ),
            )
        self.assertIsNotNone(report)
        self.assertIs(report.disposition, self.domain.ReadinessSourceState.SATISFIED)

    def test_trial_review_reference_revalidates_exact_dependencies_and_live_file(
        self,
    ) -> None:
        fixture = self.seed_trial_review_reference_dependencies()
        reference = fixture.reference
        self.add(
            "NPI Trial Review Reference Revision",
            {
                "global_id": str(reference.global_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "reference_version": reference.reference_version,
                "reference_snapshot": reference.snapshot_payload(),
                "snapshot_hash": reference.snapshot_hash,
            },
        )
        context = self.source_resolver.SourceResolutionContext(
            "TENANT-A", PROJECT_ID
        )

        def resolve(kind=None):
            with patch.dict(sys.modules, fixture.modules):
                return self.repository.get_exact_source(
                    context,
                    self.source_resolver.ExactSourceQuery(
                        kind=(
                            kind
                            or self.domain.ReadinessSourceKind.TRIAL_REVIEW_REFERENCE
                        ),
                        global_id=reference.global_id,
                        source_version=reference.reference_version,
                        snapshot_hash=reference.snapshot_hash,
                    ),
                )

        self.assertIsNotNone(resolve())
        self.assertIsNotNone(
            resolve(self.domain.ReadinessSourceKind.CONTROLLED_QUALITY_RESULT)
        )

        exact_projection_drifts = (
            (fixture.comparison_document, "snapshot_hash", "d" * 64),
            (
                fixture.trial_round_document,
                "optimistic_version",
                fixture.trial_round.optimistic_version + 1,
            ),
            (fixture.part_revision, "snapshot_hash", "d" * 64),
            (
                fixture.tooling_master,
                "originating_project_global_id",
                str(OTHER_PROJECT_ID),
            ),
            (
                fixture.tooling_revision,
                "tooling_master_global_id",
                str(uuid4()),
            ),
            (fixture.tooling_set, "tooling_master_global_id", str(uuid4())),
        )
        for document, field, drifted_value in exact_projection_drifts:
            with self.subTest(dependency=document.doctype, field=field):
                original = document.get(field)
                document[field] = drifted_value
                self.assertIsNone(resolve())
                document[field] = original

        file_revision = fixture.file_revision
        file_bucket = self.documents["NPI File Revision"]
        file_name = str(file_revision.name)
        file_bucket.pop(file_name)
        self.assertIsNone(resolve())
        file_bucket[file_name] = file_revision

        file_drifts = (
            ("project_global_id", str(OTHER_PROJECT_ID)),
            ("sha256", "d" * 64),
            ("scan_state", "pending"),
            ("is_private", 0),
            ("live_identity_matches", False),
        )
        for field, drifted_value in file_drifts:
            with self.subTest(file_field=field):
                original = file_revision.get(field)
                file_revision[field] = drifted_value
                self.assertIsNone(resolve())
                file_revision[field] = original

        self.assertIsNotNone(resolve())

    def test_trial_review_reference_rejects_minimal_self_hashed_tooling_snapshots(
        self,
    ) -> None:
        from npi_core.trial.review_domain import TrialExactReference

        fixture = self.seed_trial_review_reference_dependencies()
        context = self.source_resolver.SourceResolutionContext(
            "TENANT-A", PROJECT_ID
        )
        cases = (
            (
                "part",
                fixture.part_revision,
                "revision_snapshot",
                {
                    "globalId": str(fixture.reference.part_revision.global_id),
                    "tenantId": "TENANT-A",
                    "originatingProjectGlobalId": str(PROJECT_ID),
                },
            ),
            (
                "master",
                fixture.tooling_master,
                "master_snapshot",
                {
                    "globalId": str(
                        fixture.reference.tooling_master_global_id
                    ),
                    "tenantId": "TENANT-A",
                    "originatingProjectGlobalId": str(PROJECT_ID),
                },
            ),
            (
                "set",
                fixture.tooling_set,
                "set_snapshot",
                {
                    "globalId": str(fixture.reference.tooling_set.global_id),
                    "tenantId": "TENANT-A",
                    "projectGlobalId": str(PROJECT_ID),
                    "toolingMasterGlobalId": str(
                        fixture.reference.tooling_master_global_id
                    ),
                },
            ),
        )
        for kind, dependency, snapshot_field, partial_snapshot in cases:
            with self.subTest(dependency=kind):
                original_snapshot = dependency.get(snapshot_field)
                original_hash = dependency.snapshot_hash
                partial_hash = self.module._payload_hash(partial_snapshot)
                dependency[snapshot_field] = partial_snapshot
                dependency.snapshot_hash = partial_hash
                reference_changes: dict[str, object] = {
                    "global_id": uuid4(),
                    "snapshot_hash": "",
                }
                if kind == "part":
                    reference_changes["part_revision"] = TrialExactReference(
                        fixture.reference.part_revision.global_id,
                        partial_hash,
                    )
                elif kind == "set":
                    reference_changes["tooling_set"] = TrialExactReference(
                        fixture.reference.tooling_set.global_id,
                        partial_hash,
                    )
                forged = replace(fixture.reference, **reference_changes)
                document = self.add(
                    "NPI Trial Review Reference Revision",
                    {
                        "global_id": str(forged.global_id),
                        "tenant_id": "TENANT-A",
                        "project_global_id": str(PROJECT_ID),
                        "reference_version": forged.reference_version,
                        "reference_snapshot": forged.snapshot_payload(),
                        "snapshot_hash": forged.snapshot_hash,
                    },
                )
                try:
                    with patch.dict(sys.modules, fixture.modules):
                        observed = self.repository.get_exact_source(
                            context,
                            self.source_resolver.ExactSourceQuery(
                                kind=(
                                    self.domain.ReadinessSourceKind.TRIAL_REVIEW_REFERENCE
                                ),
                                global_id=forged.global_id,
                                source_version=forged.reference_version,
                                snapshot_hash=forged.snapshot_hash,
                            ),
                        )
                    self.assertIsNone(observed)
                finally:
                    self.documents[
                        "NPI Trial Review Reference Revision"
                    ].pop(str(document.name))
                    dependency[snapshot_field] = original_snapshot
                    dependency.snapshot_hash = original_hash

    def test_private_file_source_requires_public_exact_hash_clean_and_live_identity(self) -> None:
        module_name = (
            "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision"
        )
        file_module = types.ModuleType(module_name)

        def canonical_file_snapshot(document: FakeDocument) -> dict[str, object]:
            if int(document.get("is_private") or 0) != 1 or not str(
                document.get("file")
            ).startswith("/private/files/"):
                raise self.frappe.ValidationError("not private")
            observed_at = document.get("scan_observed_at")
            return {
                "documentGlobalId": str(document.get("document_global_id")),
                "fileContentHash": str(document.get("frappe_content_hash")),
                "fileId": str(document.get("frappe_file_id")),
                "fileName": str(document.get("file_name")),
                "fileOptimisticVersion": int(document.get("optimistic_version")),
                "globalId": str(document.get("global_id")),
                "isPrivate": True,
                "mimeType": str(document.get("mime_type")),
                "released": bool(document.get("released")),
                "revision": int(document.get("revision")),
                "scanObservedAt": str(observed_at) if observed_at else None,
                "scanState": str(document.get("scan_state")),
                "sha256": str(document.get("sha256")),
                "sizeBytes": int(document.get("size_bytes")),
            }

        file_module.file_revision_source_snapshot = canonical_file_snapshot
        file_module.has_live_private_file_identity = lambda document: (
            int(document.get("is_private") or 0) == 1
            and str(document.get("file") or "").startswith("/private/files/")
            and document.get("live_identity_matches", True) is True
        )
        file_id = uuid4()
        document_id = uuid4()
        document = self.add(
            "NPI File Revision",
            {
                "global_id": str(file_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(document_id),
                "revision": 1,
                "revision_key": f"{document_id}:1",
                "frappe_file_id": "file-evidence-1",
                "frappe_content_hash": "b" * 32,
                "file": "/private/files/evidence.pdf",
                "file_name": "evidence.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 128,
                "sha256": "c" * 64,
                "is_private": 1,
                "scan_state": "clean",
                "scan_observed_at": "2026-08-11 08:00:00",
                "released": 1,
                "optimistic_version": 3,
            },
        )
        context = self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID)

        def resolve_current():
            return self.repository.get_exact_source(
                context,
                self.source_resolver.ExactSourceQuery(
                    kind=self.domain.ReadinessSourceKind.FILE_REVISION,
                    global_id=file_id,
                    source_version=1,
                    snapshot_hash="c" * 64,
                ),
            )

        with patch.dict(sys.modules, {module_name: file_module}):
            clean = resolve_current()
            self.assertIsNotNone(clean)
            self.assertIs(
                clean.disposition,
                self.domain.ReadinessSourceState.SATISFIED,
            )

            document.scan_state = "pending"
            document.scan_observed_at = None
            self.assertIsNone(resolve_current())

            document.scan_state = "clean"
            document.scan_observed_at = "2026-08-11 08:00:00"
            document.released = 0
            self.assertIsNotNone(resolve_current())

            document.live_identity_matches = False
            self.assertIsNone(resolve_current())

            document.live_identity_matches = True
            document.sha256 = "d" * 64
            self.assertIsNone(resolve_current())

            document.sha256 = "c" * 64
            document.is_private = 0
            with self.assertRaises(self.frappe.ValidationError):
                canonical_file_snapshot(document)
            query = self.source_resolver.ExactSourceQuery(
                kind=self.domain.ReadinessSourceKind.FILE_REVISION,
                global_id=file_id,
                source_version=1,
                snapshot_hash=SHA,
            )
            self.assertIsNone(self.repository.get_exact_source(context, query))

    def test_domain_work_item_source_uses_a_public_validated_projection(self) -> None:
        work_item_id = uuid4()
        work_item = self.add(
            "NPI Domain Work Item",
            {
                "global_id": str(work_item_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "stage_global_id": str(GATE_G6_ID),
                "wbs_item_global_id": None,
                "kind": "action",
                "title": "Resolve the exact readiness action",
                "detail": "Retain one controlled Project action.",
                "owner_user_id": "admin@example.invalid",
                "due_at": "2026-09-01T08:00:00Z",
                "severity": "high",
                "blocking": 1,
                "state_key": "open",
                "state_label_source": "Open",
                "state_terminal": 0,
                "work_policy_global_id": str(uuid4()),
                "work_policy_version": 2,
                "work_policy_snapshot_hash": SHA,
                "relations": [],
                "evidence_references": [],
                "source_system": "NPI_ONE",
                "optimistic_version": 4,
            },
        )
        workspace = self.repository.readiness_workspace(PROJECT_ID)
        self.assertIsNotNone(workspace)
        option = workspace["sourceOptions"][0]
        self.assertEqual(
            set(option),
            {
                "kind",
                "globalId",
                "sourceVersion",
                "snapshotHash",
                "label",
                "stateLabelSource",
                "stateTerminal",
            },
        )
        self.assertEqual(option["globalId"], str(work_item_id))
        self.assertEqual(option["sourceVersion"], 4)
        context = self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID)
        query = self.source_resolver.ExactSourceQuery(
            kind=self.domain.ReadinessSourceKind.DOMAIN_WORK_ITEM,
            global_id=work_item_id,
            source_version=option["sourceVersion"],
            snapshot_hash=option["snapshotHash"],
        )
        self.assertIsNotNone(self.repository.get_exact_source(context, query))
        self.assertIsNone(
            self.repository.get_exact_source(
                context,
                replace(query, source_version=query.source_version + 1),
            )
        )
        self.assertIsNone(
            self.repository.get_exact_source(
                context,
                replace(query, snapshot_hash="f" * 64),
            )
        )
        work_item.source_system = "ERPNEXT"
        self.assertIsNone(self.repository.get_exact_source(context, query))
        work_item.source_system = "NPI_ONE"
        work_item.project_global_id = str(OTHER_PROJECT_ID)
        self.assertIsNone(self.repository.get_exact_source(context, query))
        work_item.project_global_id = str(PROJECT_ID)
        work_item.kind = "unsupported"
        self.assertIsNone(self.repository.get_exact_source(context, query))

    def test_internal_sources_use_real_domain_parsers_and_snapshot_disposition(self) -> None:
        from tests import test_phase6_tooling_engineering_controls_domain as tooling
        from tests import test_phase7_trial_domain as execution
        from tests import test_phase7_trial_quality_domain as quality
        from tests import test_phase7_trial_review_domain as review

        capacity_ok = replace(
            tooling.scenario(), target_monthly_assembly_units="45000"
        )
        capacity_failed = tooling.scenario()
        input_lock = execution.input_lock_revision()
        actual = execution.actual_revision(input_lock)
        sample = execution.sample_revision(input_lock)
        cavity_ok = quality.cavity_result()
        cavity_failed = quality.cavity_result(
            measurement_value=quality.measurement(value="11")
        )
        open_defect = quality.trial_defect()
        assigned_defect = quality.trial_defect(
            global_id=uuid4(),
            version=2,
            predecessor_kind=quality.TrialDefectPredecessorKind.TRIAL_DEFECT_REVISION,
            predecessor_global_id=uuid4(),
            predecessor_snapshot_hash="d" * 64,
            state=quality.ToolingDefectState.ASSIGNED,
            actions=(quality.action(state=quality.ToolingDefectActionState.PLANNED),),
        )
        closed_defect = replace(
            assigned_defect,
            global_id=uuid4(),
            state=quality.ToolingDefectState.CLOSED,
            root_cause_state=quality.ToolingDefectRootCauseState.RECORDED,
            root_cause="The exact cavity insert fit caused the condition.",
            actions=(
                quality.action(
                    state=quality.ToolingDefectActionState.VERIFIED,
                    verification_id=uuid4(),
                    verification_hash="e" * 64,
                ),
            ),
            snapshot_hash="",
        )
        verification_ok = quality.verification(assigned_defect, cavity_ok)
        verification_failed = replace(
            verification_ok,
            result=quality.TrialDefectVerificationResult.FAIL,
            snapshot_hash="",
        )
        reference_fixture = self.seed_trial_review_reference_dependencies()
        comparison = reference_fixture.comparison
        reference = reference_fixture.reference
        submitted = review.conclusion(comparison, reference)
        approved = replace(
            submitted,
            global_id=uuid4(),
            conclusion_version=2,
            predecessor_global_id=submitted.global_id,
            predecessor_snapshot_hash=submitted.snapshot_hash,
            state=review.TrialConclusionRevisionState.APPROVED,
            summary_input=review.build_one_page_summary_input(
                comparison,
                (reference,),
                review.TrialConclusionCode.PASS,
                review.TrialConclusionRevisionState.APPROVED,
            ),
            reason="Approve the exact submitted Trial conclusion.",
            snapshot_hash="",
        )
        rejected = replace(
            approved,
            global_id=uuid4(),
            state=review.TrialConclusionRevisionState.REJECTED,
            summary_input=review.build_one_page_summary_input(
                comparison,
                (reference,),
                review.TrialConclusionCode.PASS,
                review.TrialConclusionRevisionState.REJECTED,
            ),
            reason="Reject the exact submitted Trial conclusion.",
            snapshot_hash="",
        )

        cases = (
            (self.domain.ReadinessSourceKind.TOOLING_CAPACITY_SCENARIO, "NPI Tooling Capacity Scenario Revision", "scenario_version", "scenario_snapshot", capacity_ok, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TOOLING_CAPACITY_SCENARIO, "NPI Tooling Capacity Scenario Revision", "scenario_version", "scenario_snapshot", capacity_failed, self.domain.ReadinessSourceState.FAILED),
            (self.domain.ReadinessSourceKind.TRIAL_INPUT_LOCK, "NPI Trial Input Lock Revision", "lock_version", "lock_snapshot", input_lock, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_ACTUAL, "NPI Trial Actual Revision", "actual_version", "actual_snapshot", actual, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_SAMPLE, "NPI Trial Sample Batch Revision", "sample_version", "sample_snapshot", sample, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_CAVITY_RESULT, "NPI Trial Cavity Result Revision", "result_version", "cavity_result_snapshot", cavity_ok, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_CAVITY_RESULT, "NPI Trial Cavity Result Revision", "result_version", "cavity_result_snapshot", cavity_failed, self.domain.ReadinessSourceState.FAILED),
            (self.domain.ReadinessSourceKind.TRIAL_DEFECT, "NPI Trial Defect Revision", "defect_version", "trial_defect_snapshot", closed_defect, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_DEFECT, "NPI Trial Defect Revision", "defect_version", "trial_defect_snapshot", open_defect, self.domain.ReadinessSourceState.FAILED),
            (self.domain.ReadinessSourceKind.TRIAL_DEFECT_VERIFICATION, "NPI Trial Defect Verification Revision", "attempt_sequence", "verification_snapshot", verification_ok, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_DEFECT_VERIFICATION, "NPI Trial Defect Verification Revision", "attempt_sequence", "verification_snapshot", verification_failed, self.domain.ReadinessSourceState.FAILED),
            (self.domain.ReadinessSourceKind.TRIAL_COMPARISON, "NPI Trial Round Comparison Snapshot", None, "comparison_snapshot", comparison, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_REVIEW_REFERENCE, "NPI Trial Review Reference Revision", "reference_version", "reference_snapshot", reference, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_CONCLUSION, "NPI Trial Conclusion Revision", "conclusion_version", "conclusion_snapshot", approved, self.domain.ReadinessSourceState.SATISFIED),
            (self.domain.ReadinessSourceKind.TRIAL_CONCLUSION, "NPI Trial Conclusion Revision", "conclusion_version", "conclusion_snapshot", rejected, self.domain.ReadinessSourceState.FAILED),
        )
        context = self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID)
        for kind, doctype, version_field, snapshot_field, original, expected in cases:
            with self.subTest(kind=kind, expected=expected):
                source_id = uuid4()
                changes = {
                    "global_id": source_id,
                    "tenant_id": "TENANT-A",
                    "project_global_id": PROJECT_ID,
                }
                if "snapshot_hash" in original.__dataclass_fields__:
                    changes["snapshot_hash"] = ""
                value = replace(original, **changes)
                version = getattr(value, version_field) if version_field else 1
                snapshot = value.snapshot_payload()
                snapshot_hash = value.snapshot_hash
                document_values = {
                    "global_id": str(source_id),
                    "tenant_id": "TENANT-A",
                    "project_global_id": str(PROJECT_ID),
                    snapshot_field: snapshot,
                    "snapshot_hash": snapshot_hash,
                    "projection_state": "deliberately_not_authoritative",
                }
                if version_field:
                    document_values[version_field] = version
                document = self.add(doctype, document_values)
                query = self.source_resolver.ExactSourceQuery(
                    kind=kind,
                    global_id=source_id,
                    source_version=version,
                    snapshot_hash=snapshot_hash,
                )
                with patch.dict(sys.modules, reference_fixture.modules):
                    observation = self.repository.get_exact_source(context, query)
                self.assertIsNotNone(observation)
                self.assertIs(observation.disposition, expected)
                document.projection_state = "tampered_projection"
                with patch.dict(sys.modules, reference_fixture.modules):
                    repeated = self.repository.get_exact_source(context, query)
                self.assertIsNotNone(repeated)
                self.assertIs(repeated.disposition, expected)

    def test_minimal_self_hashed_domain_snapshot_is_rejected(self) -> None:
        source_id = uuid4()
        snapshot = {
            "globalId": str(source_id),
            "tenantId": "TENANT-A",
            "projectGlobalId": str(PROJECT_ID),
            "defectVersion": 1,
            "state": "closed",
        }
        snapshot_hash = self.module._payload_hash(snapshot)
        self.add(
            "NPI Trial Defect Revision",
            {
                "global_id": str(source_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "defect_version": 1,
                "trial_defect_snapshot": snapshot,
                "snapshot_hash": snapshot_hash,
            },
        )
        observation = self.repository.get_exact_source(
            self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID),
            self.source_resolver.ExactSourceQuery(
                kind=self.domain.ReadinessSourceKind.TRIAL_DEFECT,
                global_id=source_id,
                source_version=1,
                snapshot_hash=snapshot_hash,
            ),
        )
        self.assertIsNone(observation)

    def test_internal_source_missing_version_hash_project_and_tenant_drift_fail_closed(self) -> None:
        from tests import test_phase7_trial_quality_domain as quality

        source_id = uuid4()
        value = replace(
            quality.trial_defect(),
            global_id=source_id,
            tenant_id="TENANT-A",
            project_global_id=PROJECT_ID,
            snapshot_hash="",
        )
        snapshot = value.snapshot_payload()
        snapshot_hash = value.snapshot_hash
        document = self.add(
            "NPI Trial Defect Revision",
            {
                "global_id": str(source_id),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "defect_version": value.defect_version,
                "trial_defect_snapshot": snapshot,
                "snapshot_hash": snapshot_hash,
                "state": "open",
            },
        )
        context = self.source_resolver.SourceResolutionContext("TENANT-A", PROJECT_ID)

        def resolve(
            *,
            global_id: UUID = source_id,
            version: int = value.defect_version,
            source_hash: str = snapshot_hash,
        ):
            return self.repository.get_exact_source(
                context,
                self.source_resolver.ExactSourceQuery(
                    kind=self.domain.ReadinessSourceKind.TRIAL_DEFECT,
                    global_id=global_id,
                    source_version=version,
                    snapshot_hash=source_hash,
                ),
            )

        self.assertIsNotNone(resolve())
        self.assertIsNone(resolve(global_id=uuid4()))
        self.assertIsNone(resolve(version=3))
        self.assertIsNone(resolve(source_hash="f" * 64))
        document.project_global_id = str(OTHER_PROJECT_ID)
        self.assertIsNone(resolve())
        document.project_global_id = str(PROJECT_ID)
        document.tenant_id = "TENANT-B"
        self.assertIsNone(resolve())

        document.tenant_id = "TENANT-A"
        document.trial_defect_snapshot = {
            **snapshot,
            "projectGlobalId": str(OTHER_PROJECT_ID),
        }
        document.snapshot_hash = self.module._payload_hash(
            document.trial_defect_snapshot
        )
        self.assertIsNone(resolve(source_hash=document.snapshot_hash))

    def test_project_source_cannot_cross_project_even_with_an_exact_identity(self) -> None:
        published = self.create_published_template()
        self.initialize_project(published=published)
        current = self.module._project_revision_chain(self.project)[-1].project
        local_request = self.source_validation.ReadinessSourceRequest(
            requirement_key="project_truth",
            kind=self.domain.ReadinessSourceKind.PROJECT,
            global_id=PROJECT_ID,
            source_version=current.optimistic_version,
            snapshot_hash=current.snapshot_hash,
        )
        local = self.source_resolver.resolve_source(
            local_request,
            context=self.source_resolver.SourceResolutionContext(
                "TENANT-A", PROJECT_ID
            ),
            repository=self.repository,
        )
        self.assertIs(local.state, self.domain.ReadinessSourceState.SATISFIED)

        other_project = self.seed_project(OTHER_PROJECT_ID, owner="other@example.invalid")
        self.seed_member(OTHER_PROJECT_ID, OTHER_MEMBER_ID)
        self.seed_gate(OTHER_PROJECT_ID, "G6", OTHER_GATE_G6_ID)
        self.seed_gate(OTHER_PROJECT_ID, "G7", uuid4())
        self.initialize_project(
            OTHER_PROJECT_ID,
            member_id=OTHER_MEMBER_ID,
            key="4" * 64,
            published=published,
        )
        other_frozen = self.module._project_revision_chain(other_project)[-1].project
        request = self.source_validation.ReadinessSourceRequest(
            requirement_key="project_truth",
            kind=self.domain.ReadinessSourceKind.PROJECT,
            global_id=OTHER_PROJECT_ID,
            source_version=other_frozen.optimistic_version,
            snapshot_hash=other_frozen.snapshot_hash,
        )

        with self.assertRaises(self.errors.RequestValidationFailed):
            self.source_resolver.resolve_source(
                request,
                context=self.source_resolver.SourceResolutionContext(
                    "TENANT-A", PROJECT_ID
                ),
                repository=self.repository,
            )

    def test_gate_input_includes_only_matching_applicable_incomplete_p0_and_exact_dependency(self) -> None:
        initialized = self.initialize_project()
        assert initialized is not None
        first = initialized.response["currentRevision"]
        revised = self.repository.revise_readiness(
            PROJECT_ID,
            UUID(first["instanceGlobalId"]),
            idempotency_key_hash="4" * 64,
            expected_instance_version=1,
            expected_revision_global_id=UUID(first["globalId"]),
            expected_revision_snapshot_hash=first["snapshotHash"],
            item_key="done_g6",
            owner_member_global_id=MEMBER_ID,
            due_date=date(2026, 9, 2),
            state=self.domain.ReadinessItemState.COMPLETE,
            confirmation_value="Confirmed",
            source_requests=(),
        )
        assert revised is not None
        current = revised.response["currentRevision"]

        projection = self.module.current_gate_readiness_input(
            project_id=PROJECT_ID,
            gate_id=GATE_G6_ID,
        )
        self.assertEqual(len(projection["blockers"]), 1)
        blocker = projection["blockers"][0]
        current_items = {
            item["definition"]["key"]: item for item in current["items"]
        }
        self.assertEqual(blocker["globalId"], current_items["p0_g6"]["globalId"])
        self.assertNotIn(
            current_items["p1_g6"]["globalId"],
            {item["globalId"] for item in projection["blockers"]},
        )
        self.assertNotIn(
            current_items["done_g6"]["globalId"],
            {item["globalId"] for item in projection["blockers"]},
        )
        self.assertNotIn(
            current_items["p0_g7"]["globalId"],
            {item["globalId"] for item in projection["blockers"]},
        )
        self.assertNotIn(
            current_items["not_applicable_g6"]["globalId"],
            {item["globalId"] for item in projection["blockers"]},
        )
        self.assertEqual(
            projection["dependency"],
            {
                "globalId": current["globalId"],
                "version": current["instanceVersion"],
                "snapshotHash": current["snapshotHash"],
            },
        )
        self.assertEqual(
            self.module.current_gate_readiness_input(
                project_id=PROJECT_ID,
                gate_id=uuid4(),
            ),
            {"blockers": (), "dependency": None},
        )


if __name__ == "__main__":
    unittest.main()
