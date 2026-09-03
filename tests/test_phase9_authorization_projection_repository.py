from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "apps/npi_core"), str(ROOT / "apps/npi_integration")]

from npi_core.foundation.errors import PermissionDenied, VersionConflict
from npi_integration.authorization_projection.domain import (
    AuthorizationProjectionEvent,
    canonical_hash,
)


NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)
ACTOR = "erp-authorization-service@example.invalid"
TARGET = "member@example.invalid"


def event_mapping(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sourceSubjectId": "entra-subject-001",
        "targetUserId": TARGET,
        "sourceVersion": 1,
        "enabled": True,
        "roles": ["NPI Engineer"],
        "projectAccess": [
            {"projectId": str(UUID(int=904)), "access": "contribute"}
        ],
        "organizationScopes": [
            {"kind": "Company", "referenceKey": "company-reference-01"}
        ],
        "issuedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiresAt": (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    result: dict[str, object] = {
        "schemaVersion": 1,
        "operation": "replace_user_authorization",
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "objectType": "UserAuthorizationProjection",
        "eventId": str(UUID(int=900)),
        **payload,
        "traceId": "trace-p904-repository",
        "payloadHash": canonical_hash(payload),
    }
    result.update(changes)
    if set(changes).intersection(payload):
        result["payloadHash"] = canonical_hash({key: result[key] for key in payload})
    return result


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class FakeDocument(AttrDict):
    def __init__(self, owner: "ProjectionRepositoryTest", values: dict[str, object]):
        super().__init__(values)
        self.owner = owner

    def insert(self, *, ignore_permissions: bool = False):
        if not ignore_permissions:
            raise AssertionError("Controlled inserts must use the capability wrapper.")
        if self.doctype == "NPI Authorization Projection":
            self.name = self.global_id
            if self.name in self.owner.projections:
                raise self.owner.frappe.DuplicateEntryError()
            self.owner.projections[self.name] = self
        elif self.doctype == "NPI Audit Event":
            self.owner.audits.append(self)
        else:
            raise AssertionError(self.doctype)
        return self

    def save(self, *, ignore_permissions: bool = False):
        if not ignore_permissions or self.doctype != "NPI Authorization Projection":
            raise AssertionError("Controlled projection save expected.")
        self.owner.projections[self.name] = self
        return self

    def update(self, values: dict[str, object]) -> None:
        dict.update(self, values)


class FakeDatabase:
    def __init__(self, owner: "ProjectionRepositoryTest") -> None:
        self.owner = owner

    def get_value(self, doctype, name, fields, *, as_dict=False):
        if doctype == "User":
            record = self.owner.users.get(str(name))
            if not record:
                return None
            if fields == ["enabled", "user_type"] and as_dict:
                return dict(record)
            raise AssertionError((doctype, name, fields, as_dict))
        if doctype == "NPI Authorization Projection":
            record = self.owner.projections.get(str(name))
            if record is None or not as_dict:
                return None
            return {field: record.get(field) for field in fields}
        raise AssertionError((doctype, name, fields, as_dict))


class ProjectionRepositoryTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.authorization_projection.frappe_validation",
        "npi_integration.authorization_projection.frappe_repository",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.projections: dict[str, FakeDocument] = {}
        self.audits: list[FakeDocument] = []
        self.users = {
            ACTOR: {"enabled": 1, "user_type": "System User"},
            TARGET: {"enabled": 1, "user_type": "System User"},
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user=ACTOR)
        frappe.conf = {
            "npi_p9_04_authorization_role_allowlist": ["NPI Engineer", "NPI Reviewer"],
            "npi_p9_04_authorization_max_ttl_seconds": 7200,
        }
        frappe.get_roles = lambda user: ["NPI API User"] if user == ACTOR else []
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.ValidationError = type("ValidationError", (Exception,), {})
        frappe.DoesNotExistError = type("DoesNotExistError", (Exception,), {})
        frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        frappe.throw = lambda message, exception: (_ for _ in ()).throw(exception(message))
        frappe.db = FakeDatabase(self)

        def get_doc(*args, **kwargs):
            if len(args) == 1 and isinstance(args[0], dict):
                return FakeDocument(self, dict(args[0]))
            if len(args) == 2 and kwargs == {"for_update": True}:
                document = self.projections.get(str(args[1]))
                if document is None:
                    raise frappe.DoesNotExistError()
                return document
            raise AssertionError((args, kwargs))

        frappe.get_doc = get_doc
        self.frappe = frappe
        sys.modules["frappe"] = frappe
        self.module = importlib.import_module(
            "npi_integration.authorization_projection.frappe_repository"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def repository(self):
        return self.module.FrappeAuthorizationProjectionRepository(
            actor=ACTOR,
            tenant_id="tenant-p904",
            request_id=UUID(int=901),
            now=NOW,
        )

    def test_create_exact_replay_replace_and_disable_are_atomic_and_audited(self) -> None:
        first = AuthorizationProjectionEvent.from_mapping(event_mapping())
        created = self.repository().apply(first)
        replayed = self.repository().apply(first)
        replaced_event = AuthorizationProjectionEvent.from_mapping(
            event_mapping(
                eventId=str(UUID(int=902)),
                sourceVersion=2,
                roles=["NPI Reviewer"],
            )
        )
        replaced = self.repository().apply(replaced_event)
        disabled_event = AuthorizationProjectionEvent.from_mapping(
            event_mapping(
                eventId=str(UUID(int=903)),
                sourceVersion=3,
                enabled=False,
                roles=[],
                projectAccess=[],
                organizationScopes=[],
            )
        )
        disabled = self.repository().apply(disabled_event)

        self.assertEqual(created.state, "enabled")
        self.assertTrue(replayed.exact_replay)
        self.assertEqual(replaced.source_version, 2)
        self.assertEqual(disabled.state, "disabled")
        self.assertEqual(len(self.projections), 1)
        self.assertEqual(len(self.audits), 3)
        self.assertEqual([audit.result for audit in self.audits], ["created", "replaced", "disabled"])

    def test_stale_conflict_unapproved_role_and_disabled_target_fail_closed(self) -> None:
        first = AuthorizationProjectionEvent.from_mapping(event_mapping())
        self.repository().apply(first)
        with self.assertRaises(VersionConflict):
            self.repository().apply(
                AuthorizationProjectionEvent.from_mapping(
                    event_mapping(eventId=str(UUID(int=910)))
                )
            )
        with self.assertRaises(PermissionDenied):
            self.repository().apply(
                AuthorizationProjectionEvent.from_mapping(
                    event_mapping(
                        eventId=str(UUID(int=911)),
                        sourceVersion=2,
                        roles=["System Manager"],
                    )
                )
            )
        self.users[TARGET]["enabled"] = 0
        with self.assertRaises(PermissionDenied):
            self.repository().apply(
                AuthorizationProjectionEvent.from_mapping(
                    event_mapping(
                        eventId=str(UUID(int=912)),
                        sourceVersion=2,
                    )
                )
            )

    def test_resolver_returns_only_current_hash_valid_projection(self) -> None:
        event = AuthorizationProjectionEvent.from_mapping(event_mapping())
        result = self.repository().apply(event)
        resolved = self.module.resolve_authorization_projection(TARGET, "tenant-p904", NOW)
        self.assertEqual(resolved["roles"], ("NPI Engineer",))
        self.assertEqual(
            resolved["project_access"][str(UUID(int=904))], "contribute"
        )
        self.assertEqual(resolved["projection_hash"], result.projection_hash)

        document = next(iter(self.projections.values()))
        document.roles = json.dumps(["NPI Reviewer"])
        self.assertIsNone(
            self.module.resolve_authorization_projection(TARGET, "tenant-p904", NOW)
        )


if __name__ == "__main__":
    unittest.main()
