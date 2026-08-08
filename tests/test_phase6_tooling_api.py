from __future__ import annotations

import copy
import importlib
import sys
import types
import unittest
from typing import Any
from unittest.mock import patch

sys.path.insert(0, "apps/npi_core")

from npi_core.tooling.domain import (
    ToolingEvidenceConflict,
    ToolingIntakeVersionConflict,
)

PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
MASTER_ID = "0878087f-6192-4e40-862d-05e0a5927638"
PART_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
REVISION_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
RELATIONSHIP_ID = "eb233de2-5d4d-4556-ad16-9476d8f0776f"
REQUEST_ID = "a6bfd0bf-8ab3-4a92-b49e-818735db4f55"
SET_ID = "5dc0ef7b-8563-46ad-9f40-76dd474566ea"
INTAKE_ID = "45af7c0e-d4c0-4f25-9bdf-3912a4671e1e"
REQUIREMENT_ID = "d78d72bf-014f-49db-a733-0c76ce4fc3cb"
FILE_REVISION_ID = "c32eb45b-e4df-4c7e-b879-bd8e1685d1ae"
TOOLING_REVISION_ID = "60272696-371b-465b-a3ec-2324543857a1"
PROCESS_CHAIN_REVISION_ID = "78181c5b-c8bb-46dd-bfe5-4fe267ddfb48"


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self, owner: "Phase6ToolingApiTest") -> None:
        self.owner = owner
        self.rollback_count = 0

    def get_value(self, doctype: str, name: str, fieldname: str):
        if doctype == "User" and fieldname == "user_type":
            return self.owner.user_types.get(name)
        raise AssertionError((doctype, name, fieldname))

    def rollback(self) -> None:
        self.rollback_count += 1


class MockRepository:
    def __init__(self, owner: "Phase6ToolingApiTest") -> None:
        self.owner = owner
        self.scope = True
        self.replayed = False
        self.failure: Exception | None = None
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []

    def authorize_scope(self, *args: object, **kwargs: Any) -> bool:
        self.calls.append(("authorize", args, kwargs))
        return self.scope

    def cockpit(self, *args: object, **kwargs: Any):
        return self._query("cockpit", args, kwargs)

    def master_detail(self, *args: object, **kwargs: Any):
        return self._query("detail", args, kwargs)

    def create_part(self, *args: object, **kwargs: Any):
        return self._command("part", args, kwargs)

    def create_part_revision(self, *args: object, **kwargs: Any):
        return self._command("revision", args, kwargs)

    def create_requirement(self, *args: object, **kwargs: Any):
        return self._command("requirement", args, kwargs)

    def create_master(self, *args: object, **kwargs: Any):
        return self._command("master", args, kwargs)

    def create_applicability(self, *args: object, **kwargs: Any):
        return self._command("applicability", args, kwargs)

    def tooling_sets(self, *args: object, **kwargs: Any):
        return self._query("sets", args, kwargs)

    def tooling_set_detail(self, *args: object, **kwargs: Any):
        return self._query("set_detail", args, kwargs)

    def create_tooling_set(self, *args: object, **kwargs: Any):
        return self._command("set_create", args, kwargs)

    def create_tooling_intake(self, *args: object, **kwargs: Any):
        return self._command("intake_create", args, kwargs)

    def create_tooling_intake_evidence_reference(
        self,
        *args: object,
        **kwargs: Any,
    ):
        return self._command("evidence_create", args, kwargs)

    def tooling_revisions(self, *args: object, **kwargs: Any):
        return self._query("tooling_revisions", args, kwargs)

    def tooling_revision_detail(self, *args: object, **kwargs: Any):
        return self._query("tooling_revision_detail", args, kwargs)

    def part_controlled_specification(self, *args: object, **kwargs: Any):
        return self._query("part_specification", args, kwargs)

    def tooling_process_chains(self, *args: object, **kwargs: Any):
        return self._query("process_chains", args, kwargs)

    def tooling_process_chain_detail(self, *args: object, **kwargs: Any):
        return self._query("process_chain_detail", args, kwargs)

    def create_tooling_revision(self, *args: object, **kwargs: Any):
        return self._command("tooling_revision_create", args, kwargs)

    def create_part_controlled_specification(self, *args: object, **kwargs: Any):
        return self._command("part_specification_create", args, kwargs)

    def create_tooling_process_chain_revision(self, *args: object, **kwargs: Any):
        return self._command("process_chain_create", args, kwargs)

    def create_tooling_set_revision_binding(self, *args: object, **kwargs: Any):
        return self._command("set_binding_create", args, kwargs)

    def _query(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        self.calls.append((name, args, kwargs))
        if self.failure is not None:
            raise self.failure
        return copy.deepcopy(self.owner.response) if self.scope else None

    def _command(self, name: str, args: tuple[object, ...], kwargs: dict[str, Any]):
        response = self._query(name, args, kwargs)
        return types.SimpleNamespace(response=response, replayed=self.replayed)


class Phase6ToolingApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.api",
        "npi_core.request_security",
        "npi_core.tooling.diagnostics",
        "npi_core.tooling_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p6-tooling-command-0001",
            "X-Frappe-CSRF-Token": "csrf-" + "a" * 48,
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-" + "a" * 32,
        }
        self.roles = {
            "admin@example.invalid": ["System Manager"],
            "member@example.invalid": ["NPI API User"],
            "external@example.invalid": ["System Manager"],
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
            npi_p4_05_routes_disabled=False,
            npi_p5_01_routes_disabled=False,
            npi_p5_02_routes_disabled=False,
            npi_p5_03_routes_disabled=False,
            npi_p5_04_routes_disabled=False,
            npi_p5_05_routes_disabled=False,
            npi_p5_06_routes_disabled=False,
            npi_p6_01_routes_disabled=False,
            npi_p6_02_routes_disabled=False,
            npi_p6_03_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(
            npi_bff_request=False,
            npi_route_params={
                "project_id": PROJECT_ID,
                "tooling_master_id": MASTER_ID,
                "part_id": PART_ID,
                "tooling_set_id": SET_ID,
                "intake_id": INTAKE_ID,
                "part_revision_id": REVISION_ID,
                "tooling_revision_id": TOOLING_REVISION_ID,
                "process_chain_revision_id": PROCESS_CHAIN_REVISION_ID,
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

        self.api = importlib.import_module("npi_core.tooling_api")
        self.router = importlib.import_module("npi_core.bff")
        self.repository = MockRepository(self)
        self.api._repository_factory = lambda **_values: self.repository
        self.response = {
            "project": {"globalId": PROJECT_ID},
            "masters": [],
            "requirements": [],
            "parts": [],
            "applicability": [],
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
    def intake_payload() -> dict[str, object]:
        inspection_ids = (
            "7e88d1ce-2db4-4b0e-b5fd-0948673c8b01",
            "7e88d1ce-2db4-4b0e-b5fd-0948673c8b02",
            "7e88d1ce-2db4-4b0e-b5fd-0948673c8b03",
            "7e88d1ce-2db4-4b0e-b5fd-0948673c8b04",
            "7e88d1ce-2db4-4b0e-b5fd-0948673c8b05",
        )
        categories = (
            "appearance",
            "water_circuit",
            "hot_runner",
            "electrical",
            "safety",
        )
        return {
            "transportProvider": "Controlled carrier",
            "transportReference": "ARRIVAL-001",
            "arrivedAt": "2026-08-07T08:30:00Z",
            "custodyHandover": "Received by Tooling Engineering",
            "accessories": [],
            "inspections": [
                {
                    "globalId": global_id,
                    "category": category,
                    "observation": "Recorded inspection observation",
                    "differenceObserved": index == 0,
                }
                for index, (global_id, category) in enumerate(
                    zip(inspection_ids, categories, strict=True)
                )
            ],
            "differences": [
                {
                    "globalId": "a18ab34f-f6ae-4b7c-935e-17bb5ea80d44",
                    "sourceKind": "inspection",
                    "sourceGlobalId": inspection_ids[0],
                    "description": "Surface mark recorded at arrival",
                    "customerConfirmationRequired": True,
                }
            ],
        }

    @staticmethod
    def tooling_revision_payload() -> dict[str, object]:
        measurement = {"value": "1", "unit": "mm", "source": "Controlled input"}
        specification = {
            "toolingType": "Injection mold",
            "moldBaseMaterial": "P20",
            "coreMaterial": "H13",
            "hardness": {"value": "52", "unit": "HRC", "source": "Drawing"},
            "surfaceTreatment": "Nitrided",
            "cavityCount": 1,
            "hotRunner": "Valve gate",
            "length": measurement,
            "width": measurement,
            "height": measurement,
            "weight": {"value": "1200", "unit": "kg", "source": "Drawing"},
            "clampTonnage": {"value": "450", "unit": "t", "source": "Calculation"},
            "tieBarSpacingX": measurement,
            "tieBarSpacingY": measurement,
            "injectionCapacity": {"value": "1200", "unit": "g", "source": "Calculation"},
            "machineType": "Injection molding machine",
            "targetCycle": {"value": "42", "unit": "s", "source": "Target"},
            "targetLife": {"value": "1000000", "unit": "shots", "source": "Contract"},
            "warranty": "Twelve months",
            "customerStandard": "Customer standard CS-01",
            "interfaceRequirement": "Standard interface",
            "spareParts": [],
            "deliveryDocuments": [],
        }
        return {
            "revisionLabel": "R1",
            "specification": specification,
            "cavities": [
                {
                    "cavityIdentifier": "C1",
                    "toolingApplicabilityGlobalId": RELATIONSHIP_ID,
                    "structuralState": "enabled",
                }
            ],
            "inserts": [],
            "externalIdentities": [],
            "designDocumentRevisions": [],
            "reason": "Initial controlled Tooling Revision",
        }

    def test_queries_authorize_project_before_protected_master(self) -> None:
        self.assertEqual(self.call(self.api.get_tooling_cockpit), self.response)
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.assertEqual(len(self.repository.calls[0][1]), 1)
        self.repository.calls.clear()
        self.assertEqual(self.call(self.api.get_tooling_master), self.response)
        self.assertEqual([value[0] for value in self.repository.calls[:2]], ["authorize", "authorize"])
        self.assertEqual(str(self.repository.calls[1][1][1]), MASTER_ID)

    def test_part_command_is_closed_admin_actor_bound_and_replay_visible(self) -> None:
        payload = {
            "title": "Front housing",
            "revisionLabel": "A",
            "reason": "Initial engineering release",
        }
        self.assertEqual(self.call(self.api.create_engineering_part, payload), self.response)
        name, _args, values = self.repository.calls[-1]
        self.assertEqual(name, "part")
        self.assertEqual(len(values["idempotency_key_hash"]), 64)
        self.assertEqual(values["revision_label"], "A")
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.repository.replayed = True
        self.call(self.api.create_engineering_part, payload)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

    def test_project_authorization_and_admin_role_precede_body_validation(self) -> None:
        self.repository.scope = False
        result = self.call(self.api.create_engineering_part, {"doctype": "Secret"})
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][0], "authorize")
        self.repository.scope = True
        self.frappe.session.user = "member@example.invalid"
        result = self.call(
            self.api.create_engineering_part,
            {"title": "Part", "revisionLabel": "A", "reason": "Initial"},
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")
        self.frappe.session.user = "external@example.invalid"
        result = self.call(
            self.api.create_engineering_part,
            {"title": "Part", "revisionLabel": "A", "reason": "Initial"},
        )
        self.assertEqual(result["code"], "PERMISSION_DENIED")

    def test_applicability_parses_only_exact_reference_and_successor_fields(self) -> None:
        payload = {
            "toolingMasterGlobalId": MASTER_ID,
            "partRevisionGlobalId": REVISION_ID,
            "product": {"sourceSystem": "ERPNEXT", "sourceObjectId": "ITEM-001"},
            "relationshipGlobalId": RELATIONSHIP_ID,
            "expectedVersion": 1,
            "effectiveFrom": "2026-08-07",
            "effectiveTo": "2026-09-01",
            "reason": "Exact successor effectivity",
        }
        self.call(self.api.create_tooling_applicability, payload)
        name, _args, values = self.repository.calls[-1]
        self.assertEqual(name, "applicability")
        self.assertEqual(values["product"]["sourceObjectId"], "ITEM-001")
        self.assertEqual(str(values["relationship_id"]), RELATIONSHIP_ID)
        self.assertEqual(values["effective_from"].isoformat(), "2026-08-07")
        invalid = dict(payload)
        invalid.pop("expectedVersion")
        result = self.call(self.api.create_tooling_applicability, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_router_maps_all_seven_paths_and_switch_is_fail_closed(self) -> None:
        cases = {
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling"): "get_tooling_cockpit",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}"): "get_tooling_master",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/parts"): "create_engineering_part",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/parts/{PART_ID}/revisions"): "create_engineering_part_revision",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-requirements"): "create_tooling_requirement",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-masters"): "create_tooling_master",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-applicabilities"): "create_tooling_applicability",
        }
        for (method, path), suffix in cases.items():
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))
        del self.frappe.conf["npi_p6_01_routes_disabled"]
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_routes_disabled",
        )

    def test_set_queries_authorize_project_and_master_before_set_resolution(
        self,
    ) -> None:
        self.assertEqual(self.call(self.api.get_tooling_sets), self.response)
        self.assertEqual(
            [value[0] for value in self.repository.calls[:3]],
            ["authorize", "authorize", "sets"],
        )
        self.repository.calls.clear()
        self.assertEqual(self.call(self.api.get_tooling_set), self.response)
        self.assertEqual(
            [value[0] for value in self.repository.calls[:3]],
            ["authorize", "authorize", "set_detail"],
        )
        self.assertEqual(str(self.repository.calls[2][1][2]), SET_ID)

    def test_set_intake_and_evidence_commands_parse_only_closed_inputs(self) -> None:
        set_payload = {
            "toolingRequirementGlobalId": REQUIREMENT_ID,
            "physicalSerial": "CUSTOMER-SET-01",
            "customer": {
                "sourceSystem": "ERPNEXT",
                "sourceObjectId": "CUST-001",
            },
            "custodyResponsibility": "NPI One custody boundary",
            "repairAuthorizationReference": "Customer agreement CA-001",
            "returnConditions": "Return on written request",
        }
        self.call(self.api.create_tooling_set, set_payload)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "set_create")
        self.assertEqual(str(args[1]), MASTER_ID)
        self.assertEqual(str(values["tooling_requirement_id"]), REQUIREMENT_ID)
        self.assertNotIn("tenant_id", values)

        self.repository.calls.clear()
        self.call(self.api.create_tooling_intake, self.intake_payload())
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "intake_create")
        self.assertEqual(str(args[2]), SET_ID)
        self.assertEqual(len(values["inspections"]), 5)
        self.assertEqual(len(values["differences"]), 1)
        self.assertIsNone(values["expected_version"])

        self.repository.calls.clear()
        evidence_payload = {
            "evidenceRole": "customer_confirmation",
            "differenceGlobalIds": [
                "a18ab34f-f6ae-4b7c-935e-17bb5ea80d44"
            ],
            "fileRevisionGlobalId": FILE_REVISION_ID,
        }
        self.call(
            self.api.create_tooling_intake_evidence_reference,
            evidence_payload,
        )
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "evidence_create")
        self.assertEqual(str(args[3]), INTAKE_ID)
        self.assertEqual(str(values["file_revision_id"]), FILE_REVISION_ID)
        self.assertEqual(values["evidence_role"].value, "customer_confirmation")

    def test_router_maps_five_set_paths_with_independent_fail_closed_switch(
        self,
    ) -> None:
        cases = {
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets",
            ): "get_tooling_sets",
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}",
            ): "get_tooling_set",
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets",
            ): "create_tooling_set",
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/intakes",
            ): "create_tooling_intake",
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/intakes/{INTAKE_ID}/evidence",
            ): "create_tooling_intake_evidence_reference",
        }
        for (method, path), suffix in cases.items():
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))

        self.frappe.conf.npi_p6_01_routes_disabled = True
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets",
            method="GET",
        )
        self.router.route_request()
        self.assertTrue(self.frappe.local.form_dict.cmd.endswith("get_tooling_sets"))

        self.frappe.conf.npi_p6_01_routes_disabled = False
        del self.frappe.conf["npi_p6_02_routes_disabled"]
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_set_routes_disabled",
        )
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling",
            method="GET",
        )
        self.router.route_request()
        self.assertTrue(self.frappe.local.form_dict.cmd.endswith("get_tooling_cockpit"))

    def test_set_route_switch_is_directly_fail_closed(self) -> None:
        self.frappe.conf.npi_p6_02_routes_disabled = True
        result = self.call(self.api.get_tooling_sets)
        self.assertEqual(result["code"], "TOOLING_SET_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)

    def test_set_commands_fail_closed_replay_and_roll_back_exact_conflicts(
        self,
    ) -> None:
        self.repository.scope = False
        result = self.call(self.api.create_tooling_set, {"doctype": "Secret"})
        self.assertEqual(result["code"], "TOOLING_UNAVAILABLE")
        self.assertEqual(self.repository.calls[0][0], "authorize")

        self.repository.scope = True
        set_payload = {
            "toolingRequirementGlobalId": REQUIREMENT_ID,
            "physicalSerial": "CUSTOMER-SET-02",
            "custodyResponsibility": "NPI One custody boundary",
            "repairAuthorizationReference": "Customer agreement CA-002",
            "returnConditions": "Return on written request",
        }
        self.repository.replayed = True
        self.call(self.api.create_tooling_set, set_payload)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )

        self.repository.replayed = False
        self.repository.failure = ToolingIntakeVersionConflict()
        result = self.call(self.api.create_tooling_intake, self.intake_payload())
        self.assertEqual(result["code"], "TOOLING_INTAKE_VERSION_CONFLICT")
        self.assertEqual(self.frappe.local.response.http_status_code, 409)
        self.assertEqual(self.frappe.db.rollback_count, 2)

        self.repository.failure = ToolingEvidenceConflict()
        result = self.call(
            self.api.create_tooling_intake_evidence_reference,
            {
                "evidenceRole": "arrival_photo",
                "differenceGlobalIds": [],
                "fileRevisionGlobalId": FILE_REVISION_ID,
            },
        )
        self.assertEqual(result["code"], "TOOLING_EVIDENCE_CONFLICT")
        self.assertEqual(self.frappe.local.response.http_status_code, 409)
        self.assertEqual(self.frappe.db.rollback_count, 3)

    def test_revision_queries_and_commands_are_project_first_and_closed(self) -> None:
        self.assertEqual(self.call(self.api.get_tooling_revisions), self.response)
        self.assertEqual(
            [value[0] for value in self.repository.calls[:3]],
            ["authorize", "authorize", "tooling_revisions"],
        )
        self.repository.calls.clear()
        self.call(self.api.create_tooling_revision, self.tooling_revision_payload())
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "tooling_revision_create")
        self.assertEqual(str(args[1]), MASTER_ID)
        self.assertEqual(values["revision_label"], "R1")
        self.assertEqual(len(values["cavities"]), 1)
        self.assertNotIn("tenant_id", values)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)

        invalid = self.tooling_revision_payload()
        invalid["doctype"] = "Secret"
        result = self.call(self.api.create_tooling_revision, invalid)
        self.assertEqual(result["code"], "VALIDATION_FAILED")

    def test_part_specification_chain_and_binding_parse_exact_inputs(self) -> None:
        part_payload = {
            "items": [
                {
                    "kind": "material_family",
                    "normalizedValue": "PA66",
                    "rawValue": "PA 66",
                    "sourceSystem": "NPI_ONE",
                    "sourceObjectId": "SPEC-001",
                    "effectiveFrom": "2026-08-08",
                }
            ],
            "externalIdentities": [],
        }
        self.call(self.api.create_part_controlled_specification, part_payload)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "part_specification_create")
        self.assertEqual(str(args[1]), PART_ID)
        self.assertEqual(str(args[2]), REVISION_ID)
        self.assertEqual(values["items"][0]["kind"].value, "material_family")

        chain_payload = {
            "steps": [
                {
                    "stepOrder": 1,
                    "processKind": "primary_molding",
                    "toolingRevisionGlobalId": TOOLING_REVISION_ID,
                    "inputPartRevisionGlobalIds": [REVISION_ID],
                    "outputPartRevisionGlobalId": REVISION_ID,
                    "machineType": "Machine A",
                    "clampTonnage": {
                        "value": "450",
                        "unit": "t",
                        "source": "Calculation",
                    },
                },
                {
                    "stepOrder": 2,
                    "processKind": "overmold",
                    "toolingRevisionGlobalId": TOOLING_REVISION_ID,
                    "inputPartRevisionGlobalIds": [REVISION_ID],
                    "outputPartRevisionGlobalId": REVISION_ID,
                    "parentStepOrder": 1,
                    "machineType": "Machine B",
                    "clampTonnage": {
                        "value": "300",
                        "unit": "t",
                        "source": "Calculation",
                    },
                },
            ],
            "reason": "Controlled overmold chain",
        }
        self.call(self.api.create_tooling_process_chain_revision, chain_payload)
        name, _args, values = self.repository.calls[-1]
        self.assertEqual(name, "process_chain_create")
        self.assertEqual(values["steps"][1]["parent_step_order"], 1)

        self.call(
            self.api.create_tooling_set_revision_binding,
            {
                "toolingRevisionGlobalId": TOOLING_REVISION_ID,
                "reason": "Initial exact source binding",
            },
        )
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "set_binding_create")
        self.assertEqual(str(args[2]), SET_ID)
        self.assertEqual(str(values["tooling_revision_id"]), TOOLING_REVISION_ID)

    def test_router_maps_revision_paths_and_switch_is_independently_fail_closed(self) -> None:
        cases = {
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/revisions"): "get_tooling_revisions",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/revisions/{TOOLING_REVISION_ID}"): "get_tooling_revision",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/revisions"): "create_tooling_revision",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/parts/{PART_ID}/revisions/{REVISION_ID}/controlled-specification"): "get_part_controlled_specification",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/parts/{PART_ID}/revisions/{REVISION_ID}/controlled-specification"): "create_part_controlled_specification",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-process-chains"): "get_tooling_process_chains",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-process-chains"): "create_tooling_process_chain_revision",
            ("GET", f"/api/npi/v1/projects/{PROJECT_ID}/tooling-process-chains/{PROCESS_CHAIN_REVISION_ID}"): "get_tooling_process_chain",
            ("POST", f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets/{SET_ID}/revision-binding"): "create_tooling_set_revision_binding",
        }
        for (method, path), suffix in cases.items():
            with self.subTest(path=path):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.router.route_request()
                self.assertTrue(self.frappe.local.form_dict.cmd.endswith(suffix))

        del self.frappe.conf["npi_p6_03_routes_disabled"]
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/revisions",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.tooling_revision_routes_disabled",
        )
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{PROJECT_ID}/tooling/{MASTER_ID}/sets",
            method="GET",
        )
        self.router.route_request()
        self.assertTrue(self.frappe.local.form_dict.cmd.endswith("get_tooling_sets"))

    def test_revision_route_switch_is_directly_fail_closed(self) -> None:
        self.frappe.conf.npi_p6_03_routes_disabled = True
        result = self.call(self.api.get_tooling_revisions)
        self.assertEqual(result["code"], "TOOLING_REVISION_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)

    def test_direct_route_switch_and_command_failure_roll_back_fail_closed(self) -> None:
        self.frappe.conf.npi_p6_01_routes_disabled = True
        result = self.call(self.api.get_tooling_cockpit)
        self.assertEqual(result["code"], "TOOLING_ROUTES_DISABLED")
        self.assertEqual(self.frappe.local.response.http_status_code, 503)
        self.assertEqual(self.frappe.db.rollback_count, 1)

        self.frappe.conf.npi_p6_01_routes_disabled = False
        self.repository.failure = RuntimeError("synthetic protected failure")
        result = self.call(
            self.api.create_tooling_master,
            {"title": "Front housing tool"},
        )
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(self.frappe.local.response.http_status_code, 500)
        self.assertEqual(self.frappe.db.rollback_count, 2)

    def test_part_create_diagnostic_is_header_gated_response_neutral_and_sanitized(
        self,
    ) -> None:
        payload = {
            "title": "Front housing",
            "revisionLabel": "A",
            "reason": "Initial engineering release",
        }
        self.repository.failure = RuntimeError("sensitive synthetic detail")
        with patch("npi_core.api.record_safe_diagnostic") as record:
            result = self.call(self.api.create_engineering_part, payload)
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        self.assertEqual(
            [call.kwargs["code"] for call in record.call_args_list],
            ["UNEXPECTED_BFF_EXCEPTION"],
        )

        self.headers["X-NPI-Diagnostic-Scope"] = "p601-part-create-v1"
        with patch("npi_core.api.record_safe_diagnostic") as record:
            diagnostic_result = self.call(self.api.create_engineering_part, payload)
        self.assertEqual(diagnostic_result, result)
        record.assert_any_call(
            code="P601_PART_CREATE_API_RESPONSE",
            title="NPI Part create substage failed",
            exception_type="RuntimeError",
            trace_id=self.headers["X-Trace-ID"],
        )
        self.assertEqual(
            [call.kwargs["code"] for call in record.call_args_list],
            ["P601_PART_CREATE_API_RESPONSE", "UNEXPECTED_BFF_EXCEPTION"],
        )
        self.assertNotIn("sensitive synthetic detail", str(record.call_args))

    def test_applicability_diagnostic_is_route_gated_and_response_neutral(
        self,
    ) -> None:
        payload = {
            "toolingMasterGlobalId": MASTER_ID,
            "partRevisionGlobalId": REVISION_ID,
            "effectiveFrom": "2026-08-01",
            "reason": "Initial exact relationship",
        }
        self.repository.failure = RuntimeError("sensitive applicability detail")
        self.headers["X-NPI-Diagnostic-Scope"] = (
            "p601-applicability-create-v1"
        )
        with patch("npi_core.api.record_safe_diagnostic") as record:
            result = self.call(self.api.create_tooling_applicability, payload)
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")
        record.assert_any_call(
            code="P601_APPLICABILITY_CREATE_API_RESPONSE",
            title="NPI Tooling Applicability create substage failed",
            exception_type="RuntimeError",
            trace_id=self.headers["X-Trace-ID"],
        )
        self.assertEqual(
            [call.kwargs["code"] for call in record.call_args_list],
            [
                "P601_APPLICABILITY_CREATE_API_RESPONSE",
                "UNEXPECTED_BFF_EXCEPTION",
            ],
        )
        self.assertNotIn("sensitive applicability detail", str(record.call_args))

        with patch("npi_core.api.record_safe_diagnostic") as wrong_route_record:
            wrong_route_result = self.call(self.api.create_engineering_part, {
                "title": "Front housing",
                "revisionLabel": "A",
                "reason": "Initial engineering release",
            })
        self.assertEqual(wrong_route_result, result)
        self.assertEqual(
            [call.kwargs["code"] for call in wrong_route_record.call_args_list],
            ["UNEXPECTED_BFF_EXCEPTION"],
        )


if __name__ == "__main__":
    unittest.main()
