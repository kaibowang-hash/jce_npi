from __future__ import annotations

import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))

from npi_core.foundation.errors import AuthenticationRequired, PermissionDenied
from npi_core.foundation.security import authorize_organization
from npi_core.request_security import authenticated_principal


class FakeDatabase:
    def __init__(self, *, enabled: int = 1, user_type: str = "System User") -> None:
        self.enabled = enabled
        self.user_type = user_type

    def get_value(self, doctype, name, field):
        if doctype != "User" or name != "member@example.invalid":
            return None
        if field == "user_type":
            return self.user_type
        if field == "enabled":
            return self.enabled
        raise AssertionError("Only the required local User fields may be read.")


def frappe_module(*, enforced: bool, projection: object, enabled: int = 1):
    module = types.ModuleType("frappe")
    module.session = types.SimpleNamespace(user="member@example.invalid")
    module.conf = {
        "npi_tenant_id": "tenant-p904",
        "npi_p9_04_authorization_projection_enforced": enforced,
    }
    module.db = FakeDatabase(enabled=enabled)
    module.get_roles = lambda _actor: ["NPI Engineer", "Local Untrusted Role"]
    module.get_hooks = lambda name: (
        ["tests.p904.resolve"]
        if name == "npi_authorization_projection_resolver"
        else []
    )
    module.get_attr = lambda _path: (lambda _actor, _tenant, _now: projection)
    return module


def projection(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "user_id": "member@example.invalid",
        "tenant_id": "tenant-p904",
        "enabled": True,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "roles": ("NPI Engineer",),
        "project_access": {str(UUID(int=20)): "contribute"},
        "organization_scopes": {
            "Company": ("company-ref-01",),
            "Customer": (),
            "Supplier": (),
        },
        "projection_hash": "a" * 64,
    }
    value.update(changes)
    return value


class Phase9AuthorizationProjectionSecurityTest(unittest.TestCase):
    def test_existing_roles_are_retained_before_explicit_activation(self) -> None:
        with patch.dict(
            sys.modules,
            {"frappe": frappe_module(enforced=False, projection=None)},
        ):
            principal = authenticated_principal()
        self.assertEqual(
            principal.roles,
            frozenset({"NPI Engineer", "Local Untrusted Role"}),
        )

    def test_active_projection_replaces_roles_and_supplies_scopes(self) -> None:
        with patch.dict(
            sys.modules,
            {"frappe": frappe_module(enforced=True, projection=projection())},
        ):
            principal = authenticated_principal()
        self.assertEqual(principal.roles, frozenset({"NPI Engineer"}))
        self.assertEqual(
            principal.project_access[str(UUID(int=20))].value,
            "contribute",
        )
        self.assertEqual(
            principal.organization_scopes["Company"],
            frozenset({"company-ref-01"}),
        )

    def test_unknown_disabled_stale_or_unmapped_principal_fails_closed(self) -> None:
        cases = (
            None,
            projection(enabled=False),
            projection(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
            projection(user_id="different@example.invalid"),
            projection(project_access={"not-a-project-uuid": "view"}),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                with patch.dict(
                    sys.modules,
                    {"frappe": frappe_module(enforced=True, projection=candidate)},
                ):
                    with self.assertRaises(AuthenticationRequired):
                        authenticated_principal()

    def test_disabled_local_frappe_user_fails_before_projection(self) -> None:
        with patch.dict(
            sys.modules,
            {
                "frappe": frappe_module(
                    enforced=True,
                    projection=projection(),
                    enabled=0,
                )
            },
        ):
            with self.assertRaises(AuthenticationRequired):
                authenticated_principal()

    def test_organization_scope_requires_one_exact_projected_grant(self) -> None:
        with patch.dict(
            sys.modules,
            {"frappe": frappe_module(enforced=True, projection=projection())},
        ):
            principal = authenticated_principal()
        authorize_organization(principal, "Company", "company-ref-01")
        for kind, reference in (
            ("Company", "different-company"),
            ("Customer", "company-ref-01"),
            ("Unknown", "company-ref-01"),
        ):
            with self.subTest(kind=kind, reference=reference):
                with self.assertRaises(PermissionDenied):
                    authorize_organization(principal, kind, reference)


if __name__ == "__main__":
    unittest.main()
