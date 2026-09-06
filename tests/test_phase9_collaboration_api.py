from __future__ import annotations

import importlib
import sys
import types
import unittest
from typing import Any

sys.path.insert(0, "apps/npi_core")

from npi_core.collaboration.domain import STANDARD_MEETING_TEMPLATE, STANDARD_MEETING_TEMPLATE_HASH
from npi_core.foundation.errors import PermissionDenied, ReportingRoutesDisabled, RequestValidationFailed
from npi_core.foundation.security import Principal


PROJECT_ID = "00000000-0000-4000-8000-000000000201"
NOTIFICATION_ID = "00000000-0000-4000-8000-000000000202"


class Row(dict):
    def __getattr__(self, name: str) -> Any:
        return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Outcome:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response


class Repository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_meetings(self, project_id):
        self.calls.append(("list_meetings", {"project_id": project_id}))
        return {"schemaVersion": 1, "items": []}

    def create_meeting(self, project_id, **values):
        self.calls.append(("create_meeting", {"project_id": project_id, **values}))
        return Outcome({"schemaVersion": 1, "globalId": "meeting-1"})

    def notification_feed(self, **values):
        self.calls.append(("notification_feed", values))
        return {"schemaVersion": 1, "items": []}

    def mark_notification_read(self, notification_id, **values):
        self.calls.append(("mark_read", {"notification_id": notification_id, **values}))
        return Outcome({"schemaVersion": 1, "globalId": str(notification_id)})

    def notification_preference(self):
        self.calls.append(("get_preference", {}))
        return {"schemaVersion": 1, "emailKinds": [], "version": 0}

    def set_notification_preference(self, **values):
        self.calls.append(("set_preference", values))
        return Outcome({"schemaVersion": 1, "emailKinds": [], "version": 1})


class Phase9CollaborationApiTest(unittest.TestCase):
    MODULES = ("frappe", "npi_core.collaboration_api")

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source, **_values: source
        frappe.conf = Row(npi_p9_02_routes_disabled=False)
        frappe.local = types.SimpleNamespace(response=Row(), form_dict=Row())
        frappe.flags = types.SimpleNamespace(
            npi_route_params=Row(project_id=PROJECT_ID, notification_id=NOTIFICATION_ID),
        )
        frappe.get_request_header = lambda name: {
            "X-Request-ID": "00000000-0000-4000-8000-000000000001",
            "Idempotency-Key": "collaboration-command-1",
        }.get(name)
        frappe.whitelist = lambda *, allow_guest=False, methods=None: (lambda function: function)
        sys.modules["frappe"] = frappe
        self.frappe = frappe
        self.api = importlib.import_module("npi_core.collaboration_api")
        self.repository = Repository()
        self.principal = Principal(
            user_id="owner@example.invalid",
            roles=frozenset({"System Manager"}),
            tenant_id="TENANT-A",
        )
        self.api._repository_factory = lambda **_values: self.repository
        self.api.authenticated_user = lambda: self.principal.user_id
        self.api.authenticated_principal = lambda _actor: self.principal
        self.api.require_csrf_token = lambda: None
        self.api.frappe_domain_call = lambda handle, **_values: handle()

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def meeting_fields() -> dict[str, object]:
        return {
            "expectedProjectVersion": 3,
            "templateRef": {
                "globalId": STANDARD_MEETING_TEMPLATE["globalId"],
                "version": 1,
                "snapshotHash": STANDARD_MEETING_TEMPLATE_HASH,
            },
            "title": "NPI review",
            "occurredAt": "2026-09-03T08:00:00Z",
            "attendeeUserIds": ["owner@example.invalid"],
            "sections": {
                "agenda": "Review status",
                "discussion": "Review the controlled facts",
                "decisions": "Create the follow-up action",
            },
            "items": [],
        }

    def test_meeting_query_and_command_bind_exact_route_and_idempotency(self) -> None:
        self.api.get_project_meetings()
        self.assertEqual(str(self.repository.calls[-1][1]["project_id"]), PROJECT_ID)
        response = self.api.create_project_meeting(**self.meeting_fields())
        self.assertEqual(response["globalId"], "meeting-1")
        name, values = self.repository.calls[-1]
        self.assertEqual(name, "create_meeting")
        self.assertEqual(values["expected_project_version"], 3)
        self.assertEqual(values["draft"].title, "NPI review")
        self.assertEqual(len(values["idempotency_key"]), 64)

    def test_notification_query_is_bounded_and_mark_read_is_versioned(self) -> None:
        self.api.get_notifications(unreadOnly="true", limit="100")
        self.assertEqual(
            self.repository.calls[-1],
            ("notification_feed", {"unread_only": True, "cursor": None, "limit": 100}),
        )
        self.api.mark_notification_read(expectedVersion="2")
        name, values = self.repository.calls[-1]
        self.assertEqual(name, "mark_read")
        self.assertEqual(str(values["notification_id"]), NOTIFICATION_ID)
        self.assertEqual(values["expected_version"], 2)
        with self.assertRaises(RequestValidationFailed):
            self.api.get_notifications(unreadOnly=[], limit=25)

    def test_preference_allows_only_noncritical_email_kinds(self) -> None:
        self.api.get_notification_preference()
        self.assertEqual(self.repository.calls[-1][0], "get_preference")
        self.api.set_notification_preference(
            expectedVersion=0,
            emailKinds=["overdue_escalation", "due_reminder"],
        )
        name, values = self.repository.calls[-1]
        self.assertEqual(name, "set_preference")
        self.assertEqual(
            tuple(item.value for item in values["email_kinds"]),
            ("due_reminder", "overdue_escalation"),
        )
        with self.assertRaises(RequestValidationFailed):
            self.api.set_notification_preference(expectedVersion=0, emailKinds=["critical_blocker"])

    def test_external_and_disabled_access_fail_closed_before_repository(self) -> None:
        self.principal = Principal(
            user_id="external@example.invalid",
            tenant_id="TENANT-A",
            is_external=True,
        )
        with self.assertRaises(PermissionDenied):
            self.api.get_notifications()
        self.principal = Principal(
            user_id="owner@example.invalid",
            tenant_id="TENANT-A",
            roles=frozenset({"NPI API User"}),
        )
        with self.assertRaises(PermissionDenied):
            self.api.create_project_meeting(**self.meeting_fields())
        self.principal = Principal(user_id="owner@example.invalid", tenant_id="TENANT-A")
        self.frappe.conf.npi_p9_02_routes_disabled = True
        with self.assertRaises(ReportingRoutesDisabled):
            self.api.get_notifications()

    def test_unknown_fields_invalid_versions_and_invalid_route_ids_are_rejected(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            self.api.get_notifications(arbitrary="value")
        with self.assertRaises(RequestValidationFailed):
            self.api.mark_notification_read(expectedVersion=0)
        self.frappe.flags.npi_route_params.project_id = "not-a-uuid"
        with self.assertRaises(RequestValidationFailed):
            self.api.get_project_meetings()


if __name__ == "__main__":
    unittest.main()
