from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.authorization_projection.domain import (
    AuthorizationProjectionError,
    AuthorizationProjectionEvent,
    canonical_hash,
)


NOW = datetime(2026, 9, 3, 1, 0, tzinfo=UTC)


def event_mapping(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sourceSubjectId": "entra-subject-001",
        "targetUserId": "member@example.invalid",
        "sourceVersion": 3,
        "enabled": True,
        "roles": ["NPI Engineer"],
        "projectAccess": [
            {
                "projectId": str(UUID(int=20)),
                "access": "contribute",
            }
        ],
        "organizationScopes": [
            {"kind": "Company", "referenceKey": "company-ref-01"}
        ],
        "issuedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expiresAt": (NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    mapping: dict[str, object] = {
        "schemaVersion": 1,
        "operation": "replace_user_authorization",
        "sourceSystem": "ERPNEXT",
        "targetSystem": "NPI_ONE",
        "objectType": "UserAuthorizationProjection",
        "eventId": str(UUID(int=10)),
        **payload,
        "traceId": "trace-p904-001",
        "payloadHash": canonical_hash(payload),
    }
    mapping.update(changes)
    if set(changes).intersection(payload):
        changed_payload = {key: mapping[key] for key in payload}
        mapping["payloadHash"] = canonical_hash(changed_payload)
    return mapping


class Phase9AuthorizationProjectionDomainTest(unittest.TestCase):
    def test_closed_replacement_normalizes_exact_full_projection(self) -> None:
        event = AuthorizationProjectionEvent.from_mapping(event_mapping())

        self.assertEqual(event.source_version, 3)
        self.assertEqual(event.roles, ("NPI Engineer",))
        self.assertEqual(event.project_scopes[0].access.value, "contribute")
        self.assertEqual(event.organization_scopes[0].kind.value, "Company")
        self.assertEqual(len(event.source_subject_hash), 64)
        self.assertEqual(
            event.projection_id("tenant-p904"),
            event.projection_id("tenant-p904"),
        )
        self.assertNotEqual(event.event_hash, event.projection_hash)

    def test_payload_hash_and_unknown_fields_fail_closed(self) -> None:
        invalid_hash = event_mapping(payloadHash="0" * 64)
        with self.assertRaises(AuthorizationProjectionError):
            AuthorizationProjectionEvent.from_mapping(invalid_hash)

        unknown = event_mapping()
        unknown["permissionFallback"] = True
        with self.assertRaises(AuthorizationProjectionError):
            AuthorizationProjectionEvent.from_mapping(unknown)

    def test_grants_are_sorted_unique_and_bounded(self) -> None:
        for invalid in (
            ["NPI Reviewer", "NPI Engineer"],
            ["NPI Engineer", "NPI Engineer"],
            ["bad\nrole"],
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(AuthorizationProjectionError):
                    AuthorizationProjectionEvent.from_mapping(
                        event_mapping(roles=invalid)
                    )

    def test_disabled_replacement_cannot_retain_any_grant(self) -> None:
        with self.assertRaises(AuthorizationProjectionError):
            AuthorizationProjectionEvent.from_mapping(event_mapping(enabled=False))

        event = AuthorizationProjectionEvent.from_mapping(
            event_mapping(
                enabled=False,
                roles=[],
                projectAccess=[],
                organizationScopes=[],
            )
        )
        self.assertFalse(event.enabled)
        self.assertEqual(event.roles, ())

    def test_expired_or_non_boolean_shape_is_rejected(self) -> None:
        with self.assertRaises(AuthorizationProjectionError):
            AuthorizationProjectionEvent.from_mapping(
                event_mapping(
                    expiresAt=NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
            )
        with self.assertRaises(AuthorizationProjectionError):
            AuthorizationProjectionEvent.from_mapping(event_mapping(enabled=1))

    def test_target_user_is_one_canonical_email_identity(self) -> None:
        for target_user_id in (
            "Member@example.invalid",
            "member",
            "member@example",
            " member@example.invalid",
            "member@example.invalid ",
        ):
            with self.subTest(target_user_id=target_user_id):
                with self.assertRaises(AuthorizationProjectionError):
                    AuthorizationProjectionEvent.from_mapping(
                        event_mapping(targetUserId=target_user_id)
                    )


if __name__ == "__main__":
    unittest.main()
