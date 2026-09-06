from __future__ import annotations

import json
import types
import unittest
from unittest import mock
from uuid import UUID

from tests import test_phase4_project_work_api as api_fixture
from tests import test_phase4_project_work_repository_behavior as repo_fixture


class ProjectSetupApiTest(unittest.TestCase):
    def setUp(self):
        self.h = api_fixture.Phase4ProjectWorkApiTest()
        self.h.setUp()
        self.addCleanup(self.h.tearDown)
        self.h.reset_response()
        self.options = {
            "projectId": api_fixture.PROJECT_ID,
            "projectVersion": 5,
            "policies": [],
            "nextCursor": None,
        }
        self.h.repository.setup_options = mock.Mock(return_value=self.options)
        self.h.repository.prepare_injection_template = mock.Mock(
            return_value=types.SimpleNamespace(
                response={"publicationState": "draft"}, replayed=False
            )
        )

    def query(self, **payload):
        return self.h.call(
            "npi_core.project_work_api.get_project_setup_options",
            self.h.api.get_project_setup_options,
            payload,
        )

    def test_role_initialization_needs_no_people_dates_or_permission_assignments(self):
        payload = {
            "expectedProjectVersion": 5,
            "workPolicyRef": {
                "globalId": api_fixture.POLICY_ID,
                "version": 1,
                "snapshotHash": "a" * 64,
            },
        }
        result = self.h.call(
            "npi_core.project_work_api.initialize_project_work_roles",
            self.h.api.initialize_project_work_roles,
            payload,
        )
        self.assertNotIn("status", result)
        values = self.h.repository.calls[-1][2]
        self.assertEqual(values["members"], ())
        self.assertEqual(values["role_assignments"], ())
        self.assertEqual(values["substitutions"], ())
        self.assertEqual(values["raci_assignments"], ())
        self.assertEqual(
            str(values["work_policy_ref"]["global_id"]), api_fixture.POLICY_ID
        )
        self.assertEqual(values["work_policy_ref"]["version"], 1)

    def test_catalog_requires_internal_manager_and_hides_unrelated_projects(self):
        for user, status in (
            ("Guest", 401),
            ("owner@example.invalid", 403),
            ("external-manager@example.invalid", 403),
        ):
            with self.subTest(user=user):
                self.h.reset_response(user=user)
                self.assertEqual(self.query()["status"], status)
        self.h.repository.setup_options.assert_not_called()
        self.h.reset_response()
        self.h.repository.setup_options.return_value = None
        self.assertEqual(self.query()["status"], 404)

    def test_catalog_is_bounded_closed_and_correlates_the_request(self):
        self.assertEqual(self.query(), self.options)
        self.assertEqual(
            self.h.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )
        for payload in ({"after": "../all"}, {"after": 1}, {"doctype": "User"}):
            with self.subTest(payload=payload):
                self.h.reset_response()
                self.assertIn(self.query(**payload)["status"], (400, 422))
        self.h.reset_response()
        cursor = f"{api_fixture.POLICY_ID}:1"
        self.assertEqual(self.query(after=cursor), self.options)
        self.h.repository.setup_options.assert_called_with(
            UUID(api_fixture.PROJECT_ID), after=cursor
        )

    def test_draft_creation_uses_existing_csrf_permission_and_exact_version_boundary(
        self,
    ):
        payload = {
            "expectedProjectVersion": 5,
            "templateCode": "REVIEW-NEW-TOOL",
            "title": "Injection collaboration review",
        }
        command = "npi_core.project_work_api.prepare_project_injection_template"
        for user in (
            "Guest",
            "owner@example.invalid",
            "external-manager@example.invalid",
        ):
            self.h.reset_response(user=user)
            result = self.h.call(
                command, self.h.api.prepare_project_injection_template, payload
            )
            self.assertIn(result["status"], (401, 403))
        self.h.repository.prepare_injection_template.assert_not_called()
        self.h.reset_response()
        result = self.h.call(
            command, self.h.api.prepare_project_injection_template, payload
        )
        self.assertEqual(result, {"publicationState": "draft"})
        self.assertEqual(self.h.frappe.local.response.http_status_code, 201)
        self.assertEqual(
            self.h.repository.prepare_injection_template.call_args.kwargs[
                "expected_project_version"
            ],
            5,
        )
        self.assertNotIn(
            "publication_state",
            self.h.repository.prepare_injection_template.call_args.kwargs,
        )
        self.h.reset_response()
        result = self.h.call(
            command,
            self.h.api.prepare_project_injection_template,
            {**payload, "publicationState": "published"},
        )
        self.assertIn(result["status"], (400, 422))

    def test_new_routes_keep_exact_methods_and_correlation(self):
        routes = (
            ("GET", "/setup-options", "get_project_setup_options"),
            ("POST", ":initialize-work-roles", "initialize_project_work_roles"),
            (
                "POST",
                ":prepare-injection-template",
                "prepare_project_injection_template",
            ),
        )
        for method, suffix, handler in routes:
            path = f"/api/npi/v1/projects/{api_fixture.PROJECT_ID}{suffix}"
            self.h.frappe.local.form_dict = api_fixture.AttrDict()
            self.h.frappe.local.request = types.SimpleNamespace(
                path=path, method=method
            )
            self.h.router.route_request()
            self.assertEqual(
                self.h.frappe.local.form_dict.cmd,
                f"npi_core.project_work_api.{handler}",
            )
            self.assertTrue(self.h.router._requires_project_request_id(method, path))

    def test_template_write_requires_csrf_and_rolls_back_failed_insert(self):
        payload = {
            "expectedProjectVersion": 5,
            "templateCode": "REVIEW",
            "title": "Review",
        }
        command = "npi_core.project_work_api.prepare_project_injection_template"
        self.h.headers.pop("X-Frappe-CSRF-Token")
        self.assertEqual(
            self.h.call(
                command, self.h.api.prepare_project_injection_template, payload
            )["status"],
            403,
        )
        self.h.repository.prepare_injection_template.assert_not_called()
        self.h.reset_response()
        self.h.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)
        self.h.repository.prepare_injection_template.side_effect = RuntimeError(
            "draft insert failed"
        )
        self.h.frappe.db.rollback = mock.Mock()
        self.assertEqual(
            self.h.call(
                command, self.h.api.prepare_project_injection_template, payload
            )["status"],
            500,
        )
        self.h.frappe.db.rollback.assert_called()


class ProjectSetupRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.h = repo_fixture.Phase4ProjectWorkRepositoryBehaviorTest()
        self.h.setUp()
        self.addCleanup(self.h.tearDown)

    def test_query_uses_existing_authorization_before_reading_any_policy(self):
        repository, _ = self.h._repository(self.h._project())
        repository._authorized_project = mock.Mock(return_value=None)
        self.h.frappe.get_list = mock.Mock(side_effect=AssertionError("must not read"))
        self.assertIsNone(repository.setup_options(repo_fixture.PROJECT_ID))
        repository._authorized_project.assert_called_once_with(
            repo_fixture.PROJECT_ID, self.h.repository_module.ProjectAccess.ADMINISTER
        )
        self.h.frappe.get_list.assert_not_called()

    def test_bound_project_returns_only_its_existing_policy(self):
        project = self.h._project()
        repository, _ = self.h._repository(project)
        self.h.frappe.get_list = mock.Mock(
            side_effect=AssertionError("bound policy must be exact")
        )
        self.h.frappe.get_doc = mock.Mock(
            return_value=repo_fixture.AttrDoc(title="Retained policy")
        )
        result = repository.setup_options(repo_fixture.PROJECT_ID)
        self.assertIsNone(result["nextCursor"])
        self.assertEqual(len(result["policies"]), 1)
        self.assertEqual(
            result["policies"][0]["reference"], self.h._policy_mapping()["ref"]
        )
        self.h.frappe.get_list.assert_not_called()

    def test_catalog_paginates_without_silently_truncating_or_returning_drafts(self):
        project = self.h._project()
        for field in (
            "work_policy_global_id",
            "work_policy_version",
            "work_policy_snapshot_hash",
        ):
            project[field] = None
        repository, _ = self.h._repository(project)
        rows = [
            repo_fixture.AttrDoc(
                name=f"{repo_fixture.POLICY_ID}:{index}",
                policy_global_id=str(repo_fixture.POLICY_ID),
                policy_version=index,
                snapshot_hash=self.h.policy.snapshot_hash,
            )
            for index in range(1, 52)
        ]
        self.h.frappe.get_list = mock.Mock(return_value=rows)
        self.h.frappe.get_doc = mock.Mock(
            return_value=repo_fixture.AttrDoc(title="Published policy")
        )
        repository._load_policy = lambda ref: {"ref": ref, "snapshot": self.h.policy}
        result = repository.setup_options(
            repo_fixture.PROJECT_ID, after=f"{repo_fixture.POLICY_ID}:0"
        )
        self.assertEqual(len(result["policies"]), 50)
        self.assertEqual(result["nextCursor"], rows[49].name)
        query = self.h.frappe.get_list.call_args.kwargs
        self.assertEqual(query["limit_page_length"], 51)
        self.assertEqual(query["filters"]["publication_state"], "published")
        self.assertEqual(query["order_by"], "name asc")
        self.assertNotIn("role_keys", query["fields"])

    def test_template_definition_is_fresh_unpublished_and_validates_complete_lifecycles(
        self,
    ):
        from npi_core.project_work.injection_template import (
            draft_documents,
            DEPARTMENTS,
        )

        one = draft_documents("INJECTION-REVIEW", "Injection review")
        two = draft_documents("SECOND-REVIEW", "Second review")
        self.assertNotEqual(one[0]["global_id"], two[0]["global_id"])
        self.assertEqual(len(one[1]["gates"]), 8)
        self.assertEqual(
            set(DEPARTMENTS),
            {
                "engineering",
                "quality",
                "purchasing",
                "sales",
                "warehouse",
                "materials_control",
            },
        )
        self.assertEqual(one[1]["publication_state"], "draft")
        self.assertEqual(one[2]["publication_state"], "draft")
        self.assertTrue(
            all("gate_template_global_id" not in row for row in one[1]["gates"])
        )
        from npi_core.project_work.domain import (
            LifecycleDefinition,
            LifecycleState,
            ProjectWorkPolicyVersion,
            KindLifecycle,
            DomainWorkItemKind,
        )

        def lifecycle(value):
            return LifecycleDefinition(
                value["initialStateKey"],
                tuple(
                    LifecycleState(
                        row["key"], row["labelSource"], terminal=row["terminal"]
                    )
                    for row in value["states"]
                ),
            )

        policy = one[2]
        draft = ProjectWorkPolicyVersion.create_draft(
            policy_global_id=UUID(policy["policy_global_id"]),
            policy_key=policy["policy_key"],
            policy_version=1,
            title=policy["title"],
            role_keys=DEPARTMENTS,
            wbs_lifecycle=lifecycle(json.loads(policy["wbs_states"])),
            work_item_lifecycles=tuple(
                KindLifecycle(DomainWorkItemKind(value["kind"]), lifecycle(value))
                for value in json.loads(policy["work_item_lifecycles"])
            ),
        )
        self.assertEqual(draft.publication_state.value, "draft")
        self.assertTrue(
            any(
                state.terminal and state.label_source == "Completed"
                for state in draft.wbs_lifecycle.states
            )
        )

    def test_draft_replay_never_creates_another_bundle_and_rejects_version_conflicts(
        self,
    ):
        project = self.h._project()
        repository, _ = self.h._repository(project)
        repository._idempotency_replay = lambda *_: {"publicationState": "draft"}
        self.h.frappe.get_doc = mock.Mock(
            side_effect=AssertionError("replay must not insert")
        )
        result = repository.prepare_injection_template(
            repo_fixture.PROJECT_ID,
            idempotency_key="existing-command",
            expected_project_version=project.optimistic_version,
            template_code="REVIEW",
            title="Review",
        )
        self.assertTrue(result.replayed)
        self.h.frappe.get_doc.assert_not_called()
        repository._idempotency_replay = lambda *_: None
        with self.assertRaises(self.h.repository_module.VersionConflict):
            repository.prepare_injection_template(
                repo_fixture.PROJECT_ID,
                idempotency_key="new-command",
                expected_project_version=project.optimistic_version + 1,
                template_code="REVIEW",
                title="Review",
            )
        self.h.frappe.get_doc.assert_not_called()

    def test_draft_bundle_is_audited_and_sealed_only_after_all_three_inserts(self):
        project = self.h._project()
        repository, audits = self.h._repository(project)
        original_version = project.optimistic_version
        inserted = []

        def get_doc(value):
            document = repo_fixture.AttrDoc(value)
            if value["doctype"] == "NPI Project Template Version":
                document.global_id = "20000000-0000-4000-8000-000000000001"
            inserted.append(document)
            return document

        self.h.frappe.get_doc = get_doc
        repository._seal_idempotency = mock.Mock()
        result = repository.prepare_injection_template(
            repo_fixture.PROJECT_ID,
            idempotency_key="fresh-command",
            expected_project_version=original_version,
            template_code="REVIEW",
            title="Review",
        )
        self.assertEqual(len(inserted), 3)
        self.assertTrue(all(row.inserted for row in inserted))
        self.assertEqual(inserted[1].project_template, inserted[0].global_id)
        self.assertEqual(result.response["publicationState"], "draft")
        self.assertEqual(project.optimistic_version, original_version)
        self.assertEqual(audits[0]["operation"], "project.setup_template.prepare")
        repository._seal_idempotency.assert_called_once()
