from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_integration"))

from npi_integration.inbound_project.domain import (
    ClaimLease,
    EventIdentityDisposition,
    InboundProjectEvent,
    ProjectSourceContractError,
    ProjectSourceObjectType,
    SourceHead,
    SourceOrderDisposition,
    SourceStreamIdentity,
    canonical_json_bytes,
    canonical_json_hash,
    classify_event_identity,
    classify_source_order,
    issue_claim,
    parse_closed_json,
    parse_project_source_event,
    raw_body_hash,
)


NOW = datetime(2026, 8, 16, 5, 0, tzinfo=UTC)


def uid(value: int) -> str:
    return str(UUID(int=value))


def event(
    *,
    event_type: str = "erpnext.quotation.submitted",
    object_type: str = "Quotation",
    object_version: int = 1,
) -> dict[str, object]:
    payload = {
        "schema_version": 1,
        "submission_state": "submitted",
        "title": "Synthetic Quotation Project",
        "target_sop": "2026-12-31",
        "source_modified_at": "2026-08-16T04:59:00Z",
    }
    return {
        "event_id": uid(1),
        "event_type": event_type,
        "event_version": 1,
        "occurred_at": "2026-08-16T05:00:00Z",
        "source_system": "ERPNEXT",
        "target_system": "NPI_ONE",
        "global_id": uid(2),
        "object_type": object_type,
        "source_object_id": "QTN-SYNTHETIC-0001",
        "object_version": object_version,
        "correlation_id": uid(3),
        "trace_id": "trace-synthetic-0001",
        "actor": {"type": "service", "id": "erpnext-sandbox"},
        "payload_hash": canonical_json_hash(payload),
        "payload": payload,
        "sensitivity": "confidential",
    }


def raw(candidate: dict[str, object] | None = None, *, indent: int | None = None) -> bytes:
    return json.dumps(
        candidate or event(),
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=False,
    ).encode("utf-8")


class Phase8InboundProjectDomainTest(unittest.TestCase):
    def test_both_closed_events_parse_and_canonical_hash_ignores_only_json_formatting(self) -> None:
        quotation = parse_project_source_event(raw(indent=2))
        sales = parse_project_source_event(
            raw(
                event(
                    event_type="erpnext.sales_order.submitted",
                    object_type="Sales Order",
                    object_version=7,
                )
            )
        )
        self.assertIsInstance(quotation, InboundProjectEvent)
        self.assertEqual(quotation.object_type, ProjectSourceObjectType.QUOTATION)
        self.assertEqual(sales.object_type, ProjectSourceObjectType.SALES_ORDER)
        self.assertEqual(
            quotation.canonical_event_hash,
            parse_project_source_event(raw()).canonical_event_hash,
        )
        self.assertNotEqual(raw_body_hash(raw(indent=2)), raw_body_hash(raw()))

    def test_event_and_payload_are_exact_and_hash_owned(self) -> None:
        baseline = event()
        invalid: list[dict[str, object]] = [
            {**baseline, "unexpected": True},
            {key: value for key, value in baseline.items() if key != "actor"},
            {**baseline, "event_version": True},
            {**baseline, "event_type": "erpnext.generic.submitted"},
            {**baseline, "object_type": "Sales Order"},
            {**baseline, "source_system": "NPI_ONE"},
            {**baseline, "sensitivity": "internal"},
            {**baseline, "payload_hash": "0" * 64},
            {**baseline, "occurred_at": "2026-08-16T05:00:00+00:00"},
        ]
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ProjectSourceContractError):
                    parse_project_source_event(raw(candidate))
        payload = dict(baseline["payload"])
        for changed in (
            {**payload, "unexpected": True},
            {key: value for key, value in payload.items() if key != "title"},
            {**payload, "submission_state": "draft"},
            {**payload, "title": "x" * 141},
            {**payload, "target_sop": "2026-02-30"},
            {**payload, "source_modified_at": "2026-08-16 04:59:00"},
        ):
            candidate = {**baseline, "payload": changed}
            candidate["payload_hash"] = canonical_json_hash(changed)
            with self.subTest(payload=changed):
                with self.assertRaises(ProjectSourceContractError):
                    parse_project_source_event(raw(candidate))

    def test_parser_rejects_duplicate_keys_floats_constants_unicode_and_bounds(self) -> None:
        with self.assertRaises(ProjectSourceContractError):
            parse_closed_json(b'{"a":1,"a":1}')
        for body in (b'{"a":1.0}', b'{"a":NaN}', b'{"a":Infinity}', b"\xff\xfe"):
            with self.subTest(body=body):
                with self.assertRaises(ProjectSourceContractError):
                    parse_closed_json(body)
        with self.assertRaises(ProjectSourceContractError):
            parse_closed_json(b"{}" + b" " * 262_144)
        with self.assertRaises(ProjectSourceContractError):
            canonical_json_bytes({"value": "\ud800"})
        with self.assertRaises(ProjectSourceContractError):
            canonical_json_bytes({"value": 1.5})

    def test_canonical_json_is_utf8_sorted_compact_integer_only_and_stable(self) -> None:
        first = canonical_json_bytes({"z": [2, True, None], "a": "模具"})
        second = canonical_json_bytes({"a": "模具", "z": [2, True, None]})
        self.assertEqual(first, second)
        self.assertEqual(first, b'{"a":"\xe6\xa8\xa1\xe5\x85\xb7","z":[2,true,null]}')
        self.assertEqual(len(canonical_json_hash({"a": 1})), 64)

    def test_event_identity_and_positive_source_order_are_fail_closed(self) -> None:
        current = SourceHead(2, "a" * 64, UUID(int=10))
        self.assertEqual(
            classify_event_identity("a" * 64, "a" * 64),
            EventIdentityDisposition.DUPLICATE_EXACT,
        )
        self.assertEqual(
            classify_event_identity("a" * 64, "b" * 64),
            EventIdentityDisposition.CONFLICTED,
        )
        cases = (
            (SourceHead(3, "b" * 64, UUID(int=11)), False, SourceOrderDisposition.ADVANCE),
            (SourceHead(3, "b" * 64, UUID(int=11)), True, SourceOrderDisposition.RECEIVED_AFTER_CREATION),
            (SourceHead(1, "b" * 64, UUID(int=11)), False, SourceOrderDisposition.SUPERSEDED),
            (SourceHead(2, "a" * 64, UUID(int=12)), False, SourceOrderDisposition.DUPLICATE_EXACT),
            (SourceHead(2, "b" * 64, UUID(int=12)), False, SourceOrderDisposition.CONFLICTED),
        )
        for candidate, bound, expected in cases:
            with self.subTest(candidate=candidate, bound=bound):
                self.assertEqual(
                    classify_source_order(current, candidate, project_already_bound=bound),
                    expected,
                )
        with self.assertRaises(ProjectSourceContractError):
            SourceHead(0, "a" * 64, UUID(int=1))

    def test_source_key_and_claim_lease_are_deterministic_and_expiry_is_inclusive(self) -> None:
        identity = SourceStreamIdentity(
            tenant_id="tenant-synthetic",
            profile_id="erpnext-sandbox-v1",
            object_type=ProjectSourceObjectType.QUOTATION,
            source_object_id="QTN-SYNTHETIC-0001",
        )
        self.assertEqual(identity.key_hash, replace(identity).key_hash)
        lease = issue_claim(now=NOW, lease_seconds=60, previous_attempt_count=2)
        self.assertIsInstance(lease, ClaimLease)
        self.assertEqual(lease.attempt_count, 3)
        self.assertTrue(lease.is_live(NOW + timedelta(seconds=59)))
        self.assertFalse(lease.is_live(NOW + timedelta(seconds=60)))
        with self.assertRaises(ProjectSourceContractError):
            issue_claim(now=NOW, lease_seconds=0)


if __name__ == "__main__":
    unittest.main()
