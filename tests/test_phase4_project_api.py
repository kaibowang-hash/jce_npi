from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ID = UUID("2f4d63bf-4d51-4a17-aeb1-08116cb129fa")
REFERENCE_ID = UUID("9b333a43-bd44-4196-817e-3efad6d3a47c")
REQUEST_ID = "a82c52c8-120a-4df5-bbf1-da227a836762"


class AttrDict(dict):
    """Small attribute-access mapping matching the Frappe values used here."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _as_frappe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return AttrDict(
            {key: _as_frappe_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return [_as_frappe_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_as_frappe_value(item) for item in value)
    return value


class StubResponse(dict):
    def __getattr__(self, name: str) -> Any:
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubHttpResponse:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.data = b""
        self.status_code = 200

    def set_data(self, data: str) -> None:
        self.data = data.encode("utf-8")


class StubLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def error(self, message: str, *args: object) -> None:
        self.messages.append(message % args if args else message)


class StubInsertDocument:
    def __init__(self, store: "StubFrappeStore", values: Mapping[str, Any]) -> None:
        self._store = store
        self._values = dict(values)

    def insert(self) -> AttrDict:
        return self._store.insert(self._values)


class StubFrappeStore:
    UNIQUE_FIELDS = {
        "NPI Project Template Version": ("global_id", "version_key"),
        "NPI Project Idempotency": ("record_id", "actor_key_hash"),
        "NPI Project Business Code": ("reservation_key_hash",),
        "NPI Engineering Project": ("global_id",),
        "NPI Gate Shell": ("global_id", "shell_key"),
        "NPI Audit Event": ("event_id",),
    }
    NAME_FIELDS = {
        "NPI Project Template Version": "version_key",
        "NPI Project Idempotency": "record_id",
        "NPI Project Business Code": "reservation_key_hash",
        "NPI Engineering Project": "global_id",
        "NPI Gate Shell": "global_id",
        "NPI Audit Event": "event_id",
    }

    def __init__(self, user: Callable[[], str]) -> None:
        self.documents: dict[str, dict[str, AttrDict]] = {}
        self.committed_documents: dict[str, dict[str, AttrDict]] = {}
        self.insert_counts: dict[str, int] = {}
        self.fail_on: tuple[str, int] | None = None
        self.inject_business_code_race = False
        self.stale_idempotency_reads = False
        self._user = user
        self._clock = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)

    def seed(self, doctype: str, name: str, values: Mapping[str, Any]) -> None:
        document = _as_frappe_value(
            {
                "doctype": doctype,
                "name": name,
                **values,
            }
        )
        self.documents.setdefault(doctype, {})[name] = document

    def commit(self) -> None:
        self.committed_documents = copy.deepcopy(self.documents)

    def rollback(self) -> None:
        self.documents = copy.deepcopy(self.committed_documents)

    def count(self, doctype: str) -> int:
        return len(self.documents.get(doctype, {}))

    def get_doc(self, doctype: str, name: str, missing_error: type[Exception]):
        try:
            return self.documents[doctype][name]
        except KeyError as error:
            raise missing_error(f"{doctype} {name} does not exist") from error

    def get_value(
        self,
        doctype: str,
        filters: Mapping[str, object] | str,
        fields: list[str] | str,
        *,
        as_dict: bool,
    ) -> AttrDict | tuple[object, ...] | object | None:
        if isinstance(filters, str):
            document = self.documents.get(doctype, {}).get(filters)
            if document is None:
                return None
            if isinstance(fields, str):
                return document.get(fields)
            values = AttrDict({field: document.get(field) for field in fields})
            return values if as_dict else tuple(values[field] for field in fields)
        if isinstance(fields, str):
            for document in self.documents.get(doctype, {}).values():
                if all(document.get(key) == value for key, value in filters.items()):
                    return document.get(fields)
            return None
        for document in self.documents.get(doctype, {}).values():
            if all(document.get(key) == value for key, value in filters.items()):
                values = AttrDict({field: document.get(field) for field in fields})
                return values if as_dict else tuple(values[field] for field in fields)
        return None

    def insert(self, raw_values: Mapping[str, Any]) -> AttrDict:
        values = _as_frappe_value(raw_values)
        doctype = str(values["doctype"])
        occurrence = self.insert_counts.get(doctype, 0) + 1
        self.insert_counts[doctype] = occurrence
        if self.fail_on == (doctype, occurrence):
            raise RuntimeError("synthetic persistence secret must not escape")

        if doctype == "NPI Gate Shell" and not values.get("shell_key"):
            values["shell_key"] = (
                f"{values['project_global_id']}:{values['gate_key']}"
            )

        name_field = self.NAME_FIELDS[doctype]
        name = str(values[name_field])
        values["name"] = name
        existing_documents = self.documents.setdefault(doctype, {})
        if doctype == "NPI Project Business Code" and self.inject_business_code_race:
            self.inject_business_code_race = False
            competing = copy.deepcopy(values)
            competing["project_global_id"] = "00000000-0000-4000-8000-000000000099"
            existing_documents[name] = competing
            self.committed_documents.setdefault(doctype, {})[name] = copy.deepcopy(
                competing
            )
            raise StubDuplicateEntryError(name)
        if name in existing_documents:
            raise StubUniqueValidationError(name)
        for unique_field in self.UNIQUE_FIELDS.get(doctype, ()):
            unique_value = values.get(unique_field)
            if any(
                document.get(unique_field) == unique_value
                for document in existing_documents.values()
            ):
                raise StubUniqueValidationError(str(unique_value))

        timestamp = self._clock + timedelta(seconds=sum(self.insert_counts.values()))
        values.setdefault("creation", timestamp)
        values.setdefault("modified", timestamp)
        values.setdefault("modified_by", self._user())
        existing_documents[name] = values
        return values


class StubDatabase:
    def __init__(self, store: StubFrappeStore) -> None:
        self.store = store
        self.rollback_count = 0
        self.commit_count = 0

    def get_value(
        self,
        doctype: str,
        filters: Mapping[str, object] | str,
        fields: list[str] | str,
        *,
        as_dict: bool = False,
    ) -> AttrDict | tuple[object, ...] | object | None:
        if (
            doctype == "NPI Project Idempotency"
            and self.store.stale_idempotency_reads
        ):
            return None
        return self.store.get_value(
            doctype,
            filters,
            fields,
            as_dict=as_dict,
        )

    def rollback(self) -> None:
        self.rollback_count += 1
        self.store.rollback()
        self.store.stale_idempotency_reads = False

    def commit(self) -> None:
        self.commit_count += 1
        self.store.commit()


class StubDoesNotExistError(Exception):
    pass


class StubUniqueValidationError(Exception):
    pass


class StubDuplicateEntryError(Exception):
    pass


class Phase4ProjectApiTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.sessions",
        "npi_core.project.frappe_repository",
        "npi_core.project_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.headers: dict[str, str] = {
            "Idempotency-Key": "phase4-create-project-0001",
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": "trace-phase4-project-api",
        }
        self.roles: dict[str, list[str]] = {
            "Administrator": ["System Manager"],
            "manager@example.invalid": ["System Manager"],
            "external-manager@example.invalid": ["System Manager"],
            "owner@example.invalid": ["NPI User"],
            "unrelated@example.invalid": ["NPI User"],
        }
        self.logged_errors: list[dict[str, object]] = []
        self.logger = StubLogger()

        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.DoesNotExistError = StubDoesNotExistError
        self.frappe.UniqueValidationError = StubUniqueValidationError
        self.frappe.DuplicateEntryError = StubDuplicateEntryError
        self.frappe.PermissionError = type("PermissionError", (Exception,), {})
        self.frappe.ValidationError = type("ValidationError", (Exception,), {})
        self.frappe.session = types.SimpleNamespace(user="Administrator")
        self.frappe.conf = AttrDict(npi_tenant_id="TENANT-A")
        self.frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        self.frappe.local = types.SimpleNamespace(
            response=StubResponse(),
            request=types.SimpleNamespace(path="/", method="GET"),
            form_dict=AttrDict(),
        )
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.get_roles = lambda user: self.roles.get(user, [])
        self.frappe.log_error = lambda **values: self.logged_errors.append(values)
        self.frappe.logger = lambda _name: self.logger

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        self.store = StubFrappeStore(lambda: self.frappe.session.user)
        self.database = StubDatabase(self.store)
        self.frappe.db = self.database

        def get_doc(
            first: object,
            second: object | None = None,
        ):
            if isinstance(first, Mapping) and second is None:
                return StubInsertDocument(self.store, first)
            if isinstance(first, str) and isinstance(second, str):
                if (
                    first == "NPI Project Business Code"
                    and self.store.stale_idempotency_reads
                ):
                    raise StubDoesNotExistError(f"{first} {second} is stale")
                return self.store.get_doc(
                    first,
                    second,
                    StubDoesNotExistError,
                )
            raise AssertionError(f"Unexpected get_doc call: {first!r}, {second!r}")

        self.frappe.get_doc = get_doc

        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.project_api = importlib.import_module("npi_core.project_api")
        self.router = importlib.import_module("npi_core.bff")
        self.domain = importlib.import_module("npi_core.project.domain")
        for user in (
            "Administrator",
            "manager@example.invalid",
            "external-manager@example.invalid",
            "owner@example.invalid",
            "unrelated@example.invalid",
        ):
            self.store.seed(
                "User",
                user,
                {
                    "enabled": 1,
                    "user_type": (
                        "Website User"
                        if user in {
                            "external-manager@example.invalid",
                            "owner@example.invalid",
                            "unrelated@example.invalid",
                        }
                        else "System User"
                    ),
                },
            )
        self._seed_published_template()
        self.store.commit()

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def _seed_published_template(self) -> None:
        self.store.seed(
            "NPI Project Template",
            str(TEMPLATE_ID),
            {
                "global_id": str(TEMPLATE_ID),
                "template_code": "SYNTHETIC-P4-TEST",
                "title": "Synthetic P4 Test Template",
                "enabled": 1,
            },
        )
        draft = self.domain.ProjectTemplateVersion.create_draft(
            template_global_id=TEMPLATE_ID,
            template_code="SYNTHETIC-P4-TEST",
            template_version=1,
            title="Synthetic P4 Test Template",
            applicable_project_types=(
                self.domain.ProjectType.NEW_TOOL,
                self.domain.ProjectType.CUSTOMER_OWNED_TOOL,
            ),
            reference_rules=(
                self.domain.TemplateReferenceRule(
                    self.domain.ProjectReferenceType.CUSTOMER,
                    required=True,
                ),
                self.domain.TemplateReferenceRule(
                    self.domain.ProjectReferenceType.PRODUCT,
                ),
            ),
            gates=(
                self.domain.GateDefinition("G1", "Project Authorization", 2),
                self.domain.GateDefinition("G0", "Feasibility", 1),
            ),
        )
        self.template = draft.publish(expected_version=1)
        self.store.seed(
            "NPI Project Template Version",
            f"{TEMPLATE_ID}:1",
            {
                "global_id": str(self.template.global_id),
                "project_template": str(TEMPLATE_ID),
                "template_global_id": str(TEMPLATE_ID),
                "template_code": self.template.template_code,
                "template_version": 1,
                "version_key": f"{TEMPLATE_ID}:1",
                "optimistic_version": self.template.version,
                "title": self.template.title,
                "publication_state": "published",
                "applicable_project_types": json.dumps(
                    [item.value for item in self.template.applicable_project_types]
                ),
                "reference_rules": [
                    {
                        "reference_type": rule.reference_type.value,
                        "required": rule.required,
                        "allow_multiple": rule.allow_multiple,
                    }
                    for rule in self.template.reference_rules
                ],
                "gates": [
                    {
                        "gate_key": gate.key,
                        "title": gate.title,
                        "sequence": gate.sequence,
                    }
                    for gate in self.template.gates
                ],
                "snapshot_hash": self.template.snapshot_hash,
            },
        )

    def _payload(self, **changes: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "tenantId": "TENANT-A",
            "businessCode": "P4-SYNTHETIC-001",
            "title": "Synthetic New Tool Project",
            "projectType": "new_tool",
            "ownerUserId": "owner@example.invalid",
            "targetSop": "2027-06-30",
            "templateGlobalId": str(TEMPLATE_ID),
            "templateVersion": 1,
            "expectedVersion": self.template.version,
            "references": [
                {
                    "type": "customer",
                    "sourceSystem": "NPI_ONE",
                    "sourceObjectId": "CUSTOMER-SYNTHETIC",
                    "globalId": str(REFERENCE_ID),
                },
                {
                    "type": "product",
                    "sourceSystem": "ERPNEXT",
                    "sourceObjectId": "ITEM-SYNTHETIC",
                },
            ],
        }
        payload.update(changes)
        return payload

    def _reset_response(self) -> None:
        self.frappe.local.response = StubResponse()
        for name in (
            "npi_response_headers",
            "npi_response_body",
            "npi_route_params",
        ):
            try:
                delattr(self.frappe.flags, name)
            except AttributeError:
                pass
        self.frappe.flags.npi_bff_request = False

    def _create(
        self,
        payload: dict[str, object] | None = None,
        **extra_fields: object,
    ) -> dict[str, Any] | None:
        values = self._payload() if payload is None else payload
        self.frappe.local.form_dict = AttrDict(
            {"cmd": "npi_core.project_api.create_project", **values, **extra_fields}
        )
        return self.project_api.create_project(**values, **extra_fields)

    def _get_cockpit(
        self,
        project_id: str,
        **request_fields: object,
    ) -> dict[str, Any] | None:
        self.frappe.flags.npi_route_params = {"project_id": project_id}
        self.frappe.local.form_dict = AttrDict(
            {
                "cmd": "npi_core.project_api.get_project_cockpit",
                **request_fields,
            }
        )
        return self.project_api.get_project_cockpit(**request_fields)

    def assert_problem(
        self,
        result: dict[str, object] | None,
        status: int,
        code: str,
    ) -> dict[str, object]:
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(self.frappe.local.response.http_status_code, status)
        self.assertEqual(result["status"], status)
        self.assertEqual(result["code"], code)
        self.assertEqual(headers["Content-Type"], "application/problem+json")
        self.assertEqual(headers["X-Trace-ID"], result["traceId"])
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        UUID(headers["X-Request-ID"])
        return result

    def _create_and_commit(self) -> dict[str, Any]:
        result = self._create()
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.database.commit()
        return result

    def test_create_requires_authentication_system_manager_and_csrf(self) -> None:
        self.frappe.session.user = "Guest"
        result = self._create()
        self.assert_problem(result, 401, "AUTHENTICATION_REQUIRED")
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

        self._reset_response()
        self.frappe.session.user = "owner@example.invalid"
        result = self._create()
        self.assert_problem(result, 403, "PERMISSION_DENIED")
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

        self._reset_response()
        self.frappe.session.user = "Administrator"
        self.headers.pop("X-Frappe-CSRF-Token")
        result = self._create()
        problem = self.assert_problem(result, 403, "CSRF_TOKEN_INVALID")
        self.assertTrue(problem["retryable"])
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

    def test_create_fails_closed_for_tenant_scope_and_external_manager(self) -> None:
        result = self._create(self._payload(tenantId="TENANT-B"))
        self.assert_problem(result, 403, "PERMISSION_DENIED")
        self.assertEqual(self.store.count("NPI Project Idempotency"), 0)

        self._reset_response()
        del self.frappe.conf["npi_tenant_id"]
        result = self._create()
        self.assert_problem(result, 503, "TENANT_SCOPE_UNAVAILABLE")
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

        self._reset_response()
        self.frappe.conf.npi_tenant_id = "TENANT-A"
        self.frappe.session.user = "external-manager@example.invalid"
        result = self._create()
        self.assert_problem(result, 403, "PERMISSION_DENIED")
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

    def test_create_rejects_extra_fields_and_invalid_command_headers(self) -> None:
        result = self._create(unapproved="must-fail")
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            problem["fieldErrors"],
            [{"path": "unapproved", "message": "This field is not allowed."}],
        )

        self._reset_response()
        self.headers.pop("Idempotency-Key")
        result = self._create()
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "idempotencyKey")

        self._reset_response()
        self.headers["Idempotency-Key"] = "phase4-create-project-0002"
        self.headers["X-Request-ID"] = "not-a-uuid"
        result = self._create()
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "requestId")
        self.assertNotEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            "not-a-uuid",
        )
        self.assertEqual(self.store.count("NPI Project Idempotency"), 0)

    def test_create_rejects_a_disabled_or_unknown_owner_before_persistence(self) -> None:
        self.store.documents["User"]["owner@example.invalid"].enabled = 0

        result = self._create()

        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            problem["fieldErrors"],
            [
                {
                    "path": "ownerUserId",
                    "message": "Select an enabled project owner.",
                }
            ],
        )
        self.assertEqual(self.store.count("NPI Project Idempotency"), 0)
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

    def test_create_rejects_a_disabled_template_before_persistence(self) -> None:
        self.store.documents["NPI Project Template"][str(TEMPLATE_ID)].enabled = 0

        result = self._create()

        problem = self.assert_problem(result, 422, "PROJECT_TEMPLATE_UNAVAILABLE")
        self.assertEqual(problem["fieldErrors"][0]["path"], "templateVersion")
        self.assertEqual(self.store.count("NPI Project Idempotency"), 0)
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

    def test_create_validates_nested_reference_fields_before_persistence(self) -> None:
        references = list(self._payload()["references"])
        references[1] = {
            **references[1],
            "unapproved": "must-fail",
        }
        result = self._create(self._payload(references=references))

        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            problem["fieldErrors"],
            [
                {
                    "path": "references[1].unapproved",
                    "message": "This field is not allowed.",
                }
            ],
        )
        self.assertEqual(self.store.count("NPI Engineering Project"), 0)

    def test_reference_uuid_round_trips_the_openapi_canonical_syntax(self) -> None:
        references = list(self._payload()["references"])
        references[0] = {
            **references[0],
            "globalId": "00000000-0000-0000-0000-000000000000",
        }

        result = self._create(self._payload(references=references))

        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        customer = next(
            reference
            for reference in result["references"]
            if reference["type"] == "customer"
        )
        self.assertEqual(
            customer["globalId"],
            "00000000-0000-0000-0000-000000000000",
        )

    def test_create_returns_201_real_headers_and_exact_live_cockpit(self) -> None:
        result = self._create()
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)

        headers = self.frappe.flags.npi_response_headers
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-Trace-ID"], "trace-phase4-project-api")
        self.assertEqual(headers["X-Request-ID"], REQUEST_ID)
        self.assertEqual(headers["Idempotency-Replayed"], "false")
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(
            set(result),
            {"project", "templateRef", "references", "gates", "permissions"},
        )
        self.assertEqual(
            set(result["project"]),
            {
                "globalId",
                "businessCode",
                "title",
                "projectType",
                "state",
                "version",
                "tenantId",
                "ownerUserId",
                "targetSop",
                "createdAt",
                "lastChangedAt",
                "lastChangedBy",
                "source",
            },
        )
        self.assertEqual(result["project"]["businessCode"], "P4-SYNTHETIC-001")
        self.assertEqual(result["project"]["state"], "draft")
        self.assertEqual(result["project"]["version"], 1)
        self.assertEqual(
            result["project"]["source"],
            {
                "sourceSystem": "NPI_ONE",
                "editableIn": "NPI_ONE",
                "syncState": "local",
            },
        )
        self.assertEqual(result["permissions"], {
            "canView": True,
            "canContribute": True,
            "canAdminister": True,
        })
        self.assertEqual([gate["key"] for gate in result["gates"]], ["G0", "G1"])
        self.assertEqual(
            [gate["state"] for gate in result["gates"]],
            ["not_started", "not_started"],
        )
        self.assertEqual(result["templateRef"]["globalId"], str(TEMPLATE_ID))
        self.assertEqual(
            result["templateRef"]["snapshotHash"],
            self.template.snapshot_hash,
        )
        self.assertEqual(self.store.count("NPI Project Idempotency"), 1)
        self.assertEqual(self.store.count("NPI Project Business Code"), 1)
        self.assertEqual(self.store.count("NPI Engineering Project"), 1)
        self.assertEqual(self.store.count("NPI Gate Shell"), 2)
        self.assertEqual(self.store.count("NPI Audit Event"), 1)
        audit = next(iter(self.store.documents["NPI Audit Event"].values()))
        self.assertEqual(audit.operation, "project.create")
        self.assertEqual(audit.trace_id, "trace-phase4-project-api")
        self.assertNotIn("Idempotency-Key", str(audit.input_summary))

    def test_idempotent_replay_is_stable_and_changed_payload_conflicts(self) -> None:
        created = self._create_and_commit()
        created_id = created["project"]["globalId"]
        counts = {
            doctype: self.store.count(doctype)
            for doctype in (
                "NPI Project Idempotency",
                "NPI Project Business Code",
                "NPI Engineering Project",
                "NPI Gate Shell",
                "NPI Audit Event",
            )
        }
        self.store.documents["User"]["owner@example.invalid"].enabled = 0

        self._reset_response()
        self.headers["X-Request-ID"] = "d90865d7-2114-4fbc-a0a6-f8be8503ac2d"
        replayed = self._create()
        self.assertEqual(replayed["project"]["globalId"], created_id)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            "d90865d7-2114-4fbc-a0a6-f8be8503ac2d",
        )
        self.assertEqual(
            {doctype: self.store.count(doctype) for doctype in counts},
            counts,
        )
        self.assertEqual(replayed["project"]["ownerUserId"], "owner@example.invalid")

        self._reset_response()
        conflict = self._create(self._payload(title="Different payload"))
        self.assert_problem(conflict, 409, "IDEMPOTENCY_KEY_CONFLICT")
        self.assertEqual(
            {doctype: self.store.count(doctype) for doctype in counts},
            counts,
        )

    def test_concurrent_idempotency_loser_refreshes_snapshot_and_replays_winner(self) -> None:
        created = self._create_and_commit()
        project_id = created["project"]["globalId"]
        counts = {
            doctype: self.store.count(doctype)
            for doctype in (
                "NPI Project Idempotency",
                "NPI Project Business Code",
                "NPI Engineering Project",
                "NPI Gate Shell",
                "NPI Audit Event",
            )
        }
        self.store.stale_idempotency_reads = True

        self._reset_response()
        replayed = self._create()

        self.assertEqual(replayed["project"]["globalId"], project_id)
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Idempotency-Replayed"],
            "true",
        )
        self.assertEqual(self.database.rollback_count, 1)
        self.assertEqual(
            {doctype: self.store.count(doctype) for doctype in counts},
            counts,
        )

    def test_persistence_failure_rolls_back_every_partial_record(self) -> None:
        self.store.fail_on = ("NPI Gate Shell", 2)

        result = self._create()

        problem = self.assert_problem(result, 500, "INTERNAL_SERVER_ERROR")
        self.assertTrue(problem["retryable"])
        for doctype in (
            "NPI Project Idempotency",
            "NPI Project Business Code",
            "NPI Engineering Project",
            "NPI Gate Shell",
            "NPI Audit Event",
        ):
            with self.subTest(doctype=doctype):
                self.assertEqual(self.store.count(doctype), 0)
        self.assertEqual(self.database.rollback_count, 1)
        self.assertFalse(
            getattr(self.frappe.flags, "npi_project_command_write", False)
        )
        self.assertFalse(getattr(self.frappe.flags, "npi_audit_append", False))
        self.assertNotIn("synthetic persistence secret", str(problem))
        self.assertNotIn("synthetic persistence secret", str(self.logged_errors))
        self.assertNotIn("synthetic persistence secret", str(self.logger.messages))

    def test_business_code_primary_key_race_returns_conflict_and_rolls_back_loser(self) -> None:
        self.store.inject_business_code_race = True

        result = self._create()

        self.assert_problem(result, 409, "PROJECT_BUSINESS_CODE_CONFLICT")
        self.assertEqual(self.store.count("NPI Project Business Code"), 1)
        reservation = next(
            iter(self.store.documents["NPI Project Business Code"].values())
        )
        self.assertEqual(
            reservation.project_global_id,
            "00000000-0000-4000-8000-000000000099",
        )
        for doctype in (
            "NPI Project Idempotency",
            "NPI Engineering Project",
            "NPI Gate Shell",
            "NPI Audit Event",
        ):
            with self.subTest(doctype=doctype):
                self.assertEqual(self.store.count(doctype), 0)
        self.assertEqual(self.database.rollback_count, 1)

    def test_owner_and_administrator_can_read_with_distinct_permissions(self) -> None:
        created = self._create_and_commit()
        project_id = created["project"]["globalId"]

        self._reset_response()
        self.frappe.session.user = "owner@example.invalid"
        owner_view = self._get_cockpit(project_id)
        self.assertEqual(self.frappe.local.response.http_status_code, 200)
        self.assertEqual(owner_view["project"]["globalId"], project_id)
        self.assertEqual(owner_view["permissions"], {
            "canView": True,
            "canContribute": False,
            "canAdminister": False,
        })

        self._reset_response()
        self.frappe.session.user = "manager@example.invalid"
        manager_view = self._get_cockpit(project_id)
        self.assertEqual(manager_view["permissions"], {
            "canView": True,
            "canContribute": True,
            "canAdminister": True,
        })

    def test_unrelated_and_missing_projects_return_the_same_idor_safe_problem(self) -> None:
        created = self._create_and_commit()
        project_id = created["project"]["globalId"]
        self.frappe.session.user = "unrelated@example.invalid"

        self._reset_response()
        forbidden = self._get_cockpit(project_id)
        forbidden = self.assert_problem(forbidden, 404, "PROJECT_UNAVAILABLE")

        self._reset_response()
        absent = self._get_cockpit("db223d70-cf2e-4579-b9b0-cb186d023cd9")
        absent = self.assert_problem(absent, 404, "PROJECT_UNAVAILABLE")

        for field in ("status", "code", "title", "retryable"):
            self.assertEqual(forbidden[field], absent[field])
        self.assertNotIn("owner", json.dumps(forbidden).casefold())
        self.assertNotIn(project_id, json.dumps(forbidden))

    def test_tenant_mismatch_is_idor_safe_for_owner_and_administrator(self) -> None:
        created = self._create_and_commit()
        project_id = created["project"]["globalId"]
        project = self.store.documents["NPI Engineering Project"][project_id]
        project.tenant_id = "TENANT-B"

        for actor in ("owner@example.invalid", "manager@example.invalid"):
            with self.subTest(actor=actor):
                self.store.documents["NPI Engineering Project"][
                    project_id
                ].tenant_id = "TENANT-B"
                self._reset_response()
                self.frappe.session.user = actor
                result = self._get_cockpit(project_id)
                problem = self.assert_problem(result, 404, "PROJECT_UNAVAILABLE")
                self.assertNotIn(project_id, json.dumps(problem))
                self.assertNotIn("TENANT-B", json.dumps(problem))

    def test_get_rejects_guest_invalid_uuid_and_unexpected_query_fields(self) -> None:
        self.frappe.session.user = "Guest"
        result = self._get_cockpit(str(REFERENCE_ID))
        self.assert_problem(result, 401, "AUTHENTICATION_REQUIRED")

        self._reset_response()
        self.frappe.session.user = "owner@example.invalid"
        result = self._get_cockpit("not-a-uuid")
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(problem["fieldErrors"][0]["path"], "projectId")

        self._reset_response()
        result = self._get_cockpit(str(REFERENCE_ID), expand="all")
        problem = self.assert_problem(result, 422, "VALIDATION_FAILED")
        self.assertEqual(
            problem["fieldErrors"],
            [{"path": "expand", "message": "This field is not allowed."}],
        )

    def test_cockpit_omits_absent_optional_reference_global_id(self) -> None:
        created = self._create_and_commit()
        project_id = created["project"]["globalId"]
        self._reset_response()
        self.frappe.session.user = "owner@example.invalid"

        cockpit = self._get_cockpit(project_id)

        references = {item["type"]: item for item in cockpit["references"]}
        self.assertEqual(references["customer"]["globalId"], str(REFERENCE_ID))
        self.assertNotIn("globalId", references["product"])
        self.assertNotIn(None, references["product"].values())

    def test_bff_mode_preserves_201_and_emits_unwrapped_json(self) -> None:
        self.frappe.flags.npi_bff_request = True

        result = self._create()

        self.assertIsNone(result)
        self.assertEqual(self.frappe.local.response.http_status_code, 201)
        self.assertIn("project", self.frappe.flags.npi_response_body)
        self.assertNotIn("message", self.frappe.flags.npi_response_body)
        response = StubHttpResponse()
        self.router.attach_response_headers(response=response)
        body = json.loads(response.data)
        self.assertEqual(body, self.frappe.flags.npi_response_body)
        self.assertEqual(response.headers["X-Request-ID"], REQUEST_ID)
        self.assertEqual(response.headers["Idempotency-Replayed"], "false")

    def test_bff_maps_only_explicit_create_and_dynamic_cockpit_routes(self) -> None:
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path="/api/npi/v1/projects/", method="POST"
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.project_api.create_project",
        )
        self.assertEqual(self.frappe.flags.npi_route_params, {})

        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{REFERENCE_ID}/cockpit",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.project_api.get_project_cockpit",
        )
        self.assertEqual(
            self.frappe.flags.npi_route_params,
            {"project_id": str(REFERENCE_ID)},
        )

        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path=f"/api/npi/v1/projects/{REFERENCE_ID}/cockpit/extra",
            method="GET",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )

    def test_endpoint_decorators_keep_transport_open_but_domain_checks_closed(self) -> None:
        self.assertEqual(self.project_api.create_project.allowed_methods, ("POST",))
        self.assertTrue(self.project_api.create_project.allow_guest)
        self.assertEqual(
            self.project_api.get_project_cockpit.allowed_methods,
            ("GET",),
        )
        self.assertTrue(self.project_api.get_project_cockpit.allow_guest)


if __name__ == "__main__":
    unittest.main()
