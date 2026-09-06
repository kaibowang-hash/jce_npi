from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


from tests.test_phase7_production_transition_domain import (  # noqa: E402
    ACTION,
    CONTEXT_SOURCE,
    NOW,
    PROJECT_ID,
    RECEIVER_MEMBER,
    RECEIVER_ROLE,
    RETROSPECTIVE_SOURCE,
    SENDER_MEMBER,
    SENDER_ROLE,
    SOURCE,
    TENANT,
    draft_policy,
    package,
    policy,
    project,
    slots,
    uid,
)
from npi_core.production_transition.domain import (  # noqa: E402
    create_handover_package_revision,
    create_handover_package_successor,
    create_observation_period_revision,
    create_observation_period_successor,
)
from npi_core.production_transition.request_validation import (  # noqa: E402
    AcknowledgementIntent,
    CreateObservationRequest,
    CreatePolicyRequest,
    EditPolicyRequest,
    ExactSourceSelection,
    HandoverContentRequest,
    HandoverReferenceRequest,
    ManifestSourceSelection,
    NextPolicyVersionRequest,
    ObservationRevisionRequest,
    PolicyDefinitionRequest,
    PolicyReferenceRequest,
    PublishPolicyRequest,
    ReviseHandoverRequest,
    SlotAssignmentSelection,
)
from npi_core.production_transition.response_validation import (  # noqa: E402
    ProductionTransitionResponseInvalid,
)


REQUEST_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(
        self,
        owner: "Phase7ProductionTransitionRepositoryTest",
        values: dict[str, Any],
    ) -> None:
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
    def __init__(self, owner: "Phase7ProductionTransitionRepositoryTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def exists(self, doctype: str, filters: dict[str, Any] | str) -> bool:
        if isinstance(filters, dict):
            return bool(self.owner.matching(doctype, filters))
        return str(filters) in self.owner.documents.get(doctype, {})

    def count(self, doctype: str, filters: dict[str, Any]) -> int:
        return len(self.owner.matching(doctype, filters))

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fields: object,
        *,
        as_dict: bool = False,
        for_update: bool = False,
    ):
        self.owner.db_get_value_calls.append(
            {
                "doctype": doctype,
                "name_or_filters": copy.deepcopy(name_or_filters),
                "fields": copy.deepcopy(fields),
                "as_dict": as_dict,
                "for_update": for_update,
            }
        )
        if isinstance(name_or_filters, dict):
            matches = self.owner.matching(doctype, name_or_filters)
            document = matches[0] if matches else None
        else:
            document = self.owner.documents.get(doctype, {}).get(
                str(name_or_filters)
            )
        if document is None:
            return None
        if isinstance(fields, list):
            values = AttrDict({field: document.get(field) for field in fields})
            return values if as_dict else tuple(values.values())
        return document.get(str(fields))

    def rollback(self) -> None:
        self.rollback_count += 1


class Phase7ProductionTransitionRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.production_transition.frappe_validation",
        "npi_core.production_transition.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.events: list[tuple[str, str, str]] = []
        self.lookups: list[tuple[str, str, bool]] = []
        self.get_all_calls: list[dict[str, Any]] = []
        self.db_get_value_calls: list[dict[str, Any]] = []
        self.fail_on: tuple[str, str] | None = None
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError", (Exception,), {}
        )
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError", (Exception,), {}
        )
        self.frappe.PermissionError = type("PermissionError", (Exception,), {})
        self.frappe.ValidationError = type("ValidationError", (Exception,), {})
        self.frappe.db = FakeDatabase(self)
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = self.get_all
        self.frappe.throw = self.frappe_throw
        sys.modules["frappe"] = self.frappe

        self.module = importlib.import_module(
            "npi_core.production_transition.frappe_repository"
        )
        self.security = importlib.import_module("npi_core.foundation.security")
        self.errors = importlib.import_module("npi_core.foundation.errors")
        self.repository = self.repository_for()

        self.seed_user("admin@example.invalid")
        self.project = self.seed_project()
        self.seed_member(SENDER_MEMBER)
        self.seed_member(RECEIVER_MEMBER)
        self.seed_role(SENDER_ROLE)
        self.seed_role(RECEIVER_ROLE)

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
        tenant_id: str | None = TENANT,
        external: bool = False,
        request_id: str = REQUEST_ID,
    ):
        return self.module.FrappeProductionTransitionRepository(
            principal=self.security.Principal(
                user_id=user_id,
                roles=roles,
                is_external=external,
                tenant_id=tenant_id,
            ),
            request_id=request_id,
            trace_id="trace-p706-repository",
        )

    def add(
        self,
        doctype: str,
        values: dict[str, Any],
        *,
        storage_name: str | None = None,
    ) -> FakeDocument:
        document = FakeDocument(self, {"doctype": doctype, **values})
        if storage_name is None:
            return document.insert()
        document.name = storage_name
        event = ("insert", doctype, storage_name)
        self.events.append(event)
        bucket = self.documents.setdefault(doctype, {})
        if storage_name in bucket:
            raise self.frappe.DuplicateEntryError()
        bucket[storage_name] = document
        return document

    def get_doc(
        self,
        doctype_or_values: str | dict[str, Any],
        name: str | None = None,
        **kwargs: Any,
    ):
        if isinstance(doctype_or_values, dict):
            return FakeDocument(self, dict(doctype_or_values))
        self.lookups.append(
            (str(doctype_or_values), str(name), bool(kwargs.get("for_update")))
        )
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
            if operator == "in":
                return str(actual) in {str(item) for item in value}
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
        self.get_all_calls.append(
            {
                "doctype": doctype,
                "filters": dict(filters),
                "pluck": pluck,
                "fields": list(fields) if fields else None,
                "order_by": order_by,
                "limit_page_length": limit_page_length,
            }
        )
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

    def seed_user(self, user_id: str, *, enabled: int = 1) -> FakeDocument:
        existing = self.documents.get("User", {}).get(user_id)
        if existing is not None:
            existing.enabled = enabled
            return existing
        return self.add(
            "User",
            {"name": user_id, "enabled": enabled, "user_type": "System User"},
        )

    def seed_project(self) -> FakeDocument:
        value = project()
        existing = self.documents.get("NPI Engineering Project", {}).get(
            str(value.global_id)
        )
        if existing is not None:
            return existing
        return self.add(
            "NPI Engineering Project",
            {
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "business_code": value.business_code,
                "title": value.title,
                "project_type": value.project_type.value,
                "owner_user_id": value.owner_user_id,
                "target_sop": value.target_sop_date.isoformat()
                if value.target_sop_date
                else None,
                "lifecycle_state": value.lifecycle_state,
                "optimistic_version": value.optimistic_version,
                "source_system": "NPI_ONE",
                "template_global_id": str(value.template_ref.global_id),
                "template_version": value.template_ref.version,
                "template_snapshot_hash": value.template_ref.snapshot_hash,
                "template_snapshot": {},
                "work_policy_global_id": str(value.work_policy_ref.global_id),
                "work_policy_version": value.work_policy_ref.version,
                "work_policy_snapshot_hash": value.work_policy_ref.snapshot_hash,
                "references": [
                    AttrDict(
                        reference_type="customer",
                        source_system="ERPNEXT",
                        source_object_id="CUST-001",
                    )
                ],
            },
        )

    def source_context(self):
        return self.module.SourceResolutionContext(TENANT, PROJECT_ID)

    def seed_source(
        self,
        doctype: str,
        global_id: UUID,
        **values: Any,
    ) -> FakeDocument:
        return self.add(
            doctype,
            {
                "global_id": str(global_id),
                "tenant_id": TENANT,
                "project_global_id": str(PROJECT_ID),
                **values,
            },
        )

    def seed_complete_file_revision(
        self,
        global_id: UUID,
        *,
        file_document_id: UUID,
        frappe_file_id: str,
        file_name: str,
        file_url: str,
        content_hash: str,
        sha256: str,
        size_bytes: int,
        revision: int,
        optimistic_version: int,
    ) -> tuple[FakeDocument, FakeDocument]:
        file_revision = self.seed_source(
            "NPI File Revision",
            global_id,
            document_global_id=str(file_document_id),
            revision=revision,
            revision_key=f"{file_document_id}:{revision}",
            frappe_file_id=frappe_file_id,
            frappe_content_hash=content_hash,
            file=file_url,
            file_name=file_name,
            mime_type="application/pdf",
            size_bytes=size_bytes,
            sha256=sha256,
            is_private=1,
            scan_state="clean",
            scan_observed_at="2026-08-14 07:30:00+00:00",
            released=1,
            optimistic_version=optimistic_version,
        )
        live_file = self.add(
            "File",
            {
                "name": frappe_file_id,
                "is_private": 1,
                "is_remote_file": 0,
                "file_url": file_url,
                "file_name": file_name,
                "file_size": size_bytes,
                "content_hash": content_hash,
            },
        )
        return file_revision, live_file

    @staticmethod
    def complete_file_revision_identity(document: FakeDocument) -> bool:
        required = (
            "global_id",
            "tenant_id",
            "project_global_id",
            "document_global_id",
            "revision",
            "revision_key",
            "frappe_file_id",
            "frappe_content_hash",
            "file",
            "file_name",
            "mime_type",
            "size_bytes",
            "sha256",
            "is_private",
            "scan_state",
            "released",
            "optimistic_version",
        )
        return bool(
            all(document.get(field) not in {None, ""} for field in required)
            and type(document.revision) is int
            and document.revision > 0
            and type(document.optimistic_version) is int
            and document.optimistic_version > 0
            and type(document.size_bytes) is int
            and document.size_bytes >= 0
            and int(document.is_private) == 1
        )

    @classmethod
    def file_revision_source_snapshot(
        cls,
        document: FakeDocument,
    ) -> dict[str, object]:
        if not cls.complete_file_revision_identity(document):
            raise ValueError("incomplete file revision")
        return {
            "documentGlobalId": str(document.document_global_id),
            "fileContentHash": str(document.frappe_content_hash),
            "fileId": str(document.frappe_file_id),
            "fileName": str(document.file_name),
            "fileOptimisticVersion": int(document.optimistic_version),
            "globalId": str(document.global_id),
            "isPrivate": True,
            "mimeType": str(document.mime_type),
            "released": bool(document.released),
            "revision": int(document.revision),
            "scanObservedAt": str(document.scan_observed_at),
            "scanState": str(document.scan_state),
            "sha256": str(document.sha256),
            "sizeBytes": int(document.size_bytes),
        }

    def file_revision_module(self) -> types.ModuleType:
        module = types.ModuleType(
            "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision"
        )
        module.has_complete_file_revision_identity = (
            self.complete_file_revision_identity
        )
        module.file_revision_source_snapshot = self.file_revision_source_snapshot
        return module

    def seed_member(self, value) -> FakeDocument:
        self.seed_user(value.user_id)
        return self.add(
            "NPI Project Member",
            {
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "user_id": value.user_id,
                "effective_from": value.effective_from.isoformat(),
                "effective_to": value.effective_to.isoformat()
                if value.effective_to
                else None,
                "optimistic_version": value.optimistic_version,
            },
        )

    def seed_role(self, value) -> FakeDocument:
        return self.add(
            "NPI Project Role Assignment",
            {
                "global_id": str(value.global_id),
                "tenant_id": value.tenant_id,
                "project_global_id": str(value.project_global_id),
                "member_global_id": str(value.member_global_id),
                "role_key": value.role_key,
                "effective_from": value.effective_from.isoformat(),
                "effective_to": value.effective_to.isoformat()
                if value.effective_to
                else None,
                "optimistic_version": value.optimistic_version,
            },
        )

    @staticmethod
    def policy_definition() -> PolicyDefinitionRequest:
        value = draft_policy()
        return PolicyDefinitionRequest(
            applicability=value.applicability,
            receiving_groups=value.receiving_groups,
            acknowledgement_slots=value.acknowledgement_slots,
            handover_requirements=value.handover_requirements,
            observation_source_rules=value.observation_source_rules,
            observation_window_days=value.observation_window_days,
        )

    @classmethod
    def create_policy_request(
        cls,
        *,
        code: str = "PROD-TRANSITION",
        title: str = "Synthetic production transition policy",
    ) -> CreatePolicyRequest:
        return CreatePolicyRequest(code, title, cls.policy_definition())

    def seed_published_policy(self, value=None):
        value = value or policy()
        self.add(
            "NPI Production Transition Policy",
            {
                "global_id": str(value.policy_global_id),
                "tenant_id": value.tenant_id,
                "policy_code": value.policy_code,
                "policy_code_key_hash": self.module._policy_code_key_hash(
                    value.tenant_id,
                    value.policy_code,
                ),
                "title": value.title,
                "optimistic_version": value.optimistic_version,
            },
        )
        self.add(
            "NPI Production Transition Policy Version",
            {
                "global_id": str(value.global_id),
                "policy": str(value.policy_global_id),
                "policy_global_id": str(value.policy_global_id),
                "tenant_id": value.tenant_id,
                "version_key_hash": value.version_key_hash,
                "policy_code": value.policy_code,
                "policy_version": value.policy_version,
                "optimistic_version": value.optimistic_version,
                "title": value.title,
                "publication_state": value.publication_state.value,
                "predecessor_global_id": None,
                "predecessor_snapshot_hash": None,
                "policy_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            },
        )
        return value

    @staticmethod
    def published_policy_for_tenant(
        tenant_id: str,
        policy_id: UUID,
        *,
        code: str = "PROD-TRANSITION",
    ):
        template = draft_policy()
        draft = type(template).create_draft(
            policy_global_id=policy_id,
            tenant_id=tenant_id,
            policy_code=code,
            title=template.title,
            applicability=template.applicability,
            receiving_groups=template.receiving_groups,
            acknowledgement_slots=template.acknowledgement_slots,
            handover_requirements=template.handover_requirements,
            observation_source_rules=template.observation_source_rules,
            observation_window_days=template.observation_window_days,
            changed_by_user_id=template.changed_by_user_id,
            changed_at=template.changed_at,
            request_id=template.request_id,
            trace_id=template.trace_id,
        )
        return draft.publish(
            expected_version=1,
            changed_by_user_id="publisher@example.invalid",
            changed_at=NOW,
            request_id=uid(972),
            trace_id="trace-p706-policy-other-tenant",
        )

    @staticmethod
    def policy_reference(value) -> PolicyReferenceRequest:
        return PolicyReferenceRequest(
            policy_global_id=value.policy_global_id,
            policy_version=value.policy_version,
            policy_snapshot_hash=value.snapshot_hash,
        )

    @staticmethod
    def handover_reference(value) -> HandoverReferenceRequest:
        return HandoverReferenceRequest(
            handover_global_id=value.handover_global_id,
            handover_version=value.handover_version,
            handover_revision_global_id=value.global_id,
            handover_snapshot_hash=value.snapshot_hash,
        )

    @classmethod
    def handover_content(
        cls,
        value,
        *,
        reason: str,
    ) -> HandoverContentRequest:
        return HandoverContentRequest(
            expected_project_version=project().optimistic_version,
            policy=cls.policy_reference(value),
            slot_assignments=(
                SlotAssignmentSelection(
                    slot_key="sender",
                    member_global_id=SENDER_MEMBER.global_id,
                    member_expected_version=SENDER_MEMBER.optimistic_version,
                    role_assignment_global_id=SENDER_ROLE.global_id,
                    role_expected_version=SENDER_ROLE.optimistic_version,
                ),
                SlotAssignmentSelection(
                    slot_key="receiver",
                    member_global_id=RECEIVER_MEMBER.global_id,
                    member_expected_version=RECEIVER_MEMBER.optimistic_version,
                    role_assignment_global_id=RECEIVER_ROLE.global_id,
                    role_expected_version=RECEIVER_ROLE.optimistic_version,
                ),
            ),
            manifest_sources=(
                ManifestSourceSelection(
                    requirement_key=SOURCE.requirement_key,
                    kind=SOURCE.kind.value,
                    global_id=SOURCE.global_id,
                    expected_version=SOURCE.source_version,
                ),
            ),
            reason=reason,
        )

    def assert_no_adjacent_truth_mutation(
        self,
        project_before: dict[str, Any],
    ) -> None:
        self.assertEqual(dict(self.project), project_before)
        forbidden = (
            "NPI Engineering Project",
            "NPI Domain Work Item",
            "NPI Gate",
            "ERP",
            "Outbox",
        )
        written = {
            doctype
            for action, doctype, _name in self.events
            if action in {"insert", "save"}
        }
        self.assertFalse(
            any(
                token in doctype
                for token in forbidden
                for doctype in written
            ),
            written,
        )

    def audit_summary(self, operation: str) -> dict[str, Any]:
        matching = [
            document.input_summary
            for document in self.documents.get("NPI Audit Event", {}).values()
            if document.operation == operation
        ]
        self.assertEqual(len(matching), 1, matching)
        self.assertIsInstance(matching[0], dict)
        return matching[0]

    def assert_audit_summary_omits_sensitive_material(
        self,
        summary: dict[str, Any],
    ) -> None:
        serialized = json.dumps(summary, sort_keys=True).casefold()
        for marker in (
            "url",
            "token",
            "secret",
            "/private/files/",
            "http://",
            "https://",
            "authorization",
            "bearer ",
        ):
            self.assertNotIn(marker, serialized)

    def seed_handover(self, value, *, storage_name: str | None = None) -> FakeDocument:
        return self.add(
            "NPI Handover Package Revision",
            {
                "global_id": str(value.global_id),
                "handover_global_id": str(value.handover_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project": str(value.project.global_id),
                "project_global_id": str(value.project.global_id),
                "project_optimistic_version": value.project.optimistic_version,
                "project_snapshot_hash": value.project.snapshot_hash,
                "policy_version": str(value.policy_ref.global_id),
                "policy_version_global_id": str(value.policy_ref.global_id),
                "policy_business_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "handover_version": value.handover_version,
                "predecessor_global_id": str(value.predecessor_global_id)
                if value.predecessor_global_id
                else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "readiness_revision_global_id": str(value.readiness_ref.global_id)
                if value.readiness_ref
                else None,
                "readiness_revision_version": value.readiness_ref.version
                if value.readiness_ref
                else None,
                "readiness_revision_snapshot_hash": value.readiness_ref.snapshot_hash
                if value.readiness_ref
                else None,
                "project_snapshot": value.project.snapshot_payload(),
                "slot_snapshot": [item.snapshot_payload() for item in value.slots],
                "manifest_snapshot": [
                    item.snapshot_payload() for item in value.manifest
                ],
                "unresolved_selector_snapshot": {
                    "mode": "all_non_terminal",
                    "kinds": ["action", "decision_request", "issue", "risk"],
                },
                "unresolved_action_snapshot": [
                    item.snapshot_payload() for item in value.unresolved_actions
                ],
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": value.created_at,
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "package_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            },
            storage_name=storage_name,
        )

    def seed_observation(self, value, *, storage_name: str | None = None) -> FakeDocument:
        return self.add(
            "NPI Observation Period Revision",
            {
                "global_id": str(value.global_id),
                "observation_global_id": str(value.observation_global_id),
                "version_key_hash": value.version_key_hash,
                "tenant_id": value.tenant_id,
                "project": str(value.project.global_id),
                "project_global_id": str(value.project.global_id),
                "project_optimistic_version": value.project.optimistic_version,
                "project_snapshot_hash": value.project.snapshot_hash,
                "policy_version": str(value.policy_ref.global_id),
                "policy_version_global_id": str(value.policy_ref.global_id),
                "policy_business_version": value.policy_ref.version,
                "policy_snapshot_hash": value.policy_ref.snapshot_hash,
                "observation_version": value.observation_version,
                "predecessor_global_id": str(value.predecessor_global_id)
                if value.predecessor_global_id
                else None,
                "predecessor_snapshot_hash": value.predecessor_snapshot_hash,
                "handover_package_revision": str(
                    value.handover_package_ref.global_id
                )
                if value.handover_package_ref
                else None,
                "handover_package_revision_global_id": str(
                    value.handover_package_ref.global_id
                )
                if value.handover_package_ref
                else None,
                "handover_package_version": value.handover_package_ref.version
                if value.handover_package_ref
                else None,
                "handover_package_snapshot_hash": (
                    value.handover_package_ref.snapshot_hash
                    if value.handover_package_ref
                    else None
                ),
                "project_snapshot": value.project.snapshot_payload(),
                "provider_source_snapshot": [
                    item.snapshot_payload() for item in value.providers
                ],
                "context_reference_snapshot": [
                    item.snapshot_payload() for item in value.context_references
                ],
                "retrospective_evidence_snapshot": [
                    item.snapshot_payload()
                    for item in value.retrospective_references
                ],
                "observation_state": value.observation_state.value,
                "technical_disposition": value.technical_disposition.value,
                "retrospective_note": value.retrospective_note,
                "reason": value.reason,
                "created_by_user_id": value.created_by_user_id,
                "created_at": value.created_at,
                "request_id": str(value.request_id),
                "trace_id": value.trace_id,
                "observation_snapshot": value.snapshot_payload(),
                "snapshot_hash": value.snapshot_hash,
            },
            storage_name=storage_name,
        )

    def test_policy_create_edit_publish_and_next_version_are_exact(self) -> None:
        created = self.repository.create_policy(
            idempotency_key_hash="1" * 64,
            request=self.create_policy_request(),
        )
        self.assertFalse(created.replayed)
        policy_id = UUID(created.response["policyGlobalId"])
        version_id = UUID(created.response["globalId"])
        self.assertEqual(created.target_global_id, policy_id)
        self.assertEqual(created.response["policyVersion"], 1)
        self.assertEqual(created.response["optimisticVersion"], 1)
        self.assertEqual(created.response["publicationState"], "draft")

        edited = self.repository.edit_policy(
            policy_id,
            1,
            idempotency_key_hash="2" * 64,
            request=EditPolicyRequest(
                expected_optimistic_version=1,
                title="Edited production transition policy",
                definition=self.policy_definition(),
            ),
        )
        self.assertEqual(edited.target_global_id, version_id)
        self.assertEqual(edited.response["globalId"], str(version_id))
        self.assertEqual(edited.response["optimisticVersion"], 2)

        published = self.repository.publish_policy(
            policy_id,
            1,
            idempotency_key_hash="3" * 64,
            request=PublishPolicyRequest(
                expected_optimistic_version=2,
                expected_snapshot_hash=edited.response["snapshotHash"],
            ),
        )
        self.assertEqual(published.response["publicationState"], "published")
        self.assertEqual(published.response["optimisticVersion"], 3)

        successor = self.repository.create_policy_version(
            policy_id,
            idempotency_key_hash="4" * 64,
            request=NextPolicyVersionRequest(
                expected_published_version=1,
                expected_published_snapshot_hash=published.response["snapshotHash"],
            ),
        )
        self.assertEqual(successor.response["policyVersion"], 2)
        self.assertEqual(successor.response["publicationState"], "draft")
        self.assertEqual(
            successor.response["priorVersionRef"]["globalId"],
            published.response["globalId"],
        )
        self.assertEqual(
            successor.response["priorVersionRef"]["snapshotHash"],
            published.response["snapshotHash"],
        )
        self.assertEqual(
            len(self.documents["NPI Production Transition Policy Version"]), 2
        )

    def test_policy_code_and_idempotency_are_isolated_by_actor_tenant(self) -> None:
        request = self.create_policy_request()
        tenant_a = self.repository.create_policy(
            idempotency_key_hash="a" * 64,
            request=request,
        )
        tenant_b_repository = self.repository_for(tenant_id="tenant-b")
        tenant_b = tenant_b_repository.create_policy(
            idempotency_key_hash="a" * 64,
            request=request,
        )
        with self.assertRaises(self.module.ProductionTransitionVersionConflict):
            self.repository.create_policy(
                idempotency_key_hash="f" * 64,
                request=self.create_policy_request(code="prod-transition"),
            )

        self.assertEqual(tenant_a.response["tenantId"], TENANT)
        self.assertEqual(tenant_b.response["tenantId"], "tenant-b")
        self.assertNotEqual(tenant_a.target_global_id, tenant_b.target_global_id)
        roots = tuple(
            self.documents["NPI Production Transition Policy"].values()
        )
        self.assertEqual({root.policy_code for root in roots}, {"PROD-TRANSITION"})
        self.assertEqual({root.tenant_id for root in roots}, {TENANT, "tenant-b"})
        self.assertEqual(len({root.policy_code_key_hash for root in roots}), 2)
        receipts = tuple(
            self.documents[
                "NPI Production Transition Command Idempotency"
            ].values()
        )
        self.assertEqual({receipt.tenant_id for receipt in receipts}, {TENANT, "tenant-b"})
        audits = tuple(self.documents["NPI Audit Event"].values())
        self.assertEqual(
            {audit.input_summary["tenantId"] for audit in audits},
            {TENANT, "tenant-b"},
        )

    def test_policy_catalog_and_uuid_commands_never_cross_tenant_boundary(self) -> None:
        same_tenant = self.seed_published_policy()
        cross_tenant = self.published_policy_for_tenant(
            "tenant-b",
            uid(970),
        )
        self.seed_published_policy(cross_tenant)

        with patch.object(
            self.module,
            "_project_snapshot",
            return_value=project(),
        ):
            catalog = self.repository.policy_catalog(PROJECT_ID)
        self.assertEqual(
            [item["policyGlobalId"] for item in catalog["policies"]],
            [str(same_tenant.policy_global_id)],
        )
        policy_queries = [
            call
            for call in self.get_all_calls
            if call["doctype"] == "NPI Production Transition Policy Version"
        ]
        self.assertTrue(policy_queries)
        self.assertTrue(
            all(call["filters"].get("tenant_id") == TENANT for call in policy_queries)
        )

        tenant_b_repository = self.repository_for(tenant_id="tenant-b")
        version_before = copy.deepcopy(
            dict(
                self.documents["NPI Production Transition Policy Version"][
                    str(same_tenant.global_id)
                ]
            )
        )
        root_before = copy.deepcopy(
            dict(
                self.documents["NPI Production Transition Policy"][
                    str(same_tenant.policy_global_id)
                ]
            )
        )
        self.events.clear()
        self.lookups.clear()
        self.assertIsNone(
            tenant_b_repository.edit_policy(
                same_tenant.policy_global_id,
                same_tenant.policy_version,
                idempotency_key_hash="b" * 64,
                request=EditPolicyRequest(
                    expected_optimistic_version=same_tenant.optimistic_version,
                    title="Cross-tenant mutation must remain unavailable",
                    definition=self.policy_definition(),
                ),
            )
        )
        self.assertIsNone(
            tenant_b_repository.publish_policy(
                same_tenant.policy_global_id,
                same_tenant.policy_version,
                idempotency_key_hash="d" * 64,
                request=PublishPolicyRequest(
                    expected_optimistic_version=same_tenant.optimistic_version,
                    expected_snapshot_hash=same_tenant.snapshot_hash,
                ),
            )
        )
        self.assertIsNone(
            tenant_b_repository.create_policy_version(
                same_tenant.policy_global_id,
                idempotency_key_hash="c" * 64,
                request=NextPolicyVersionRequest(
                    expected_published_version=same_tenant.policy_version,
                    expected_published_snapshot_hash=same_tenant.snapshot_hash,
                ),
            )
        )
        self.assertEqual(
            dict(
                self.documents["NPI Production Transition Policy Version"][
                    str(same_tenant.global_id)
                ]
            ),
            version_before,
        )
        self.assertEqual(
            dict(
                self.documents["NPI Production Transition Policy"][
                    str(same_tenant.policy_global_id)
                ]
            ),
            root_before,
        )
        self.assertFalse(
            any(
                doctype
                in {
                    "NPI Production Transition Policy",
                    "NPI Production Transition Policy Version",
                }
                for action, doctype, _name in self.events
                if action in {"insert", "save"}
            )
        )
        self.assertNotIn(
            (
                "NPI Production Transition Policy Version",
                str(same_tenant.global_id),
                True,
            ),
            self.lookups,
        )

    def test_policy_receipt_replay_is_actor_bound_and_payload_conflicts(self) -> None:
        request = self.create_policy_request()
        created = self.repository.create_policy(
            idempotency_key_hash="5" * 64,
            request=request,
        )
        replayed = self.repository.create_policy(
            idempotency_key_hash="5" * 64,
            request=request,
        )
        self.assertTrue(replayed.replayed)
        self.assertEqual(replayed.response, created.response)
        self.assertEqual(replayed.target_global_id, created.target_global_id)
        self.assertEqual(
            len(self.documents["NPI Production Transition Policy Version"]), 1
        )

        with self.assertRaises(self.module.ProductionTransitionIdempotencyConflict):
            self.repository.create_policy(
                idempotency_key_hash="5" * 64,
                request=self.create_policy_request(title="A different payload"),
            )

        self.seed_user("other-admin@example.invalid")
        other_actor = self.repository_for(
            user_id="other-admin@example.invalid",
            request_id="fb233de2-5d4d-4556-ad16-9476d8f0776f",
        )
        other_actor.create_policy(
            idempotency_key_hash="5" * 64,
            request=self.create_policy_request(
                code="PROD-TRANSITION-OTHER",
                title="Other actor policy",
            ),
        )
        receipts = tuple(
            self.documents["NPI Production Transition Command Idempotency"].values()
        )
        self.assertEqual(len(receipts), 2)
        self.assertEqual(
            {value.actor_user_id for value in receipts},
            {"admin@example.invalid", "other-admin@example.invalid"},
        )
        self.assertTrue(all(value.project_global_id is None for value in receipts))
        self.assertTrue(all(value.sealed == 1 for value in receipts))
        self.assertTrue(all(value.target_global_id for value in receipts))

    def test_policy_receipt_replay_rejects_cross_tenant_canonical_payload(self) -> None:
        request = self.create_policy_request()
        created = self.repository.create_policy(
            idempotency_key_hash="e" * 64,
            request=request,
        )
        receipt = next(
            iter(
                self.documents[
                    "NPI Production Transition Command Idempotency"
                ].values()
            )
        )
        created_snapshot = copy.deepcopy(created.response)
        created_snapshot.pop("snapshotHash")
        other_tenant = replace(
            self.module.policy_from_snapshot(created_snapshot),
            tenant_id="tenant-b",
        )
        cross_tenant_response = {
            **other_tenant.snapshot_payload(),
            "snapshotHash": other_tenant.snapshot_hash,
        }
        self.assertEqual(
            cross_tenant_response["policyGlobalId"],
            created.response["policyGlobalId"],
        )
        receipt.response_payload = cross_tenant_response
        receipt.response_hash = self.module._payload_hash(cross_tenant_response)
        self.events.clear()

        with self.assertRaises(ProductionTransitionResponseInvalid):
            self.repository.create_policy(
                idempotency_key_hash="e" * 64,
                request=request,
            )
        self.assertEqual(self.events, [])

    def test_receipt_business_rows_audit_and_seal_are_ordered(self) -> None:
        self.events.clear()
        outcome = self.repository.create_policy(
            idempotency_key_hash="6" * 64,
            request=self.create_policy_request(),
        )
        self.assertIsNotNone(outcome)
        observed = [(action, doctype) for action, doctype, _name in self.events]
        self.assertEqual(
            observed,
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Production Transition Policy"),
                ("insert", "NPI Production Transition Policy Version"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        receipt = next(
            iter(self.documents["NPI Production Transition Command Idempotency"].values())
        )
        self.assertEqual(receipt.sealed, 1)
        self.assertEqual(receipt.response_payload, outcome.response)

    def test_failure_before_audit_never_seals_or_replays_fake_success(self) -> None:
        self.fail_on = ("insert", "NPI Audit Event")
        with self.assertRaisesRegex(RuntimeError, "Injected failure"):
            self.repository.create_policy(
                idempotency_key_hash="7" * 64,
                request=self.create_policy_request(),
            )
        receipt = next(
            iter(self.documents["NPI Production Transition Command Idempotency"].values())
        )
        self.assertEqual(receipt.sealed, 0)
        self.assertFalse(receipt.response_payload)
        self.assertNotIn(
            ("save", "NPI Production Transition Command Idempotency"),
            [(action, doctype) for action, doctype, _name in self.events],
        )

        self.fail_on = None
        with self.assertRaisesRegex(RuntimeError, "receipt integrity failed"):
            self.repository.create_policy(
                idempotency_key_hash="7" * 64,
                request=self.create_policy_request(),
            )

    def test_published_policy_root_must_match_the_exact_current_chain_tip(
        self,
    ) -> None:
        published = self.seed_published_policy()
        root = self.documents["NPI Production Transition Policy"][
            str(published.policy_global_id)
        ]
        expected = {
            "global_id": root.global_id,
            "tenant_id": root.tenant_id,
            "policy_code": root.policy_code,
            "policy_code_key_hash": root.policy_code_key_hash,
            "title": root.title,
            "optimistic_version": root.optimistic_version,
        }
        drifted = {
            "global_id": str(uid(980)),
            "tenant_id": "tenant-b",
            "policy_code": "DRIFTED-POLICY-CODE",
            "policy_code_key_hash": "0" * 64,
            "title": "Drifted policy title",
            "optimistic_version": int(root.optimistic_version) + 1,
        }
        request = self.handover_content(
            published,
            reason="Reject a policy root that disagrees with its current tip.",
        )

        for index, (field, wrong_value) in enumerate(drifted.items(), start=1):
            with self.subTest(field=field):
                root[field] = wrong_value
                self.events.clear()
                with (
                    patch.object(
                        self.module,
                        "_project_snapshot",
                        return_value=project(),
                    ),
                    patch.object(
                        self.module,
                        "resolve_manifest_sources",
                        return_value=(SOURCE,),
                    ),
                    self.assertRaisesRegex(
                        RuntimeError,
                        "Policy root (?:integrity failed|is unavailable)",
                    ),
                ):
                    self.repository.create_handover(
                        PROJECT_ID,
                        idempotency_key_hash=f"{index:x}" * 64,
                        request=request,
                    )
                self.assertEqual(self.events, [])
                root[field] = expected[field]

    def test_create_handover_persists_one_current_tip_without_adjacent_mutation(
        self,
    ) -> None:
        published = self.seed_published_policy()
        request = self.handover_content(
            published,
            reason="Create the exact production handover package.",
        )
        project_before = copy.deepcopy(dict(self.project))
        self.events.clear()

        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_manifest_sources",
                return_value=(SOURCE,),
            ) as resolver,
        ):
            outcome = self.repository.create_handover(
                PROJECT_ID,
                idempotency_key_hash="c" * 64,
                request=request,
            )

        self.assertIsNotNone(outcome)
        revision = outcome.response["handoverPackage"]
        self.assertEqual(revision["handoverVersion"], 1)
        self.assertIsNone(revision["predecessorGlobalId"])
        self.assertEqual(revision["manifest"], [SOURCE.snapshot_payload()])
        self.assertEqual(len(self.documents["NPI Handover Package Revision"]), 1)
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Handover Package Revision"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        audit = self.audit_summary("production_handover.create")
        self.assertEqual(audit["tenantId"], TENANT)
        self.assertEqual(audit["policyRef"], revision["policyRef"])
        self.assertEqual(audit["manifestSourceSummary"], revision["manifest"])
        self.assertIsNone(audit["predecessorGlobalId"])
        self.assertIsNone(audit["predecessorSnapshotHash"])
        self.assertEqual(audit["occurredAt"], revision["createdAt"])
        self.assert_audit_summary_omits_sensitive_material(audit)
        resolver.assert_called_once()
        workspace = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            workspace["currentHandover"]["revision"]["globalId"],
            revision["globalId"],
        )
        self.assertEqual(len(workspace["handoverHistory"]), 1)
        self.assert_no_adjacent_truth_mutation(project_before)

    def test_revise_handover_appends_exact_successor_and_rejects_stale_tip(
        self,
    ) -> None:
        published = self.seed_published_policy()
        project_before = copy.deepcopy(dict(self.project))
        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_manifest_sources",
                return_value=(SOURCE,),
            ),
        ):
            created = self.repository.create_handover(
                PROJECT_ID,
                idempotency_key_hash="d" * 64,
                request=self.handover_content(
                    published,
                    reason="Create the handover predecessor.",
                ),
            )
        first = created.response["handoverPackage"]
        request = ReviseHandoverRequest(
            expected_revision_global_id=UUID(first["globalId"]),
            expected_snapshot_hash=first["snapshotHash"],
            content=self.handover_content(
                published,
                reason="Append the exact corrected handover successor.",
            ),
        )
        self.events.clear()

        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_manifest_sources",
                return_value=(SOURCE,),
            ),
        ):
            revised = self.repository.revise_handover(
                PROJECT_ID,
                UUID(first["handoverGlobalId"]),
                idempotency_key_hash="e" * 64,
                request=request,
            )

        successor = revised.response["handoverPackage"]
        self.assertEqual(successor["handoverVersion"], 2)
        self.assertEqual(successor["predecessorGlobalId"], first["globalId"])
        self.assertEqual(
            successor["predecessorSnapshotHash"], first["snapshotHash"]
        )
        self.assertEqual(len(self.documents["NPI Handover Package Revision"]), 2)
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Handover Package Revision"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        audit = self.audit_summary("production_handover.revise")
        self.assertEqual(audit["tenantId"], TENANT)
        self.assertEqual(audit["policyRef"], successor["policyRef"])
        self.assertEqual(
            audit["manifestSourceSummary"],
            successor["manifest"],
        )
        self.assertEqual(audit["predecessorGlobalId"], first["globalId"])
        self.assertEqual(
            audit["predecessorSnapshotHash"],
            first["snapshotHash"],
        )
        self.assertEqual(audit["occurredAt"], successor["createdAt"])
        self.assert_audit_summary_omits_sensitive_material(audit)
        workspace = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            workspace["currentHandover"]["revision"]["globalId"],
            successor["globalId"],
        )
        self.assertEqual(
            [
                value["revision"]["handoverVersion"]
                for value in workspace["handoverHistory"]
            ],
            [1, 2],
        )
        self.assert_no_adjacent_truth_mutation(project_before)

        self.events.clear()
        with self.assertRaises(self.module.ProductionTransitionVersionConflict):
            self.repository.revise_handover(
                PROJECT_ID,
                UUID(first["handoverGlobalId"]),
                idempotency_key_hash="f" * 64,
                request=request,
            )
        self.assertEqual(self.events, [])

    def test_create_observation_persists_one_current_tip_without_adjacent_mutation(
        self,
    ) -> None:
        published = self.seed_published_policy()
        current_handover = package()
        self.seed_handover(current_handover)
        source = ExactSourceSelection(
            kind=SOURCE.kind.value,
            global_id=SOURCE.global_id,
            expected_version=SOURCE.source_version,
        )
        request = CreateObservationRequest(
            expected_project_version=project().optimistic_version,
            policy=self.policy_reference(published),
            handover=self.handover_reference(current_handover),
            context_sources=(source,),
            retrospective_sources=(source,),
            retrospective_note="Freeze the retrospective technical evidence.",
            reason="Create the independent technical observation period.",
        )
        project_before = copy.deepcopy(dict(self.project))
        self.events.clear()

        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_observation_sources",
                return_value=((CONTEXT_SOURCE,), (RETROSPECTIVE_SOURCE,)),
            ) as resolver,
        ):
            outcome = self.repository.create_observation(
                PROJECT_ID,
                idempotency_key_hash="1" * 64,
                request=request,
            )

        self.assertIsNotNone(outcome)
        revision = outcome.response["observationPeriod"]
        self.assertEqual(revision["observationVersion"], 1)
        self.assertIsNone(revision["predecessorGlobalId"])
        self.assertEqual(len(self.documents["NPI Observation Period Revision"]), 1)
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Observation Period Revision"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        audit = self.audit_summary("observation_period.create")
        self.assertEqual(audit["tenantId"], TENANT)
        self.assertEqual(audit["policyRef"], revision["policyRef"])
        self.assertEqual(
            audit["handoverPackageRef"],
            revision["handoverPackageRef"],
        )
        self.assertEqual(
            audit["contextSourceSummary"],
            [CONTEXT_SOURCE.snapshot_payload()],
        )
        self.assertEqual(
            audit["retrospectiveSourceSummary"],
            [RETROSPECTIVE_SOURCE.snapshot_payload()],
        )
        self.assertEqual(
            audit["technicalDisposition"],
            revision["technicalDisposition"],
        )
        self.assertEqual(audit["occurredAt"], revision["createdAt"])
        self.assert_audit_summary_omits_sensitive_material(audit)
        resolver.assert_called_once()
        workspace = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            workspace["currentObservation"]["globalId"], revision["globalId"]
        )
        self.assertEqual(len(workspace["observationHistory"]), 1)
        self.assert_no_adjacent_truth_mutation(project_before)

    def test_revise_observation_appends_exact_successor_and_rejects_stale_tip(
        self,
    ) -> None:
        published = self.seed_published_policy()
        current_handover = package()
        self.seed_handover(current_handover)
        source = ExactSourceSelection(
            kind=SOURCE.kind.value,
            global_id=SOURCE.global_id,
            expected_version=SOURCE.source_version,
        )
        project_before = copy.deepcopy(dict(self.project))
        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_observation_sources",
                return_value=((CONTEXT_SOURCE,), ()),
            ),
        ):
            created = self.repository.create_observation(
                PROJECT_ID,
                idempotency_key_hash="2" * 64,
                request=CreateObservationRequest(
                    expected_project_version=project().optimistic_version,
                    policy=self.policy_reference(published),
                    handover=self.handover_reference(current_handover),
                    context_sources=(source,),
                    retrospective_sources=(),
                    retrospective_note=None,
                    reason="Create the observation predecessor.",
                ),
            )
        first = created.response["observationPeriod"]
        request = ObservationRevisionRequest(
            expected_revision_global_id=UUID(first["globalId"]),
            expected_snapshot_hash=first["snapshotHash"],
            context_sources=(source,),
            retrospective_sources=(source,),
            retrospective_note="Review the exact retrospective evidence.",
            reason="Append the exact observation successor.",
        )
        self.events.clear()

        with (
            patch.object(
                self.module,
                "_project_snapshot",
                return_value=project(),
            ),
            patch.object(
                self.module,
                "resolve_observation_sources",
                return_value=((CONTEXT_SOURCE,), (RETROSPECTIVE_SOURCE,)),
            ),
        ):
            revised = self.repository.revise_observation(
                PROJECT_ID,
                UUID(first["observationGlobalId"]),
                idempotency_key_hash="3" * 64,
                request=request,
            )

        successor = revised.response["observationPeriod"]
        self.assertEqual(successor["observationVersion"], 2)
        self.assertEqual(successor["predecessorGlobalId"], first["globalId"])
        self.assertEqual(
            successor["predecessorSnapshotHash"], first["snapshotHash"]
        )
        self.assertEqual(len(self.documents["NPI Observation Period Revision"]), 2)
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Observation Period Revision"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        audit = self.audit_summary("observation_period.revise")
        self.assertEqual(audit["tenantId"], TENANT)
        self.assertEqual(audit["policyRef"], successor["policyRef"])
        self.assertEqual(
            audit["handoverPackageRef"],
            successor["handoverPackageRef"],
        )
        self.assertEqual(
            audit["contextSourceSummary"],
            [CONTEXT_SOURCE.snapshot_payload()],
        )
        self.assertEqual(
            audit["retrospectiveSourceSummary"],
            [RETROSPECTIVE_SOURCE.snapshot_payload()],
        )
        self.assertEqual(
            audit["technicalDisposition"],
            successor["technicalDisposition"],
        )
        self.assertEqual(audit["occurredAt"], successor["createdAt"])
        self.assert_audit_summary_omits_sensitive_material(audit)
        workspace = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            workspace["currentObservation"]["globalId"], successor["globalId"]
        )
        self.assertEqual(
            [
                value["observationVersion"]
                for value in workspace["observationHistory"]
            ],
            [1, 2],
        )
        self.assert_no_adjacent_truth_mutation(project_before)

        self.events.clear()
        with self.assertRaises(self.module.ProductionTransitionVersionConflict):
            self.repository.revise_observation(
                PROJECT_ID,
                UUID(first["observationGlobalId"]),
                idempotency_key_hash="4" * 64,
                request=request,
            )
        self.assertEqual(self.events, [])

    def test_project_is_authorized_before_handover_secondary_identifiers(self) -> None:
        outsider = self.repository_for(
            user_id="external@example.invalid",
            roles=frozenset({"NPI API User"}),
            external=True,
        )
        request = ReviseHandoverRequest(
            expected_revision_global_id=uid(901),
            expected_snapshot_hash="9" * 64,
            content=HandoverContentRequest(
                expected_project_version=7,
                policy=PolicyReferenceRequest(uid(902), 99, "8" * 64),
                slot_assignments=(),
                manifest_sources=(),
                reason="The caller cannot enumerate secondary objects.",
            ),
        )
        self.lookups.clear()
        result = outsider.revise_handover(
            PROJECT_ID,
            uid(903),
            idempotency_key_hash="8" * 64,
            request=request,
        )
        self.assertIsNone(result)
        self.assertTrue(self.lookups)
        self.assertEqual(self.lookups[0][0], "NPI Engineering Project")
        self.assertFalse(
            {
                "NPI Production Transition Policy Version",
                "NPI Handover Package Revision",
                "NPI Project Member",
                "NPI Project Role Assignment",
            }
            & {doctype for doctype, _name, _locked in self.lookups[1:]}
        )

    def test_domain_work_item_adapter_uses_canonical_time_aware_projection(
        self,
    ) -> None:
        source_id = uid(940)
        document = self.seed_source(
            "NPI Domain Work Item",
            source_id,
            source_system="NPI_ONE",
        )
        value = types.SimpleNamespace(global_id=source_id, version=17)
        projection = {
            "globalId": str(source_id),
            "dueAt": datetime(2026, 8, 14, 7, 30, tzinfo=UTC),
            "optimisticVersion": 17,
            "stateLabelSource": "Waiting for controlled review",
        }
        parse_value = Mock(return_value=value)
        source_snapshot = Mock(return_value=projection)
        readiness_repository = types.ModuleType(
            "npi_core.readiness.frappe_repository"
        )
        readiness_repository._domain_work_item_value = parse_value
        readiness_repository._domain_work_item_source_snapshot = source_snapshot

        with patch.dict(
            sys.modules,
            {"npi_core.readiness.frappe_repository": readiness_repository},
        ):
            resolved = self.repository.load_domain_work_item(
                self.source_context(),
                source_id,
                for_update=True,
            )

            self.assertEqual(
                resolved.kind,
                self.module.HandoverSourceKind.DOMAIN_WORK_ITEM,
            )
            self.assertEqual(resolved.global_id, source_id)
            self.assertEqual(resolved.source_version, 17)
            self.assertEqual(
                resolved.snapshot_hash,
                self.module._payload_hash(projection),
            )
            parse_value.assert_called_once_with(document)
            source_snapshot.assert_called_once_with(value)
            self.assertIn(
                ("NPI Domain Work Item", str(source_id), True),
                self.lookups,
            )

            parse_value.reset_mock()
            source_snapshot.reset_mock()
            parse_value.return_value = None
            self.assertIsNone(
                self.repository.load_domain_work_item(
                    self.source_context(),
                    source_id,
                    for_update=False,
                )
            )
            parse_value.assert_called_once_with(document)
            source_snapshot.assert_not_called()

    def test_file_adapter_freezes_full_url_free_live_private_projection(self) -> None:
        source_id = uid(941)
        document, live_file = self.seed_complete_file_revision(
            source_id,
            file_document_id=uid(942),
            frappe_file_id="FILE-0001",
            file_name="controlled-a.pdf",
            file_url="/private/files/controlled-a.pdf",
            content_hash="f" * 32,
            sha256="a" * 64,
            size_bytes=4096,
            revision=3,
            optimistic_version=23,
        )
        projection = self.file_revision_source_snapshot(document)
        file_module = self.file_revision_module()

        with patch.dict(
            sys.modules,
            {
                "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision": (
                    file_module
                )
            },
        ):
            first = self.repository.load_file_revision(
                self.source_context(),
                source_id,
                for_update=True,
            )
            self.assertEqual(
                first.kind,
                self.module.HandoverSourceKind.FILE_REVISION,
            )
            self.assertEqual(first.source_version, 23)
            self.assertEqual(first.snapshot_hash, self.module.sha256_json(projection))
            self.assertNotIn("file", projection)
            self.assertNotIn("fileUrl", projection)
            self.assertIn(
                ("NPI File Revision", str(source_id), True),
                self.lookups,
            )
            self.assertIn(("File", "FILE-0001", True), self.lookups)

            self.lookups.clear()
            live_file.file_url = "/private/files/a-different-route.pdf"
            self.assertIsNone(
                self.repository.load_file_revision(
                    self.source_context(),
                    source_id,
                    for_update=True,
                )
            )
            self.assertIn(("File", "FILE-0001", True), self.lookups)

            live_file.file_url = document.file
            live_file.content_hash = "0" * 32
            self.assertIsNone(
                self.repository.load_file_revision(
                    self.source_context(),
                    source_id,
                    for_update=True,
                )
            )

            live_file.content_hash = document.frappe_content_hash
            second = self.repository.load_file_revision(
                self.source_context(),
                source_id,
                for_update=False,
            )
            self.assertEqual(second.snapshot_hash, first.snapshot_hash)

            document.scan_state = "infected"
            self.lookups.clear()
            self.assertIsNone(
                self.repository.load_file_revision(
                    self.source_context(),
                    source_id,
                    for_update=False,
                )
            )
            self.assertNotIn(("File", "FILE-0001", False), self.lookups)

    def test_readiness_adapter_accepts_only_the_exact_current_project_tip(
        self,
    ) -> None:
        older_id = uid(943)
        current_id = uid(944)
        self.seed_source("NPI Readiness Instance Revision", older_id)
        self.seed_source("NPI Readiness Instance Revision", current_id)
        older = types.SimpleNamespace(
            global_id=older_id,
            instance_version=6,
            snapshot_hash="6" * 64,
        )
        current = types.SimpleNamespace(
            global_id=current_id,
            instance_version=7,
            snapshot_hash="7" * 64,
        )
        project_chain = Mock(return_value=(older, current))
        readiness_repository = types.ModuleType(
            "npi_core.readiness.frappe_repository"
        )
        readiness_repository._project_revision_chain = project_chain

        with patch.dict(
            sys.modules,
            {"npi_core.readiness.frappe_repository": readiness_repository},
        ):
            self.assertIsNone(
                self.repository.load_readiness_instance_revision(
                    self.source_context(),
                    older_id,
                    for_update=True,
                )
            )
            resolved = self.repository.load_readiness_instance_revision(
                self.source_context(),
                current_id,
                for_update=True,
            )

        self.assertEqual(
            resolved.kind,
            self.module.HandoverSourceKind.READINESS_INSTANCE_REVISION,
        )
        self.assertEqual(resolved.global_id, current_id)
        self.assertEqual(resolved.source_version, 7)
        self.assertEqual(resolved.snapshot_hash, "7" * 64)
        self.assertEqual(project_chain.call_count, 2)
        self.assertTrue(
            all(call.args[0] is self.seed_project() for call in project_chain.call_args_list)
        )

    def test_released_document_adapter_delegates_full_currentness_closure(
        self,
    ) -> None:
        source_id = uid(945)
        controlled_document_id = uid(970)
        file_revision_id = uid(971)
        file_document_id = uid(972)
        association_id = uid(973)
        revision = self.seed_source(
            "NPI Document Revision",
            source_id,
            document_global_id=str(controlled_document_id),
        )
        self.add(
            "NPI Document Revision Lifecycle",
            {
                "tenant_id": TENANT,
                "project_global_id": str(PROJECT_ID),
                "revision_global_id": str(source_id),
                "lifecycle_version": 9,
                "release_snapshot_hash": "9" * 64,
            },
            storage_name="released-document-lifecycle",
        )
        self.add(
            "NPI Document Revision File",
            {
                "global_id": str(association_id),
                "tenant_id": TENANT,
                "project_global_id": str(PROJECT_ID),
                "document_global_id": str(controlled_document_id),
                "document_revision_global_id": str(source_id),
                "file_revision_global_id": str(file_revision_id),
            },
        )
        _file_revision, live_file = self.seed_complete_file_revision(
            file_revision_id,
            file_document_id=file_document_id,
            frappe_file_id="FILE-RELEASED-0001",
            file_name="released-controlled.pdf",
            file_url="/private/files/released-controlled.pdf",
            content_hash="e" * 32,
            sha256="d" * 64,
            size_bytes=8192,
            revision=4,
            optimistic_version=11,
        )

        readiness_domain = types.ModuleType("npi_core.readiness.domain")
        readiness_domain.ReadinessSourceKind = types.SimpleNamespace(
            RELEASED_DOCUMENT="released_document"
        )
        query_factory = Mock(
            side_effect=lambda kind, global_id, source_version, snapshot_hash: (
                types.SimpleNamespace(
                    kind=kind,
                    global_id=global_id,
                    source_version=source_version,
                    snapshot_hash=snapshot_hash,
                )
            )
        )
        context_factory = Mock(
            side_effect=lambda tenant_id, project_global_id: types.SimpleNamespace(
                tenant_id=tenant_id,
                project_global_id=project_global_id,
            )
        )
        readiness_source_resolver = types.ModuleType(
            "npi_core.readiness.source_resolver"
        )
        readiness_source_resolver.ExactSourceQuery = query_factory
        readiness_source_resolver.SourceResolutionContext = context_factory
        def assert_dependencies_locked(*_args: object) -> bool:
            expected = (
                ("NPI Document Revision File", str(association_id), True),
                ("NPI File Revision", str(file_revision_id), True),
                ("File", "FILE-RELEASED-0001", True),
            )
            positions = [self.lookups.index(value) for value in expected]
            self.assertEqual(positions, sorted(positions))
            return True

        currentness = Mock(side_effect=assert_dependencies_locked)
        readiness_repository = types.ModuleType(
            "npi_core.readiness.frappe_repository"
        )
        readiness_repository._released_document_source_is_current = currentness
        file_module = self.file_revision_module()

        with patch.dict(
            sys.modules,
            {
                "npi_core.readiness.domain": readiness_domain,
                "npi_core.readiness.frappe_repository": readiness_repository,
                "npi_core.readiness.source_resolver": readiness_source_resolver,
                "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision": (
                    file_module
                ),
            },
        ):
            self.lookups.clear()
            resolved = self.repository.load_released_document(
                self.source_context(),
                source_id,
                for_update=True,
            )
            self.assertEqual(resolved.source_version, 9)
            self.assertEqual(resolved.snapshot_hash, "9" * 64)
            closure_context, closure_query, closure_revision = currentness.call_args.args
            self.assertEqual(closure_context.tenant_id, TENANT)
            self.assertEqual(closure_context.project_global_id, PROJECT_ID)
            self.assertEqual(closure_query.kind, "released_document")
            self.assertEqual(closure_query.global_id, source_id)
            self.assertEqual(closure_query.source_version, 9)
            self.assertEqual(closure_query.snapshot_hash, "9" * 64)
            self.assertIs(closure_revision, revision)
            self.assertIn(
                ("NPI Document Revision File", str(association_id), True),
                self.lookups,
            )
            self.assertIn(
                ("NPI File Revision", str(file_revision_id), True),
                self.lookups,
            )
            self.assertIn(("File", "FILE-RELEASED-0001", True), self.lookups)

            currentness.reset_mock()
            live_file.file_name = "identity-drift.pdf"
            self.assertIsNone(
                self.repository.load_released_document(
                    self.source_context(),
                    source_id,
                    for_update=True,
                )
            )
            currentness.assert_not_called()

            live_file.file_name = "released-controlled.pdf"
            currentness.side_effect = None
            currentness.return_value = False
            self.assertIsNone(
                self.repository.load_released_document(
                    self.source_context(),
                    source_id,
                    for_update=False,
                )
            )

    def test_release_baseline_adapter_delegates_exact_locked_project_loader(
        self,
    ) -> None:
        source_id = uid(966)
        baseline = types.SimpleNamespace(
            global_id=source_id,
            version=8,
            snapshot_hash="8" * 64,
        )
        load_baseline = Mock(return_value=baseline)
        baseline_repository = types.ModuleType(
            "npi_core.documents.baseline_repository"
        )
        baseline_repository.load_document_baseline = load_baseline

        with patch.dict(
            sys.modules,
            {"npi_core.documents.baseline_repository": baseline_repository},
        ):
            resolved = self.repository.load_release_baseline(
                self.source_context(),
                source_id,
                for_update=True,
            )
            self.assertEqual(
                resolved.kind,
                self.module.HandoverSourceKind.RELEASE_BASELINE,
            )
            self.assertEqual(resolved.global_id, source_id)
            self.assertEqual(resolved.source_version, 8)
            self.assertEqual(resolved.snapshot_hash, "8" * 64)
            load_baseline.assert_called_once_with(
                self.seed_project(),
                source_id,
                lock=True,
            )

            load_baseline.reset_mock()
            load_baseline.return_value = types.SimpleNamespace(
                global_id=uid(967),
                version=8,
                snapshot_hash="8" * 64,
            )
            self.assertIsNone(
                self.repository.load_release_baseline(
                    self.source_context(),
                    source_id,
                    for_update=False,
                )
            )
            load_baseline.assert_called_once_with(
                self.seed_project(),
                source_id,
                lock=False,
            )

    def test_project_snapshot_validates_exact_template_and_work_policy(self) -> None:
        document = self.seed_project()
        template_calls: list[tuple[UUID, int]] = []
        work_policy_calls: list[dict[str, object]] = []
        template_result = types.SimpleNamespace(
            snapshot_hash=document.template_snapshot_hash,
            publication_state=types.SimpleNamespace(value="published"),
        )
        work_policy_result = {
            "ref": {
                "globalId": document.work_policy_global_id,
                "version": document.work_policy_version,
                "snapshotHash": document.work_policy_snapshot_hash,
            }
        }

        class FakeProjectRepository:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def get_template_version(self, global_id: UUID, version: int):
                template_calls.append((global_id, version))
                return template_result

        class FakeProjectWorkRepository:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def _load_policy(self, reference: dict[str, object]):
                work_policy_calls.append(reference)
                return work_policy_result

        project_repository = types.ModuleType("npi_core.project.frappe_repository")
        project_repository.FrappeProjectRepository = FakeProjectRepository
        work_repository = types.ModuleType(
            "npi_core.project_work.frappe_repository"
        )
        work_repository.FrappeProjectWorkRepository = FakeProjectWorkRepository

        with patch.dict(
            sys.modules,
            {
                "npi_core.project.frappe_repository": project_repository,
                "npi_core.project_work.frappe_repository": work_repository,
            },
        ):
            snapshot = self.module._project_snapshot(document)
            self.assertEqual(snapshot.template_ref.global_id, UUID(document.template_global_id))
            self.assertEqual(snapshot.template_ref.version, document.template_version)
            self.assertEqual(
                snapshot.work_policy_ref.global_id,
                UUID(document.work_policy_global_id),
            )
            self.assertEqual(snapshot.customer_reference_keys, ("ERPNEXT:CUST-001",))
            self.assertEqual(
                template_calls,
                [(UUID(document.template_global_id), document.template_version)],
            )
            self.assertEqual(work_policy_calls, [work_policy_result["ref"]])

            template_result.snapshot_hash = "0" * 64
            with self.assertRaisesRegex(RuntimeError, "Project transition snapshot"):
                self.module._project_snapshot(document)

            template_result.snapshot_hash = document.template_snapshot_hash
            work_policy_result["ref"] = {
                **work_policy_result["ref"],
                "snapshotHash": "0" * 64,
            }
            with self.assertRaisesRegex(RuntimeError, "Project transition snapshot"):
                self.module._project_snapshot(document)

    def test_tooling_capacity_adapter_accepts_only_exact_current_scenario_tip(
        self,
    ) -> None:
        older_id = uid(946)
        current_id = uid(947)
        master_id = uid(948)
        scenario_id = uid(949)
        for source_id in (older_id, current_id):
            self.seed_source(
                "NPI Tooling Capacity Scenario Revision",
                source_id,
                tooling_master_global_id=str(master_id),
                scenario_global_id=str(scenario_id),
            )
        older = types.SimpleNamespace(
            global_id=older_id,
            scenario_version=3,
            snapshot_hash="3" * 64,
        )
        current = types.SimpleNamespace(
            global_id=current_id,
            scenario_version=4,
            snapshot_hash="4" * 64,
        )
        calls: list[tuple[object, UUID, UUID | None]] = []

        class FakeToolingRepository:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def _engineering_capacity_scenarios(
                self,
                project_document: object,
                tooling_master_id: UUID,
                *,
                scenario_id: UUID | None = None,
            ):
                calls.append((project_document, tooling_master_id, scenario_id))
                return (older, current)

        tooling_repository = types.ModuleType(
            "npi_core.tooling.frappe_repository"
        )
        tooling_repository.FrappeToolingRepository = FakeToolingRepository

        with patch.dict(
            sys.modules,
            {"npi_core.tooling.frappe_repository": tooling_repository},
        ):
            self.assertIsNone(
                self.repository.load_tooling_capacity_scenario(
                    self.source_context(),
                    older_id,
                    for_update=True,
                )
            )
            resolved = self.repository.load_tooling_capacity_scenario(
                self.source_context(),
                current_id,
                for_update=True,
            )

        self.assertEqual(
            resolved.kind,
            self.module.HandoverSourceKind.TOOLING_CAPACITY_SCENARIO,
        )
        self.assertEqual(resolved.global_id, current_id)
        self.assertEqual(resolved.source_version, 4)
        self.assertEqual(resolved.snapshot_hash, "4" * 64)
        self.assertEqual(
            [
                (tooling_master_id, selected_scenario_id)
                for _, tooling_master_id, selected_scenario_id in calls
            ],
            [(master_id, scenario_id), (master_id, scenario_id)],
        )
        self.assertTrue(all(value[0] is self.seed_project() for value in calls))

    def test_trial_defect_adapter_accepts_only_exact_locked_current_tip(self) -> None:
        older_id = uid(950)
        current_id = uid(951)
        defect_id = uid(952)
        for source_id in (older_id, current_id):
            self.seed_source(
                "NPI Trial Defect Revision",
                source_id,
                defect_global_id=str(defect_id),
            )
        older = types.SimpleNamespace(
            global_id=older_id,
            defect_version=11,
            snapshot_hash="b" * 64,
        )
        current = types.SimpleNamespace(
            global_id=current_id,
            defect_version=12,
            snapshot_hash="c" * 64,
        )
        calls: list[tuple[object, UUID, bool]] = []

        class FakeTrialQualityRepository:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def _trial_defect_chain(
                self,
                project_document: object,
                *,
                defect_id: UUID,
                for_update: bool,
            ):
                calls.append((project_document, defect_id, for_update))
                return (older, current)

        trial_quality_repository = types.ModuleType(
            "npi_core.trial.quality_repository"
        )
        trial_quality_repository.FrappeTrialQualityRepository = (
            FakeTrialQualityRepository
        )

        with patch.dict(
            sys.modules,
            {"npi_core.trial.quality_repository": trial_quality_repository},
        ):
            self.assertIsNone(
                self.repository.load_trial_defect_revision(
                    self.source_context(),
                    older_id,
                    for_update=False,
                )
            )
            resolved = self.repository.load_trial_defect_revision(
                self.source_context(),
                current_id,
                for_update=True,
            )

        self.assertEqual(
            resolved.kind,
            self.module.HandoverSourceKind.TRIAL_DEFECT_REVISION,
        )
        self.assertEqual(resolved.global_id, current_id)
        self.assertEqual(resolved.source_version, 12)
        self.assertEqual(resolved.snapshot_hash, "c" * 64)
        self.assertEqual(
            [(selected_defect_id, locked) for _, selected_defect_id, locked in calls],
            [(defect_id, False), (defect_id, True)],
        )

    def test_trial_review_adapters_require_current_tip_and_live_sources(
        self,
    ) -> None:
        older_reference_id = uid(953)
        current_reference_id = uid(954)
        round_id = uid(955)
        reference_id = uid(956)
        older_conclusion_id = uid(957)
        current_conclusion_id = uid(958)
        conclusion_round_id = uid(959)
        conclusion_id = uid(960)
        file_revision_id = uid(974)
        file_document_id = uid(975)
        file_revision, live_file = self.seed_complete_file_revision(
            file_revision_id,
            file_document_id=file_document_id,
            frappe_file_id="FILE-TRIAL-REVIEW-0001",
            file_name="trial-review-controlled.pdf",
            file_url="/private/files/trial-review-controlled.pdf",
            content_hash="7" * 32,
            sha256="8" * 64,
            size_bytes=6144,
            revision=2,
            optimistic_version=6,
        )
        file_snapshot_hash = self.module.sha256_json(
            self.file_revision_source_snapshot(file_revision)
        )
        older_file_reference = types.SimpleNamespace(
            global_id=file_revision_id,
            version=6,
            snapshot_hash=file_snapshot_hash,
        )
        current_file_reference = types.SimpleNamespace(
            global_id=file_revision_id,
            version=6,
            snapshot_hash=file_snapshot_hash,
        )
        for source_id in (older_reference_id, current_reference_id):
            self.seed_source(
                "NPI Trial Review Reference Revision",
                source_id,
                trial_round_global_id=str(round_id),
                reference_global_id=str(reference_id),
            )
        for source_id in (older_conclusion_id, current_conclusion_id):
            self.seed_source(
                "NPI Trial Conclusion Revision",
                source_id,
                trial_round_global_id=str(conclusion_round_id),
                conclusion_global_id=str(conclusion_id),
            )
        reference_chain = (
            types.SimpleNamespace(
                global_id=older_reference_id,
                reference_version=4,
                snapshot_hash="d" * 64,
                file_revision=older_file_reference,
            ),
            types.SimpleNamespace(
                global_id=current_reference_id,
                reference_version=5,
                snapshot_hash="e" * 64,
                file_revision=current_file_reference,
            ),
        )
        conclusion_chain = (
            types.SimpleNamespace(
                global_id=older_conclusion_id,
                conclusion_version=2,
                snapshot_hash="1" * 64,
            ),
            types.SimpleNamespace(
                global_id=current_conclusion_id,
                conclusion_version=3,
                snapshot_hash="2" * 64,
            ),
        )

        class FakeTrialReviewRepository:
            def __init__(self, **_kwargs: Any) -> None:
                pass

            def _reference_chain(
                self,
                _project_document: object,
                selected_round_id: UUID,
                selected_reference_id: UUID,
            ):
                self_outer.assertEqual(selected_round_id, round_id)
                self_outer.assertEqual(selected_reference_id, reference_id)
                return reference_chain

            def _conclusion_chain(
                self,
                _project_document: object,
                selected_round_id: UUID,
                selected_conclusion_id: UUID,
            ):
                self_outer.assertEqual(selected_round_id, conclusion_round_id)
                self_outer.assertEqual(selected_conclusion_id, conclusion_id)
                return conclusion_chain

        self_outer = self
        trial_review_repository = types.ModuleType(
            "npi_core.trial.review_repository"
        )
        trial_review_repository.FrappeTrialReviewRepository = (
            FakeTrialReviewRepository
        )
        currentness_state = {"allowed": True}

        def assert_locked_before_full_currentness(
            _context: object,
            _value: object,
        ) -> bool:
            expected = (
                ("NPI File Revision", str(file_revision_id), True),
                ("File", "FILE-TRIAL-REVIEW-0001", True),
            )
            positions = [self.lookups.index(value) for value in expected]
            self.assertEqual(positions, sorted(positions))
            return currentness_state["allowed"]

        currentness = Mock(side_effect=assert_locked_before_full_currentness)
        readiness_repository = types.ModuleType(
            "npi_core.readiness.frappe_repository"
        )
        readiness_repository._trial_review_reference_sources_are_current = (
            currentness
        )

        class ReadinessContext:
            def __init__(self, tenant_id: str, project_global_id: UUID) -> None:
                self.tenant_id = tenant_id
                self.project_global_id = project_global_id

        readiness_source_resolver = types.ModuleType(
            "npi_core.readiness.source_resolver"
        )
        readiness_source_resolver.SourceResolutionContext = ReadinessContext
        file_module = self.file_revision_module()

        with patch.dict(
            sys.modules,
            {
                "npi_core.readiness.frappe_repository": readiness_repository,
                "npi_core.readiness.source_resolver": readiness_source_resolver,
                "npi_core.trial.review_repository": trial_review_repository,
                "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision": (
                    file_module
                ),
            },
        ):
            self.lookups.clear()
            self.assertIsNone(
                self.repository.load_trial_review_reference(
                    self.source_context(),
                    older_reference_id,
                    for_update=True,
                )
            )
            currentness.assert_not_called()

            self.lookups.clear()
            reference = self.repository.load_trial_review_reference(
                self.source_context(),
                current_reference_id,
                for_update=True,
            )
            self.assertEqual(reference.global_id, current_reference_id)
            self.assertEqual(reference.source_version, 5)
            closure_context, closure_value = currentness.call_args.args
            self.assertEqual(closure_context.tenant_id, TENANT)
            self.assertEqual(closure_context.project_global_id, PROJECT_ID)
            self.assertIs(closure_value, reference_chain[-1])
            self.assertIn(
                ("NPI File Revision", str(file_revision_id), True),
                self.lookups,
            )
            self.assertIn(
                ("File", "FILE-TRIAL-REVIEW-0001", True),
                self.lookups,
            )

            currentness.reset_mock()
            self.lookups.clear()
            live_file.file_url = "/private/files/drifted-trial-review.pdf"
            self.assertIsNone(
                self.repository.load_trial_review_reference(
                    self.source_context(),
                    current_reference_id,
                    for_update=True,
                )
            )
            currentness.assert_not_called()

            live_file.file_url = file_revision.file
            current_file_reference.snapshot_hash = "0" * 64
            self.assertIsNone(
                self.repository.load_trial_review_reference(
                    self.source_context(),
                    current_reference_id,
                    for_update=True,
                )
            )
            currentness.assert_not_called()

            current_file_reference.snapshot_hash = file_snapshot_hash
            currentness_state["allowed"] = False
            self.assertIsNone(
                self.repository.load_trial_review_reference(
                    self.source_context(),
                    current_reference_id,
                    for_update=False,
                )
            )
            currentness.assert_called_once()

            self.assertIsNone(
                self.repository.load_trial_conclusion(
                    self.source_context(),
                    older_conclusion_id,
                    for_update=False,
                )
            )
            conclusion = self.repository.load_trial_conclusion(
                self.source_context(),
                current_conclusion_id,
                for_update=True,
            )
            self.assertEqual(conclusion.global_id, current_conclusion_id)
            self.assertEqual(conclusion.source_version, 3)
            self.assertEqual(conclusion.snapshot_hash, "2" * 64)

    def test_unresolved_action_snapshot_is_all_nonterminal_bounded_and_sorted(
        self,
    ) -> None:
        planned = (
            (uid(964), self.module.WorkItemKind.RISK, 14),
            (uid(961), self.module.WorkItemKind.ACTION, 11),
            (uid(963), self.module.WorkItemKind.ISSUE, 13),
            (uid(962), self.module.WorkItemKind.DECISION_REQUEST, 12),
        )
        values: dict[UUID, types.SimpleNamespace] = {}
        projections: dict[UUID, dict[str, object]] = {}
        for global_id, kind, version in planned:
            self.seed_source(
                "NPI Domain Work Item",
                global_id,
                state_terminal=0,
                source_system="NPI_ONE",
            )
            value = types.SimpleNamespace(
                global_id=global_id,
                tenant_id=TENANT,
                project_global_id=PROJECT_ID,
                state_terminal=False,
                kind=kind,
                state_key=f"open_{kind.value}",
                owner_user_id="owner@example.invalid",
                due_at=datetime(2026, 8, version, 6, 15, tzinfo=UTC),
                version=version,
            )
            values[global_id] = value
            projections[global_id] = {
                "globalId": str(global_id),
                "kind": kind.value,
                "dueAt": value.due_at,
                "ownerUserId": value.owner_user_id,
                "optimisticVersion": version,
                "stateTerminal": False,
            }
        terminal_id = uid(965)
        self.seed_source(
            "NPI Domain Work Item",
            terminal_id,
            state_terminal=1,
            source_system="NPI_ONE",
        )
        parse_value = Mock(
            side_effect=lambda document: values[UUID(str(document.global_id))]
        )
        source_snapshot = Mock(
            side_effect=lambda value: projections[value.global_id]
        )
        readiness_repository = types.ModuleType(
            "npi_core.readiness.frappe_repository"
        )
        readiness_repository._domain_work_item_value = parse_value
        readiness_repository._domain_work_item_source_snapshot = source_snapshot

        with patch.dict(
            sys.modules,
            {"npi_core.readiness.frappe_repository": readiness_repository},
        ):
            result = self.repository._unresolved_actions(
                self.seed_project(),
                for_update=True,
            )
            ordered_ids = tuple(sorted(values, key=str))
            self.assertEqual(
                tuple(item.global_id for item in result),
                ordered_ids,
            )
            self.assertEqual(
                {item.kind for item in result},
                set(self.module.WorkItemKind),
            )
            for item in result:
                value = values[item.global_id]
                self.assertEqual(item.source_version, value.version)
                self.assertEqual(item.owner_user_id, value.owner_user_id)
                self.assertEqual(item.due_date, value.due_at.date())
                self.assertEqual(item.state, value.state_key)
                self.assertEqual(
                    item.snapshot_hash,
                    self.module._payload_hash(projections[item.global_id]),
                )
            self.assertEqual(parse_value.call_count, 4)
            self.assertNotIn(
                ("NPI Domain Work Item", str(terminal_id), True),
                self.lookups,
            )
            self.assertTrue(
                all(
                    ("NPI Domain Work Item", str(global_id), True)
                    in self.lookups
                    for global_id in values
                )
            )
            query = next(
                call
                for call in reversed(self.get_all_calls)
                if call["doctype"] == "NPI Domain Work Item"
            )
            self.assertEqual(
                query["filters"],
                {
                    "tenant_id": TENANT,
                    "project_global_id": str(PROJECT_ID),
                    "state_terminal": 0,
                },
            )
            self.assertEqual(query["order_by"], "global_id asc")
            self.assertEqual(
                query["limit_page_length"],
                self.module._MAX_UNRESOLVED_ACTIONS + 1,
            )

            with patch.object(
                self.frappe,
                "get_all",
                return_value=[
                    f"unsafe-{index}"
                    for index in range(self.module._MAX_UNRESOLVED_ACTIONS + 1)
                ],
            ):
                with self.assertRaises(self.errors.RequestValidationFailed):
                    self.repository._unresolved_actions(
                        self.seed_project(),
                        for_update=False,
                    )

            values[ordered_ids[0]].owner_user_id = ""
            with self.assertRaisesRegex(
                RuntimeError,
                "unresolved Work Item integrity",
            ):
                self.repository._unresolved_actions(
                    self.seed_project(),
                    for_update=False,
                )

    def test_handover_workspace_requires_one_exact_linear_stream(self) -> None:
        first = package()
        self.seed_handover(first)
        current = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            current["currentHandover"]["revision"]["globalId"],
            str(first.global_id),
        )

        successor = create_handover_package_successor(
            first,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Create the exact handover successor.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(910),
            trace_id="trace-p706-repository-handover-next",
        )
        self.seed_handover(successor)
        revised = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            [
                item["revision"]["handoverVersion"]
                for item in revised["handoverHistory"]
            ],
            [1, 2],
        )

        self.seed_handover(successor, storage_name="duplicate-handover-tip")
        with self.assertRaisesRegex(
            RuntimeError,
            "handover.*(?:ambiguous|scope is invalid)",
        ):
            self.repository.production_transition_workspace(PROJECT_ID)

    def test_handover_workspace_rejects_multiple_active_streams(self) -> None:
        self.seed_handover(package())
        other = create_handover_package_revision(
            handover_global_id=uid(911),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Create a conflicting active handover stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(912),
            trace_id="trace-p706-repository-handover-other",
        )
        self.seed_handover(other)
        with self.assertRaisesRegex(
            RuntimeError,
            "handover.*(?:ambiguous|scope is invalid)",
        ):
            self.repository.production_transition_workspace(PROJECT_ID)

    def test_observation_workspace_requires_one_exact_linear_stream(self) -> None:
        first = create_observation_period_revision(
            observation_global_id=uid(920),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Create an independent observation stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(921),
            trace_id="trace-p706-repository-observation",
        )
        self.seed_observation(first)
        successor = create_observation_period_successor(
            first,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(CONTEXT_SOURCE,),
            retrospective_references=(RETROSPECTIVE_SOURCE,),
            retrospective_note="Review the exact retrospective reference.",
            reason="Create the exact observation successor.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(922),
            trace_id="trace-p706-repository-observation-next",
        )
        self.seed_observation(successor)

        workspace = self.repository.production_transition_workspace(PROJECT_ID)
        self.assertEqual(
            [value["observationVersion"] for value in workspace["observationHistory"]],
            [1, 2],
        )
        self.assertEqual(
            workspace["currentObservation"]["globalId"], str(successor.global_id)
        )

        self.seed_observation(successor, storage_name="duplicate-observation-tip")
        with self.assertRaisesRegex(
            RuntimeError,
            "observation.*(?:ambiguous|scope is invalid)",
        ):
            self.repository.production_transition_workspace(PROJECT_ID)

    def test_observation_workspace_rejects_multiple_active_streams(self) -> None:
        first = create_observation_period_revision(
            observation_global_id=uid(923),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Create the first observation stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(924),
            trace_id="trace-p706-repository-observation-first",
        )
        other = create_observation_period_revision(
            observation_global_id=uid(925),
            tenant_id=TENANT,
            project=project(),
            policy=policy(),
            handover_package_ref=None,
            context_references=(),
            retrospective_references=(),
            retrospective_note=None,
            reason="Create a conflicting observation stream.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(926),
            trace_id="trace-p706-repository-observation-other",
        )
        self.seed_observation(first)
        self.seed_observation(other)
        with self.assertRaisesRegex(
            RuntimeError,
            "observation.*(?:ambiguous|scope is invalid)",
        ):
            self.repository.production_transition_workspace(PROJECT_ID)

    def test_persisted_handover_predecessor_index_drift_fails_closed(self) -> None:
        first = package()
        successor = create_handover_package_successor(
            first,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Create the handover predecessor chain.",
            created_by_user_id="admin@example.invalid",
            created_at=NOW,
            request_id=uid(927),
            trace_id="trace-p706-repository-handover-integrity",
        )
        self.seed_handover(first)
        successor_document = self.seed_handover(successor)
        successor_document.predecessor_snapshot_hash = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "handover.*integrity"):
            self.repository.production_transition_workspace(PROJECT_ID)

    def test_acknowledgement_is_current_package_actor_bound_and_not_proxyable(
        self,
    ) -> None:
        current = package()
        self.seed_handover(current)
        sender_repository = self.repository_for(
            user_id=SENDER_MEMBER.user_id,
            roles=frozenset({"NPI API User"}),
            request_id="cb233de2-5d4d-4556-ad16-9476d8f0776f",
        )
        intent = AcknowledgementIntent(
            expected_revision_global_id=current.global_id,
            expected_snapshot_hash=current.snapshot_hash,
            slot_key="sender",
            intent="acknowledge",
        )
        self.events.clear()
        self.db_get_value_calls.clear()
        acknowledged = sender_repository.acknowledge_handover(
            PROJECT_ID,
            current.handover_global_id,
            current.handover_version,
            idempotency_key_hash="9" * 64,
            request=intent,
        )
        self.assertFalse(acknowledged.replayed)
        self.assertEqual(
            acknowledged.response["acknowledgement"]["actorUserId"],
            SENDER_MEMBER.user_id,
        )
        self.assertEqual(
            acknowledged.response["acknowledgement"]["packageRevisionGlobalId"],
            str(current.global_id),
        )
        self.assertEqual(
            [(action, doctype) for action, doctype, _name in self.events],
            [
                ("insert", "NPI Production Transition Command Idempotency"),
                ("insert", "NPI Handover Acknowledgement"),
                ("insert", "NPI Audit Event"),
                ("save", "NPI Production Transition Command Idempotency"),
            ],
        )
        self.assertTrue(
            any(
                call["doctype"] == "User"
                and call["name_or_filters"] == SENDER_MEMBER.user_id
                and call["for_update"] is True
                for call in self.db_get_value_calls
            ),
            self.db_get_value_calls,
        )
        acknowledgement = acknowledged.response["acknowledgement"]
        audit = self.audit_summary("production_handover.acknowledge")
        self.assertEqual(audit["tenantId"], TENANT)
        self.assertEqual(
            audit["acknowledgedAt"],
            acknowledgement["acknowledgedAt"],
        )
        self.assertEqual(
            audit["memberRef"],
            {
                "globalId": acknowledgement["memberGlobalId"],
                "optimisticVersion": acknowledgement[
                    "memberOptimisticVersion"
                ],
                "snapshotHash": acknowledgement["memberSnapshotHash"],
            },
        )
        self.assertEqual(
            audit["roleRef"],
            {
                "globalId": acknowledgement["roleGlobalId"],
                "optimisticVersion": acknowledgement[
                    "roleOptimisticVersion"
                ],
                "snapshotHash": acknowledgement["roleSnapshotHash"],
            },
        )
        self.assertEqual(audit["policyRef"], current.policy_ref.snapshot_payload())
        self.assert_audit_summary_omits_sensitive_material(audit)

        self.events.clear()
        replayed = sender_repository.acknowledge_handover(
            PROJECT_ID,
            current.handover_global_id,
            current.handover_version,
            idempotency_key_hash="9" * 64,
            request=intent,
        )
        self.assertTrue(replayed.replayed)
        self.assertEqual(replayed.response, acknowledged.response)
        self.assertEqual(self.events, [])
        receipt = next(
            value
            for value in self.documents[
                "NPI Production Transition Command Idempotency"
            ].values()
            if value.operation == "production_handover.acknowledge"
        )
        self.assertEqual(receipt.project_global_id, str(PROJECT_ID))
        self.assertEqual(receipt.actor_user_id, SENDER_MEMBER.user_id)

        with self.assertRaises(self.module.ProductionTransitionIdempotencyConflict):
            sender_repository.acknowledge_handover(
                PROJECT_ID,
                current.handover_global_id,
                current.handover_version,
                idempotency_key_hash="9" * 64,
                request=replace(intent, slot_key="receiver"),
            )

        proxy_intent = replace(intent, slot_key="receiver")
        with self.assertRaises(self.errors.PermissionDenied):
            self.repository.acknowledge_handover(
                PROJECT_ID,
                current.handover_global_id,
                current.handover_version,
                idempotency_key_hash="a" * 64,
                request=proxy_intent,
            )

        successor = create_handover_package_successor(
            current,
            project=project(),
            policy=policy(),
            readiness_ref=None,
            slots=slots(),
            manifest=(SOURCE,),
            server_unresolved_actions=(ACTION,),
            enabled_user_ids=frozenset(
                {SENDER_MEMBER.user_id, RECEIVER_MEMBER.user_id}
            ),
            reason="Supersede the package before another acknowledgement.",
            created_by_user_id="admin@example.invalid",
            created_at=datetime.now(UTC),
            request_id=uid(930),
            trace_id="trace-p706-repository-ack-stale",
        )
        self.seed_handover(successor)
        with self.assertRaises(
            self.module.ProductionTransitionVersionConflict
        ):
            sender_repository.acknowledge_handover(
                PROJECT_ID,
                current.handover_global_id,
                current.handover_version,
                idempotency_key_hash="b" * 64,
                request=intent,
            )


if __name__ == "__main__":
    unittest.main()
