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
    __setattr__ = dict.__setitem__

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


class FakeDocument(AttrDict):
    def __init__(self, owner: "ProjectionRepositoryTest", values: dict[str, object]):
        super().__init__(values)
        self.owner = owner
        self.flags = types.SimpleNamespace()

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
        elif self.doctype == "User":
            self.name = self.email
            if self.name in self.owner.users:
                raise self.owner.frappe.DuplicateEntryError()
            self.user_type = (
                "System User"
                if [role.get("role") for role in self.roles] == ["Desk User"]
                else "Website User"
            )
            self.owner.users[self.name] = self
            self.owner.user_writes.append((self.name, "created", int(self.enabled)))
        else:
            raise AssertionError(self.doctype)
        return self

    def save(self, *, ignore_permissions: bool = False):
        if not ignore_permissions:
            raise AssertionError("Controlled save expected.")
        if self.doctype == "NPI Authorization Projection":
            self.owner.projections[self.name] = self
        elif self.doctype == "User":
            self.owner.users[self.name] = self
            self.owner.user_writes.append((self.name, "saved", int(self.enabled)))
        else:
            raise AssertionError("Controlled projection or User save expected.")
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
        self.user_writes: list[tuple[str, str, int]] = []
        self.users = {
            ACTOR: {
                "doctype": "User",
                "name": ACTOR,
                "email": ACTOR,
                "enabled": 1,
                "user_type": "System User",
                "roles": [{"role": "NPI API User"}],
            },
            TARGET: {
                "doctype": "User",
                "name": TARGET,
                "email": TARGET,
                "enabled": 1,
                "user_type": "System User",
                "roles": [{"role": "Desk User"}],
            },
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.flags = types.SimpleNamespace()
        frappe.session = types.SimpleNamespace(user=ACTOR)
        frappe.conf = {
            "npi_p9_04_authorization_role_allowlist": ["NPI Engineer", "NPI Reviewer"],
            "npi_p9_04_authorization_max_ttl_seconds": 7200,
        }
        frappe.get_roles = lambda user: [
            str(role["role"])
            for role in self.users.get(user, {}).get("roles", [])
        ]
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
                if args[0] == "NPI Authorization Projection":
                    document = self.projections.get(str(args[1]))
                elif args[0] == "User":
                    values = self.users.get(str(args[1]))
                    document = (
                        values
                        if isinstance(values, FakeDocument)
                        else FakeDocument(self, dict(values)) if values else None
                    )
                else:
                    raise AssertionError((args, kwargs))
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
        self.assertEqual(disabled.local_user_state, "disabled")
        self.assertEqual(disabled.local_user_disposition, "disabled")
        self.assertEqual(int(self.users[TARGET]["enabled"]), 0)
        self.assertEqual(len(self.projections), 1)
        self.assertEqual(len(self.audits), 3)
        self.assertEqual([audit.result for audit in self.audits], ["created", "replaced", "disabled"])

    def test_stale_conflict_unapproved_role_and_website_target_fail_closed(self) -> None:
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
        self.users[TARGET]["user_type"] = "Website User"
        with self.assertRaises(PermissionDenied):
            self.repository().apply(
                AuthorizationProjectionEvent.from_mapping(
                    event_mapping(
                        eventId=str(UUID(int=912)),
                        sourceVersion=2,
                    )
                )
            )

    def test_missing_user_is_passwordless_provisioned_replayed_disabled_and_enabled(self) -> None:
        self.users.pop(TARGET)
        first_event = AuthorizationProjectionEvent.from_mapping(event_mapping())
        first = self.repository().apply(first_event)
        replay = self.repository().apply(first_event)
        user = self.users[TARGET]

        self.assertEqual(first.local_user_state, "enabled")
        self.assertEqual(first.local_user_disposition, "created")
        self.assertEqual(replay.local_user_disposition, "exact_replay")
        self.assertEqual(user["first_name"], "member")
        self.assertEqual(user["roles"], [{"role": "Desk User"}])
        self.assertEqual(user["send_welcome_email"], 0)
        self.assertNotIn("new_password", user)

        disabled = self.repository().apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    eventId=str(UUID(int=920)),
                    sourceVersion=2,
                    enabled=False,
                    roles=[],
                    projectAccess=[],
                    organizationScopes=[],
                )
            )
        )
        enabled = self.repository().apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    eventId=str(UUID(int=921)),
                    sourceVersion=3,
                )
            )
        )
        self.assertEqual(disabled.local_user_disposition, "disabled")
        self.assertEqual(enabled.local_user_disposition, "enabled")
        self.assertEqual(int(self.users[TARGET]["enabled"]), 1)
        self.assertEqual(
            self.user_writes,
            [
                (TARGET, "created", 1),
                (TARGET, "saved", 0),
                (TARGET, "saved", 1),
            ],
        )

    def test_disabled_absent_user_and_existing_manager_follow_erp_truth(self) -> None:
        self.users.pop(TARGET)
        disabled = self.repository().apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    enabled=False,
                    roles=[],
                    projectAccess=[],
                    organizationScopes=[],
                )
            )
        )
        self.assertEqual(disabled.local_user_state, "absent_disabled")
        self.assertNotIn(TARGET, self.users)

        privileged = "manager@example.invalid"
        self.users[privileged] = {
            "doctype": "User",
            "name": privileged,
            "email": privileged,
            "enabled": 1,
            "user_type": "System User",
            "roles": [{"role": "System Manager"}],
        }
        adopted = self.repository().apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    eventId=str(UUID(int=922)),
                    targetUserId=privileged,
                )
            )
        )
        revoked = self.repository().apply(
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    eventId=str(UUID(int=923)),
                    targetUserId=privileged,
                    sourceVersion=2,
                    enabled=False,
                    roles=[],
                    projectAccess=[],
                    organizationScopes=[],
                )
            )
        )
        self.assertEqual(adopted.local_user_disposition, "retained")
        self.assertEqual(revoked.local_user_disposition, "disabled")
        self.assertEqual(int(self.users[privileged]["enabled"]), 0)

        with self.assertRaises(PermissionDenied):
            self.repository().apply(
                AuthorizationProjectionEvent.from_mapping(
                    event_mapping(
                        eventId=str(UUID(int=924)),
                        targetUserId=ACTOR,
                    )
                )
            )

    def test_exact_replay_rejects_projection_or_local_user_drift(self) -> None:
        event = AuthorizationProjectionEvent.from_mapping(event_mapping())
        self.repository().apply(event)
        projection = next(iter(self.projections.values()))
        projection.projection_hash = "0" * 64
        with self.assertRaises(VersionConflict):
            self.repository().apply(event)

        projection.projection_hash = event.projection_hash
        self.users[TARGET]["enabled"] = 0
        with self.assertRaises(VersionConflict):
            self.repository().apply(event)

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
