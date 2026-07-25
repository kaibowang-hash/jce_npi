from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
import types
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

sys.path.insert(0, "apps/npi_core")

PROJECT_ID = UUID("47444697-ce5c-4ea4-8df1-1e1cf809dc2f")
OTHER_PROJECT_ID = UUID("873f818c-cc37-48d7-a446-c32f8f92f330")
GATE_ID = UUID("2bf63d3d-12db-47c7-b623-4dd42e76a7cb")
OTHER_GATE_ID = UUID("8e497b7e-5090-4eb6-b118-25ecaee44390")
CYCLE_ID = uuid5(GATE_ID, "review-cycle:1")
EXCEPTION_ID = UUID("0c15b8b7-9794-45a8-a2c5-e7e6762e0400")
MEMBER_ID = UUID("44f7b429-a527-4304-865d-d61e6a42320b")
POLICY_ID = UUID("2e61347c-313a-4443-b531-b605e90d5f45")
GATE_TEMPLATE_ID = UUID("27a34964-9987-4e3c-b010-2e5165782c62")
DEPENDENCY_ID = UUID("4abcc093-5366-4a58-a6d2-7efcdf824840")
REFERENCE_ID = UUID("9ac17691-24cf-4b28-a2ef-6597df9414dd")
SOURCE_ID = UUID("d73df0ec-ef0e-444a-a8bc-a5e9a08c0014")
RESOLVED_ACTION_ID = UUID("a05978ee-1e35-4340-a693-6e211bc0880c")
SECOND_RESOLVED_ACTION_ID = UUID("21b9baf4-4ed8-49fb-adca-d23c9996aca9")
TENANT_ID = "tenant-test"
ACTOR = "reviewer@example.test"
STEP_REVIEWER = "step-reviewer@example.test"
EXCEPTION_APPROVER = "exception-approver@example.test"
NOW = datetime(2026, 7, 24, 9, 30, tzinfo=UTC)


class AttrDoc(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def set(self, name: str, value: Any) -> None:
        self[name] = value

    def insert(self):
        self._store.insert(self)
        return self

    def save(self):
        self._store.save(self)
        return self

    def get_doc_before_save(self):
        return self.get("_previous")


class FakeStore:
    def __init__(self, frappe_module: types.ModuleType) -> None:
        self.frappe = frappe_module
        self.documents: dict[str, dict[str, AttrDoc]] = {}
        self.users: dict[str, AttrDoc] = {}
        self.get_doc_calls: list[tuple[str, str, bool]] = []
        self.get_value_calls: list[tuple[str, object, object, bool, bool]] = []
        self.rollback_count = 0

    def add(self, doctype: str, name: object, **values: object) -> AttrDoc:
        document = AttrDoc(
            doctype=doctype,
            name=str(name),
            _store=self,
            _persisted=True,
            **values,
        )
        self.documents.setdefault(doctype, {})[str(name)] = document
        return document

    def get_doc(
        self,
        doctype_or_values: object,
        name: object = None,
        *,
        for_update: bool = False,
    ) -> AttrDoc:
        if isinstance(doctype_or_values, dict):
            return AttrDoc(
                copy.deepcopy(doctype_or_values),
                _store=self,
                _persisted=False,
            )
        doctype = str(doctype_or_values)
        key = str(name)
        self.get_doc_calls.append((doctype, key, for_update))
        document = self.documents.get(doctype, {}).get(key)
        if document is None:
            raise self.frappe.DoesNotExistError()
        return document

    def get_all(
        self,
        doctype: str,
        *,
        filters: dict[str, object],
        pluck: str | None = None,
        fields: list[str] | None = None,
        order_by: str,
        limit_page_length: int,
    ) -> list[Any]:
        values = [
            document
            for document in self.documents.get(doctype, {}).values()
            if all(
                (
                    document.get(key) in value[1]
                    if isinstance(value, list)
                    and len(value) == 2
                    and value[0] == "in"
                    and isinstance(value[1], (list, tuple))
                    else document.get(key) == value
                )
                for key, value in filters.items()
            )
        ]
        order_parts = [item.strip().split() for item in order_by.split(",")]
        for part in reversed(order_parts):
            values.sort(
                key=lambda document: str(document.get(part[0]) or ""),
                reverse=len(part) > 1 and part[1].lower() == "desc",
            )
        selected = values[:limit_page_length]
        if pluck is not None:
            return [str(document.get(pluck)) for document in selected]
        if fields is not None:
            return [
                AttrDoc({field: document.get(field) for field in fields})
                for document in selected
            ]
        return selected

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fieldname: object,
        *,
        as_dict: bool = False,
        for_update: bool = False,
    ) -> object:
        self.get_value_calls.append(
            (
                doctype,
                copy.deepcopy(name_or_filters),
                copy.deepcopy(fieldname),
                as_dict,
                for_update,
            )
        )
        if doctype == "User":
            document = self.users.get(str(name_or_filters))
        elif isinstance(name_or_filters, dict):
            document = next(
                (
                    candidate
                    for candidate in self.documents.get(doctype, {}).values()
                    if all(
                        candidate.get(key) == value
                        for key, value in name_or_filters.items()
                    )
                ),
                None,
            )
        else:
            document = self.documents.get(doctype, {}).get(str(name_or_filters))
        if document is None:
            return None
        if isinstance(fieldname, list):
            result = AttrDoc({field: document.get(field) for field in fieldname})
            return result if as_dict else tuple(result.values())
        return document.get(str(fieldname))

    def insert(self, document: AttrDoc) -> None:
        doctype = str(document.doctype)
        if doctype == "NPI Gate Review Idempotency" and any(
            candidate.actor_key_hash == document.actor_key_hash
            for candidate in self.documents.get(doctype, {}).values()
        ):
            raise self.frappe.UniqueValidationError()
        name_field = {
            "NPI Gate Review Idempotency": "record_id",
            "NPI Audit Event": "event_id",
        }.get(doctype, "global_id")
        name = str(document.get(name_field) or document.get("name"))
        document.name = name
        document._persisted = True
        self.documents.setdefault(doctype, {})[name] = document

    def save(self, document: AttrDoc) -> None:
        document._persisted = True
        self.documents.setdefault(str(document.doctype), {})[
            str(document.name)
        ] = document

    def rollback(self) -> None:
        self.rollback_count += 1


class Phase4GateReviewRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.api",
        "npi_core.controlled_evidence_validation",
        "npi_core.foundation.audit",
        "npi_core.gate_evidence.frappe_repository",
        "npi_core.gate_evidence_api",
        "npi_core.gate_review.frappe_policy_repository",
        "npi_core.gate_review.frappe_repository",
        "npi_core.gate_review.frappe_validation",
        "npi_core.gate_review_api",
        ("npi_core.npi_core.doctype.npi_file_revision." "npi_file_revision"),
        (
            "npi_core.npi_core.doctype.npi_gate_evidence_reference."
            "npi_gate_evidence_reference"
        ),
        "npi_core.request_security",
    )

    def setUp(self) -> None:
        self.saved_modules = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.session = types.SimpleNamespace(user=ACTOR)
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.UniqueValidationError = type(
            "UniqueValidationError", (Exception,), {}
        )
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.get_roles = lambda _actor: []
        self.enqueued: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.frappe.enqueue = lambda *args, **kwargs: self.enqueued.append(
            (args, kwargs)
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            del methods, allow_guest

            def decorate(function):
                return function

            return decorate

        self.frappe.whitelist = whitelist
        self.store = FakeStore(self.frappe)
        self.frappe.get_doc = self.store.get_doc
        self.frappe.get_all = self.store.get_all
        self.frappe.db = self.store
        sys.modules["frappe"] = self.frappe

        self._install_dependency_stubs()
        self.repository_module = importlib.import_module(
            "npi_core.gate_review.frappe_repository"
        )
        self.domain = importlib.import_module("npi_core.gate_review.domain")
        self.security = importlib.import_module("npi_core.foundation.security")
        self.errors = importlib.import_module("npi_core.foundation.errors")
        self.project_domain = importlib.import_module("npi_core.project.domain")
        self._seed_root_scope()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def _install_dependency_stubs(self) -> None:
        controlled = types.ModuleType("npi_core.controlled_evidence_validation")
        controlled.canonical_snapshot_hash = self._canonical_hash
        controlled.has_controlled_file_write = lambda: False
        sys.modules[controlled.__name__] = controlled

        audit = types.ModuleType("npi_core.foundation.audit")
        audit.create_audit_event = lambda **values: types.SimpleNamespace(
            event_id=UUID("13f9c9fd-291e-4112-b3e2-9a71f7ad7f76"),
            **values,
        )
        sys.modules[audit.__name__] = audit

        evidence = types.ModuleType("npi_core.gate_evidence.frappe_repository")
        evidence.FrappeGateEvidenceRepository = type(
            "FrappeGateEvidenceRepository",
            (),
            {
                "__init__": lambda self, **_values: None,
                "_workspace_for": lambda self, project, gate: {},
            },
        )
        sys.modules[evidence.__name__] = evidence

        policy = types.ModuleType("npi_core.gate_review.frappe_policy_repository")
        policy.load_available_gate_review_policy_version = (
            lambda *_args, **_kwargs: None
        )
        policy.load_exact_gate_review_policy_version = lambda *_args, **_kwargs: None
        sys.modules[policy.__name__] = policy

        validation = types.ModuleType("npi_core.gate_review.frappe_validation")
        validation.GATE_REVIEW_COMMAND_FLAG = "npi_gate_review_command_write"
        validation.canonical_json_hash = self._canonical_hash
        sys.modules[validation.__name__] = validation

        file_revision = types.ModuleType(
            "npi_core.npi_core.doctype.npi_file_revision.npi_file_revision"
        )
        file_revision.file_revision_source_snapshot = lambda document: {}
        file_revision.has_complete_file_revision_identity = lambda document: False
        file_revision.has_live_private_file_identity = lambda document: False
        sys.modules[file_revision.__name__] = file_revision

        evidence_reference = types.ModuleType(
            "npi_core.npi_core.doctype.npi_gate_evidence_reference."
            "npi_gate_evidence_reference"
        )
        evidence_reference.wbs_item_source_snapshot = lambda document: {}
        sys.modules[evidence_reference.__name__] = evidence_reference

        api = types.ModuleType("npi_core.api")
        api.frappe_domain_call = lambda function, **_values: function()
        sys.modules[api.__name__] = api

        gate_evidence_api = types.ModuleType("npi_core.gate_evidence_api")
        gate_evidence_api.GateUnavailable = type("GateUnavailable", (Exception,), {})
        sys.modules[gate_evidence_api.__name__] = gate_evidence_api

        request_security = types.ModuleType("npi_core.request_security")
        request_security.authenticated_principal = lambda _actor: None
        request_security.authenticated_user = lambda: ACTOR
        request_security.reject_unexpected_request_fields = (
            lambda *_args, **_kwargs: None
        )
        request_security.require_csrf_token = lambda: None
        request_security.response_request_id = lambda: "request-id"
        sys.modules[request_security.__name__] = request_security

    @staticmethod
    def _canonical_hash(value: object) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(encoded.encode()).hexdigest()

    def _seed_root_scope(self) -> None:
        self.project = self.store.add(
            "NPI Engineering Project",
            PROJECT_ID,
            global_id=str(PROJECT_ID),
            tenant_id=TENANT_ID,
            owner_user_id="owner@example.test",
            business_code="P4-04",
            title="Repository Gate",
        )
        self.gate = self.store.add(
            "NPI Gate Shell",
            GATE_ID,
            global_id=str(GATE_ID),
            project_global_id=str(PROJECT_ID),
            engineering_project=str(PROJECT_ID),
            gate_template_global_id=str(GATE_TEMPLATE_ID),
            gate_template_version=1,
            gate_template_snapshot_hash="b" * 64,
            gate_key="G2",
            title="Gate Two",
            current_review_cycle_global_id=str(CYCLE_ID),
            review_policy_global_id=str(POLICY_ID),
            review_policy_version=1,
            review_policy_snapshot_hash=None,
            latest_decision_snapshot_global_id=None,
            latest_decision_snapshot_hash=None,
            latest_decision_outcome=None,
            review_state="in_review",
            optimistic_version=3,
        )
        self.cycle_document = self.store.add(
            "NPI Gate Review Cycle",
            CYCLE_ID,
            global_id=str(CYCLE_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            gate_shell=str(GATE_ID),
        )
        self.exception_document = self.store.add(
            "NPI Gate Review Exception",
            EXCEPTION_ID,
            global_id=str(EXCEPTION_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            cycle_global_id=str(CYCLE_ID),
        )
        self._add_member(ACTOR, MEMBER_ID)

    def _add_member(
        self,
        user_id: str,
        member_id: UUID,
        *,
        effective_from: str = "2026-01-01",
        effective_to: str | None = None,
        enabled: int = 1,
        user_type: str = "System User",
    ) -> AttrDoc:
        member = self.store.add(
            "NPI Project Member",
            member_id,
            global_id=str(member_id),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            user_id=user_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self.store.users[user_id] = AttrDoc(
            enabled=enabled,
            user_type=user_type,
            full_name=user_id.split("@")[0].title(),
        )
        return member

    def _principal(
        self,
        actor: str = ACTOR,
        *,
        roles: frozenset[str] = frozenset({"NPI API User"}),
        project_access: dict[str, object] | None = None,
    ):
        return self.security.Principal(
            user_id=actor,
            roles=roles,
            project_access=project_access or {},
            is_external=False,
            tenant_id=TENANT_ID,
        )

    def _repository(self, principal=None, *, dependency_system: bool = False):
        if dependency_system:
            return self.repository_module._dependency_system_repository(
                tenant_id=TENANT_ID,
                request_id="2ef22035-71df-4c07-a2ae-e88ea461d80c",
                trace_id="trace-p4-04-repository",
            )
        return self.repository_module.FrappeGateReviewRepository(
            principal=principal or self._principal(),
            request_id="2ef22035-71df-4c07-a2ae-e88ea461d80c",
            trace_id="trace-p4-04-repository",
        )

    def _dependency_policy_and_bindings(self):
        domain = self.domain
        policy = domain.ReviewPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_code="P4-04-BLOCKER-RESOLUTION",
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_hash="b" * 64,
            steps=(
                domain.ReviewStep(
                    "engineering",
                    1,
                    "engineering_reviewer",
                ),
            ),
            decision_authority_slot="gate_decider",
            reopen_authority_slot="gate_reopener",
            exception_rules=(),
            dependency_evaluators=(domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
        ).publish(1)
        bindings = (
            domain.AuthorityBinding(
                "engineering_reviewer", MEMBER_ID, ACTOR, "Reviewer"
            ),
            domain.AuthorityBinding(
                "gate_decider",
                UUID(int=51),
                "decider@example.test",
                "Decider",
            ),
            domain.AuthorityBinding(
                "gate_reopener",
                UUID(int=52),
                "reopener@example.test",
                "Reopener",
            ),
        )
        return policy, bindings

    def _gate_input(self, *, blockers):
        domain = self.domain
        return domain.GateInputSnapshot(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            gate_version=1,
            requirements=(),
            evidence=(),
            blockers=tuple(blockers),
            dependencies=(
                domain.GateDependencyInput(
                    domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                    DEPENDENCY_ID,
                    1,
                    "e" * 64,
                ),
            ),
        )

    def _projection_policy_and_bindings(self):
        domain = self.domain
        step_member_id = UUID(int=91)
        exception_member_id = UUID(int=92)
        reopen_member_id = UUID(int=93)
        self._add_member(STEP_REVIEWER, step_member_id)
        self._add_member(EXCEPTION_APPROVER, exception_member_id)
        self._add_member("reopener@example.test", reopen_member_id)
        policy = domain.ReviewPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_code="P4-04-UI-PROJECTION",
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_hash="b" * 64,
            steps=(
                domain.ReviewStep(
                    "engineering",
                    1,
                    "engineering_reviewer",
                ),
            ),
            decision_authority_slot="gate_decider",
            reopen_authority_slot="gate_reopener",
            exception_rules=(
                domain.ExceptionRule(
                    "p1_evidence_timing",
                    ("supplier_timing",),
                    "exception_approver",
                    14,
                    "action",
                ),
            ),
            dependency_evaluators=(domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
        ).publish(1)
        bindings = (
            domain.AuthorityBinding(
                "engineering_reviewer",
                step_member_id,
                STEP_REVIEWER,
                "Step Reviewer",
            ),
            domain.AuthorityBinding(
                "gate_decider",
                MEMBER_ID,
                ACTOR,
                "Gate Decider",
            ),
            domain.AuthorityBinding(
                "gate_reopener",
                reopen_member_id,
                "reopener@example.test",
                "Gate Reopener",
            ),
            domain.AuthorityBinding(
                "exception_approver",
                exception_member_id,
                EXCEPTION_APPROVER,
                "Exception Approver",
            ),
        )
        return policy, bindings

    def _projection_input(
        self,
        *,
        p0_complete: bool = True,
        p1_complete: bool = False,
        file_safe: bool = True,
        blocker: bool = False,
        dependency_hash: str = "e" * 64,
    ):
        domain = self.domain
        p0_id = UUID(int=101)
        p1_id = UUID(int=102)
        return domain.GateInputSnapshot(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            gate_version=1,
            requirements=(
                domain.GateRequirementInput(
                    p0_id,
                    "design_release",
                    "P0",
                    1,
                    "1" * 64,
                    p0_complete,
                ),
                domain.GateRequirementInput(
                    p1_id,
                    "supplier_timing",
                    "P1",
                    1,
                    "2" * 64,
                    p1_complete,
                ),
            ),
            evidence=(
                domain.GateEvidenceInput(
                    UUID(int=103),
                    p0_id,
                    "file_revision",
                    UUID(int=104),
                    1,
                    "3" * 64,
                    True,
                    file_safe,
                ),
            ),
            blockers=(
                domain.GateBlockerInput(
                    UUID(int=105),
                    1,
                    "open",
                    blocker,
                    False,
                ),
            ),
            dependencies=(
                domain.GateDependencyInput(
                    domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                    DEPENDENCY_ID,
                    1,
                    dependency_hash,
                ),
            ),
        )

    def _projection_cycle(self, snapshot=None):
        policy, bindings = self._projection_policy_and_bindings()
        frozen_input = snapshot or self._projection_input()
        return self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=frozen_input,
        )

    def _approve_projection_review(self, cycle):
        return cycle.submit_review(
            step_key="engineering",
            actor_user_id=STEP_REVIEWER,
            outcome=self.domain.ReviewOutcome.APPROVED,
            opinion="Approved for the projection test.",
            occurred_at=NOW,
            expected_version=cycle.version,
            expected_input_hash=cycle.input_hash,
        )

    def _request_projection_exception(self, cycle):
        action = self._closure_action(UUID(int=106))
        return cycle.request_exception(
            exception_global_id=EXCEPTION_ID,
            requester_member_global_id=MEMBER_ID,
            actor_user_id=ACTOR,
            kind="p1_evidence_timing",
            requirement_key="supplier_timing",
            reason="Controlled exception request.",
            risk="Controlled residual risk.",
            closure_action_ref=self.repository_module._closure_action_reference(action),
            closure_action_kind="action",
            requested_at=NOW,
            expires_at=NOW + timedelta(days=1),
            expected_version=cycle.version,
            expected_input_hash=cycle.input_hash,
        )

    def _conditional_projection_decision(self):
        cycle = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        cycle = cycle.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id=EXCEPTION_APPROVER,
            outcome=self.domain.ExceptionOutcome.APPROVED,
            opinion="Approved with the exact closure action.",
            occurred_at=NOW + timedelta(minutes=30),
            expected_version=cycle.version,
            expected_input_hash=cycle.input_hash,
            expected_exception_version=1,
        )
        action = self.store.documents["NPI Domain Work Item"][str(UUID(int=106))]
        return (
            cycle.decide(
                actor_user_id=ACTOR,
                outcome=self.domain.DecisionOutcome.CONDITIONAL_PASS,
                occurred_at=NOW + timedelta(hours=1),
                expected_version=cycle.version,
                expected_input_hash=cycle.input_hash,
                current_input=cycle.input_snapshot,
                current_closure_action_refs={
                    EXCEPTION_ID: self.repository_module._closure_action_reference(
                        action
                    )
                },
            ),
            action,
        )

    def _closure_action(
        self,
        identity: UUID = UUID(int=106),
        *,
        version: int = 1,
        terminal: int = 0,
    ) -> AttrDoc:
        return self.store.add(
            "NPI Domain Work Item",
            identity,
            global_id=str(identity),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            stage_global_id=str(GATE_ID),
            source_system="NPI_ONE",
            blocking=0,
            state_terminal=terminal,
            state_key="open" if not terminal else "resolved",
            state_label_source="Open" if not terminal else "Resolved",
            optimistic_version=version,
            kind="action",
            title="Close the exact exception",
            detail="Exact closure action detail.",
            wbs_item_global_id=None,
            owner_user_id=ACTOR,
            due_at=NOW.isoformat(),
            severity="high",
            work_policy_global_id=str(UUID(int=107)),
            work_policy_version=1,
            work_policy_snapshot_hash="9" * 64,
            relations=[],
            evidence_references=[],
        )

    def _resolved_blocker(
        self,
        identity: UUID = RESOLVED_ACTION_ID,
    ) -> AttrDoc:
        return self.store.add(
            "NPI Domain Work Item",
            identity,
            global_id=str(identity),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            stage_global_id=str(GATE_ID),
            source_system="NPI_ONE",
            blocking=1,
            state_terminal=1,
            state_key="resolved",
            optimistic_version=2,
            kind="action",
        )

    def _add_dependency_event(
        self,
        *,
        prior_cycle_id: UUID,
        successor_cycle_id: UUID,
        event_type: str,
        occurred_at: datetime,
        action_id: UUID | None,
        old_input_hash: str,
        new_input_hash: str,
        prior_decision_id: UUID | None = None,
        prior_decision_hash: str | None = None,
        initiated_by_user_id: str | None = ACTOR,
        reason: str = "GATE_INPUT_CHANGED",
        schema_version: int = 2,
        legacy_detail: bool = False,
    ) -> AttrDoc:
        event_id = uuid5(
            prior_cycle_id,
            f"{event_type}:{successor_cycle_id}:{new_input_hash}",
        )
        event_key = f"{prior_cycle_id}:{event_type}:{successor_cycle_id}"
        detail = {
            "reason": reason,
            "oldInputHash": old_input_hash,
            "newInputHash": new_input_hash,
            "priorDecisionSnapshotGlobalId": (
                str(prior_decision_id) if prior_decision_id is not None else None
            ),
            "priorDecisionHash": prior_decision_hash,
            "initiatedByUserId": initiated_by_user_id,
        }
        if legacy_detail:
            detail.pop("reason")
            detail.pop("initiatedByUserId")
        payload = {
            "schemaVersion": schema_version,
            "globalId": str(event_id),
            "eventKey": event_key,
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "gateGlobalId": str(GATE_ID),
            "cycleGlobalId": str(prior_cycle_id),
            "successorCycleGlobalId": str(successor_cycle_id),
            "actionGlobalId": str(action_id) if action_id is not None else None,
            "eventType": event_type,
            "actorUserId": (self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR),
            "occurredAt": occurred_at.isoformat(),
            "requestId": "2ef22035-71df-4c07-a2ae-e88ea461d80c",
            "traceId": "trace-p4-04-repository",
            "detail": detail,
        }
        return self.store.add(
            "NPI Gate Review Event",
            event_id,
            global_id=str(event_id),
            event_key=event_key,
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            cycle_global_id=str(prior_cycle_id),
            successor_cycle_global_id=str(successor_cycle_id),
            action_global_id=str(action_id) if action_id is not None else None,
            event_type=event_type,
            actor_user_id=(self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR),
            occurred_at=occurred_at.isoformat(),
            request_id="2ef22035-71df-4c07-a2ae-e88ea461d80c",
            trace_id="trace-p4-04-repository",
            payload=payload,
            payload_hash=self._canonical_hash(payload),
        )

    def test_default_api_factory_imports_the_concrete_repository(self) -> None:
        api = importlib.import_module("npi_core.gate_review_api")
        repository = api._repository_factory(
            principal=self._principal(),
            request_id="request-p4-04",
            trace_id="trace-p4-04",
        )
        self.assertIsInstance(
            repository,
            self.repository_module.FrappeGateReviewRepository,
        )
        self.assertEqual(repository.actor, ACTOR)

    def test_locked_scope_uses_fixed_root_order_and_fails_closed_as_none(
        self,
    ) -> None:
        repository = self._repository()
        self.store.get_doc_calls.clear()
        locked = repository._locked_review_scope(
            PROJECT_ID,
            GATE_ID,
            CYCLE_ID,
            exception_id=EXCEPTION_ID,
        )
        self.assertEqual(
            locked,
            (
                self.project,
                self.gate,
                self.cycle_document,
                self.exception_document,
            ),
        )
        self.assertEqual(
            [
                doctype
                for doctype, _name, for_update in self.store.get_doc_calls
                if for_update
            ],
            [
                "NPI Engineering Project",
                "NPI Gate Shell",
                "NPI Gate Review Cycle",
                "NPI Gate Review Exception",
            ],
        )

        self.assertIsNone(
            repository._locked_review_scope(
                OTHER_PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                exception_id=EXCEPTION_ID,
            )
        )

        original_tenant = self.project.tenant_id
        self.project.tenant_id = "other-tenant"
        self.assertIsNone(
            repository._locked_review_scope(PROJECT_ID, GATE_ID, CYCLE_ID)
        )
        self.project.tenant_id = original_tenant

        member = self.store.documents["NPI Project Member"].pop(str(MEMBER_ID))
        self.assertIsNone(
            repository._locked_review_scope(PROJECT_ID, GATE_ID, CYCLE_ID)
        )
        self.store.documents["NPI Project Member"][str(MEMBER_ID)] = member

        original_project = self.gate.engineering_project
        self.gate.engineering_project = str(OTHER_PROJECT_ID)
        self.assertIsNone(
            repository._locked_review_scope(PROJECT_ID, GATE_ID, CYCLE_ID)
        )
        self.gate.engineering_project = original_project

        original_gate = self.cycle_document.gate_shell
        self.cycle_document.gate_shell = str(OTHER_GATE_ID)
        self.assertIsNone(
            repository._locked_review_scope(PROJECT_ID, GATE_ID, CYCLE_ID)
        )
        self.cycle_document.gate_shell = original_gate

        original_cycle = self.exception_document.cycle_global_id
        self.exception_document.cycle_global_id = str(uuid5(GATE_ID, "review-cycle:2"))
        self.assertIsNone(
            repository._locked_review_scope(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                exception_id=EXCEPTION_ID,
            )
        )
        self.exception_document.cycle_global_id = original_cycle

    def test_roles_owner_and_project_access_cannot_bypass_frozen_binding(
        self,
    ) -> None:
        binding = self.domain.AuthorityBinding(
            "engineering_reviewer",
            MEMBER_ID,
            ACTOR,
            "Reviewer",
        )
        cycle = types.SimpleNamespace(bindings=(binding,))
        exact = self._repository()
        exact._require_current_binding_actor(
            self.project,
            cycle,
            "engineering_reviewer",
        )

        scenarios = (
            (
                "manager@example.test",
                frozenset({"System Manager"}),
                {},
                False,
            ),
            (
                "owner@example.test",
                frozenset(),
                {},
                True,
            ),
            (
                "access@example.test",
                frozenset(),
                {
                    str(PROJECT_ID): self.security.ProjectAccess.ADMINISTER,
                },
                False,
            ),
            (
                "transport@example.test",
                frozenset({"NPI API User"}),
                {},
                False,
            ),
        )
        for index, (actor, roles, access, owner) in enumerate(scenarios, 10):
            with self.subTest(actor=actor):
                self._add_member(actor, UUID(int=index))
                self.project.owner_user_id = actor if owner else "owner@example.test"
                repository = self._repository(
                    self._principal(
                        actor,
                        roles=roles,
                        project_access=access,
                    )
                )
                with self.assertRaises(self.errors.PermissionDenied):
                    repository._require_current_binding_actor(
                        self.project,
                        cycle,
                        "engineering_reviewer",
                    )

    def test_frozen_binding_requires_one_live_enabled_internal_member(
        self,
    ) -> None:
        binding = self.domain.AuthorityBinding(
            "engineering_reviewer",
            MEMBER_ID,
            ACTOR,
            "Reviewer",
        )
        cycle = types.SimpleNamespace(bindings=(binding,))
        repository = self._repository()

        self.store.users[ACTOR].enabled = 0
        with self.assertRaises(self.errors.PermissionDenied):
            repository._require_current_binding_actor(
                self.project, cycle, "engineering_reviewer"
            )

        self.store.users[ACTOR].enabled = 1
        self.store.users[ACTOR].user_type = "Website User"
        with self.assertRaises(self.errors.PermissionDenied):
            repository._require_current_binding_actor(
                self.project, cycle, "engineering_reviewer"
            )

        self.store.users[ACTOR].user_type = "System User"
        member = self.store.documents["NPI Project Member"][str(MEMBER_ID)]
        member.effective_to = "2026-01-02"
        with self.assertRaises(self.errors.PermissionDenied):
            repository._require_current_binding_actor(
                self.project, cycle, "engineering_reviewer"
            )

        member.effective_to = None
        self._add_member(ACTOR, UUID(int=99))
        with self.assertRaises(self.errors.PermissionDenied):
            repository._require_current_binding_actor(
                self.project, cycle, "engineering_reviewer"
            )

    def test_actor_scoped_idempotency_replays_conflicts_and_seals(self) -> None:
        repository = self._repository()
        operation = "gate.review.submit"
        key_hash = "actor-key-hash"
        payload_hash = "a" * 64
        response = {"gate": {"globalId": str(GATE_ID)}}
        receipt = self.store.add(
            "NPI Gate Review Idempotency",
            "existing-receipt",
            record_id="existing-receipt",
            actor=ACTOR,
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            operation=operation,
            actor_key_hash=key_hash,
            payload_hash=payload_hash,
            response_json=response,
            response_sealed=1,
        )
        self.assertEqual(
            repository._idempotency_replay(
                key_hash,
                payload_hash,
                self.project,
                self.gate,
                operation,
            ),
            response,
        )

        conflicts = (
            ("actor", "other@example.test"),
            ("tenant_id", "other-tenant"),
            ("project_global_id", str(OTHER_PROJECT_ID)),
            ("gate_global_id", str(OTHER_GATE_ID)),
            ("operation", "gate.review.decide"),
            ("payload_hash", "b" * 64),
        )
        for fieldname, invalid in conflicts:
            with self.subTest(fieldname=fieldname):
                original = receipt[fieldname]
                receipt[fieldname] = invalid
                with self.assertRaises(self.project_domain.IdempotencyConflict):
                    repository._idempotency_replay(
                        key_hash,
                        payload_hash,
                        self.project,
                        self.gate,
                        operation,
                    )
                receipt[fieldname] = original

        receipt.response_sealed = 0
        with self.assertRaisesRegex(RuntimeError, "unsealed"):
            repository._idempotency_replay(
                key_hash,
                payload_hash,
                self.project,
                self.gate,
                operation,
            )
        receipt.response_sealed = 1

        del self.store.documents["NPI Gate Review Idempotency"]["existing-receipt"]
        inserted = repository._insert_idempotency(
            "new-actor-key",
            "c" * 64,
            self.project,
            self.gate,
            operation,
        )
        self.assertEqual(inserted.actor, ACTOR)
        self.assertEqual(inserted.response_sealed, 0)
        repository._seal_idempotency(inserted, response)
        self.assertEqual(inserted.response_json, response)
        self.assertEqual(inserted.response_sealed, 1)

        with self.assertRaises(self.project_domain.IdempotencyConflict):
            repository._insert_idempotency(
                "new-actor-key",
                "c" * 64,
                self.project,
                self.gate,
                operation,
            )
        self.assertEqual(self.store.rollback_count, 0)

    def test_command_receipt_reconciles_only_the_exact_sealed_actor_scope(
        self,
    ) -> None:
        repository = self._repository()
        operation = "gate.review.submit"
        actor_key_hash = "a" * 64

        self.store.get_doc_calls.clear()
        self.store.get_value_calls.clear()
        self.assertEqual(
            repository.command_receipt(
                PROJECT_ID,
                GATE_ID,
                operation=operation,
                actor_key_hash=actor_key_hash,
            ),
            {
                "operation": operation,
                "status": "absent",
                "workspaceReloadRequired": True,
            },
        )
        self.assertEqual(
            [call for call in self.store.get_doc_calls if call[2]][:2],
            [
                ("NPI Engineering Project", str(PROJECT_ID), True),
                ("NPI Gate Shell", str(GATE_ID), True),
            ],
        )
        receipt_reads = [
            call
            for call in self.store.get_value_calls
            if call[0] == "NPI Gate Review Idempotency"
        ]
        self.assertEqual(len(receipt_reads), 1)
        self.assertTrue(receipt_reads[0][4])

        receipt = self.store.add(
            "NPI Gate Review Idempotency",
            "receipt-reconciliation",
            record_id="receipt-reconciliation",
            actor=ACTOR,
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            operation=operation,
            actor_key_hash=actor_key_hash,
            response_sealed=1,
        )
        self.assertEqual(
            repository.command_receipt(
                PROJECT_ID,
                GATE_ID,
                operation=operation,
                actor_key_hash=actor_key_hash,
            ),
            {
                "operation": operation,
                "status": "completed",
                "workspaceReloadRequired": True,
            },
        )

        receipt.actor = "other@example.test"
        self.assertIsNone(
            repository.command_receipt(
                PROJECT_ID,
                GATE_ID,
                operation=operation,
                actor_key_hash=actor_key_hash,
            )
        )
        receipt.actor = ACTOR
        receipt.response_sealed = 0
        with self.assertRaisesRegex(RuntimeError, "not sealed"):
            repository.command_receipt(
                PROJECT_ID,
                GATE_ID,
                operation=operation,
                actor_key_hash=actor_key_hash,
            )

        with self.assertRaisesRegex(ValueError, "unsupported"):
            repository.command_receipt(
                PROJECT_ID,
                GATE_ID,
                operation="gate.review.unknown",
                actor_key_hash=actor_key_hash,
            )

    def test_dependency_worker_validates_reference_and_uses_no_initiator_authority(
        self,
    ) -> None:
        reference = self.store.add(
            "NPI Gate Evidence Reference",
            REFERENCE_ID,
            global_id=str(REFERENCE_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            evidence_kind="wbs_item",
            source_object_type="wbs_item",
            source_global_id=str(SOURCE_ID),
        )
        del self.store.documents["NPI Project Member"][str(MEMBER_ID)]
        self.store.users[ACTOR].enabled = 0
        captured: list[tuple[object, object, object, object]] = []
        repository_type = self.repository_module.FrappeGateReviewRepository
        original_refresh = repository_type.refresh_gate_for_dependency_change_locked

        def refresh(
            repository,
            project,
            gate,
            *,
            reason,
            occurred_at=None,
            initiated_by_user_id=None,
        ):
            del occurred_at
            captured.append((repository, project, gate, (reason, initiated_by_user_id)))
            return True

        repository_type.refresh_gate_for_dependency_change_locked = refresh
        try:
            self.assertTrue(
                self.repository_module.evaluate_gate_review_dependency(
                    reference_id=str(REFERENCE_ID),
                    tenant_id=TENANT_ID,
                    project_id=str(PROJECT_ID),
                    gate_id=str(GATE_ID),
                    source_kind="wbs_item",
                    source_global_id=str(SOURCE_ID),
                    initiated_by_user_id=ACTOR,
                )
            )
            repository = captured[0][0]
            self.assertEqual(
                repository.actor,
                self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR,
            )
            self.assertTrue(repository._dependency_system)
            self.assertFalse(repository._is_internal_system_manager())
            self.assertEqual(
                captured[0][3],
                ("GATE_SOURCE_CHANGED", ACTOR),
            )
            binding = self.domain.AuthorityBinding(
                "engineering_reviewer",
                MEMBER_ID,
                ACTOR,
                "Reviewer",
            )
            with self.assertRaises(self.errors.PermissionDenied):
                repository._require_current_binding_actor(
                    self.project,
                    types.SimpleNamespace(bindings=(binding,)),
                    "engineering_reviewer",
                )

            reference.gate_global_id = str(OTHER_GATE_ID)
            self.store.get_doc_calls.clear()
            self.assertFalse(
                self.repository_module.evaluate_gate_review_dependency(
                    reference_id=str(REFERENCE_ID),
                    tenant_id=TENANT_ID,
                    project_id=str(PROJECT_ID),
                    gate_id=str(GATE_ID),
                    source_kind="wbs_item",
                    source_global_id=str(SOURCE_ID),
                    initiated_by_user_id=ACTOR,
                )
            )
            self.assertEqual(len(captured), 1)
            self.assertFalse(
                any(
                    doctype == "NPI Engineering Project" and for_update
                    for doctype, _name, for_update in self.store.get_doc_calls
                )
            )
        finally:
            repository_type.refresh_gate_for_dependency_change_locked = original_refresh

    def test_file_hook_queues_gate_recalculation_for_each_identity_change_only(
        self,
    ) -> None:
        file_id = "private/files/gate-evidence.pdf"
        self.store.add(
            "NPI File Revision",
            SOURCE_ID,
            global_id=str(SOURCE_ID),
            frappe_file_id=file_id,
        )
        self.store.add(
            "NPI Gate Evidence Reference",
            REFERENCE_ID,
            global_id=str(REFERENCE_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            source_object_type="file_revision",
            source_global_id=str(SOURCE_ID),
        )
        previous = AttrDoc(
            doctype="File",
            name=file_id,
            is_private=1,
            is_remote_file=0,
            file_url="/private/files/gate-evidence.pdf",
            content_hash="a" * 64,
            file_size=1024,
            file_name="gate-evidence.pdf",
        )
        changes = {
            "is_private": 0,
            "is_remote_file": 1,
            "file_url": "https://files.example.test/gate-evidence.pdf",
            "content_hash": "b" * 64,
            "file_size": 2048,
            "file_name": "renamed-gate-evidence.pdf",
        }
        for fieldname, changed_value in changes.items():
            with self.subTest(fieldname=fieldname):
                self.enqueued.clear()
                changed = AttrDoc(
                    previous,
                    **{fieldname: changed_value},
                    _previous=previous,
                )
                self.repository_module.queue_gate_review_file_dependency_evaluation(
                    changed
                )
                self.assertEqual(len(self.enqueued), 1)
                args, queued = self.enqueued[0]
                self.assertEqual(
                    args,
                    (
                        "npi_core.gate_review.frappe_repository."
                        "evaluate_gate_review_dependency",
                    ),
                )
                self.assertEqual(queued["reference_id"], str(REFERENCE_ID))
                self.assertEqual(queued["source_kind"], "file_revision")
                self.assertEqual(queued["source_global_id"], str(SOURCE_ID))
                self.assertEqual(queued["gate_id"], str(GATE_ID))
                self.assertTrue(queued["enqueue_after_commit"])

        self.enqueued.clear()
        unrelated = AttrDoc(
            previous,
            folder="Home/Attachments",
            _previous=previous,
        )
        self.repository_module.queue_gate_review_file_dependency_evaluation(unrelated)
        self.assertEqual(self.enqueued, [])

        deleted = AttrDoc(previous)
        self.repository_module.queue_gate_review_file_dependency_evaluation(
            deleted,
            method="on_trash",
        )
        self.assertEqual(len(self.enqueued), 1)
        _args, deleted_job = self.enqueued[0]
        self.assertTrue(deleted_job["enqueue_after_commit"])
        self.assertEqual(deleted_job["reference_id"], str(REFERENCE_ID))
        self.assertEqual(deleted_job["source_kind"], "file_revision")
        self.assertEqual(deleted_job["source_global_id"], str(SOURCE_ID))

    def test_work_item_hook_queues_active_blockers_and_npi_actions(self) -> None:
        self.frappe.flags.npi_project_work_command_write = True
        base = {
            "doctype": "NPI Domain Work Item",
            "global_id": str(RESOLVED_ACTION_ID),
            "tenant_id": TENANT_ID,
            "project_global_id": str(PROJECT_ID),
            "stage_global_id": str(GATE_ID),
            "source_system": "NPI_ONE",
            "blocking": 1,
            "state_terminal": 0,
            "state_key": "open",
            "optimistic_version": 1,
            "kind": "issue",
        }
        cases = (
            ("active", {}, 1),
            ("nonblocking", {"blocking": 0}, 0),
            ("terminal", {"state_terminal": 1}, 0),
            ("nonblocking_action", {"blocking": 0, "kind": "action"}, 1),
            (
                "terminal_action",
                {"blocking": 0, "kind": "action", "state_terminal": 1},
                1,
            ),
            (
                "external_action",
                {"blocking": 0, "kind": "action", "source_system": "ERP_NEXT"},
                0,
            ),
        )
        for label, changes, expected_count in cases:
            with self.subTest(label=label):
                self.enqueued.clear()
                inserted = AttrDoc(base, **changes)
                self.repository_module.queue_gate_review_work_item_evaluation(inserted)
                self.assertEqual(len(self.enqueued), expected_count)
                if expected_count:
                    _args, queued = self.enqueued[0]
                    self.assertEqual(queued["gate_id"], str(GATE_ID))
                    self.assertEqual(
                        queued["work_item_id"],
                        str(RESOLVED_ACTION_ID),
                    )

    def test_work_item_hook_queues_before_after_active_blocker_gate_union(
        self,
    ) -> None:
        previous = AttrDoc(
            doctype="NPI Domain Work Item",
            global_id=str(RESOLVED_ACTION_ID),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            stage_global_id=str(GATE_ID),
            source_system="NPI_ONE",
            blocking=1,
            state_terminal=0,
            state_key="open",
            optimistic_version=1,
        )
        moved = AttrDoc(
            previous,
            stage_global_id=str(OTHER_GATE_ID),
            optimistic_version=2,
            _previous=previous,
        )
        self.repository_module.queue_gate_review_work_item_evaluation(moved)
        self.assertEqual(self.enqueued, [])

        self.frappe.flags.npi_project_work_command_write = True
        self.repository_module.queue_gate_review_work_item_evaluation(moved)
        self.assertEqual(len(self.enqueued), 2)
        self.assertEqual(
            {queued["gate_id"] for _args, queued in self.enqueued},
            {str(GATE_ID), str(OTHER_GATE_ID)},
        )
        args, queued = self.enqueued[0]
        worker_name = "evaluate_gate_review_work_item_dependency"
        expected_worker = f"{self.repository_module.__name__}.{worker_name}"
        self.assertEqual(args, (expected_worker,))
        self.assertTrue(queued["enqueue_after_commit"])
        self.assertEqual(queued["queue"], "short")
        self.assertEqual(queued["work_item_id"], str(RESOLVED_ACTION_ID))
        self.assertEqual(queued["tenant_id"], TENANT_ID)
        self.assertEqual(queued["project_id"], str(PROJECT_ID))
        self.assertEqual(queued["observed_version"], 2)
        self.assertEqual(queued["initiated_by_user_id"], ACTOR)

        self.enqueued.clear()
        resolved = AttrDoc(
            previous,
            state_terminal=1,
            state_key="resolved",
            optimistic_version=2,
            _previous=previous,
        )
        self.repository_module.queue_gate_review_work_item_evaluation(resolved)
        self.assertEqual(len(self.enqueued), 1)
        self.assertEqual(self.enqueued[0][1]["gate_id"], str(GATE_ID))

        del self.store.documents["NPI Project Member"][str(MEMBER_ID)]
        self.store.users[ACTOR].enabled = 0
        captured: list[tuple[object, object, object, object]] = []
        repository_type = self.repository_module.FrappeGateReviewRepository
        original_refresh = repository_type.refresh_gate_for_work_item_dependency_locked

        def refresh(
            repository,
            project,
            gate,
            *,
            work_item_global_id,
            reason,
            occurred_at=None,
            initiated_by_user_id=None,
        ):
            del occurred_at
            captured.append(
                (
                    repository,
                    project,
                    gate,
                    (
                        work_item_global_id,
                        reason,
                        initiated_by_user_id,
                    ),
                )
            )
            return True

        repository_type.refresh_gate_for_work_item_dependency_locked = refresh
        worker_values = {
            key: value
            for key, value in self.enqueued[0][1].items()
            if key not in {"queue", "enqueue_after_commit"}
        }
        try:
            self.assertTrue(
                self.repository_module.evaluate_gate_review_work_item_dependency(
                    **worker_values
                )
            )
            repository = captured[0][0]
            self.assertEqual(
                repository.actor,
                self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR,
            )
            self.assertTrue(repository._dependency_system)
            self.assertEqual(
                captured[0][3],
                (
                    RESOLVED_ACTION_ID,
                    "GATE_WORK_ITEM_CHANGED",
                    ACTOR,
                ),
            )
            self.assertFalse(
                self.repository_module.evaluate_gate_review_work_item_dependency(
                    **{**worker_values, "observed_version": 0}
                )
            )
            self.assertEqual(len(captured), 1)
        finally:
            repository_type.refresh_gate_for_work_item_dependency_locked = (
                original_refresh
            )

    def test_closure_action_drift_covers_exact_version_terminal_and_scope(self) -> None:
        decided, action = self._conditional_projection_decision()
        repository = self._repository(dependency_system=True)
        action_id = UUID(str(action.global_id))

        self.assertFalse(
            repository._closure_action_reference_drifted_locked(
                self.project,
                self.gate,
                decided,
                action_id,
            )
        )
        original = {
            fieldname: action.get(fieldname)
            for fieldname in (
                "detail",
                "optimistic_version",
                "state_terminal",
                "state_key",
                "stage_global_id",
                "project_global_id",
            )
        }
        cases = (
            ("version", {"optimistic_version": 2}),
            (
                "content",
                {
                    "detail": "Changed exact closure action detail.",
                    "optimistic_version": 2,
                },
            ),
            (
                "terminal",
                {
                    "state_terminal": 1,
                    "state_key": "resolved",
                    "optimistic_version": 2,
                },
            ),
            (
                "moved_gate",
                {
                    "stage_global_id": str(OTHER_GATE_ID),
                    "optimistic_version": 2,
                },
            ),
            (
                "moved_project",
                {
                    "project_global_id": str(OTHER_PROJECT_ID),
                    "optimistic_version": 2,
                },
            ),
        )
        for label, changes in cases:
            with self.subTest(label=label):
                action.update(original)
                action.update(changes)
                self.assertTrue(
                    repository._closure_action_reference_drifted_locked(
                        self.project,
                        self.gate,
                        decided,
                        action_id,
                    )
                )

        action.update(original)
        removed = self.store.documents["NPI Domain Work Item"].pop(str(action_id))
        try:
            self.assertTrue(
                repository._closure_action_reference_drifted_locked(
                    self.project,
                    self.gate,
                    decided,
                    action_id,
                )
            )
        finally:
            self.store.documents["NPI Domain Work Item"][str(action_id)] = removed

    def test_closure_action_job_invalidates_once_and_requires_review(self) -> None:
        domain = self.domain
        decided, action = self._conditional_projection_decision()
        assert decided.decision is not None
        self.cycle_document.update(
            state="decided",
            optimistic_version=decided.version,
        )
        decision_document = self.store.add(
            "NPI Gate Decision Snapshot",
            decided.decision.global_id,
            global_id=str(decided.decision.global_id),
            cycle_global_id=str(decided.global_id),
            snapshot_hash=decided.decision.snapshot_hash,
            outcome=decided.decision.outcome.value,
        )
        self.gate.update(
            review_state="decided",
            current_review_cycle=str(decided.global_id),
            current_review_cycle_global_id=str(decided.global_id),
            latest_decision_snapshot=str(decided.decision.global_id),
            latest_decision_snapshot_global_id=str(decided.decision.global_id),
            latest_decision_snapshot_hash=decided.decision.snapshot_hash,
            latest_decision_outcome=decided.decision.outcome.value,
            review_input_version=1,
            optimistic_version=5,
        )
        action.detail = "Changed exact closure action detail."
        action.optimistic_version = 2
        changed_input = replace(
            decided.input_snapshot,
            gate_version=2,
            dependencies=(
                replace(
                    decided.input_snapshot.dependencies[0],
                    version=2,
                    snapshot_hash="f" * 64,
                ),
            ),
        )
        cycles = {decided.global_id: decided}
        repository_type = self.repository_module.FrappeGateReviewRepository
        original_hydrate = repository_type._hydrate_cycle
        original_build = repository_type._build_current_input
        original_audit = repository_type._audit
        repository_type._hydrate_cycle = (
            lambda _repository, document, **_values: cycles[
                UUID(str(document.global_id))
            ]
        )
        repository_type._build_current_input = (
            lambda _repository, _project, _gate: changed_input
        )
        repository_type._audit = lambda *_args, **_kwargs: None
        worker_values = {
            "work_item_id": str(action.global_id),
            "tenant_id": TENANT_ID,
            "project_id": str(PROJECT_ID),
            "gate_id": str(GATE_ID),
            "observed_version": 2,
            "initiated_by_user_id": ACTOR,
        }
        try:
            self.assertTrue(
                self.repository_module.evaluate_gate_review_work_item_dependency(
                    **worker_values
                )
            )
            successor_id = uuid5(GATE_ID, "review-cycle:2")
            cycles[successor_id] = decided.invalidate_for_dependency_change(
                actor_user_id=(
                    self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR
                ),
                initiated_by_user_id=ACTOR,
                reason="GATE_WORK_ITEM_CHANGED",
                occurred_at=NOW,
                current_input=changed_input,
                current_bindings=decided.bindings,
                gate_current_cycle_global_id=decided.global_id,
                expected_version=decided.version,
                expected_input_hash=decided.input_hash,
            ).current_cycle

            self.assertEqual(self.gate.review_input_version, 2)
            self.assertEqual(self.gate.optimistic_version, 6)
            self.assertEqual(self.gate.review_state, "requires_review")
            self.assertEqual(
                self.gate.current_review_cycle_global_id,
                str(successor_id),
            )
            self.assertEqual(
                self.gate.latest_decision_snapshot_global_id,
                str(decided.decision.global_id),
            )
            self.assertIs(
                self.store.documents["NPI Gate Decision Snapshot"][
                    str(decided.decision.global_id)
                ],
                decision_document,
            )
            self.assertEqual(
                len(self.store.documents["NPI Gate Review Event"]),
                1,
            )
            self.assertEqual(
                len(self.store.documents["NPI Gate Review Cycle"]),
                2,
            )
            self.assertFalse(
                self.repository_module.evaluate_gate_review_work_item_dependency(
                    **worker_values
                )
            )
            self.assertEqual(self.gate.review_input_version, 2)
            self.assertEqual(self.gate.optimistic_version, 6)
            self.assertEqual(
                len(self.store.documents["NPI Gate Review Event"]),
                1,
            )
            self.assertEqual(
                len(self.store.documents["NPI Gate Review Cycle"]),
                2,
            )
        finally:
            repository_type._hydrate_cycle = original_hydrate
            repository_type._build_current_input = original_build
            repository_type._audit = original_audit

    def test_closure_action_job_exposes_disabled_authority_without_substitution(
        self,
    ) -> None:
        domain = self.domain
        decided, action = self._conditional_projection_decision()
        action.detail = "Changed exact closure action detail."
        action.optimistic_version = 2
        self.cycle_document.update(
            state="decided",
            optimistic_version=decided.version,
        )
        self.gate.update(
            review_state="decided",
            current_review_cycle=str(decided.global_id),
            current_review_cycle_global_id=str(decided.global_id),
            review_input_version=1,
        )
        self.store.users[STEP_REVIEWER].enabled = 0
        repository_type = self.repository_module.FrappeGateReviewRepository
        original_hydrate = repository_type._hydrate_cycle
        repository_type._hydrate_cycle = (
            lambda _repository, _document, **_values: decided
        )
        original_bindings = decided.bindings
        try:
            with self.assertRaises(self.errors.PermissionDenied):
                self.repository_module.evaluate_gate_review_work_item_dependency(
                    work_item_id=str(action.global_id),
                    tenant_id=TENANT_ID,
                    project_id=str(PROJECT_ID),
                    gate_id=str(GATE_ID),
                    observed_version=2,
                    initiated_by_user_id=ACTOR,
                )
        finally:
            repository_type._hydrate_cycle = original_hydrate

        self.assertEqual(decided.bindings, original_bindings)
        self.assertEqual(self.gate.review_input_version, 1)
        self.assertEqual(self.gate.review_state, "decided")
        self.assertEqual(
            len(self.store.documents["NPI Gate Review Cycle"]),
            1,
        )
        self.assertEqual(
            len(self.store.documents.get("NPI Gate Review Event", {})),
            0,
        )
        self.assertFalse(
            domain.downstream_decision_is_current(
                decided,
                gate_current_cycle_global_id=decided.global_id,
                current_input=decided.input_snapshot,
                at=NOW + timedelta(hours=2),
                current_closure_action_refs={
                    EXCEPTION_ID: self.repository_module._closure_action_reference(
                        action
                    )
                },
            )
        )

    def test_concurrent_blocker_resolutions_refresh_once_without_an_impact_action(
        self,
    ) -> None:
        domain = self.domain
        policy, bindings = self._dependency_policy_and_bindings()
        blocked_input = self._gate_input(
            blockers=(
                domain.GateBlockerInput(
                    RESOLVED_ACTION_ID,
                    1,
                    "open",
                    True,
                    False,
                ),
                domain.GateBlockerInput(
                    SECOND_RESOLVED_ACTION_ID,
                    1,
                    "open",
                    True,
                    False,
                ),
            )
        )
        resolved_input = self._gate_input(blockers=())
        active = domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=blocked_input,
        )
        active = active.submit_review(
            step_key="engineering",
            actor_user_id=ACTOR,
            outcome=domain.ReviewOutcome.APPROVED,
            opinion="The frozen input was reviewed.",
            occurred_at=NOW,
            expected_version=active.version,
            expected_input_hash=active.input_hash,
        )
        with self.assertRaises(domain.ReviewDenied) as blocked:
            active.decide(
                actor_user_id="decider@example.test",
                outcome=domain.DecisionOutcome.PASS,
                occurred_at=NOW,
                expected_version=active.version,
                expected_input_hash=active.input_hash,
                current_input=blocked_input,
            )
        self.assertEqual(blocked.exception.code, "GATE_BLOCKED")

        self.cycle_document.update(
            state="active",
            optimistic_version=active.version,
        )
        self.gate.update(
            review_state="in_review",
            current_review_cycle=str(active.global_id),
            current_review_cycle_global_id=str(active.global_id),
        )
        review_document = self.store.add(
            "NPI Gate Review Record",
            uuid5(active.global_id, "review:engineering"),
            global_id=str(uuid5(active.global_id, "review:engineering")),
            cycle_global_id=str(active.global_id),
            marker="frozen-review",
        )
        self.exception_document.marker = "frozen-exception"
        self._resolved_blocker()
        self._resolved_blocker(SECOND_RESOLVED_ACTION_ID)
        repository = self._repository(dependency_system=True)
        repository._hydrate_cycle = lambda document, **_values: active
        repository._build_current_input = lambda project, gate: resolved_input
        repository._resolve_frozen_binding = lambda project, binding, now: binding
        audit_calls: list[tuple[object, ...]] = []
        repository._audit = lambda *args, **_kwargs: audit_calls.append(args)

        self.assertTrue(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                reason="GATE_WORK_ITEM_CHANGED",
                occurred_at=NOW,
                initiated_by_user_id=ACTOR,
            )
        )

        successor_id = uuid5(GATE_ID, "review-cycle:2")
        successor_document = self.store.documents["NPI Gate Review Cycle"][
            str(successor_id)
        ]
        self.assertEqual(self.cycle_document.state, "superseded")
        self.assertEqual(successor_document.state, "active")
        self.assertEqual(successor_document.input_snapshot["blockers"], [])
        self.assertEqual(successor_document.input_hash, resolved_input.snapshot_hash)
        self.assertEqual(self.gate.review_state, "requires_review")
        self.assertEqual(
            self.gate.current_review_cycle_global_id,
            str(successor_id),
        )
        event = next(iter(self.store.documents["NPI Gate Review Event"].values()))
        self.assertEqual(event.event_type, "refreshed")
        self.assertIsNone(event.action_global_id)
        self.assertEqual(
            event.payload["detail"]["reason"],
            "GATE_WORK_ITEM_CHANGED",
        )
        self.assertEqual(
            event.payload["detail"]["initiatedByUserId"],
            ACTOR,
        )
        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(
            audit_calls[0][3]["newInputHash"],
            resolved_input.snapshot_hash,
        )
        self.assertEqual(
            len(self.store.documents["NPI Domain Work Item"]),
            2,
        )
        self.assertIs(
            self.store.documents["NPI Gate Review Record"][review_document.name],
            review_document,
        )
        self.assertEqual(review_document.marker, "frozen-review")
        self.assertIs(
            self.store.documents["NPI Gate Review Exception"][
                self.exception_document.name
            ],
            self.exception_document,
        )
        self.assertEqual(self.exception_document.marker, "frozen-exception")

        successor = active.invalidate_for_dependency_change(
            actor_user_id=(self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR),
            initiated_by_user_id=ACTOR,
            reason="GATE_WORK_ITEM_CHANGED",
            occurred_at=NOW,
            current_input=resolved_input,
            current_bindings=bindings,
            gate_current_cycle_global_id=active.global_id,
            expected_version=active.version,
            expected_input_hash=active.input_hash,
        ).current_cycle
        repository._hydrate_cycle = lambda document, **_values: successor
        self.assertFalse(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                reason="GATE_WORK_ITEM_CHANGED",
                occurred_at=NOW,
                initiated_by_user_id=ACTOR,
            )
        )
        successor = successor.submit_review(
            step_key="engineering",
            actor_user_id=ACTOR,
            outcome=domain.ReviewOutcome.APPROVED,
            opinion="The resolved input was reviewed again.",
            occurred_at=NOW,
            expected_version=successor.version,
            expected_input_hash=successor.input_hash,
        )
        passed = successor.decide(
            actor_user_id="decider@example.test",
            outcome=domain.DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=successor.version,
            expected_input_hash=successor.input_hash,
            current_input=resolved_input,
        )
        self.assertEqual(passed.decision.outcome, domain.DecisionOutcome.PASS)

        self.assertEqual(
            len(self.store.documents["NPI Gate Review Cycle"]),
            2,
        )
        self.assertEqual(
            len(self.store.documents["NPI Gate Review Event"]),
            1,
        )
        self.assertEqual(
            len(self.store.documents["NPI Domain Work Item"]),
            2,
        )

    def test_work_item_change_with_other_drift_freezes_exact_live_input_without_action(
        self,
    ) -> None:
        domain = self.domain
        policy, bindings = self._dependency_policy_and_bindings()
        blocked_input = self._gate_input(
            blockers=(
                domain.GateBlockerInput(
                    RESOLVED_ACTION_ID,
                    1,
                    "open",
                    True,
                    False,
                ),
            )
        )
        resolved_input = self._gate_input(blockers=())
        drifted_input = replace(
            resolved_input,
            dependencies=(
                replace(
                    resolved_input.dependencies[0],
                    version=2,
                    snapshot_hash="f" * 64,
                ),
            ),
        )
        active = domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=blocked_input,
        )
        self.cycle_document.update(
            state="active",
            optimistic_version=active.version,
        )
        self.gate.update(
            review_state="in_review",
            current_review_cycle=str(active.global_id),
            current_review_cycle_global_id=str(active.global_id),
        )
        self._resolved_blocker()
        repository = self._repository(dependency_system=True)
        repository._hydrate_cycle = lambda document, **_values: active
        self.current_live_input = drifted_input
        repository._build_current_input = lambda project, gate: self.current_live_input
        repository._resolve_frozen_binding = lambda project, binding, now: binding
        repository._audit = lambda *_args, **_kwargs: None
        self.assertTrue(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                reason="GATE_WORK_ITEM_CHANGED",
                occurred_at=NOW,
                initiated_by_user_id=ACTOR,
            )
        )

        successor_id = uuid5(GATE_ID, "review-cycle:2")
        successor = self.store.documents["NPI Gate Review Cycle"][str(successor_id)]
        self.assertEqual(self.cycle_document.state, "superseded")
        self.assertEqual(successor.input_hash, self.current_live_input.snapshot_hash)
        self.assertNotIn(
            str(RESOLVED_ACTION_ID),
            {value["globalId"] for value in successor.input_snapshot["blockers"]},
        )
        event = next(iter(self.store.documents["NPI Gate Review Event"].values()))
        self.assertIsNone(event.action_global_id)
        self.assertIsNone(event.payload["actionGlobalId"])
        self.assertEqual(event.payload["detail"]["reason"], "GATE_WORK_ITEM_CHANGED")
        self.assertEqual(
            len(self.store.documents["NPI Domain Work Item"]),
            1,
        )

    def test_decided_blocker_resolution_invalidates_without_new_impact_action(
        self,
    ) -> None:
        domain = self.domain
        policy, bindings = self._dependency_policy_and_bindings()
        blocked_input = self._gate_input(
            blockers=(
                domain.GateBlockerInput(
                    RESOLVED_ACTION_ID,
                    1,
                    "open",
                    True,
                    False,
                ),
            )
        )
        resolved_input = self._gate_input(blockers=())
        decided = domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=blocked_input,
        )
        decided = decided.submit_review(
            step_key="engineering",
            actor_user_id=ACTOR,
            outcome=domain.ReviewOutcome.APPROVED,
            opinion="The frozen input was reviewed.",
            occurred_at=NOW,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        decided = decided.decide(
            actor_user_id="decider@example.test",
            outcome=domain.DecisionOutcome.REJECT,
            occurred_at=NOW,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
            current_input=blocked_input,
        )
        assert decided.decision is not None
        self.cycle_document.update(
            state="decided",
            optimistic_version=decided.version,
        )
        decision_document = self.store.add(
            "NPI Gate Decision Snapshot",
            decided.decision.global_id,
            global_id=str(decided.decision.global_id),
            cycle_global_id=str(decided.global_id),
            snapshot_hash=decided.decision.snapshot_hash,
            outcome=decided.decision.outcome.value,
        )
        self.gate.update(
            review_state="decided",
            current_review_cycle=str(decided.global_id),
            current_review_cycle_global_id=str(decided.global_id),
            latest_decision_snapshot=str(decided.decision.global_id),
            latest_decision_snapshot_global_id=str(decided.decision.global_id),
            latest_decision_snapshot_hash=decided.decision.snapshot_hash,
            latest_decision_outcome=decided.decision.outcome.value,
        )
        self._resolved_blocker()
        repository = self._repository(dependency_system=True)
        repository._hydrate_cycle = lambda document, **_values: decided
        repository._build_current_input = lambda project, gate: resolved_input
        repository._resolve_frozen_binding = lambda project, binding, now: binding
        repository._audit = lambda *_args, **_kwargs: None

        self.assertTrue(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                reason="GATE_WORK_ITEM_CHANGED",
                occurred_at=NOW,
                initiated_by_user_id=ACTOR,
            )
        )

        successor_id = uuid5(GATE_ID, "review-cycle:2")
        successor_document = self.store.documents["NPI Gate Review Cycle"][
            str(successor_id)
        ]
        self.assertEqual(self.cycle_document.state, "invalidated")
        self.assertEqual(successor_document.state, "active")
        self.assertEqual(successor_document.input_snapshot["blockers"], [])
        self.assertEqual(
            successor_document.prior_decision_snapshot_global_id,
            str(decided.decision.global_id),
        )
        self.assertEqual(
            successor_document.prior_decision_hash,
            decided.decision.snapshot_hash,
        )
        self.assertIs(
            self.store.documents["NPI Gate Decision Snapshot"][
                str(decided.decision.global_id)
            ],
            decision_document,
        )
        self.assertEqual(
            len(self.store.documents["NPI Domain Work Item"]),
            1,
        )
        event = next(iter(self.store.documents["NPI Gate Review Event"].values()))
        self.assertEqual(event.event_type, "invalidated")
        self.assertEqual(event.payload["schemaVersion"], 2)
        self.assertIsNone(event.action_global_id)
        self.assertEqual(
            event.payload["detail"]["reason"],
            "GATE_WORK_ITEM_CHANGED",
        )

    def test_dependency_invalidation_preserves_decision_and_creates_once(
        self,
    ) -> None:
        domain = self.domain
        policy = domain.ReviewPolicyVersion.create_draft(
            policy_global_id=POLICY_ID,
            policy_code="P4-04-REPOSITORY",
            gate_template_global_id=GATE_TEMPLATE_ID,
            gate_template_version=1,
            gate_template_hash="b" * 64,
            steps=(
                domain.ReviewStep(
                    "engineering",
                    1,
                    "engineering_reviewer",
                ),
            ),
            decision_authority_slot="gate_decider",
            reopen_authority_slot="gate_reopener",
            exception_rules=(),
            dependency_evaluators=(domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,),
        ).publish(1)
        bindings = (
            domain.AuthorityBinding(
                "engineering_reviewer", MEMBER_ID, ACTOR, "Reviewer"
            ),
            domain.AuthorityBinding(
                "gate_decider",
                UUID(int=51),
                "decider@example.test",
                "Decider",
            ),
            domain.AuthorityBinding(
                "gate_reopener",
                UUID(int=52),
                "reopener@example.test",
                "Reopener",
            ),
        )

        def input_snapshot(dependency_hash: str, gate_version: int):
            return domain.GateInputSnapshot(
                gate_global_id=GATE_ID,
                project_global_id=PROJECT_ID,
                tenant_id=TENANT_ID,
                gate_version=gate_version,
                requirements=(),
                evidence=(),
                blockers=(),
                dependencies=(
                    domain.GateDependencyInput(
                        domain.DependencyEvaluator.GATE_INPUT_SNAPSHOT,
                        DEPENDENCY_ID,
                        gate_version,
                        dependency_hash,
                    ),
                ),
            )

        original_input = input_snapshot("e" * 64, 1)
        changed_input = input_snapshot("f" * 64, 2)
        decided = domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=original_input,
        )
        decided = decided.submit_review(
            step_key="engineering",
            actor_user_id=ACTOR,
            outcome=domain.ReviewOutcome.APPROVED,
            opinion="The frozen evidence is acceptable.",
            occurred_at=NOW,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        )
        decided = decided.decide(
            actor_user_id="decider@example.test",
            outcome=domain.DecisionOutcome.PASS,
            occurred_at=NOW,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
            current_input=original_input,
        )
        assert decided.decision is not None

        self.cycle_document.update(
            state="decided",
            optimistic_version=decided.version,
        )
        decision_document = self.store.add(
            "NPI Gate Decision Snapshot",
            decided.decision.global_id,
            global_id=str(decided.decision.global_id),
            cycle_global_id=str(decided.global_id),
            snapshot_hash=decided.decision.snapshot_hash,
            outcome=decided.decision.outcome.value,
        )
        self.gate.update(
            review_state="decided",
            current_review_cycle=str(decided.global_id),
            current_review_cycle_global_id=str(decided.global_id),
            latest_decision_snapshot=str(decided.decision.global_id),
            latest_decision_snapshot_global_id=str(decided.decision.global_id),
            latest_decision_snapshot_hash=decided.decision.snapshot_hash,
            latest_decision_outcome=decided.decision.outcome.value,
            optimistic_version=5,
        )
        repository = self._repository(dependency_system=True)
        repository._hydrate_cycle = lambda document, **_values: decided
        self.current_live_input = changed_input
        repository._build_current_input = lambda project, gate: self.current_live_input
        repository._resolve_frozen_binding = lambda project, binding, now: binding
        repository._audit = lambda *_args, **_kwargs: None

        original_decision_hash = decision_document.snapshot_hash

        self.assertTrue(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                occurred_at=NOW,
            )
        )
        successor_id = uuid5(GATE_ID, "review-cycle:2")
        successor = self.store.documents["NPI Gate Review Cycle"][str(successor_id)]
        self.assertEqual(self.cycle_document.state, "invalidated")
        self.assertEqual(successor.state, "active")
        self.assertEqual(successor.prior_cycle_global_id, str(CYCLE_ID))
        self.assertEqual(
            successor.prior_decision_hash,
            decided.decision.snapshot_hash,
        )
        first_successor_input = self.current_live_input
        self.assertEqual(
            successor.input_hash,
            first_successor_input.snapshot_hash,
        )
        self.assertIs(
            self.store.documents["NPI Gate Decision Snapshot"][
                str(decided.decision.global_id)
            ],
            decision_document,
        )
        self.assertEqual(decision_document.snapshot_hash, original_decision_hash)
        self.assertEqual(self.gate.review_state, "requires_review")
        self.assertEqual(
            self.gate.current_review_cycle_global_id,
            str(successor_id),
        )
        self.assertEqual(
            self.gate.latest_decision_snapshot_global_id,
            str(decided.decision.global_id),
        )
        self.assertEqual(
            self.gate.latest_decision_snapshot_hash,
            original_decision_hash,
        )
        events = self.store.documents["NPI Gate Review Event"]
        self.assertEqual(len(events), 1)
        event = next(iter(events.values()))
        self.assertEqual(event.event_type, "invalidated")
        self.assertEqual(event.payload["schemaVersion"], 2)
        self.assertIsNone(event.action_global_id)
        self.assertIsNone(event.payload["actionGlobalId"])
        self.assertEqual(
            event.payload["detail"]["priorDecisionHash"],
            original_decision_hash,
        )

        active = decided.invalidate_for_dependency_change(
            actor_user_id=(self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR),
            reason="GATE_INPUT_CHANGED",
            occurred_at=NOW,
            current_input=first_successor_input,
            current_bindings=bindings,
            gate_current_cycle_global_id=decided.global_id,
            expected_version=decided.version,
            expected_input_hash=decided.input_hash,
        ).current_cycle
        repository._hydrate_cycle = lambda document, **_values: active
        self.assertFalse(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                occurred_at=NOW,
            )
        )
        self.assertEqual(
            len(self.store.documents["NPI Gate Review Event"]),
            1,
        )
        self.assertEqual(
            len(self.store.documents["NPI Gate Review Cycle"]),
            2,
        )

        changed_again = replace(
            first_successor_input,
            gate_version=3,
            dependencies=(
                replace(
                    first_successor_input.dependencies[0],
                    version=3,
                    snapshot_hash="d" * 64,
                ),
            ),
        )
        self.current_live_input = changed_again
        repository._hydrate_cycle = lambda document, **_values: active
        self.assertTrue(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                occurred_at=NOW,
                initiated_by_user_id="disabled-initiator@example.test",
            )
        )
        third_cycle_id = uuid5(GATE_ID, "review-cycle:3")
        third_cycle = self.store.documents["NPI Gate Review Cycle"][str(third_cycle_id)]
        self.assertEqual(successor.state, "superseded")
        self.assertEqual(third_cycle.state, "active")
        self.assertEqual(
            third_cycle.prior_decision_snapshot_global_id,
            str(decided.decision.global_id),
        )
        self.assertEqual(
            third_cycle.prior_decision_hash,
            original_decision_hash,
        )
        refreshed_events = [
            value
            for value in self.store.documents["NPI Gate Review Event"].values()
            if value.event_type == "refreshed"
        ]
        self.assertEqual(len(refreshed_events), 1)
        self.assertEqual(
            refreshed_events[0].payload["detail"]["initiatedByUserId"],
            "disabled-initiator@example.test",
        )
        self.assertEqual(
            len(self.store.documents.get("NPI Domain Work Item", {})),
            0,
        )
        self.assertEqual(
            decision_document.snapshot_hash,
            original_decision_hash,
        )
        second_successor_input = self.current_live_input
        third_active = active.invalidate_for_dependency_change(
            actor_user_id=(self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR),
            initiated_by_user_id="disabled-initiator@example.test",
            reason="GATE_INPUT_CHANGED",
            occurred_at=NOW,
            current_input=second_successor_input,
            current_bindings=bindings,
            gate_current_cycle_global_id=active.global_id,
            expected_version=active.version,
            expected_input_hash=active.input_hash,
        ).current_cycle
        repository._hydrate_cycle = lambda document, **_values: third_active
        self.assertFalse(
            repository.refresh_gate_for_dependency_change_locked(
                self.project,
                self.gate,
                occurred_at=NOW,
                initiated_by_user_id="disabled-initiator@example.test",
            )
        )

    def test_decision_readiness_trials_each_outcome_against_domain_truth(
        self,
    ) -> None:
        repository = self._repository()
        actor_member = repository._current_actor_member(self.project)

        def readiness(cycle, current_input=None):
            current_closure_action_refs = repository._current_closure_action_references(
                self.project,
                self.gate,
                cycle,
                lock=False,
            )
            return repository._decision_readiness(
                self.project,
                self.gate,
                cycle,
                current_input=current_input or cycle.input_snapshot,
                actor_member=actor_member,
                at=NOW + timedelta(hours=1),
                current_closure_action_refs=current_closure_action_refs,
            )

        def blocked(value):
            return {
                reason["outcome"]: reason["code"] for reason in value["blockedReasons"]
            }

        incomplete = self._projection_cycle()
        projected = readiness(incomplete)
        self.assertEqual(projected["allowedOutcomes"], ["reject"])
        self.assertEqual(
            blocked(projected),
            {
                "pass": "REVIEWS_INCOMPLETE",
                "conditional_pass": "REVIEWS_INCOMPLETE",
            },
        )

        complete = self._approve_projection_review(
            self._projection_cycle(self._projection_input(p1_complete=True))
        )
        projected = readiness(complete)
        self.assertEqual(projected["allowedOutcomes"], ["pass", "reject"])
        self.assertEqual(
            blocked(projected),
            {"conditional_pass": "EXCEPTION_NOT_REQUIRED"},
        )

        missing = self._approve_projection_review(self._projection_cycle())
        projected = readiness(missing)
        self.assertEqual(projected["allowedOutcomes"], ["reject"])
        self.assertEqual(
            blocked(projected),
            {
                "pass": "REQUIRED_EVIDENCE_MISSING",
                "conditional_pass": "APPROVED_EXCEPTION_REQUIRED",
            },
        )

        conditional = self._request_projection_exception(missing)
        conditional = conditional.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id=EXCEPTION_APPROVER,
            outcome=self.domain.ExceptionOutcome.APPROVED,
            opinion="Approved for one day.",
            occurred_at=NOW + timedelta(minutes=30),
            expected_version=conditional.version,
            expected_input_hash=conditional.input_hash,
            expected_exception_version=1,
        )
        projected = readiness(conditional)
        self.assertEqual(
            projected["allowedOutcomes"],
            ["conditional_pass", "reject"],
        )
        self.assertEqual(
            blocked(projected),
            {"pass": "REQUIRED_EVIDENCE_MISSING"},
        )

        unsafe = self._approve_projection_review(
            self._projection_cycle(
                self._projection_input(p1_complete=True, file_safe=False)
            )
        )
        self.assertEqual(
            blocked(readiness(unsafe)),
            {
                "pass": "FILE_EVIDENCE_UNSAFE",
                "conditional_pass": "FILE_EVIDENCE_UNSAFE",
            },
        )

        with_blocker = self._approve_projection_review(
            self._projection_cycle(
                self._projection_input(p1_complete=True, blocker=True)
            )
        )
        self.assertEqual(
            blocked(readiness(with_blocker)),
            {
                "pass": "GATE_BLOCKED",
                "conditional_pass": "GATE_BLOCKED",
            },
        )

        p0_missing = self._approve_projection_review(
            self._projection_cycle(
                self._projection_input(p0_complete=False, p1_complete=True)
            )
        )
        self.assertEqual(
            blocked(readiness(p0_missing)),
            {
                "pass": "REQUIRED_P0_EVIDENCE_MISSING",
                "conditional_pass": "REQUIRED_P0_EVIDENCE_MISSING",
            },
        )

        changed_input = replace(
            complete.input_snapshot,
            dependencies=(
                replace(
                    complete.input_snapshot.dependencies[0],
                    snapshot_hash="d" * 64,
                ),
            ),
        )
        changed_readiness = readiness(complete, changed_input)
        self.assertEqual(
            blocked(changed_readiness),
            {
                "pass": "GATE_INPUT_CHANGED",
                "conditional_pass": "GATE_INPUT_CHANGED",
                "reject": "GATE_INPUT_CHANGED",
            },
        )
        self.assertFalse(
            repository._workspace_permissions(
                self.project,
                self.gate,
                complete,
                available_policies=[],
                decision_readiness=changed_readiness,
            )["canDecide"]
        )
        self.assertTrue(
            repository._workspace_permissions(
                self.project,
                self.gate,
                complete,
                available_policies=[],
                decision_readiness=readiness(complete),
            )["canDecide"]
        )

        other_repository = self._repository(self._principal(STEP_REVIEWER))
        authority_denied = other_repository._decision_readiness(
            self.project,
            self.gate,
            complete,
            current_input=complete.input_snapshot,
            actor_member=other_repository._current_actor_member(self.project),
            at=NOW + timedelta(hours=1),
            current_closure_action_refs={},
        )
        self.assertEqual(
            set(blocked(authority_denied).values()),
            {"DECISION_AUTHORITY_REQUIRED"},
        )

        self.gate.review_state = "decided"
        closed = readiness(complete)
        self.assertEqual(
            set(blocked(closed).values()),
            {"REVIEW_CYCLE_CLOSED"},
        )
        self.assertEqual(
            self.repository_module._DECISION_BLOCKED_CODES,
            {
                "REVIEW_CYCLE_CLOSED",
                "GATE_INPUT_CHANGED",
                "DECISION_AUTHORITY_REQUIRED",
                "REVIEWS_INCOMPLETE",
                "FILE_EVIDENCE_UNSAFE",
                "GATE_BLOCKED",
                "REQUIRED_P0_EVIDENCE_MISSING",
                "REQUIRED_EVIDENCE_MISSING",
                "EXCEPTION_NOT_REQUIRED",
                "APPROVED_EXCEPTION_REQUIRED",
            },
        )
        self.gate.review_state = "in_review"

        def deny_with_uncontracted_code(**_values):
            raise self.domain.ReviewDenied(
                "UNCONTRACTED_DECISION_DENIAL",
                "This code must not cross the API boundary.",
            )

        uncontracted = types.SimpleNamespace(
            state=self.domain.CycleState.ACTIVE,
            policy=complete.policy,
            bindings=complete.bindings,
            exceptions=(),
            version=complete.version,
            input_hash=complete.input_hash,
            decide=deny_with_uncontracted_code,
        )
        with self.assertRaisesRegex(ValueError, "uncontracted denial"):
            repository._decision_readiness(
                self.project,
                self.gate,
                uncontracted,
                current_input=complete.input_snapshot,
                actor_member=actor_member,
                at=NOW + timedelta(hours=1),
                current_closure_action_refs={},
            )

    def test_exception_request_options_are_exact_domain_requestability(
        self,
    ) -> None:
        action = self._closure_action(UUID(int=106))
        self._closure_action(UUID(int=108), version=2, terminal=1)
        repository = self._repository()
        cycle = self._projection_cycle()
        closure_actions = repository._closure_action_documents(self.project, self.gate)
        self.assertEqual(closure_actions, (action,))
        actor_member = repository._current_actor_member(self.project)
        options = repository._exception_request_options(
            self.project,
            self.gate,
            cycle,
            current_input=cycle.input_snapshot,
            closure_actions=closure_actions,
            actor_member=actor_member,
            at=NOW,
        )
        self.assertEqual(
            options,
            [
                {
                    "requirementGlobalId": str(UUID(int=102)),
                    "requirementKey": "supplier_timing",
                    "kind": "p1_evidence_timing",
                    "maximumValidityDays": 14,
                    "closureActionGlobalIds": [str(UUID(int=106))],
                }
            ],
        )
        permissions = repository._workspace_permissions(
            self.project,
            self.gate,
            cycle,
            available_policies=[],
            exception_request_options=options,
        )
        self.assertTrue(permissions["canRequestException"])

        for snapshot in (
            self._projection_input(p0_complete=False, p1_complete=True),
            self._projection_input(file_safe=False),
        ):
            with self.subTest(snapshot=snapshot.snapshot_hash):
                denied_cycle = self._projection_cycle(snapshot)
                self.assertEqual(
                    repository._exception_request_options(
                        self.project,
                        self.gate,
                        denied_cycle,
                        current_input=denied_cycle.input_snapshot,
                        closure_actions=closure_actions,
                        actor_member=actor_member,
                        at=NOW,
                    ),
                    [],
                )

        conflict_bindings = tuple(
            (
                replace(
                    binding,
                    member_global_id=MEMBER_ID,
                    user_id=ACTOR,
                    display_name="Gate Decider",
                )
                if binding.slot == "exception_approver"
                else binding
            )
            for binding in cycle.bindings
        )
        conflicted = replace(cycle, bindings=conflict_bindings)
        self.assertEqual(
            repository._exception_request_options(
                self.project,
                self.gate,
                conflicted,
                current_input=conflicted.input_snapshot,
                closure_actions=closure_actions,
                actor_member=actor_member,
                at=NOW,
            ),
            [],
        )
        self.assertEqual(
            repository._exception_request_options(
                self.project,
                self.gate,
                cycle,
                current_input=cycle.input_snapshot,
                closure_actions=(),
                actor_member=actor_member,
                at=NOW,
            ),
            [],
        )
        changed_input = replace(
            cycle.input_snapshot,
            dependencies=(
                replace(
                    cycle.input_snapshot.dependencies[0],
                    snapshot_hash="d" * 64,
                ),
            ),
        )
        self.assertEqual(
            repository._exception_request_options(
                self.project,
                self.gate,
                cycle,
                current_input=changed_input,
                closure_actions=closure_actions,
                actor_member=actor_member,
                at=NOW,
            ),
            [],
        )
        self.assertFalse(
            repository._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
                exception_request_options=[],
            )["canRequestException"]
        )
        reviewer = self._repository(self._principal(STEP_REVIEWER))
        self.assertTrue(
            reviewer._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
                current_input=cycle.input_snapshot,
            )["canReview"]
        )
        self.assertFalse(
            reviewer._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
                current_input=changed_input,
            )["canReview"]
        )

    def test_exception_allowed_outcomes_are_actor_state_and_expiry_exact(
        self,
    ) -> None:
        cycle = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        approver = self._repository(self._principal(EXCEPTION_APPROVER))
        approver_member = approver._current_actor_member(self.project)
        allowed = approver._exception_allowed_outcomes(
            self.project,
            self.gate,
            cycle,
            current_input=cycle.input_snapshot,
            actor_member=approver_member,
            at=NOW + timedelta(hours=1),
            current_closure_action_refs=(
                approver._current_closure_action_references(
                    self.project,
                    self.gate,
                    cycle,
                    lock=False,
                )
            ),
        )
        self.assertEqual(
            allowed,
            {EXCEPTION_ID: ("approved", "rejected")},
        )
        self.assertTrue(
            approver._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
                exception_allowed_outcomes=allowed,
            )["canApproveException"]
        )
        response = approver._exception_response(
            cycle.exceptions[0],
            types.SimpleNamespace(
                request_snapshot={"schemaVersion": 2},
                request_snapshot_hash="a" * 64,
            ),
            allowed_outcomes=allowed[EXCEPTION_ID],
        )
        self.assertEqual(response["allowedOutcomes"], ["approved", "rejected"])
        self.assertEqual(response["requestSchemaVersion"], 2)

        action = self.store.documents["NPI Domain Work Item"][str(UUID(int=106))]
        action.optimistic_version = 2
        action.title = "Mutated after the exception request"
        self.assertEqual(
            approver._exception_allowed_outcomes(
                self.project,
                self.gate,
                cycle,
                current_input=cycle.input_snapshot,
                actor_member=approver_member,
                at=NOW + timedelta(hours=1),
                current_closure_action_refs=(
                    approver._current_closure_action_references(
                        self.project,
                        self.gate,
                        cycle,
                        lock=False,
                    )
                ),
            ),
            {EXCEPTION_ID: ("rejected",)},
        )

        expired = approver._exception_allowed_outcomes(
            self.project,
            self.gate,
            cycle,
            current_input=cycle.input_snapshot,
            actor_member=approver_member,
            at=NOW + timedelta(days=2),
            current_closure_action_refs=(
                approver._current_closure_action_references(
                    self.project,
                    self.gate,
                    cycle,
                    lock=False,
                )
            ),
        )
        self.assertEqual(expired, {EXCEPTION_ID: ("rejected",)})

        requester = self._repository()
        self.assertEqual(
            requester._exception_allowed_outcomes(
                self.project,
                self.gate,
                cycle,
                current_input=cycle.input_snapshot,
                actor_member=requester._current_actor_member(self.project),
                at=NOW + timedelta(hours=1),
                current_closure_action_refs=(
                    requester._current_closure_action_references(
                        self.project,
                        self.gate,
                        cycle,
                        lock=False,
                    )
                ),
            ),
            {EXCEPTION_ID: ()},
        )

        decided = cycle.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id=EXCEPTION_APPROVER,
            outcome=self.domain.ExceptionOutcome.REJECTED,
            opinion="Rejected.",
            occurred_at=NOW + timedelta(hours=1),
            expected_version=cycle.version,
            expected_input_hash=cycle.input_hash,
            expected_exception_version=1,
        )
        self.assertEqual(
            approver._exception_allowed_outcomes(
                self.project,
                self.gate,
                decided,
                current_input=decided.input_snapshot,
                actor_member=approver_member,
                at=NOW + timedelta(hours=2),
                current_closure_action_refs=(
                    approver._current_closure_action_references(
                        self.project,
                        self.gate,
                        decided,
                        lock=False,
                    )
                ),
            ),
            {EXCEPTION_ID: ()},
        )
        self.gate.review_state = "decided"
        self.assertEqual(
            approver._exception_allowed_outcomes(
                self.project,
                self.gate,
                cycle,
                current_input=cycle.input_snapshot,
                actor_member=approver_member,
                at=NOW + timedelta(hours=1),
                current_closure_action_refs=(
                    approver._current_closure_action_references(
                        self.project,
                        self.gate,
                        cycle,
                        lock=False,
                    )
                ),
            ),
            {EXCEPTION_ID: ()},
        )

    def test_non_start_workspace_capabilities_require_transport_role(self) -> None:
        cycle = self._projection_cycle()
        complete = self._approve_projection_review(cycle)
        pending = self._request_projection_exception(complete)
        closure_actions = self._repository()._closure_action_documents(
            self.project,
            self.gate,
        )

        requester = self._repository(self._principal(roles=frozenset()))
        requester_member = requester._current_actor_member(self.project)
        self.assertEqual(
            requester._exception_request_options(
                self.project,
                self.gate,
                cycle,
                current_input=cycle.input_snapshot,
                closure_actions=closure_actions,
                actor_member=requester_member,
                at=NOW,
            ),
            [],
        )
        readiness = requester._decision_readiness(
            self.project,
            self.gate,
            complete,
            current_input=complete.input_snapshot,
            actor_member=requester_member,
            at=NOW + timedelta(hours=1),
            current_closure_action_refs={},
        )
        self.assertEqual(readiness["allowedOutcomes"], [])
        self.assertEqual(
            {value["code"] for value in readiness["blockedReasons"]},
            {"DECISION_AUTHORITY_REQUIRED"},
        )
        permissions = requester._workspace_permissions(
            self.project,
            self.gate,
            cycle,
            available_policies=[],
            current_input=cycle.input_snapshot,
            exception_request_options=[{"kind": "p1_evidence_timing"}],
            exception_allowed_outcomes={EXCEPTION_ID: ("approved", "rejected")},
            decision_readiness={
                "allowedOutcomes": ["reject"],
                "blockedReasons": [],
            },
        )
        for key in (
            "canRequestException",
            "canApproveException",
            "canDecide",
        ):
            self.assertFalse(permissions[key])

        reviewer = self._repository(self._principal(STEP_REVIEWER, roles=frozenset()))
        self.assertFalse(
            reviewer._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
                current_input=cycle.input_snapshot,
            )["canReview"]
        )

        approver = self._repository(
            self._principal(EXCEPTION_APPROVER, roles=frozenset())
        )
        approver_member = approver._current_actor_member(self.project)
        self.assertEqual(
            approver._exception_allowed_outcomes(
                self.project,
                self.gate,
                pending,
                current_input=pending.input_snapshot,
                actor_member=approver_member,
                at=NOW + timedelta(hours=1),
                current_closure_action_refs=(
                    approver._current_closure_action_references(
                        self.project,
                        self.gate,
                        pending,
                        lock=False,
                    )
                ),
            ),
            {EXCEPTION_ID: ()},
        )

        decided = complete.decide(
            actor_user_id=ACTOR,
            outcome=self.domain.DecisionOutcome.REJECT,
            occurred_at=NOW + timedelta(hours=1),
            expected_version=complete.version,
            expected_input_hash=complete.input_hash,
            current_input=complete.input_snapshot,
        )
        self.gate.review_state = "decided"
        self.gate.review_policy_global_id = str(decided.policy.policy_global_id)
        self.gate.review_policy_version = decided.policy.policy_version
        self.gate.review_policy_snapshot_hash = decided.policy.snapshot_hash
        reopener = self._repository(
            self._principal("reopener@example.test", roles=frozenset())
        )
        self.assertFalse(
            reopener._workspace_permissions(
                self.project,
                self.gate,
                decided,
                available_policies=[
                    self.repository_module._policy_option(decided.policy)
                ],
            )["canReopen"]
        )

        self.gate.review_state = "requires_review"
        manager = self._repository(self._principal(roles=frozenset({"System Manager"})))
        self.assertTrue(
            manager._workspace_permissions(
                self.project,
                self.gate,
                decided,
                available_policies=[
                    self.repository_module._policy_option(decided.policy)
                ],
            )["canStartReview"]
        )

    def test_closure_action_reference_freezes_the_complete_stable_payload(
        self,
    ) -> None:
        action = self._closure_action()
        action.wbs_item_global_id = str(UUID(int=109))
        action.relations = [
            {
                "relationType": "depends_on",
                "targetGlobalId": str(UUID(int=110)),
            }
        ]
        action.evidence_references = [
            {
                "globalId": str(UUID(int=111)),
                "version": 2,
                "snapshotHash": "7" * 64,
            }
        ]
        captured: list[dict[str, object]] = []
        original_hash = self.repository_module._canonical_hash

        def capture_hash(value):
            captured.append(copy.deepcopy(value))
            return original_hash(value)

        self.repository_module._canonical_hash = capture_hash
        try:
            reference = self.repository_module._closure_action_reference(action)
        finally:
            self.repository_module._canonical_hash = original_hash

        expected = {
            "globalId": str(UUID(int=106)),
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "stageGlobalId": str(GATE_ID),
            "kind": "action",
            "title": "Close the exact exception",
            "detail": "Exact closure action detail.",
            "wbsItemGlobalId": str(UUID(int=109)),
            "ownerUserId": ACTOR,
            "dueAt": NOW.isoformat(),
            "severity": "high",
            "blocking": False,
            "stateKey": "open",
            "stateLabelSource": "Open",
            "stateTerminal": False,
            "workPolicyRef": {
                "globalId": str(UUID(int=107)),
                "version": 1,
                "snapshotHash": "9" * 64,
            },
            "relations": action.relations,
            "evidenceReferences": action.evidence_references,
            "sourceSystem": "NPI_ONE",
            "optimisticVersion": 1,
        }
        self.assertEqual(captured, [expected])
        self.assertEqual(
            set(captured[0]),
            {
                "globalId",
                "tenantId",
                "projectGlobalId",
                "stageGlobalId",
                "kind",
                "title",
                "detail",
                "wbsItemGlobalId",
                "ownerUserId",
                "dueAt",
                "severity",
                "blocking",
                "stateKey",
                "stateLabelSource",
                "stateTerminal",
                "workPolicyRef",
                "relations",
                "evidenceReferences",
                "sourceSystem",
                "optimisticVersion",
            },
        )
        self.assertEqual(reference.snapshot_hash, original_hash(expected))
        self.assertEqual(reference.version, 1)

        mutations = {
            "global_id": str(UUID(int=112)),
            "tenant_id": "tenant-changed",
            "project_global_id": str(OTHER_PROJECT_ID),
            "stage_global_id": str(OTHER_GATE_ID),
            "kind": "issue",
            "title": "Changed title",
            "detail": "Changed detail.",
            "wbs_item_global_id": str(UUID(int=113)),
            "owner_user_id": "changed-owner@example.test",
            "due_at": (NOW + timedelta(days=1)).isoformat(),
            "severity": "medium",
            "blocking": 1,
            "state_key": "in_progress",
            "state_label_source": "In progress",
            "state_terminal": 1,
            "work_policy_global_id": str(UUID(int=114)),
            "work_policy_version": 2,
            "work_policy_snapshot_hash": "8" * 64,
            "relations": [],
            "evidence_references": [],
            "source_system": "EXTERNAL",
            "optimistic_version": 2,
        }
        for fieldname, changed_value in mutations.items():
            with self.subTest(fieldname=fieldname):
                changed = AttrDoc(dict(action))
                changed[fieldname] = changed_value
                changed_reference = self.repository_module._closure_action_reference(
                    changed
                )
                self.assertNotEqual(
                    changed_reference.snapshot_hash,
                    reference.snapshot_hash,
                )

    def test_closure_action_reads_use_command_locks_and_stable_id_order(
        self,
    ) -> None:
        lower_id = UUID(int=106)
        higher_id = UUID(int=206)
        lower_action = self._closure_action(lower_id)
        higher_action = self._closure_action(higher_id)
        lower_ref = self.repository_module._closure_action_reference(lower_action)
        higher_ref = self.repository_module._closure_action_reference(higher_action)
        exceptions = (
            types.SimpleNamespace(
                global_id=UUID(int=303),
                closure_action_ref=higher_ref,
            ),
            types.SimpleNamespace(
                global_id=UUID(int=301),
                closure_action_ref=lower_ref,
            ),
            types.SimpleNamespace(
                global_id=UUID(int=302),
                closure_action_ref=higher_ref,
            ),
        )
        cycle = types.SimpleNamespace(exceptions=exceptions)
        repository = self._repository()

        self.store.get_doc_calls.clear()
        references = repository._current_closure_action_references(
            self.project,
            self.gate,
            cycle,
            lock=True,
        )
        action_reads = [
            call
            for call in self.store.get_doc_calls
            if call[0] == "NPI Domain Work Item"
        ]
        self.assertEqual(
            action_reads,
            [
                ("NPI Domain Work Item", str(lower_id), True),
                ("NPI Domain Work Item", str(higher_id), True),
            ],
        )
        self.assertEqual(
            references,
            {
                UUID(int=301): lower_ref,
                UUID(int=302): higher_ref,
                UUID(int=303): higher_ref,
            },
        )

        self.store.get_doc_calls.clear()
        repository._current_closure_action_references(
            self.project,
            self.gate,
            cycle,
            lock=False,
        )
        self.assertEqual(
            [
                call
                for call in self.store.get_doc_calls
                if call[0] == "NPI Domain Work Item"
            ],
            [
                ("NPI Domain Work Item", str(lower_id), False),
                ("NPI Domain Work Item", str(higher_id), False),
            ],
        )

    def test_exception_commands_lock_the_exact_closure_action(self) -> None:
        request_cycle = self._projection_cycle()
        action = self._closure_action()
        requester = self._repository()
        requester._hydrate_cycle = lambda *_args, **_kwargs: request_cycle
        requester._build_current_input = lambda *_args: request_cycle.input_snapshot
        requester._insert_idempotency = lambda *_args: object()
        requester._insert_exception = lambda *_args: None
        requester._update_cycle = lambda *_args: None
        requester._audit = lambda *_args: None
        requester._workspace_for = lambda *_args: {"acknowledged": True}
        requester._seal_idempotency = lambda *_args: None

        self.store.get_doc_calls.clear()
        requested = requester.request_exception(
            PROJECT_ID,
            GATE_ID,
            CYCLE_ID,
            idempotency_key="5" * 64,
            expected_cycle_version=request_cycle.version,
            expected_input_hash=request_cycle.input_hash,
            requirement_global_id=UUID(int=102),
            requirement_key="supplier_timing",
            kind="p1_evidence_timing",
            reason="Lock the exact action before freezing it.",
            risk="An unlocked action could drift during the request.",
            expires_at=NOW + timedelta(days=1),
            closure_action_global_id=UUID(int=106),
        )
        self.assertEqual(requested.response, {"acknowledged": True})
        self.assertIn(
            ("NPI Domain Work Item", str(action.global_id), True),
            self.store.get_doc_calls,
        )

        pending = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        approver = self._repository(self._principal(EXCEPTION_APPROVER))
        approver._hydrate_cycle = lambda *_args, **_kwargs: pending
        approver._build_current_input = lambda *_args: pending.input_snapshot
        approver._insert_idempotency = lambda *_args: object()
        approver._update_exception = lambda *_args: None
        approver._update_cycle = lambda *_args: None
        approver._insert_exception_decision_event = (
            lambda *_args, **_kwargs: types.SimpleNamespace(global_id=UUID(int=304))
        )
        approver._audit = lambda *_args: None
        approver._workspace_for = lambda *_args: {"acknowledged": True}
        approver._seal_idempotency = lambda *_args: None

        self.store.get_doc_calls.clear()
        approved = approver.decide_exception(
            PROJECT_ID,
            GATE_ID,
            CYCLE_ID,
            EXCEPTION_ID,
            idempotency_key="6" * 64,
            expected_cycle_version=pending.version,
            expected_exception_version=1,
            expected_input_hash=pending.input_hash,
            outcome="approved",
            opinion="The locked action remains exact.",
        )
        self.assertEqual(approved.response, {"acknowledged": True})
        self.assertIn(
            ("NPI Domain Work Item", str(action.global_id), True),
            self.store.get_doc_calls,
        )

    def test_gate_decision_locks_actions_and_fails_closed_on_drift_or_terminal_state(
        self,
    ) -> None:
        conditional = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        conditional = conditional.decide_exception(
            exception_global_id=EXCEPTION_ID,
            actor_user_id=EXCEPTION_APPROVER,
            outcome=self.domain.ExceptionOutcome.APPROVED,
            opinion="Approved for the exact action.",
            occurred_at=NOW + timedelta(minutes=30),
            expected_version=conditional.version,
            expected_input_hash=conditional.input_hash,
            expected_exception_version=1,
        )
        action = self.store.documents["NPI Domain Work Item"][str(UUID(int=106))]
        repository = self._repository()
        repository._hydrate_cycle = lambda *_args, **_kwargs: conditional
        repository._build_current_input = lambda *_args: conditional.input_snapshot
        repository._insert_idempotency = lambda *_args: object()
        repository._insert_decision = lambda decision: types.SimpleNamespace(
            snapshot_hash=decision.snapshot_hash
        )
        repository._update_cycle = lambda *_args: None
        repository._set_gate_decision = lambda *_args: None
        repository._audit = lambda *_args: None
        repository._workspace_for = lambda *_args: {"acknowledged": True}
        repository._seal_idempotency = lambda *_args: None

        self.store.get_doc_calls.clear()
        decided = repository.decide_gate(
            PROJECT_ID,
            GATE_ID,
            idempotency_key="7" * 64,
            expected_gate_version=3,
            expected_cycle_version=conditional.version,
            expected_input_hash=conditional.input_hash,
            outcome="conditional_pass",
        )
        self.assertEqual(decided.response, {"acknowledged": True})
        self.assertIn(
            ("NPI Domain Work Item", str(action.global_id), True),
            self.store.get_doc_calls,
        )

        original_title = action.title
        original_version = action.optimistic_version
        for label, changes in (
            ("snapshot-drift", {"title": "Changed after approval"}),
            ("terminal", {"state_terminal": 1, "state_key": "resolved"}),
        ):
            with self.subTest(label=label):
                action.title = original_title
                action.optimistic_version = original_version
                action.state_terminal = 0
                action.state_key = "open"
                for fieldname, changed_value in changes.items():
                    action[fieldname] = changed_value
                self.store.get_doc_calls.clear()
                with self.assertRaises(self.domain.ReviewDenied) as denied:
                    repository.decide_gate(
                        PROJECT_ID,
                        GATE_ID,
                        idempotency_key=("8" if label == "snapshot-drift" else "9")
                        * 64,
                        expected_gate_version=3,
                        expected_cycle_version=conditional.version,
                        expected_input_hash=conditional.input_hash,
                        outcome="conditional_pass",
                    )
                self.assertEqual(
                    denied.exception.code,
                    "APPROVED_EXCEPTION_REQUIRED",
                )
                self.assertIn(
                    (
                        "NPI Domain Work Item",
                        str(action.global_id),
                        True,
                    ),
                    self.store.get_doc_calls,
                )

    def test_workspace_reuses_one_nonlocking_closure_action_projection(
        self,
    ) -> None:
        cycle = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        repository = self._repository()
        repository._build_current_input = lambda *_args: cycle.input_snapshot
        repository._current_cycle_document = lambda *_args: self.cycle_document
        repository._hydrate_cycle = lambda *_args, **_kwargs: cycle
        repository._decision_documents = lambda *_args: ()
        repository._blocker_documents = lambda *_args: ()
        repository._available_policy_options = lambda *_args: []
        repository._closure_action_documents = lambda *_args: ()
        repository._exception_request_options = lambda *_args, **_kwargs: []
        repository._dependency_changes = lambda *_args: []
        repository._cycle_response = lambda *_args, **_kwargs: {}
        repository._workspace_permissions = lambda *_args, **_kwargs: {}
        observed: list[object] = []

        def decision_readiness(*_args, **kwargs):
            observed.append(kwargs["current_closure_action_refs"])
            return {"allowedOutcomes": [], "blockedReasons": []}

        def exception_outcomes(*_args, **kwargs):
            observed.append(kwargs["current_closure_action_refs"])
            return {}

        repository._decision_readiness = decision_readiness
        repository._exception_allowed_outcomes = exception_outcomes

        self.store.get_doc_calls.clear()
        repository._workspace_for(self.project, self.gate)
        self.assertEqual(len(observed), 2)
        self.assertIs(observed[0], observed[1])
        self.assertEqual(
            [
                call
                for call in self.store.get_doc_calls
                if call[0] == "NPI Domain Work Item"
            ],
            [
                ("NPI Domain Work Item", str(UUID(int=106)), False),
            ],
        )

    def test_mutating_review_commands_revalidate_the_live_gate_input(
        self,
    ) -> None:
        base = self._projection_cycle()
        changed_input = replace(
            base.input_snapshot,
            dependencies=(
                replace(
                    base.input_snapshot.dependencies[0],
                    snapshot_hash="d" * 64,
                ),
            ),
        )

        reviewer = self._repository(self._principal(STEP_REVIEWER))
        reviewer._hydrate_cycle = lambda *_args, **_kwargs: base
        reviewer._build_current_input = lambda *_args: changed_input
        commands = [
            lambda: reviewer.submit_review(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                idempotency_key="1" * 64,
                expected_cycle_version=base.version,
                expected_input_hash=base.input_hash,
                step_key="engineering",
                outcome="approved",
                opinion="Must not be written against stale input.",
            )
        ]

        requester = self._repository()
        requester._hydrate_cycle = lambda *_args, **_kwargs: base
        requester._build_current_input = lambda *_args: changed_input
        commands.append(
            lambda: requester.request_exception(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                idempotency_key="2" * 64,
                expected_cycle_version=base.version,
                expected_input_hash=base.input_hash,
                requirement_global_id=UUID(int=102),
                requirement_key="supplier_timing",
                kind="p1_evidence_timing",
                reason="Must not be written against stale input.",
                risk="The live Gate input has already changed.",
                expires_at=NOW + timedelta(days=1),
                closure_action_global_id=UUID(int=106),
            )
        )

        pending = self._request_projection_exception(
            self._approve_projection_review(base)
        )
        approver = self._repository(self._principal(EXCEPTION_APPROVER))
        approver._hydrate_cycle = lambda *_args, **_kwargs: pending
        approver._build_current_input = lambda *_args: changed_input
        commands.append(
            lambda: approver.decide_exception(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                EXCEPTION_ID,
                idempotency_key="3" * 64,
                expected_cycle_version=pending.version,
                expected_exception_version=1,
                expected_input_hash=pending.input_hash,
                outcome="approved",
                opinion="Must not be written against stale input.",
            )
        )

        for command in commands:
            with self.subTest(command=command), self.assertRaises(
                self.domain.ReviewDenied
            ) as denied:
                command()
            self.assertEqual(denied.exception.code, "GATE_INPUT_CHANGED")
        self.assertEqual(
            self.store.documents.get("NPI Gate Review Idempotency", {}),
            {},
        )

    def test_exception_approval_rejects_a_changed_closure_action_reference(
        self,
    ) -> None:
        pending = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        action = self.store.documents["NPI Domain Work Item"][str(UUID(int=106))]
        action.optimistic_version = 2
        action.title = "Changed after the exception request"
        approver = self._repository(self._principal(EXCEPTION_APPROVER))
        approver._hydrate_cycle = lambda *_args, **_kwargs: pending
        approver._build_current_input = lambda *_args: pending.input_snapshot

        with self.assertRaises(self.domain.ReviewDenied) as denied:
            approver.decide_exception(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                EXCEPTION_ID,
                idempotency_key="4" * 64,
                expected_cycle_version=pending.version,
                expected_exception_version=1,
                expected_input_hash=pending.input_hash,
                outcome="approved",
                opinion="The changed action must not support approval.",
            )
        self.assertEqual(
            denied.exception.code,
            "APPROVED_EXCEPTION_REQUIRED",
        )
        self.assertEqual(
            self.store.documents.get("NPI Gate Review Idempotency", {}),
            {},
        )

    def test_requires_review_is_fail_closed_until_clean_acknowledgement(
        self,
    ) -> None:
        policy, bindings = self._dependency_policy_and_bindings()
        input_snapshot = self._gate_input(blockers=())
        cycle = self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=input_snapshot,
        )
        self.gate.review_state = "requires_review"
        self.gate.review_policy_global_id = str(policy.policy_global_id)
        self.gate.review_policy_version = policy.policy_version
        self.gate.review_policy_snapshot_hash = policy.snapshot_hash
        self.cycle_document.started_at = NOW.isoformat()
        self.cycle_document.started_by = (
            self.repository_module.GATE_REVIEW_DEPENDENCY_SYSTEM_ACTOR
        )
        repository = self._repository(
            self._principal(roles=frozenset({"System Manager"}))
        )
        option = self.repository_module._policy_option(policy)
        permissions = repository._workspace_permissions(
            self.project,
            self.gate,
            cycle,
            available_policies=[option],
        )
        self.assertTrue(permissions["canStartReview"])
        for key in (
            "canReview",
            "canRequestException",
            "canApproveException",
            "canDecide",
        ):
            self.assertFalse(permissions[key])
        cycle_response = repository._cycle_response(
            self.cycle_document,
            cycle,
            review_open=False,
        )
        self.assertTrue(cycle_response["selectedSteps"])
        self.assertTrue(
            all(step["state"] == "waiting" for step in cycle_response["selectedSteps"])
        )

        commands = (
            lambda: repository.submit_review(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                idempotency_key="requires-review-submit",
                expected_cycle_version=1,
                expected_input_hash=input_snapshot.snapshot_hash,
                step_key="engineering",
                outcome="approved",
                opinion="Reviewed.",
            ),
            lambda: repository.request_exception(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                idempotency_key="requires-review-exception-request",
                expected_cycle_version=1,
                expected_input_hash=input_snapshot.snapshot_hash,
                requirement_global_id=UUID(int=801),
                requirement_key="required-input",
                kind="waiver",
                reason="Controlled reason.",
                risk="Controlled risk.",
                expires_at=NOW + timedelta(days=1),
                closure_action_global_id=UUID(int=802),
            ),
            lambda: repository.decide_exception(
                PROJECT_ID,
                GATE_ID,
                CYCLE_ID,
                EXCEPTION_ID,
                idempotency_key="requires-review-exception-decision",
                expected_cycle_version=1,
                expected_exception_version=1,
                expected_input_hash=input_snapshot.snapshot_hash,
                outcome="approved",
                opinion="Approved.",
            ),
            lambda: repository.decide_gate(
                PROJECT_ID,
                GATE_ID,
                idempotency_key="requires-review-gate-decision",
                expected_gate_version=3,
                expected_cycle_version=1,
                expected_input_hash=input_snapshot.snapshot_hash,
                outcome="pass",
            ),
        )
        for command in commands:
            with self.subTest(command=command), self.assertRaises(
                self.errors.VersionConflict
            ):
                command()
        self.assertEqual(
            self.store.documents.get("NPI Gate Review Idempotency", {}),
            {},
        )

        repository._idempotency_replay = lambda *_args, **_kwargs: {
            "gate": {"reviewState": "in_review"}
        }
        replay = repository.submit_review(
            PROJECT_ID,
            GATE_ID,
            CYCLE_ID,
            idempotency_key="already-completed",
            expected_cycle_version=1,
            expected_input_hash=input_snapshot.snapshot_hash,
            step_key="engineering",
            outcome="approved",
            opinion="Reviewed.",
        )
        self.assertTrue(replay.replayed)

    def test_requires_review_start_rejects_polluted_successor_before_receipt(
        self,
    ) -> None:
        policy, bindings = self._dependency_policy_and_bindings()
        input_snapshot = self._gate_input(blockers=())
        clean = self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=input_snapshot,
        )
        self.gate.review_state = "requires_review"
        self.gate.review_policy_global_id = str(policy.policy_global_id)
        self.gate.review_policy_version = policy.policy_version
        self.gate.review_policy_snapshot_hash = policy.snapshot_hash
        repository = self._repository(
            self._principal(roles=frozenset({"System Manager"}))
        )
        self.repository_module.load_available_gate_review_policy_version = (
            lambda *_args: policy
        )
        repository._resolve_bindings = lambda *_args, **_kwargs: bindings
        repository._build_current_input = lambda *_args: input_snapshot
        repository._workspace_for = lambda *_args: {"acknowledged": True}

        pollution = (
            types.SimpleNamespace(
                **{
                    field: getattr(clean, field)
                    for field in (
                        "state",
                        "reviews",
                        "exceptions",
                        "decision",
                        "policy",
                        "bindings",
                        "input_snapshot",
                    )
                },
                version=2,
            ),
            types.SimpleNamespace(
                state=clean.state,
                version=1,
                reviews=(object(),),
                exceptions=(),
                decision=None,
                policy=policy,
                bindings=bindings,
                input_snapshot=input_snapshot,
            ),
            types.SimpleNamespace(
                state=clean.state,
                version=1,
                reviews=(),
                exceptions=(object(),),
                decision=None,
                policy=policy,
                bindings=bindings,
                input_snapshot=input_snapshot,
            ),
            types.SimpleNamespace(
                state=clean.state,
                version=1,
                reviews=(),
                exceptions=(),
                decision=object(),
                policy=policy,
                bindings=bindings,
                input_snapshot=input_snapshot,
            ),
        )
        for index, polluted in enumerate(pollution):
            with self.subTest(index=index):
                repository._hydrate_cycle = (
                    lambda _document, polluted=polluted, **_values: polluted
                )
                with self.assertRaises(self.errors.VersionConflict):
                    repository.start_review(
                        PROJECT_ID,
                        GATE_ID,
                        idempotency_key=f"polluted-successor-{index}",
                        expected_gate_version=3,
                        policy_global_id=policy.policy_global_id,
                        policy_version=policy.policy_version,
                        policy_snapshot_hash=policy.snapshot_hash,
                        bindings=(),
                    )
                self.assertEqual(self.gate.review_state, "requires_review")
                self.assertEqual(
                    self.store.documents.get("NPI Gate Review Idempotency", {}),
                    {},
                )

        repository._hydrate_cycle = lambda _document, **_values: clean
        acknowledged = repository.start_review(
            PROJECT_ID,
            GATE_ID,
            idempotency_key="clean-successor",
            expected_gate_version=3,
            policy_global_id=policy.policy_global_id,
            policy_version=policy.policy_version,
            policy_snapshot_hash=policy.snapshot_hash,
            bindings=(),
        )
        self.assertEqual(acknowledged.response, {"acknowledged": True})
        self.assertEqual(self.gate.review_state, "in_review")
        self.assertEqual(
            len(self.store.documents["NPI Gate Review Idempotency"]),
            1,
        )

    def test_frozen_policy_remains_readable_when_no_policy_is_available(
        self,
    ) -> None:
        policy, bindings = self._dependency_policy_and_bindings()
        input_snapshot = self._gate_input(blockers=())
        cycle = self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=input_snapshot,
        )
        self.cycle_document.started_at = NOW.isoformat()
        self.cycle_document.started_by = ACTOR
        repository = self._repository()
        response = repository._cycle_response(
            self.cycle_document,
            cycle,
            review_open=True,
        )
        self.assertEqual(
            response["policyDefinition"]["policyRef"], response["policyRef"]
        )
        self.assertEqual(
            response["policyDefinition"],
            self.repository_module._policy_option(policy),
        )

        self.gate.review_state = "requires_review"
        self.gate.review_policy_global_id = str(policy.policy_global_id)
        self.gate.review_policy_version = policy.policy_version
        self.gate.review_policy_snapshot_hash = policy.snapshot_hash
        manager = self._repository(self._principal(roles=frozenset({"System Manager"})))
        self.assertFalse(
            manager._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[],
            )["canStartReview"]
        )
        wrong_option = copy.deepcopy(self.repository_module._policy_option(policy))
        wrong_option["policyRef"]["snapshotHash"] = "f" * 64
        self.assertFalse(
            manager._workspace_permissions(
                self.project,
                self.gate,
                cycle,
                available_policies=[wrong_option],
            )["canStartReview"]
        )

        self.gate.review_state = "decided"
        decided_cycle = types.SimpleNamespace(
            state=self.domain.CycleState.DECIDED,
            reviews=(),
            bindings=bindings,
            policy=policy,
            exceptions=(),
            selected_steps=cycle.selected_steps,
        )
        self.assertFalse(
            repository._workspace_permissions(
                self.project,
                self.gate,
                decided_cycle,
                available_policies=[],
            )["canReopen"]
        )
        self._add_member("reopener@example.test", UUID(int=52))
        reopener = self._repository(self._principal("reopener@example.test"))
        self.assertFalse(
            reopener._workspace_permissions(
                self.project,
                self.gate,
                decided_cycle,
                available_policies=[wrong_option],
            )["canReopen"]
        )
        self.assertTrue(
            reopener._workspace_permissions(
                self.project,
                self.gate,
                decided_cycle,
                available_policies=[self.repository_module._policy_option(policy)],
            )["canReopen"]
        )

    def test_decision_response_exposes_exact_lineage_and_rejects_summary_drift(
        self,
    ) -> None:
        policy, bindings = self._dependency_policy_and_bindings()
        input_snapshot = self._gate_input(blockers=())
        cycle = self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=input_snapshot,
        )
        reviewed = cycle.submit_review(
            step_key="engineering",
            actor_user_id=ACTOR,
            outcome=self.domain.ReviewOutcome.APPROVED,
            opinion="The frozen Gate input is acceptable.",
            occurred_at=NOW,
            expected_version=cycle.version,
            expected_input_hash=cycle.input_hash,
        )
        decided = reviewed.decide(
            actor_user_id="decider@example.test",
            outcome=self.domain.DecisionOutcome.PASS,
            occurred_at=NOW + timedelta(hours=1),
            expected_version=reviewed.version,
            expected_input_hash=reviewed.input_hash,
            current_input=input_snapshot,
        )
        decision = decided.decision
        assert decision is not None
        repository = self._repository()
        repository._hydrate_cycle = lambda *_args, **_kwargs: decided
        snapshot = {
            "schemaVersion": 1,
            "globalId": str(decision.global_id),
            "tenantId": decision.tenant_id,
            "projectGlobalId": str(decision.project_global_id),
            "gateGlobalId": str(decision.gate_global_id),
            "cycleGlobalId": str(decision.cycle_global_id),
            "cycleNumber": decision.cycle_number,
            "outcome": decision.outcome.value,
            "actorUserId": decision.actor_user_id,
            "occurredAt": self.repository_module._datetime_canonical(
                decision.occurred_at
            ),
            "policyRef": self.repository_module._policy_ref(policy),
            "inputSnapshot": decision.input_snapshot.canonical_dict(),
            "inputHash": decision.input_hash,
            "reviewHashes": list(decision.review_hashes),
            "exceptionHashes": list(decision.exception_hashes),
            "cycleVersion": decision.cycle_version,
            "requestId": repository.request_id,
            "traceId": repository.trace_id,
        }
        document = AttrDoc(
            global_id=str(decision.global_id),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            cycle_global_id=str(CYCLE_ID),
            cycle_number=decision.cycle_number,
            outcome=decision.outcome.value,
            actor_user_id=decision.actor_user_id,
            occurred_at=decision.occurred_at,
            policy_global_id=str(decision.policy_global_id),
            policy_version=decision.policy_version,
            policy_snapshot_hash=decision.policy_hash,
            decision_snapshot=snapshot,
            snapshot_hash=self._canonical_hash(snapshot),
            input_snapshot=decision.input_snapshot.canonical_dict(),
            input_hash=decision.input_hash,
            review_hashes=list(decision.review_hashes),
            exception_hashes=list(decision.exception_hashes),
            cycle_version=decision.cycle_version,
            request_id=repository.request_id,
            trace_id=repository.trace_id,
        )

        response = repository._decision_response(
            self.project,
            self.gate,
            document,
            current=True,
        )
        self.assertEqual(
            response["detail"],
            {
                "lineageHash": decision.snapshot_hash,
                "cycleNumber": decision.cycle_number,
                "policyRef": self.repository_module._policy_ref(policy),
                "inputSnapshot": decision.input_snapshot.canonical_dict(),
                "reviewHashes": list(decision.review_hashes),
                "exceptionHashes": list(decision.exception_hashes),
                "cycleVersion": decision.cycle_version,
            },
        )
        self.assertNotEqual(
            response["snapshotHash"],
            response["detail"]["lineageHash"],
        )

        document.review_hashes = ["f" * 64]
        with self.assertRaisesRegex(ValueError, "summary drifted"):
            repository._decision_response(
                self.project,
                self.gate,
                document,
                current=True,
            )
        document.review_hashes = list(decision.review_hashes)

        tampered_snapshot = copy.deepcopy(snapshot)
        tampered_snapshot["outcome"] = "reject"
        document.decision_snapshot = tampered_snapshot
        document.snapshot_hash = self._canonical_hash(tampered_snapshot)
        with self.assertRaisesRegex(ValueError, "summary drifted"):
            repository._decision_response(
                self.project,
                self.gate,
                document,
                current=True,
            )

    def test_workspace_computes_policy_options_once_and_returns_state_labels(
        self,
    ) -> None:
        policy, _bindings = self._dependency_policy_and_bindings()
        option = self.repository_module._policy_option(policy)
        self.gate.review_state = "not_started"
        self.gate.current_review_cycle_global_id = None
        self.gate.review_policy_global_id = None
        self.gate.review_policy_version = None
        self.gate.review_policy_snapshot_hash = None
        work_item = self.store.add(
            "NPI Domain Work Item",
            UUID(int=811),
            global_id=str(UUID(int=811)),
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            stage_global_id=str(GATE_ID),
            kind="action",
            title="Close the Gate issue",
            state_key="open",
            state_label_source="Open",
            optimistic_version=1,
            blocking=1,
            state_terminal=0,
            due_at=NOW.isoformat(),
            owner_user_id=ACTOR,
        )
        repository = self._repository(
            self._principal(roles=frozenset({"System Manager"}))
        )
        input_snapshot = self._gate_input(blockers=())
        repository._build_current_input = lambda *_args: input_snapshot
        calls = 0

        def available(_gate):
            nonlocal calls
            calls += 1
            return [option]

        repository._available_policy_options = available
        workspace = repository._workspace_for(self.project, self.gate)
        self.assertEqual(calls, 1)
        self.assertEqual(workspace["availablePolicies"], [option])
        self.assertEqual(
            workspace["eligibleClosureActions"][0]["stateLabelSource"],
            work_item.state_label_source,
        )
        self.assertEqual(
            workspace["blockers"][0]["stateLabelSource"],
            work_item.state_label_source,
        )
        self.assertEqual(
            workspace["decisionReadiness"],
            {
                "allowedOutcomes": [],
                "blockedReasons": [
                    {
                        "outcome": outcome,
                        "code": "REVIEW_CYCLE_CLOSED",
                    }
                    for outcome in ("pass", "conditional_pass", "reject")
                ],
            },
        )
        self.assertEqual(workspace["exceptionRequestOptions"], [])
        self.assertTrue(workspace["permissions"]["canStartReview"])
        self.assertFalse(workspace["permissions"]["canRequestException"])
        self.assertFalse(workspace["permissions"]["canApproveException"])

    def test_all_inserted_review_event_payload_timestamps_are_canonical(
        self,
    ) -> None:
        repository = self._repository(dependency_system=True)
        self.exception_document.decision_snapshot_hash = "d" * 64
        exception = types.SimpleNamespace(
            global_id=EXCEPTION_ID,
            version=2,
            cycle_global_id=CYCLE_ID,
            tenant_id=TENANT_ID,
            project_global_id=PROJECT_ID,
            gate_global_id=GATE_ID,
            state=self.domain.ExceptionState.APPROVED,
        )
        exception_event = repository._insert_exception_decision_event(
            types.SimpleNamespace(),
            exception,
            now=NOW,
        )
        self.assertEqual(exception_event.payload["occurredAt"], NOW.isoformat())
        self.assertFalse(exception_event.payload["occurredAt"].endswith("Z"))

        policy, bindings = self._dependency_policy_and_bindings()
        original_input = self._gate_input(blockers=())
        changed_input = replace(
            original_input,
            gate_version=2,
            dependencies=(
                replace(
                    original_input.dependencies[0],
                    version=2,
                    snapshot_hash="c" * 64,
                ),
            ),
        )
        active = self.domain.ReviewCycle.start(
            gate_global_id=GATE_ID,
            project_global_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            cycle_number=1,
            trigger=self.domain.CycleTrigger.MANUAL_START,
            policy=policy,
            bindings=bindings,
            input_snapshot=original_input,
        )
        transition = active.invalidate_for_dependency_change(
            actor_user_id=repository.actor,
            reason="GATE_INPUT_CHANGED",
            occurred_at=NOW,
            current_input=changed_input,
            current_bindings=bindings,
            gate_current_cycle_global_id=active.global_id,
            expected_version=active.version,
            expected_input_hash=active.input_hash,
        )
        transition_event = repository._insert_transition_event(
            transition,
            tenant_id=TENANT_ID,
            reason="GATE_INPUT_CHANGED",
            occurred_at=NOW,
            initiated_by_user_id=ACTOR,
        )
        self.assertEqual(transition_event.payload["occurredAt"], NOW.isoformat())
        self.assertIsNone(transition_event.action_global_id)
        self.assertIsNone(transition_event.payload["actionGlobalId"])
        public = repository._dependency_change_response(transition_event)
        self.assertEqual(public["occurredAt"], "2026-07-24T09:30:00Z")

    def test_dependency_changes_are_strict_bounded_lineage_projections(
        self,
    ) -> None:
        cycles = tuple(
            uuid5(GATE_ID, f"review-cycle:{number}") for number in range(1, 5)
        )
        decision_id = uuid5(cycles[1], "decision-snapshot")
        self._add_dependency_event(
            prior_cycle_id=cycles[0],
            successor_cycle_id=cycles[1],
            event_type="refreshed",
            occurred_at=NOW,
            action_id=UUID(int=821),
            old_input_hash="1" * 64,
            new_input_hash="2" * 64,
            prior_decision_id=None,
            prior_decision_hash=None,
        )
        self._add_dependency_event(
            prior_cycle_id=cycles[1],
            successor_cycle_id=cycles[2],
            event_type="invalidated",
            occurred_at=NOW + timedelta(minutes=1),
            action_id=UUID(int=822),
            old_input_hash="2" * 64,
            new_input_hash="3" * 64,
            prior_decision_id=decision_id,
            prior_decision_hash="a" * 64,
        )
        newest = self._add_dependency_event(
            prior_cycle_id=cycles[2],
            successor_cycle_id=cycles[3],
            event_type="refreshed",
            occurred_at=NOW + timedelta(minutes=2),
            action_id=UUID(int=823),
            old_input_hash="3" * 64,
            new_input_hash="4" * 64,
            prior_decision_id=decision_id,
            prior_decision_hash="a" * 64,
            initiated_by_user_id=None,
        )
        changes = self._repository()._dependency_changes(self.project, self.gate)
        self.assertEqual(len(changes), 3)
        self.assertEqual(
            [value["eventType"] for value in changes],
            ["refreshed", "invalidated", "refreshed"],
        )
        self.assertEqual(
            [value["occurredAt"] for value in changes],
            [
                "2026-07-24T09:32:00Z",
                "2026-07-24T09:31:00Z",
                "2026-07-24T09:30:00Z",
            ],
        )
        self.assertEqual(changes[0]["priorDecisionGlobalId"], str(decision_id))
        self.assertEqual(changes[0]["priorDecisionLineageHash"], "a" * 64)
        self.assertIsNone(changes[0]["initiatedByUserId"])
        self.assertIsNone(changes[-1]["priorDecisionGlobalId"])
        self.assertIsNone(changes[-1]["priorDecisionLineageHash"])
        self.assertEqual(
            set(changes[0]),
            {
                "eventGlobalId",
                "eventType",
                "priorCycleGlobalId",
                "successorCycleGlobalId",
                "impactActionGlobalId",
                "oldInputHash",
                "newInputHash",
                "priorDecisionGlobalId",
                "priorDecisionLineageHash",
                "actorUserId",
                "initiatedByUserId",
                "occurredAt",
                "reason",
            },
        )
        newest.payload["detail"]["rawDocument"] = {"unsafe": True}
        newest.payload_hash = self._canonical_hash(newest.payload)
        with self.assertRaisesRegex(ValueError, "detail is not closed"):
            self._repository()._dependency_changes(self.project, self.gate)

    def test_dependency_reader_preserves_closed_legacy_v1_events(self) -> None:
        prior_cycle_id = uuid5(GATE_ID, "review-cycle:40")
        successor_cycle_id = uuid5(GATE_ID, "review-cycle:41")
        decision_id = uuid5(prior_cycle_id, "decision-snapshot")
        legacy = self._add_dependency_event(
            prior_cycle_id=prior_cycle_id,
            successor_cycle_id=successor_cycle_id,
            event_type="invalidated",
            occurred_at=NOW,
            action_id=UUID(int=824),
            old_input_hash="4" * 64,
            new_input_hash="5" * 64,
            prior_decision_id=decision_id,
            prior_decision_hash="b" * 64,
            schema_version=1,
            legacy_detail=True,
        )

        public = self.repository_module.FrappeGateReviewRepository._dependency_change_response(
            legacy
        )
        self.assertEqual(public["reason"], "GATE_INPUT_CHANGED")
        self.assertIsNone(public["initiatedByUserId"])
        self.assertEqual(public["impactActionGlobalId"], str(UUID(int=824)))

        transitional = self._add_dependency_event(
            prior_cycle_id=successor_cycle_id,
            successor_cycle_id=uuid5(GATE_ID, "review-cycle:42"),
            event_type="refreshed",
            occurred_at=NOW + timedelta(minutes=1),
            action_id=None,
            old_input_hash="5" * 64,
            new_input_hash="6" * 64,
            prior_decision_id=decision_id,
            prior_decision_hash="b" * 64,
            schema_version=1,
            reason="GATE_SOURCE_CHANGED",
        )
        transitional_public = self.repository_module.FrappeGateReviewRepository._dependency_change_response(
            transitional
        )
        self.assertEqual(
            transitional_public["reason"],
            "GATE_SOURCE_CHANGED",
        )

    def test_exception_reader_preserves_legacy_v1_without_inventing_revision(
        self,
    ) -> None:
        exception_key = f"{CYCLE_ID}:{EXCEPTION_ID}"
        expires_at = NOW + timedelta(days=1)
        document = AttrDoc(
            global_id=str(EXCEPTION_ID),
            exception_key=exception_key,
            tenant_id=TENANT_ID,
            project_global_id=str(PROJECT_ID),
            gate_global_id=str(GATE_ID),
            cycle_global_id=str(CYCLE_ID),
            policy_global_id=str(POLICY_ID),
            policy_version=1,
            policy_snapshot_hash="a" * 64,
            requirement_global_id=str(UUID(int=102)),
            requirement_key="supplier_timing",
            exception_kind="p1_evidence_timing",
            reason="Legacy controlled reason.",
            risk="Legacy controlled risk.",
            requester_member_global_id=str(MEMBER_ID),
            requester_user_id=ACTOR,
            requested_at=NOW,
            expires_at=expires_at,
            closure_action_global_id=str(UUID(int=106)),
            closure_action_version=None,
            closure_action_snapshot_hash=None,
            approver_authority_slot="exception_approver",
            approver_member_global_id=str(UUID(int=53)),
            approver_user_id=EXCEPTION_APPROVER,
        )
        legacy_snapshot = {
            "schemaVersion": 1,
            "globalId": str(EXCEPTION_ID),
            "exceptionKey": exception_key,
            "tenantId": TENANT_ID,
            "projectGlobalId": str(PROJECT_ID),
            "gateGlobalId": str(GATE_ID),
            "cycleGlobalId": str(CYCLE_ID),
            "policyRef": {
                "globalId": str(POLICY_ID),
                "version": 1,
                "snapshotHash": "a" * 64,
            },
            "requirementRef": {
                "globalId": str(UUID(int=102)),
                "key": "supplier_timing",
            },
            "kind": "p1_evidence_timing",
            "reason": "Legacy controlled reason.",
            "risk": "Legacy controlled risk.",
            "requester": {
                "memberGlobalId": str(MEMBER_ID),
                "userId": ACTOR,
            },
            "requestedAt": NOW.isoformat(),
            "expiresAt": expires_at.isoformat(),
            "closureActionGlobalId": str(UUID(int=106)),
            "approver": {
                "authoritySlot": "exception_approver",
                "memberGlobalId": str(UUID(int=53)),
                "userId": EXCEPTION_APPROVER,
            },
        }

        reference = self.repository_module._exception_closure_action_reference(
            document,
            legacy_snapshot,
        )
        self.assertEqual(reference.global_id, UUID(int=106))
        self.assertIsNone(reference.version)
        self.assertIsNone(reference.snapshot_hash)
        self.assertFalse(reference.is_exact)

        document.closure_action_version = 9
        with self.assertRaises(ValueError):
            self.repository_module._exception_closure_action_reference(
                document,
                legacy_snapshot,
            )

        pending = self._request_projection_exception(
            self._approve_projection_review(self._projection_cycle())
        )
        exact_exception = pending.exceptions[0]
        legacy_exception = replace(
            exact_exception,
            closure_action_ref=self.domain.ClosureActionReference(
                exact_exception.closure_action_ref.global_id,
                None,
                None,
            ),
        )
        public_document = types.SimpleNamespace(
            request_snapshot={"schemaVersion": 1},
            request_snapshot_hash="c" * 64,
        )
        legacy_public = (
            self.repository_module.FrappeGateReviewRepository._exception_response(
                legacy_exception,
                public_document,
                allowed_outcomes=(),
            )
        )
        self.assertEqual(legacy_public["requestSchemaVersion"], 1)
        self.assertIsNone(legacy_public["closureActionRef"]["version"])
        self.assertEqual(legacy_public["allowedOutcomes"], [])

        collision_public = (
            self.repository_module.FrappeGateReviewRepository._exception_response(
                exact_exception,
                public_document,
                allowed_outcomes=("approved", "rejected"),
            )
        )
        self.assertEqual(collision_public["requestSchemaVersion"], 1)
        self.assertEqual(collision_public["closureActionRef"]["version"], 1)

        public_document.request_snapshot = {"schemaVersion": 2}
        with self.assertRaisesRegex(ValueError, "profile"):
            self.repository_module.FrappeGateReviewRepository._exception_response(
                legacy_exception,
                public_document,
                allowed_outcomes=(),
            )


if __name__ == "__main__":
    unittest.main()
