from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = UUID("2e96f421-5872-4c96-a0dd-718d5c970a21")
MASTER_ID = UUID("0878087f-6192-4e40-862d-05e0a5927638")
MEMBER_ID = UUID("29e933a3-3954-4a96-9400-2be1987ae370")
ROUND_ID = UUID("89953948-4178-46dc-b7ca-8b94f2ac4e36")
REQUEST_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
SHA256_A = "a" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class FakeDocument(AttrDict):
    def __init__(self, owner: "Phase7TrialRepositoryTest", values: dict[str, Any]):
        super().__init__(values)
        self._owner = owner

    def insert(self):
        name = self.get("name") or self.get("event_id") or self.get("global_id")
        if name is None:
            raise AssertionError(self)
        self.name = str(name)
        bucket = self._owner.documents.setdefault(self.doctype, {})
        if self.name in bucket:
            raise self._owner.frappe.DuplicateEntryError()
        for fieldname in ("plan_snapshot", "round_snapshot", "link_snapshot"):
            if isinstance(self.get(fieldname), dict):
                self[fieldname] = json.dumps(
                    self[fieldname],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
        bucket[self.name] = self
        return self

    def save(self):
        self._owner.documents.setdefault(self.doctype, {})[self.name] = self
        return self


class FakeDatabase:
    def __init__(self, owner: "Phase7TrialRepositoryTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def count(self, doctype: str, filters: dict[str, Any]) -> int:
        return len(self.owner.matching(doctype, filters))

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


class FakeWorkRepository:
    owner: "Phase7TrialRepositoryTest"

    def __init__(self, **_values: Any) -> None:
        pass

    def create_domain_work_items_in_parent_command(self, project, *, items):
        created = []
        for item in items:
            document = FakeDocument(
                self.owner,
                {
                    "doctype": "NPI Domain Work Item",
                    "global_id": str(uuid4()),
                    "tenant_id": project.tenant_id,
                    "project_global_id": project.global_id,
                    "title": item["title"],
                },
            ).insert()
            created.append(
                {
                    "actionKey": item["actionKey"],
                    "document": document,
                    "response": {"globalId": document.global_id},
                }
            )
        project.optimistic_version = int(project.optimistic_version) + 1
        return created


class Phase7TrialRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.project_work.frappe_repository",
        "npi_core.trial.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.documents: dict[str, dict[str, FakeDocument]] = {}
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.flags = types.SimpleNamespace()
        self.frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        self.frappe.db = FakeDatabase(self)
        self.frappe.get_doc = self.get_doc
        self.frappe.get_all = self.get_all
        sys.modules["frappe"] = self.frappe

        self.module = importlib.import_module("npi_core.trial.frappe_repository")
        security = importlib.import_module("npi_core.foundation.security")
        self.principal = security.Principal(
            user_id="admin@example.invalid",
            roles=frozenset({"NPI API User", "System Manager"}),
            is_external=False,
            tenant_id="TENANT-A",
        )
        self.repository = self.module.FrappeTrialRepository(
            principal=self.principal,
            request_id=REQUEST_ID,
            trace_id="trace-trial-repository-001",
        )
        self.project = self.add(
            "NPI Engineering Project",
            {
                "global_id": str(PROJECT_ID),
                "tenant_id": "TENANT-A",
                "owner_user_id": "owner@example.invalid",
                "lifecycle_state": "active",
                "optimistic_version": 3,
            },
        )
        self.add(
            "NPI Tooling Master",
            {"global_id": str(MASTER_ID), "tenant_id": "TENANT-A"},
        )
        self.add(
            "NPI Tooling Applicability",
            {
                "global_id": str(uuid4()),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "tooling_master_global_id": str(MASTER_ID),
            },
        )
        self.add(
            "NPI Project Member",
            {
                "global_id": str(MEMBER_ID),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "user_id": "member@example.invalid",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "optimistic_version": 2,
            },
        )
        self.add(
            "User",
            {
                "name": "member@example.invalid",
                "enabled": 1,
                "user_type": "System User",
            },
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def add(self, doctype: str, values: dict[str, Any]) -> FakeDocument:
        document = FakeDocument(self, {"doctype": doctype, **values})
        return document.insert()

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
            if all(self._matches(document.get(field), expected) for field, expected in filters.items())
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
                documents.sort(key=lambda item: item.get(field), reverse=reverse)
        if limit_page_length is not None:
            documents = documents[:limit_page_length]
        if pluck:
            return [document.get(pluck) for document in documents]
        if fields:
            return [AttrDict({field: document.get(field) for field in fields}) for document in documents]
        return documents

    @staticmethod
    def plan_values() -> dict[str, Any]:
        domain = importlib.import_module("npi_core.trial.domain")
        return {
            "idempotency_key_hash": "1" * 64,
            "tooling_master_global_id": MASTER_ID,
            "purpose": domain.TrialPurpose.FIRST_TRIAL,
            "objective": "Confirm the first immutable Trial Plan.",
            "planned_start_at": datetime(2026, 8, 11, 8, tzinfo=UTC),
            "planned_end_at": datetime(2026, 8, 11, 12, tzinfo=UTC),
            "resources": (
                {
                    "kind": "machine",
                    "sourceSystem": "NPI_ONE",
                    "sourceObjectId": "machine-proposal-1",
                    "label": "Machine proposal",
                },
                {
                    "kind": "material",
                    "sourceSystem": "ERPNEXT",
                    "sourceObjectId": "material-proposal-1",
                    "label": "Material proposal",
                    "quantity": 25,
                    "unit": "kg",
                },
            ),
            "responsible_member_global_ids": (MEMBER_ID,),
            "sample_quantity": 80,
            "measurement_plan": {"description": "Inspect dimensions."},
            "reason": "Create the first Trial Plan revision.",
        }

    def test_create_plan_seals_exact_actor_bound_replay(self) -> None:
        outcome = self.repository.create_plan(PROJECT_ID, **self.plan_values())
        self.assertIsNotNone(outcome)
        self.assertFalse(outcome.replayed)
        self.assertEqual(len(self.documents["NPI Trial Plan Revision"]), 1)
        receipt = next(iter(self.documents["NPI Trial Command Idempotency"].values()))
        self.assertEqual(receipt.sealed, 1)
        self.assertEqual(receipt.operation, "trial_plan.create")
        self.assertEqual(receipt.response_payload, outcome.response)
        self.assertEqual(outcome.response["latestRevision"]["planVersion"], 1)

        replay = self.repository.create_plan(PROJECT_ID, **self.plan_values())
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.response, outcome.response)
        self.assertEqual(len(self.documents["NPI Trial Plan Revision"]), 1)

    def test_same_key_different_payload_conflicts(self) -> None:
        values = self.plan_values()
        self.repository.create_plan(PROJECT_ID, **values)
        values["objective"] = "A different immutable objective."
        with self.assertRaises(self.module.TrialIdempotencyConflict):
            self.repository.create_plan(PROJECT_ID, **values)

    def test_revision_requires_exact_current_predecessor(self) -> None:
        created = self.repository.create_plan(PROJECT_ID, **self.plan_values())
        latest = created.response["latestRevision"]
        values = self.plan_values()
        values.pop("tooling_master_global_id")
        values["idempotency_key_hash"] = "2" * 64
        revised = self.repository.create_plan_revision(
            PROJECT_ID,
            UUID(created.response["planGlobalId"]),
            expected_revision_global_id=UUID(latest["globalId"]),
            expected_revision_snapshot_hash=latest["snapshotHash"],
            expected_plan_version=1,
            **values,
        )
        self.assertEqual(revised.response["latestRevision"]["planVersion"], 2)
        self.assertEqual(len(revised.response["revisions"]), 2)
        with self.assertRaises(self.module.TrialVersionConflict):
            self.repository.create_plan_revision(
                PROJECT_ID,
                UUID(created.response["planGlobalId"]),
                expected_revision_global_id=UUID(latest["globalId"]),
                expected_revision_snapshot_hash=latest["snapshotHash"],
                expected_plan_version=1,
                **{**values, "idempotency_key_hash": "3" * 64},
            )

    def test_round_identity_is_distinct_and_label_unique(self) -> None:
        created = self.repository.create_plan(PROJECT_ID, **self.plan_values())
        plan_id = UUID(created.response["planGlobalId"])
        revision = created.response["latestRevision"]
        outcome = self.repository.create_round(
            PROJECT_ID,
            plan_id,
            idempotency_key_hash="4" * 64,
            expected_plan_revision_global_id=UUID(revision["globalId"]),
            expected_plan_revision_snapshot_hash=revision["snapshotHash"],
            display_label=None,
            reason="Create the first planned Trial Round.",
        )
        self.assertEqual(outcome.response["rounds"][0]["roundSequence"], 0)
        self.assertEqual(outcome.response["rounds"][0]["displayLabel"], "T0")
        self.assertEqual(len(self.documents["NPI Trial Round Lifecycle Event"]), 1)
        with self.assertRaises(self.module.TrialLabelConflict):
            self.repository.create_round(
                PROJECT_ID,
                plan_id,
                idempotency_key_hash="5" * 64,
                expected_plan_revision_global_id=UUID(revision["globalId"]),
                expected_plan_revision_snapshot_hash=revision["snapshotHash"],
                display_label="t0",
                reason="Attempt a duplicate label.",
            )

    def test_generate_actions_creates_work_truth_then_immutable_links(self) -> None:
        created = self.repository.create_plan(PROJECT_ID, **self.plan_values())
        plan_id = UUID(created.response["planGlobalId"])
        revision = created.response["latestRevision"]
        FakeWorkRepository.owner = self
        with patch.object(
            self.module,
            "FrappeProjectWorkRepository",
            FakeWorkRepository,
        ):
            outcome = self.repository.generate_actions(
                PROJECT_ID,
                plan_id,
                idempotency_key_hash="6" * 64,
                expected_plan_revision_global_id=UUID(revision["globalId"]),
                expected_plan_revision_snapshot_hash=revision["snapshotHash"],
                trial_round_global_id=None,
                actions=(
                    {
                        "actionKey": "dimension-check",
                        "title": "Verify dimensional evidence",
                        "description": None,
                        "responsibleMemberGlobalId": MEMBER_ID,
                        "dueAt": datetime(2026, 8, 12, 8, tzinfo=UTC),
                        "severity": "high",
                        "blocking": True,
                    },
                ),
                reason="Generate governed Project actions.",
            )
        self.assertEqual(len(self.documents["NPI Domain Work Item"]), 1)
        self.assertEqual(len(self.documents["NPI Trial Plan Work Link"]), 1)
        link = outcome.response["actionLinks"][0]
        self.assertIn(link["domainWorkItemGlobalId"], self.documents["NPI Domain Work Item"])
        self.assertNotIn("state", link)
        self.assertEqual(self.project.optimistic_version, 4)

    def test_member_view_is_exact_current_and_ambiguous_membership_fails(self) -> None:
        security = importlib.import_module("npi_core.foundation.security")
        member_principal = security.Principal(
            user_id="member@example.invalid",
            roles=frozenset({"NPI API User"}),
            is_external=False,
            tenant_id="TENANT-A",
        )
        repository = self.module.FrappeTrialRepository(
            principal=member_principal,
            request_id=REQUEST_ID,
            trace_id="trace-trial-member-001",
        )
        self.assertIsNotNone(repository.planning_workspace(PROJECT_ID))
        self.add(
            "NPI Project Member",
            {
                "global_id": str(uuid4()),
                "tenant_id": "TENANT-A",
                "project_global_id": str(PROJECT_ID),
                "user_id": "member@example.invalid",
                "effective_from": date.today().isoformat(),
                "effective_to": None,
                "optimistic_version": 1,
            },
        )
        self.assertIsNone(repository.planning_workspace(PROJECT_ID))

    def test_responsible_member_with_future_end_date_remains_current(self) -> None:
        member = self.documents["NPI Project Member"][str(MEMBER_ID)]
        member.effective_to = (date.today() + timedelta(days=30)).isoformat()
        resolved = self.repository._responsible_member(self.project, MEMBER_ID)
        self.assertEqual(resolved.global_id, MEMBER_ID)
        self.assertEqual(resolved.user_id, "member@example.invalid")


if __name__ == "__main__":
    unittest.main()
