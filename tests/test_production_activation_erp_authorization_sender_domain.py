from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
ERP_APP = ROOT / "apps/npi_erpnext_connector"
NPI_APP = ROOT / "apps/npi_integration"
for path in (ERP_APP, NPI_APP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from npi_erpnext_connector.domain import (  # noqa: E402
    AuthorizationSenderError,
    MappingIncomplete,
    SenderPolicy,
    SourcePermission,
    SourceUser,
    build_event,
    project_source_user,
)
from npi_integration.authorization_projection.domain import (  # noqa: E402
    AuthorizationProjectionEvent,
)


PROJECT_ID = "34dc62c5-ab4b-44ec-882b-fb3df759dc79"


def _policy(**changes: object) -> SenderPolicy:
    value: dict[str, object] = {
        "roleMap": {
            "Manufacturing User": "NPI Engineer",
            "Quality Manager": "NPI Reviewer",
        },
        "projectMap": {"ERP-PROJECT-001": PROJECT_ID},
        "projectAccessByRole": {
            "Manufacturing User": "contribute",
            "Quality Manager": "approve",
        },
        "ttlSeconds": 3600,
    }
    value.update(changes)
    return SenderPolicy.from_mapping(value)


class ProductionActivationERPAuthorizationSenderDomainTest(unittest.TestCase):
    def test_builds_receiver_compatible_complete_replacement(self) -> None:
        source = SourceUser(
            source_subject_id="user@example.com",
            target_user_id="user@example.com",
            enabled=True,
            user_type="System User",
            roles=("Manufacturing User", "Quality Manager"),
            permissions=(
                SourcePermission("Company", "JCE"),
                SourcePermission("Project", "ERP-PROJECT-001"),
                SourcePermission("Supplier", "SUPPLIER-001"),
            ),
        )
        snapshot = project_source_user(source, _policy())
        self.assertTrue(snapshot.enabled)
        self.assertEqual(snapshot.roles, ("NPI Engineer", "NPI Reviewer"))
        self.assertEqual(snapshot.project_access, ((PROJECT_ID, "approve"),))
        self.assertEqual(
            snapshot.organization_scopes,
            (("Company", "JCE"), ("Supplier", "SUPPLIER-001")),
        )

        event = build_event(
            snapshot,
            source_version=7,
            issued_at=datetime(2026, 9, 4, 1, 2, 3, 987654, tzinfo=UTC),
            ttl_seconds=3600,
        )
        received = AuthorizationProjectionEvent.from_mapping(event.event)
        self.assertEqual(received.source_version, 7)
        self.assertEqual(received.target_user_id, "user@example.com")
        self.assertEqual(received.payload_hash, event.event["payloadHash"])
        self.assertEqual(event.event["issuedAt"], "2026-09-04T01:02:03Z")
        self.assertEqual(event.event["expiresAt"], "2026-09-04T02:02:03Z")
        self.assertNotEqual(event.request_id, event.event_id)

    def test_event_and_request_identity_are_deterministic_for_exact_retry(self) -> None:
        snapshot = project_source_user(
            SourceUser(
                "user@example.com",
                "user@example.com",
                True,
                "System User",
                ("Manufacturing User",),
                (),
            ),
            _policy(),
        )
        first = build_event(
            snapshot,
            source_version=1,
            issued_at=datetime(2026, 9, 4, tzinfo=UTC),
            ttl_seconds=3600,
        )
        second = build_event(
            snapshot,
            source_version=1,
            issued_at=datetime(2026, 9, 4, tzinfo=UTC),
            ttl_seconds=3600,
        )
        self.assertEqual(first.event, second.event)
        self.assertEqual(first.request_id, second.request_id)
        self.assertEqual(first.event_hash, second.event_hash)

    def test_disabled_or_unmapped_user_emits_revocation_without_grants(self) -> None:
        for source in (
            SourceUser(
                "user@example.com",
                "user@example.com",
                False,
                "System User",
                ("Manufacturing User",),
                (SourcePermission("Company", "JCE"),),
            ),
            SourceUser(
                "user@example.com",
                "user@example.com",
                True,
                "Website User",
                ("Manufacturing User",),
                (SourcePermission("Company", "JCE"),),
            ),
            SourceUser(
                "user@example.com",
                "user@example.com",
                True,
                "System User",
                ("Accounts User",),
                (SourcePermission("Company", "JCE"),),
            ),
        ):
            with self.subTest(source=source):
                snapshot = project_source_user(source, _policy())
                self.assertFalse(snapshot.enabled)
                self.assertEqual(snapshot.roles, ())
                self.assertEqual(snapshot.project_access, ())
                self.assertEqual(snapshot.organization_scopes, ())

    def test_project_permission_requires_explicit_id_and_access_mapping(self) -> None:
        source = SourceUser(
            "user@example.com",
            "user@example.com",
            True,
            "System User",
            ("Manufacturing User",),
            (SourcePermission("Project", "ERP-PROJECT-001"),),
        )
        with self.assertRaisesRegex(MappingIncomplete, "without an approved access mapping"):
            project_source_user(
                source,
                _policy(projectAccessByRole={}),
            )
        with self.assertRaisesRegex(MappingIncomplete, "no approved LaunchFlow Project"):
            project_source_user(
                source,
                _policy(projectMap={}),
            )

    def test_identity_and_policy_never_guess_defaults(self) -> None:
        with self.assertRaisesRegex(MappingIncomplete, "canonical lowercase"):
            SourceUser(
                "User@example.com",
                "User@example.com",
                True,
                "System User",
                (),
                (),
            )
        with self.assertRaisesRegex(MappingIncomplete, "do not match"):
            SourceUser(
                "different@example.com",
                "user@example.com",
                True,
                "System User",
                (),
                (),
            )
        with self.assertRaisesRegex(AuthorizationSenderError, "required"):
            _policy(roleMap={})
        with self.assertRaisesRegex(AuthorizationSenderError, "validity"):
            _policy(ttlSeconds=86_401)
        with self.assertRaisesRegex(AuthorizationSenderError, "also exist"):
            _policy(projectAccessByRole={"Unmapped Role": "view"})

    def test_policy_requires_canonical_project_uuid(self) -> None:
        policy = _policy()
        self.assertEqual(
            policy.project_map["ERP-PROJECT-001"],
            UUID(PROJECT_ID),
        )
        with self.assertRaisesRegex(AuthorizationSenderError, "LaunchFlow Project"):
            _policy(projectMap={"ERP-PROJECT-001": "not-a-uuid"})


if __name__ == "__main__":
    unittest.main()
