from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "apps/npi_core")

from npi_core.collaboration.domain import (
    STANDARD_MEETING_TEMPLATE,
    STANDARD_MEETING_TEMPLATE_HASH,
    MeetingDraft,
    NotificationKind,
    notification_bucket,
    notification_kind,
    preference_email_kinds,
)
from npi_core.foundation.errors import RequestValidationFailed


NOW = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)


def meeting_input() -> dict[str, object]:
    return {
        "template_ref_value": {
            "globalId": STANDARD_MEETING_TEMPLATE["globalId"],
            "version": 1,
            "snapshotHash": STANDARD_MEETING_TEMPLATE_HASH,
        },
        "title_value": "Tooling review",
        "occurred_at_value": "2026-09-03T08:00:00Z",
        "attendee_values": ["Owner@Example.invalid", "quality@example.invalid"],
        "section_values": {
            "agenda": "Review tooling status",
            "discussion": "Line one\nLine two",
            "decisions": "Release the action list",
        },
        "item_values": [
            {
                "itemKey": "tooling.follow_up",
                "kind": "action",
                "title": "Confirm the latest drawing",
                "detail": "Check revision A.\nRetain the exact source.",
                "ownerUserId": "owner@example.invalid",
                "dueAt": "2026-09-05T08:00:00Z",
                "severity": "high",
                "blocking": True,
            }
        ],
    }


class Phase9CollaborationDomainTest(unittest.TestCase):
    def test_meeting_is_closed_versioned_and_preserves_long_text(self) -> None:
        draft = MeetingDraft.parse(**meeting_input())
        self.assertEqual(draft.attendee_user_ids[0], "owner@example.invalid")
        self.assertEqual(draft.sections["discussion"], "Line one\nLine two")
        self.assertEqual(draft.items[0].detail, "Check revision A.\nRetain the exact source.")
        self.assertEqual(draft.items[0].parent_input()["parentOperation"], "meeting_minute.create")
        self.assertNotIn("items", draft.minute_content())
        self.assertEqual(draft.snapshot()["schemaVersion"], 1)

    def test_meeting_rejects_template_drift_duplicate_identity_and_unknown_shape(self) -> None:
        for mutate in (
            lambda value: value["template_ref_value"].update(snapshotHash="f" * 64),
            lambda value: value["attendee_values"].append("owner@example.invalid"),
            lambda value: value["section_values"].update(extra="not allowed"),
            lambda value: value["item_values"][0].update(kind="task"),
            lambda value: value["item_values"][0].update(extra="not allowed"),
        ):
            values = meeting_input()
            mutate(values)
            with self.subTest(values=values), self.assertRaises(RequestValidationFailed):
                MeetingDraft.parse(**values)

    def test_notification_classification_is_deterministic_and_critical_wins(self) -> None:
        base = {
            "active": True,
            "due_at": NOW + timedelta(days=1),
            "category": "work",
            "priority_value": "medium",
            "blocking": False,
        }
        self.assertEqual(notification_kind(base, NOW), (NotificationKind.DUE_REMINDER, False))
        self.assertEqual(
            notification_kind({**base, "due_at": NOW - timedelta(minutes=1)}, NOW),
            (NotificationKind.OVERDUE_ESCALATION, False),
        )
        self.assertEqual(
            notification_kind({**base, "category": "approval", "due_at": NOW + timedelta(days=6)}, NOW),
            (NotificationKind.GATE_ATTENTION, False),
        )
        self.assertEqual(
            notification_kind({**base, "blocking": True, "priority_value": "critical"}, NOW),
            (NotificationKind.CRITICAL_BLOCKER, True),
        )
        self.assertIsNone(notification_kind({**base, "active": False}, NOW))
        self.assertEqual(
            notification_bucket(NotificationKind.OVERDUE_ESCALATION, NOW, NOW - timedelta(days=2)),
            "2026-09-03",
        )

    def test_preferences_never_allow_disabling_critical_audit_delivery(self) -> None:
        result = preference_email_kinds(["gate_attention", "due_reminder"])
        self.assertEqual(result, (NotificationKind.DUE_REMINDER, NotificationKind.GATE_ATTENTION))
        for invalid in (["critical_blocker"], ["due_reminder", "due_reminder"], "due_reminder"):
            with self.subTest(invalid=invalid), self.assertRaises(RequestValidationFailed):
                preference_email_kinds(invalid)


if __name__ == "__main__":
    unittest.main()
