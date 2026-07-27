from __future__ import annotations

import copy
import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


TENANT_ID = "TENANT-A"
OTHER_TENANT_ID = "TENANT-B"
ACTOR = "engineer@example.invalid"
OTHER_ACTOR = "planner@example.invalid"
PROJECT_ID = UUID("263881ed-8fc2-463b-acd8-e519171578fc")
PUBLISHED_VIEW_ID = UUID("d6d1c05b-f5b7-4581-af57-a3a593399abe")
FIRST_REVISION_ID = UUID("fd8d8600-014b-4896-9347-475415364fad")
SECOND_REVISION_ID = UUID("2f2d13d3-b6fc-46e2-84d7-6df070485366")
THIRD_REVISION_ID = UUID("95d625b9-9f0e-48aa-bc14-69b15fca2fc2")
REQUEST_ID = "c52c33c1-5e30-4217-91bb-3565a48283df"
SECOND_REQUEST_ID = UUID("20af16fa-4054-433c-a670-4a147fdba337")
THIRD_REQUEST_ID = UUID("237357be-63e1-4318-89af-d91eecf35372")
TRACE_ID = "trace-r104-repository-api"
PUBLISHED_AT = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)


class AttrDict(dict):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def set(self, name: str, value: Any) -> None:
        self[name] = value


class StubResponse(dict):
    def __getattr__(self, name: str) -> Any:
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class StubDatabase:
    def __init__(self) -> None:
        self.rollback_count = 0
        self.user_types = {
            ACTOR: "System User",
            OTHER_ACTOR: "System User",
            "external@example.invalid": "Website User",
        }

    def get_value(
        self,
        doctype: str,
        name_or_filters: object,
        fieldname: object,
        **_kwargs: object,
    ) -> object | None:
        if doctype == "User" and fieldname == "user_type":
            return self.user_types.get(str(name_or_filters))
        return None

    def rollback(self) -> None:
        self.rollback_count += 1


class MemoryDocument(AttrDict):
    def __init__(
        self,
        values: dict[str, object],
        *,
        insert_callback,
        save_callback,
    ) -> None:
        super().__init__(copy.deepcopy(values))
        self._insert_callback = insert_callback
        self._save_callback = save_callback

    def insert(self):
        self._insert_callback(self)
        return self

    def save(self):
        self._save_callback(self)
        return self


class MemoryPreferenceStore:
    def __init__(self, frappe_module: types.ModuleType) -> None:
        self.frappe = frappe_module
        self.documents: dict[str, MemoryDocument] = {}
        self.find_calls: list[tuple[str, bool]] = []
        self.fail_insert_with_duplicate = False
        self.fail_next_write = False

    def find(self, key_hash: str, *, for_update: bool) -> object | None:
        self.find_calls.append((key_hash, for_update))
        return self.documents.get(key_hash)

    def has_obsolete(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
    ) -> bool:
        return any(
            document.get("tenant_id") == tenant_id
            and document.get("actor_user_id") == actor_user_id
            and document.get("grid_id") == "my-work"
            and document.get("table_schema_version") != "my-work-grid-v1"
            for document in self.documents.values()
        )

    def create(self, values: dict[str, object]) -> MemoryDocument:
        return MemoryDocument(
            values,
            insert_callback=self._insert,
            save_callback=self._save,
        )

    def _insert(self, document: MemoryDocument) -> None:
        self._assert_controlled()
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("Synthetic preference write failure.")
        if self.fail_insert_with_duplicate:
            raise self.frappe.DuplicateEntryError()
        key_hash = str(document["preference_key_hash"])
        if key_hash in self.documents:
            raise self.frappe.DuplicateEntryError()
        self.documents[key_hash] = document

    def _save(self, document: MemoryDocument) -> None:
        self._assert_controlled()
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("Synthetic preference write failure.")
        self.documents[str(document["preference_key_hash"])] = document

    def _assert_controlled(self) -> None:
        if not getattr(
            self.frappe.flags,
            "npi_grid_personalization_write",
            False,
        ):
            raise AssertionError("The preference write escaped its control flag.")


class MemoryPublishedStore:
    def __init__(self, frappe_module: types.ModuleType) -> None:
        self.frappe = frappe_module
        self.roots: dict[UUID, MemoryDocument] = {}
        self.revisions: dict[tuple[UUID, int], MemoryDocument] = {}

    def find_root(self, global_id: UUID, *, for_update: bool) -> object | None:
        del for_update
        return self.roots.get(global_id)

    def find_revision(
        self,
        published_view_global_id: UUID,
        revision_number: int,
    ) -> object | None:
        return self.revisions.get(
            (published_view_global_id, revision_number)
        )

    def create_root(self, values: dict[str, object]) -> MemoryDocument:
        return MemoryDocument(
            values,
            insert_callback=self._insert_root,
            save_callback=self._save_root,
        )

    def create_revision(self, values: dict[str, object]) -> MemoryDocument:
        return MemoryDocument(
            values,
            insert_callback=self._insert_revision,
            save_callback=self._save_revision,
        )

    def _insert_root(self, document: MemoryDocument) -> None:
        self._assert_controlled()
        global_id = UUID(str(document["global_id"]))
        if global_id in self.roots:
            raise self.frappe.DuplicateEntryError()
        self.roots[global_id] = document

    def _save_root(self, document: MemoryDocument) -> None:
        self._assert_controlled()
        self.roots[UUID(str(document["global_id"]))] = document

    def _insert_revision(self, document: MemoryDocument) -> None:
        self._assert_controlled()
        key = (
            UUID(str(document["published_view_global_id"])),
            int(document["revision_number"]),
        )
        if key in self.revisions:
            raise self.frappe.DuplicateEntryError()
        self.revisions[key] = document

    def _save_revision(self, document: MemoryDocument) -> None:
        raise AssertionError(("Published revisions are immutable.", document))

    def _assert_controlled(self) -> None:
        if not getattr(
            self.frappe.flags,
            "npi_grid_personalization_write",
            False,
        ):
            raise AssertionError("The published write escaped its control flag.")


class GridPersonalizationRepositoryApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "frappe.sessions",
        "npi_core.documents.frappe_validation",
        "npi_core.grid_personalization.frappe_validation",
        "npi_core.grid_personalization.frappe_repository",
        "npi_core.grid_personalization_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES
        }
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.headers = {
            "X-Frappe-CSRF-Token": "csrf-" + ("a" * 48),
            "X-Request-ID": REQUEST_ID,
            "X-Trace-ID": TRACE_ID,
        }
        self.frappe = types.ModuleType("frappe")
        self.frappe._ = lambda source: source
        self.frappe.conf = AttrDict(
            npi_tenant_id=TENANT_ID,
            npi_p4_05_routes_disabled=False,
        )
        self.frappe.flags = types.SimpleNamespace(npi_bff_request=False)
        self.frappe.session = types.SimpleNamespace(user=ACTOR)
        self.frappe.local = types.SimpleNamespace(
            form_dict=AttrDict(),
            request=types.SimpleNamespace(path="/", method="GET"),
            response=StubResponse(),
        )
        self.frappe.db = StubDatabase()
        self.frappe.get_roles = lambda _actor: ["NPI API User"]
        self.frappe.get_request_header = lambda name: self.headers.get(name)
        self.frappe.log_error = lambda **_values: None
        self.frappe.logger = lambda _name: types.SimpleNamespace(
            error=lambda *_args, **_kwargs: None
        )
        self.frappe.DuplicateEntryError = type(
            "DuplicateEntryError",
            (Exception,),
            {},
        )
        self.frappe.ValidationError = type(
            "ValidationError",
            (Exception,),
            {},
        )

        def throw(
            message: str,
            exception: type[Exception] = Exception,
        ) -> None:
            raise exception(message)

        self.frappe.throw = throw

        def whitelist(*, methods: list[str], allow_guest: bool = False):
            def decorate(function):
                function.allowed_methods = tuple(methods)
                function.allow_guest = allow_guest
                return function

            return decorate

        self.frappe.whitelist = whitelist
        sessions = types.ModuleType("frappe.sessions")
        sessions.get_csrf_token = lambda: "csrf-" + ("a" * 48)
        self.frappe.sessions = sessions
        sys.modules["frappe"] = self.frappe
        sys.modules["frappe.sessions"] = sessions

        self.repository_module = importlib.import_module(
            "npi_core.grid_personalization.frappe_repository"
        )
        self.validation = importlib.import_module(
            "npi_core.grid_personalization.frappe_validation"
        )
        self.api = importlib.import_module(
            "npi_core.grid_personalization_api"
        )
        self.router = importlib.import_module("npi_core.bff")
        self.domain = importlib.import_module(
            "npi_core.grid_personalization.domain"
        )
        self.security = importlib.import_module("npi_core.foundation.security")
        self.errors = importlib.import_module("npi_core.foundation.errors")
        self.preference_store = MemoryPreferenceStore(self.frappe)
        self.project_ids = frozenset({PROJECT_ID})
        self.factory_calls: list[dict[str, object]] = []

        def repository_factory(**values: object):
            self.factory_calls.append(values)
            return self.repository_module.FrappeGridPersonalizationRepository(
                **values,
                store=self.preference_store,
                accessible_project_loader=lambda: self.project_ids,
                clock=lambda: datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
            )

        self.api._repository_factory = repository_factory

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def principal(
        self,
        *,
        actor: str = ACTOR,
        tenant_id: str = TENANT_ID,
    ):
        return self.security.Principal(
            user_id=actor,
            roles=frozenset({"NPI API User"}),
            tenant_id=tenant_id,
        )

    def repository(
        self,
        *,
        actor: str = ACTOR,
        tenant_id: str = TENANT_ID,
        project_loader=None,
    ):
        return self.repository_module.FrappeGridPersonalizationRepository(
            principal=self.principal(actor=actor, tenant_id=tenant_id),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
            store=self.preference_store,
            accessible_project_loader=(
                project_loader
                if project_loader is not None
                else lambda: self.project_ids
            ),
            clock=lambda: datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
        )

    def preference(
        self,
        *,
        current=None,
        view_id: str = "all",
        search: str = "",
    ):
        source = current or self.domain.PersonalGridPreference.default()
        return source.update(
            view_id=view_id,
            layout=self.domain.GridLayout.default().canonical_dict(),
            filter_snapshot={
                "projectId": None,
                "priority": None,
                "search": search,
            },
            save_filter=True,
            favorite_view_ids=[view_id],
            recent_view_ids=[view_id],
            default_project_id=None,
        )

    def reset_request(self, *, user: str = ACTOR) -> None:
        self.frappe.session.user = user
        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.response = StubResponse()
        self.frappe.flags.npi_bff_request = False
        self.frappe.flags.npi_response_body = None
        self.frappe.flags.npi_response_headers = None

    def call(self, function, payload: dict[str, object]):
        command = (
            "npi_core.grid_personalization_api."
            + function.__name__
        )
        self.frappe.local.form_dict = AttrDict(
            {"cmd": command, **payload}
        )
        return function(**payload)

    def assert_problem(
        self,
        result: object,
        *,
        status: int,
        code: str,
    ) -> dict[str, object]:
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["status"], status)
        self.assertEqual(result["code"], code)
        self.assertEqual(
            self.frappe.local.response.http_status_code,
            status,
        )
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )
        return result

    def put_payload(self, *, expected_version: int = 0) -> dict[str, object]:
        return {
            "expectedVersion": expected_version,
            "tableSchemaVersion": self.domain.TABLE_SCHEMA_VERSION,
            "viewId": "all",
            "layout": self.domain.GridLayout.default().canonical_dict(),
            "filter": {
                "projectId": None,
                "priority": None,
                "search": "",
            },
            "saveFilter": False,
            "favoriteViewIds": ["all"],
            "recentViewIds": ["all"],
            "defaultProjectId": None,
        }

    def published_definition(self, *, search: str = ""):
        return self.domain.PublishedGridViewDefinition.parse(
            {
                "viewId": "all",
                "layout": self.domain.GridLayout.default().canonical_dict(),
                "filter": {
                    "projectId": str(PROJECT_ID),
                    "priority": None,
                    "search": search,
                },
            }
        )

    def authority(self):
        return self.domain.PublicationAuthorityDecision(
            allowed=True,
            reason_code="verified_test_fixture",
            evidence={
                "bindings": [{"members": [ACTOR]}],
                "policy": {"version": 1},
            },
        )

    def published_revision(
        self,
        *,
        global_id: UUID,
        revision_number: int,
        request_id: UUID,
        definition,
        prior_revision=None,
        restored_from_revision=None,
    ):
        return self.domain.PublishedGridViewRevision.create(
            global_id=global_id,
            published_view_global_id=PUBLISHED_VIEW_ID,
            tenant_id=TENANT_ID,
            project_global_id=PROJECT_ID,
            revision_number=revision_number,
            prior_revision=prior_revision,
            restored_from_revision=restored_from_revision,
            name=f"Published My Work {revision_number}",
            description=f"Controlled revision {revision_number}",
            definition=definition,
            published_by=ACTOR,
            published_at=PUBLISHED_AT + timedelta(minutes=revision_number),
            authority=self.authority(),
            request_id=request_id,
            trace_id=TRACE_ID,
        )

    def test_personal_key_isolated_by_actor_and_tenant(self) -> None:
        repositories = (
            self.repository(),
            self.repository(actor=OTHER_ACTOR),
            self.repository(tenant_id=OTHER_TENANT_ID),
        )
        self.assertEqual(len({repo.key_hash for repo in repositories}), 3)

        first = repositories[0]
        first.save(
            self.preference(),
            expected_version=0,
            changed_view_id="all",
        )
        self.assertEqual(first.load().source, "stored")
        self.assertEqual(repositories[1].load().source, "default")
        self.assertEqual(repositories[2].load().source, "default")
        self.assertEqual(
            {key for key, _locked in self.preference_store.find_calls[-3:]},
            {repo.key_hash for repo in repositories},
        )

    def test_personal_load_default_stored_and_corrupt_fallback(self) -> None:
        repository = self.repository()
        loaded = repository.load()
        self.assertEqual(loaded.source, "default")
        self.assertEqual(loaded.preference.version, 0)

        saved = self.preference(search="fixture inspection")
        repository.save(
            saved,
            expected_version=0,
            changed_view_id="all",
        )
        loaded = repository.load()
        self.assertEqual(loaded.source, "stored")
        self.assertEqual(loaded.preference, saved)

        document = self.preference_store.documents[repository.key_hash]
        document["preference_snapshot"] = '{"tableSchemaVersion":'
        loaded = repository.load()
        self.assertEqual(loaded.source, "default")
        self.assertEqual(loaded.reason_code, "stored_preference_invalid")
        self.assertEqual(loaded.preference.version, 1)
        self.reset_request()
        response = self.call(
            self.api.get_my_work_grid_preferences,
            {},
        )
        self.assertEqual(
            response["recoveryReason"],
            "stored_preference_invalid",
        )

        document["optimistic_version"] = 0
        loaded = repository.load()
        self.assertEqual(loaded.source, "default")
        self.assertEqual(loaded.reason_code, "stored_preference_invalid")
        self.assertEqual(loaded.preference.version, 0)
        repaired = self.preference()
        repository.save(
            repaired,
            expected_version=0,
            changed_view_id="all",
        )
        self.assertEqual(repository.load().preference, repaired)

    def test_obsolete_schema_row_returns_stable_default_reason(self) -> None:
        repository = self.repository()
        obsolete_key = "f" * 64
        self.preference_store.documents[obsolete_key] = MemoryDocument(
            {
                "tenant_id": TENANT_ID,
                "actor_user_id": ACTOR,
                "grid_id": "my-work",
                "table_schema_version": "my-work-grid-obsolete",
            },
            insert_callback=lambda _document: None,
            save_callback=lambda _document: None,
        )

        loaded = repository.load()

        self.assertEqual(loaded.source, "default")
        self.assertEqual(loaded.preference.version, 0)
        self.assertEqual(loaded.reason_code, "stored_preference_invalid")

    def test_personal_insert_update_conflicts_and_flag_restoration(self) -> None:
        repository = self.repository()
        first = self.preference()
        repository.save(
            first,
            expected_version=0,
            changed_view_id="all",
        )
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_grid_personalization_write",
            )
        )

        with self.assertRaises(self.errors.VersionConflict):
            repository.save(
                first,
                expected_version=0,
                changed_view_id="all",
            )

        second = self.preference(current=first, search="drawing")
        repository.save(
            second,
            expected_version=1,
            changed_view_id="all",
        )
        self.assertEqual(repository.load().preference, second)

        stale = self.preference(current=first, search="stale")
        with self.assertRaises(self.errors.VersionConflict):
            repository.save(
                stale,
                expected_version=1,
                changed_view_id="all",
            )

        self.frappe.flags.npi_grid_personalization_write = "previous"
        self.preference_store.fail_next_write = True
        failing = self.preference(current=second, search="failure")
        with self.assertRaisesRegex(
            RuntimeError,
            "Synthetic preference write failure",
        ):
            repository.save(
                failing,
                expected_version=2,
                changed_view_id="all",
            )
        self.assertEqual(
            self.frappe.flags.npi_grid_personalization_write,
            "previous",
        )

    def test_personal_duplicate_insert_is_version_conflict(self) -> None:
        self.preference_store.fail_insert_with_duplicate = True
        with self.assertRaises(self.errors.VersionConflict):
            self.repository().save(
                self.preference(),
                expected_version=0,
                changed_view_id="all",
            )
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_grid_personalization_write",
            )
        )

    def test_accessible_project_loader_requires_canonical_uuid_set(self) -> None:
        valid = self.repository(
            project_loader=lambda: frozenset({PROJECT_ID})
        )
        self.assertEqual(valid.accessible_project_ids(), frozenset({PROJECT_ID}))

        invalid_values = (
            {PROJECT_ID},
            frozenset({str(PROJECT_ID)}),
            frozenset({UUID(int=0)}),
        )
        for values in invalid_values:
            with self.subTest(values=values):
                repository = self.repository(
                    project_loader=lambda values=values: values
                )
                with self.assertRaisesRegex(
                    RuntimeError,
                    "access projection is invalid",
                ):
                    repository.accessible_project_ids()

    def test_datetime_immutable_comparison_is_storage_type_aware(self) -> None:
        current = AttrDict(
            created_at="2026-07-26 09:00:00.000000",
            global_id=str(PUBLISHED_VIEW_ID),
        )
        previous = AttrDict(
            created_at=datetime(2026, 7, 26, 9, 0),
            global_id=str(PUBLISHED_VIEW_ID),
        )

        self.validation.require_immutable_fields(
            current,
            previous,
            ("global_id", "created_at"),
        )
        current["created_at"] = "2026-07-26 09:00:01.000000"
        with self.assertRaises(self.frappe.ValidationError):
            self.validation.require_immutable_fields(
                current,
                previous,
                ("global_id", "created_at"),
            )

    def test_api_get_and_put_are_actor_bound_and_cache_private(self) -> None:
        result = self.call(
            self.api.get_my_work_grid_preferences,
            {},
        )
        self.assertEqual(result["version"], 0)
        self.assertEqual(result["gridId"], "my-work")
        self.assertEqual(
            self.frappe.flags.npi_response_headers["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            self.factory_calls[-1]["principal"].user_id,
            ACTOR,
        )

        self.reset_request()
        result = self.call(
            self.api.set_my_work_grid_preferences,
            self.put_payload(),
        )
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["favoriteViewIds"], ["all"])
        self.assertEqual(
            self.frappe.flags.npi_response_headers["X-Request-ID"],
            REQUEST_ID,
        )

    def test_api_guest_and_external_access_fail_closed(self) -> None:
        for user, status, code in (
            ("Guest", 401, "AUTHENTICATION_REQUIRED"),
            ("external@example.invalid", 403, "PERMISSION_DENIED"),
        ):
            with self.subTest(user=user):
                self.reset_request(user=user)
                problem = self.call(
                    self.api.get_my_work_grid_preferences,
                    {"owner": ACTOR},
                )
                self.assert_problem(problem, status=status, code=code)

    def test_api_get_rejects_extra_fields_after_authentication(self) -> None:
        problem = self.call(
            self.api.get_my_work_grid_preferences,
            {"owner": ACTOR},
        )
        validated = self.assert_problem(
            problem,
            status=422,
            code="VALIDATION_FAILED",
        )
        self.assertEqual(validated["fieldErrors"][0]["path"], "owner")

    def test_api_put_requires_csrf_and_exact_complete_fields(self) -> None:
        self.headers.pop("X-Frappe-CSRF-Token")
        problem = self.call(
            self.api.set_my_work_grid_preferences,
            self.put_payload(),
        )
        self.assert_problem(
            problem,
            status=403,
            code="CSRF_TOKEN_INVALID",
        )
        self.headers["X-Frappe-CSRF-Token"] = "csrf-" + ("a" * 48)

        self.reset_request()
        extra = {**self.put_payload(), "owner": ACTOR}
        problem = self.call(
            self.api.set_my_work_grid_preferences,
            extra,
        )
        validated = self.assert_problem(
            problem,
            status=422,
            code="VALIDATION_FAILED",
        )
        self.assertEqual(validated["fieldErrors"][0]["path"], "owner")

        self.reset_request()
        missing = self.put_payload()
        missing.pop("layout")
        problem = self.call(
            self.api.set_my_work_grid_preferences,
            missing,
        )
        validated = self.assert_problem(
            problem,
            status=422,
            code="VALIDATION_FAILED",
        )
        self.assertEqual(validated["fieldErrors"][0]["path"], "layout")

    def test_api_put_maps_domain_validation_and_version_conflict(self) -> None:
        invalid = self.put_payload()
        invalid["layout"] = {
            **invalid["layout"],
            "hiddenColumnIds": ["item"],
        }
        problem = self.call(
            self.api.set_my_work_grid_preferences,
            invalid,
        )
        validated = self.assert_problem(
            problem,
            status=422,
            code="VALIDATION_FAILED",
        )
        self.assertEqual(
            validated["fieldErrors"][0]["path"],
            "layout.hiddenColumnIds",
        )

        self.reset_request()
        self.call(
            self.api.set_my_work_grid_preferences,
            self.put_payload(),
        )
        self.reset_request()
        problem = self.call(
            self.api.set_my_work_grid_preferences,
            self.put_payload(),
        )
        self.assert_problem(
            problem,
            status=409,
            code="VERSION_CONFLICT",
        )

    def test_bff_maps_only_fixed_get_and_put_preference_routes(self) -> None:
        expected_commands = {
            "GET": (
                "npi_core.grid_personalization_api."
                "get_my_work_grid_preferences"
            ),
            "PUT": (
                "npi_core.grid_personalization_api."
                "set_my_work_grid_preferences"
            ),
        }
        path = "/api/npi/v1/me/preferences/my-work-grid"
        for method, command in expected_commands.items():
            with self.subTest(method=method):
                self.frappe.local.form_dict = AttrDict()
                self.frappe.local.request = types.SimpleNamespace(
                    path=path,
                    method=method,
                )
                self.router.route_request()
                self.assertEqual(
                    self.frappe.local.form_dict.cmd,
                    command,
                )
                self.assertEqual(self.frappe.flags.npi_route_params, {})
                self.assertTrue(
                    self.router._requires_project_request_id(method, path)
                )

        self.frappe.local.form_dict = AttrDict()
        self.frappe.local.request = types.SimpleNamespace(
            path=path,
            method="POST",
        )
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.bff.route_not_found",
        )

    def test_published_repository_persists_exact_restore_lineage(self) -> None:
        store = MemoryPublishedStore(self.frappe)
        repository = self.repository_module.FrappePublishedGridViewRepository(
            principal=self.principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
            store=store,
        )
        first = self.published_revision(
            global_id=FIRST_REVISION_ID,
            revision_number=1,
            request_id=UUID(REQUEST_ID),
            definition=self.published_definition(search="first"),
        )
        first_root = self.domain.PublishedGridViewRoot.from_first_revision(
            first
        )
        repository.persist_first(root=first_root, revision=first)
        first_document = store.revisions[(PUBLISHED_VIEW_ID, 1)]
        expected_authority_evidence = {
            "bindings": [{"members": [ACTOR]}],
            "policy": {"version": 1},
        }
        self.assertEqual(
            json.loads(first_document["authority_evidence"]),
            expected_authority_evidence,
        )
        first_snapshot = json.loads(first_document["revision_snapshot"])
        self.assertEqual(
            first_snapshot["authorityEvidence"],
            expected_authority_evidence,
        )
        self.assertEqual(
            first_document["snapshot_hash"],
            self.domain.canonical_hash(first_snapshot),
        )

        second = self.published_revision(
            global_id=SECOND_REVISION_ID,
            revision_number=2,
            request_id=SECOND_REQUEST_ID,
            definition=self.published_definition(search="second"),
            prior_revision=first.reference,
        )
        second_root = first_root.advance(second)
        repository = self.repository_module.FrappePublishedGridViewRepository(
            principal=self.principal(),
            request_id=str(SECOND_REQUEST_ID),
            trace_id=TRACE_ID,
            store=store,
        )
        repository.append(
            root=second_root,
            revision=second,
            expected_version=1,
        )

        forged_restore = self.published_revision(
            global_id=THIRD_REVISION_ID,
            revision_number=3,
            request_id=THIRD_REQUEST_ID,
            definition=first.definition,
            prior_revision=second.reference,
            restored_from_revision=first.reference,
        )
        forged_root = second_root.advance(forged_restore)
        repository = self.repository_module.FrappePublishedGridViewRepository(
            principal=self.principal(),
            request_id=str(THIRD_REQUEST_ID),
            trace_id=TRACE_ID,
            store=store,
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "rollback content does not match",
        ):
            repository.append(
                root=forged_root,
                revision=forged_restore,
                expected_version=2,
            )

        restored = self.domain.rollback_as_new_revision(
            root=second_root,
            current_revision=second,
            target_revision=first,
            published_by=ACTOR,
            published_at=PUBLISHED_AT + timedelta(minutes=3),
            authority=self.authority(),
            request_id=THIRD_REQUEST_ID,
            trace_id=TRACE_ID,
        )
        restored_root = second_root.advance(restored)
        result = repository.append(
            root=restored_root,
            revision=restored,
            expected_version=2,
        )

        self.assertEqual(result.current_revision, restored.reference)
        self.assertEqual(len(store.revisions), 3)
        revision_document = store.revisions[(PUBLISHED_VIEW_ID, 3)]
        self.assertEqual(
            revision_document["prior_revision_global_id"],
            str(SECOND_REVISION_ID),
        )
        self.assertEqual(
            revision_document["restored_from_revision_global_id"],
            str(FIRST_REVISION_ID),
        )
        self.assertFalse(
            hasattr(
                self.frappe.flags,
                "npi_grid_personalization_write",
            )
        )

    def test_published_repository_rejects_stale_and_corrupt_lineage(self) -> None:
        store = MemoryPublishedStore(self.frappe)
        repository = self.repository_module.FrappePublishedGridViewRepository(
            principal=self.principal(),
            request_id=REQUEST_ID,
            trace_id=TRACE_ID,
            store=store,
        )
        first = self.published_revision(
            global_id=FIRST_REVISION_ID,
            revision_number=1,
            request_id=UUID(REQUEST_ID),
            definition=self.published_definition(),
        )
        first_root = self.domain.PublishedGridViewRoot.from_first_revision(
            first
        )
        repository.persist_first(root=first_root, revision=first)

        second = self.published_revision(
            global_id=SECOND_REVISION_ID,
            revision_number=2,
            request_id=SECOND_REQUEST_ID,
            definition=self.published_definition(search="second"),
            prior_revision=first.reference,
        )
        second_root = first_root.advance(second)
        repository = self.repository_module.FrappePublishedGridViewRepository(
            principal=self.principal(),
            request_id=str(SECOND_REQUEST_ID),
            trace_id=TRACE_ID,
            store=store,
        )
        with self.assertRaises(self.errors.VersionConflict):
            repository.append(
                root=second_root,
                revision=second,
                expected_version=2,
            )

        store.revisions[(PUBLISHED_VIEW_ID, 1)]["snapshot_hash"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "lineage is invalid"):
            repository.append(
                root=second_root,
                revision=second,
                expected_version=1,
            )


if __name__ == "__main__":
    unittest.main()
