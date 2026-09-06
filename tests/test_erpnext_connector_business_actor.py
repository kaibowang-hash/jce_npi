from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/npi_erpnext_connector"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from npi_erpnext_connector.receiver_security import (  # noqa: E402
    business_actor_context,
    business_actor_is_enabled,
)


class _Database:
    def __init__(self) -> None:
        self.rows = {
            "engineer@example.invalid": {
                "enabled": 1,
                "user_type": "System User",
            },
            "disabled@example.invalid": {
                "enabled": 0,
                "user_type": "System User",
            },
            "service@example.invalid": {
                "enabled": 1,
                "user_type": "Website User",
            },
        }

    def get_value(
        self,
        doctype: str,
        name: str,
        fields: list[str],
        *,
        as_dict: bool,
    ) -> dict[str, object] | None:
        if doctype != "User" or fields != ["enabled", "user_type"] or not as_dict:
            raise AssertionError("Business actor lookup escaped its closed User query.")
        return self.rows.get(name)


class ERPNextConnectorBusinessActorTest(unittest.TestCase):
    def test_only_enabled_erpnext_system_user_can_own_created_document(self) -> None:
        frappe = SimpleNamespace(db=_Database())
        with patch.dict(sys.modules, {"frappe": frappe}):
            self.assertTrue(
                business_actor_is_enabled(
                    "engineer@example.invalid",
                    service_user="service@example.invalid",
                )
            )
            for actor in (
                "disabled@example.invalid",
                "service@example.invalid",
                "missing@example.invalid",
                "Engineer@example.invalid",
                "administrator",
            ):
                with self.subTest(actor=actor):
                    self.assertFalse(
                        business_actor_is_enabled(
                            actor,
                            service_user="service@example.invalid",
                        )
                    )

    def test_bounded_creator_context_always_restores_transport_user(self) -> None:
        session = SimpleNamespace(user="service@example.invalid")
        frappe = SimpleNamespace(session=session)

        def set_user(user_id: str) -> None:
            session.user = user_id

        frappe.set_user = set_user
        with patch.dict(sys.modules, {"frappe": frappe}):
            with self.assertRaisesRegex(RuntimeError, "target failure"):
                with business_actor_context("engineer@example.invalid"):
                    self.assertEqual(session.user, "engineer@example.invalid")
                    raise RuntimeError("target failure")
            self.assertEqual(session.user, "service@example.invalid")


if __name__ == "__main__":
    unittest.main()
