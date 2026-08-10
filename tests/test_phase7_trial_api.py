from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
PLAN_ID = "0878087f-6192-4e40-862d-05e0a5927638"
REVISION_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
ROUND_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
SAMPLE_ID = "6dd227c4-2c74-4f2f-a3ce-347497758118"
EVIDENCE_ID = "99d03125-7947-4a72-a94f-47930cfcb7bb"
FILE_REVISION_ID = "97adf8ba-827c-4e31-a62c-370248685ab8"
MASTER_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
MEMBER_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
REQUEST_ID = "5dc0ef7b-8563-46ad-9f40-76dd474566ea"
SHA256_A = "a" * 64


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase7TrialApiTest") -> None:
        self.owner = owner

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        return None


class MockRepository:
    def __init__(self, owner: "Phase7TrialApiTest") -> None:
        self.owner = owner
        self.replayed = False
        self.available = True
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def planning_workspace(self, *args: object, **kwargs: Any):
        return self._query("workspace", args, kwargs)

    def plan_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs)

    def create_plan(self, *args: object, **kwargs: Any):
        return self._command("create_plan", args, kwargs)

    def create_plan_revision(self, *args: object, **kwargs: Any):
        return self._command("revise_plan", args, kwargs)

    def create_round(self, *args: object, **kwargs: Any):
        return self._command("create_round", args, kwargs)

    def generate_actions(self, *args: object, **kwargs: Any):
        return self._command("generate_actions", args, kwargs)

    def execution_workspace(self, *args: object, **kwargs: Any):
        return self._query("execution_workspace", args, kwargs)

    def prepare_round(self, *args: object, **kwargs: Any):
        return self._command("prepare_round", args, kwargs)

    def start_round(self, *args: object, **kwargs: Any):
        return self._command("start_round", args, kwargs)

    def append_actual_revision(self, *args: object, **kwargs: Any):
        return self._command("append_actual_revision", args, kwargs)

    def create_sample_batch(self, *args: object, **kwargs: Any):
        return self._command("create_sample_batch", args, kwargs)

    def append_sample_batch_revision(self, *args: object, **kwargs: Any):
        return self._command("append_sample_batch_revision", args, kwargs)

    def upload_evidence_file(self, *args: object, **kwargs: Any):
        return self._command("upload_evidence_file", args, kwargs)

    def bind_evidence(self, *args: object, **kwargs: Any):
        return self._command("bind_evidence", args, kwargs)

    def _query(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        self.calls.append((name, args, kwargs))
        return copy.deepcopy(self.owner.response) if self.available else None

    def _command(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        response = self._query(name, args, kwargs)
        if response is None:
            return None
        return types.SimpleNamespace(response=response, replayed=self.replayed)


class Phase7TrialApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.trial_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p7-trial-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        self.roles = {
            "admin@example.invalid": ["NPI API User", "System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["NPI API User"],
        }
        self.user_types = {
            "admin@example.invalid": "System User",
            "member@example.invalid": "System User",
            "external@example.invalid": "Website User",
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.session = types.SimpleNamespace(user="admin@example.invalid")
        self.frappe.conf = AttrDict(
            npi_tenant_id="TENANT-A",
            npi_p7_01_routes_disabled=False,
            npi_p7_02_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "trial_plan_id": PLAN_ID,
                "trial_round_id": ROUND_ID,
                "sample_batch_id": SAMPLE_ID,
                "evidence_id": EVIDENCE_ID,
            },
        )
        self.frappe.local = types.SimpleNamespace(
            response=AttrDict(),
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
        )
        self.frappe.request = self.frappe.local.request
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.db = StubDatabase(self)
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
        )

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + "a" * 48
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.api = importlib.import_module("npi_core.trial_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.api._execution_repository_factory = lambda **_values: self.repository
        self.response = {
            "projectGlobalId": PROJECT_ID,
            "plans": [],
            "capabilities": [],
            "permissions": {
                "canCreatePlan": True,
                "canRevisePlan": True,
                "canCreateRound": True,
                "canGenerateActions": True,
            },
        }

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def call(self, function, payload: dict[str, object] | None = None):
        self.frappe.local.form_dict = AttrDict(payload or {})
        return function(**(payload or {}))

    @staticmethod
    def plan_payload() -> dict[str, object]:
        return {
            "toolingMasterGlobalId": MASTER_ID,
            "purpose": "first_trial",
            "objective": "Confirm the initial Trial planning intent.",
            "plannedStartAt": "2026-08-11T08:00:00Z",
            "plannedEndAt": "2026-08-11T12:00:00Z",
            "resources": [
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
            ],
            "responsibleMemberGlobalIds": [MEMBER_ID],
            "sampleQuantity": 80,
            "measurementPlan": {"description": "Inspect controlled dimensions."},
            "reason": "Create the first immutable Trial Plan revision.",
        }

    @staticmethod
    def action_payload() -> dict[str, object]:
        return {
            "expectedPlanRevisionGlobalId": REVISION_ID,
            "expectedPlanRevisionSnapshotHash": SHA256_A,
            "trialRoundGlobalId": ROUND_ID,
            "actions": [
                {
                    "actionKey": "trial-dimension-check",
                    "title": "Verify dimensional evidence",
                    "description": "Record the exact controlled result.",
                    "responsibleMemberGlobalId": MEMBER_ID,
                    "dueAt": "2026-08-12T08:00:00Z",
                    "severity": "high",
                    "blocking": True,
                }
            ],
            "reason": "Generate governed Project actions.",
        }

    @staticmethod
    def prepare_payload() -> dict[str, object]:
        reference_kinds = (
            "design_baseline",
            "part_revision",
            "tooling_revision",
            "tooling_set",
            "tooling_set_binding",
            "cavity",
            "process_chain",
            "inspection_document",
        )
        return {
            "expectedRoundOptimisticVersion": 1,
            "references": [
                {
                    "globalId": str(UUID(int=index + 100)),
                    "kind": kind,
                    "expectedOptimisticVersion": 1,
                }
                for index, kind in enumerate(reference_kinds)
            ],
            "material": {
                "sourceSystem": "NPI_ONE",
                "sourceObjectId": "material-1",
                "lotBatchCode": "lot-1",
                "label": "PA66 lot 1",
                "observedAt": "2026-08-10T08:00:00Z",
            },
            "parameterDefinitions": [
                {
                    "key": "melt_temperature",
                    "category": "temperature",
                    "valueKind": "decimal",
                    "required": True,
                    "unit": "degC",
                }
            ],
            "reason": "Freeze exact Trial execution inputs.",
        }

    def test_project_first_route_matrix_maps_exact_handlers(self) -> None:
        cases = (
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/trials", "get_trial_planning_workspace"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trials", "create_trial_plan"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/trial-plans/{PLAN_ID}", "get_trial_plan"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-plans/{PLAN_ID}/revisions", "create_trial_plan_revision"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-plans/{PLAN_ID}/rounds", "create_planned_trial_round"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-plans/{PLAN_ID}/actions:generate", "generate_trial_plan_actions"),
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/execution", "get_trial_round_execution"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}:prepare", "prepare_trial_round"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}:start", "start_trial_round"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/actual-revisions", "append_trial_actual_revision"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/sample-batches", "create_trial_sample_batch"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/sample-batches/{SAMPLE_ID}/revisions", "append_trial_sample_batch_revision"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/files", "upload_trial_evidence_file"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/evidence", "bind_trial_evidence"),
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/evidence/{EVIDENCE_ID}:content", "read_trial_evidence_content"),
        )
        for method, path, command in cases:
            with self.subTest(method=method, path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    f"npi_core.trial_api.{command}",
                )
                self.assertEqual(
                    self.frappe.flags.npi_route_params["project_id"],
                    PROJECT_ID,
                )

    def test_route_switch_defaults_closed_and_is_independent(self) -> None:
        self.frappe.conf.pop("npi_p7_01_routes_disabled")
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/trials",
            method="GET",
        )
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.trial_routes_disabled",
        )
        self.frappe.conf.npi_p7_01_routes_disabled = False
        self.frappe.conf.pop("npi_p7_02_routes_disabled")
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/execution",
            method="GET",
        )
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.trial_api.trial_execution_routes_disabled",
        )
        self.frappe.conf.npi_p7_02_routes_disabled = False
        self.frappe.conf.pop("npi_p7_01_routes_disabled")
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.trial_api.get_trial_round_execution",
        )

    def test_workspace_query_uses_opaque_project_identity(self) -> None:
        response = self.call(self.api.get_trial_planning_workspace)
        self.assertEqual(response, self.response)
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "workspace")
        self.assertEqual(args, (UUID(PROJECT_ID),))

    def test_execution_query_uses_project_and_round_identity(self) -> None:
        response = self.call(self.api.get_trial_round_execution)
        self.assertEqual(response, self.response)
        name, args, _kwargs = self.repository.calls[-1]
        self.assertEqual(name, "execution_workspace")
        self.assertEqual(args, (UUID(PROJECT_ID), UUID(ROUND_ID)))

    def test_prepare_parses_exact_references_and_rejects_forged_hash(self) -> None:
        payload = self.prepare_payload()
        response = self.call(self.api.prepare_trial_round, payload)
        self.assertEqual(response, self.response)
        name, args, kwargs = self.repository.calls[-1]
        self.assertEqual(name, "prepare_round")
        self.assertEqual(args, (UUID(PROJECT_ID), UUID(ROUND_ID)))
        self.assertEqual(len(kwargs["references"]), 8)
        self.assertIsInstance(kwargs["references"][0]["globalId"], UUID)
        self.assertIsInstance(kwargs["material"]["observedAt"], self.api.datetime)

        forged = self.prepare_payload()
        forged["references"][0]["snapshotHash"] = SHA256_A
        response = self.call(self.api.prepare_trial_round, forged)
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(
            response["fieldErrors"][0]["path"],
            "references[0].snapshotHash",
        )

    def test_bind_evidence_requires_complete_sample_revision_pair(self) -> None:
        payload = {
            "expectedRoundOptimisticVersion": 3,
            "role": "photo",
            "fileRevisionGlobalId": FILE_REVISION_ID,
            "expectedFileOptimisticVersion": 2,
            "sampleBatchRevisionGlobalId": SAMPLE_ID,
        }
        response = self.call(self.api.bind_trial_evidence, payload)
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(
            response["fieldErrors"][0]["path"],
            "sampleBatchRevisionGlobalId",
        )

    def test_upload_normalizes_only_one_canonical_multipart_version(self) -> None:
        response = self.call(
            self.api.upload_trial_evidence_file,
            {"expectedRoundOptimisticVersion": "3"},
        )
        self.assertEqual(response, self.response)
        name, _args, kwargs = self.repository.calls[-1]
        self.assertEqual(name, "upload_evidence_file")
        self.assertEqual(kwargs["expected_round_optimistic_version"], 3)

        rejected = self.call(
            self.api.upload_trial_evidence_file,
            {"expectedRoundOptimisticVersion": "03"},
        )
        self.assertEqual(rejected["code"], "VALIDATION_FAILED")
        self.assertEqual(
            rejected["fieldErrors"][0]["path"],
            "expectedRoundOptimisticVersion",
        )

    def test_create_plan_parses_closed_resource_and_measurement_intent(self) -> None:
        response = self.call(self.api.create_trial_plan, self.plan_payload())
        self.assertEqual(response, self.response)
        name, args, kwargs = self.repository.calls[-1]
        self.assertEqual(name, "create_plan")
        self.assertEqual(args, (UUID(PROJECT_ID),))
        self.assertEqual(kwargs["tooling_master_global_id"], UUID(MASTER_ID))
        self.assertEqual(kwargs["resources"][1]["quantity"], 25)
        self.assertEqual(
            kwargs["responsible_member_global_ids"],
            (UUID(MEMBER_ID),),
        )
        self.assertIsInstance(kwargs["planned_start_at"], self.api.datetime)

    def test_generate_actions_uses_domain_work_vocabulary(self) -> None:
        self.call(self.api.generate_trial_plan_actions, self.action_payload())
        name, _args, kwargs = self.repository.calls[-1]
        self.assertEqual(name, "generate_actions")
        action = kwargs["actions"][0]
        self.assertEqual(action["severity"], "high")
        self.assertIs(action["blocking"], True)
        self.assertIsInstance(action["dueAt"], self.api.datetime)
        self.assertNotIn("priority", action)

    def test_round_label_is_optional_server_sequence_input(self) -> None:
        payload = {
            "expectedPlanRevisionGlobalId": REVISION_ID,
            "expectedPlanRevisionSnapshotHash": SHA256_A,
            "reason": "Create a server-labelled planned Trial Round.",
        }
        self.call(self.api.create_planned_trial_round, payload)
        name, _args, kwargs = self.repository.calls[-1]
        self.assertEqual(name, "create_round")
        self.assertIsNone(kwargs["display_label"])

    def test_generate_actions_rejects_missing_due_and_forged_state(self) -> None:
        missing_due = self.action_payload()
        del missing_due["actions"][0]["dueAt"]
        response = self.call(self.api.generate_trial_plan_actions, missing_due)
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(
            response["fieldErrors"][0]["path"],
            "actions[0].dueAt",
        )
        forged = self.action_payload()
        forged["actions"][0]["state"] = "done"
        response = self.call(self.api.generate_trial_plan_actions, forged)
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(response["fieldErrors"][0]["path"], "actions[0].state")

    def test_resource_input_rejects_booking_claim(self) -> None:
        payload = self.plan_payload()
        payload["resources"][0]["bookingState"] = "reserved"
        response = self.call(self.api.create_trial_plan, payload)
        self.assertEqual(response["code"], "VALIDATION_FAILED")
        self.assertEqual(
            response["fieldErrors"][0]["path"],
            "resources[0].bookingState",
        )

    def test_external_principal_fails_before_repository_access(self) -> None:
        self.frappe.session.user = "external@example.invalid"
        response = self.call(self.api.get_trial_planning_workspace)
        self.assertEqual(response["code"], "PERMISSION_DENIED")
        self.assertEqual(self.repository.calls, [])

    def test_replay_header_is_forwarded(self) -> None:
        self.repository.replayed = True
        self.call(self.api.create_trial_plan, self.plan_payload())
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

    def test_unknown_and_legacy_trial_routes_remain_closed(self) -> None:
        for path in (
            f"/api/npi/v1/tooling/{MASTER_ID}/trials",
            f"/api/npi/v1/trials/{ROUND_ID}/workspace",
            f"/api/npi/v1/projects/{PROJECT_ID}/trial-plans/{PLAN_ID}:submit",
        ):
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method="POST")
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    "npi_core.bff.route_not_found",
                )


if __name__ == "__main__":
    unittest.main()
