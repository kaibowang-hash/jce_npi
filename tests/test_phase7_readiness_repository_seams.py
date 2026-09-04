from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import UUID

sys.path.insert(0, "apps/npi_core")

from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.readiness.domain import (
    EXTERNAL_SOURCE_KINDS,
    ReadinessSourceKind,
    ReadinessSourceState,
)
from npi_core.readiness.request_validation import (
    ReadinessSourceRequest,
    closed_payload,
    parse_source_request,
    parse_source_requests,
)
from npi_core.readiness.source_resolver import (
    EXTERNAL_UNAVAILABLE_REASON_CODES,
    ExactSourceObservation,
    SourceResolutionContext,
    resolve_source,
)


PROJECT_ID = UUID(int=701)
OTHER_PROJECT_ID = UUID(int=702)
SOURCE_ID = UUID(int=703)
HASH = "7" * 64
CONTEXT = SourceResolutionContext("tenant-a", PROJECT_ID)


def internal_payload(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "requirementKey": "released_quality_report",
        "kind": "controlled_quality_result",
        "globalId": str(SOURCE_ID),
        "sourceVersion": 4,
        "snapshotHash": HASH,
    }
    value.update(changes)
    return value


def exact_request() -> ReadinessSourceRequest:
    return parse_source_request(internal_payload())


def observation(**changes: object) -> ExactSourceObservation:
    value: dict[str, object] = {
        "tenant_id": "tenant-a",
        "project_global_id": PROJECT_ID,
        "kind": ReadinessSourceKind.CONTROLLED_QUALITY_RESULT,
        "global_id": SOURCE_ID,
        "source_version": 4,
        "snapshot_hash": HASH,
        "disposition": ReadinessSourceState.SATISFIED,
        "reason_code": None,
    }
    value.update(changes)
    return ExactSourceObservation(**value)  # type: ignore[arg-type]


class FakeExactRepository:
    def __init__(self, source: object) -> None:
        self.source = source
        self.calls: list[tuple[str, object, object]] = []
        self.deny = False

    def get_exact_source(self, context: object, query: object):
        self.calls.append(("get", context, query))
        return self.source

    def authorize_exact_source(self, context: object, source: object) -> None:
        self.calls.append(("authorize", context, source))
        if self.deny:
            raise PermissionDenied()


class ExplodingRepository:
    def get_exact_source(self, *_args: object, **_kwargs: object):
        raise AssertionError("external providers must not be called")

    def authorize_exact_source(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("external providers must not be called")


class Phase7ReadinessRequestValidationTest(unittest.TestCase):
    def test_internal_source_requires_one_exact_identity_without_caller_state(self) -> None:
        parsed = parse_source_request(internal_payload())

        self.assertEqual(parsed.requirement_key, "released_quality_report")
        self.assertIs(parsed.kind, ReadinessSourceKind.CONTROLLED_QUALITY_RESULT)
        self.assertEqual(parsed.global_id, SOURCE_ID)
        self.assertEqual(parsed.source_version, 4)
        self.assertEqual(parsed.snapshot_hash, HASH)

    def test_external_source_is_identity_free(self) -> None:
        parsed = parse_source_request(
            {
                "requirementKey": "formal_quality",
                "kind": "erp_quality_result",
            }
        )

        self.assertIs(parsed.kind, ReadinessSourceKind.ERP_QUALITY_RESULT)
        self.assertIsNone(parsed.global_id)
        self.assertIsNone(parsed.source_version)
        self.assertIsNone(parsed.snapshot_hash)

    def test_source_rejects_every_caller_derived_or_containment_field(self) -> None:
        payload = internal_payload(
            state="satisfied",
            disposition="satisfied",
            reasonCode="passed",
            score=10_000,
            blocker=False,
            ready=True,
            tenantId="tenant-a",
            projectId=str(PROJECT_ID),
        )

        with self.assertRaises(RequestValidationFailed) as raised:
            parse_source_request(payload)

        self.assertEqual(
            {item["path"] for item in raised.exception.field_errors},
            {
                "source.blocker",
                "source.disposition",
                "source.projectId",
                "source.ready",
                "source.reasonCode",
                "source.score",
                "source.state",
                "source.tenantId",
            },
        )

    def test_closed_payload_rejects_top_level_score_and_blocker_claims(self) -> None:
        with self.assertRaises(RequestValidationFailed) as raised:
            closed_payload(
                {"expectedInstanceVersion": 2, "score": 10_000, "blocker": False},
                "request",
                frozenset({"expectedInstanceVersion"}),
            )

        self.assertEqual(
            [item["path"] for item in raised.exception.field_errors],
            ["request.blocker", "request.score"],
        )

    def test_external_source_rejects_identity_even_when_values_are_null(self) -> None:
        with self.assertRaises(RequestValidationFailed) as raised:
            parse_source_request(
                {
                    "requirementKey": "formal_quality",
                    "kind": "erp_quality_result",
                    "globalId": None,
                    "sourceVersion": None,
                    "snapshotHash": None,
                }
            )

        self.assertEqual(
            {item["path"] for item in raised.exception.field_errors},
            {"source.globalId", "source.sourceVersion", "source.snapshotHash"},
        )

    def test_internal_source_rejects_missing_or_malformed_exact_identity(self) -> None:
        cases = (
            ({"snapshotHash": None}, "source.snapshotHash"),
            ({"sourceVersion": 0}, "source.sourceVersion"),
            ({"globalId": "not-a-uuid"}, "source.globalId"),
        )
        for changes, expected_path in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(RequestValidationFailed) as raised:
                    parse_source_request(internal_payload(**changes))
                self.assertEqual(raised.exception.field_errors[0]["path"], expected_path)

        missing = internal_payload()
        del missing["sourceVersion"]
        with self.assertRaises(RequestValidationFailed) as raised:
            parse_source_request(missing)
        self.assertEqual(raised.exception.field_errors[0]["path"], "source.sourceVersion")

    def test_source_list_is_bounded_and_duplicate_free(self) -> None:
        with self.assertRaises(RequestValidationFailed):
            parse_source_requests([internal_payload(), internal_payload()])
        with self.assertRaises(RequestValidationFailed):
            parse_source_requests("not-a-list")


class Phase7ReadinessSourceResolverTest(unittest.TestCase):
    def test_explicit_satisfied_disposition_maps_after_exact_reauthorization(self) -> None:
        repository = FakeExactRepository(observation())

        resolved = resolve_source(exact_request(), context=CONTEXT, repository=repository)

        self.assertIs(resolved.state, ReadinessSourceState.SATISFIED)
        self.assertEqual(resolved.global_id, SOURCE_ID)
        self.assertEqual(resolved.source_version, 4)
        self.assertEqual(resolved.snapshot_hash, HASH)
        self.assertEqual([item[0] for item in repository.calls], ["get", "authorize"])
        query = repository.calls[0][2]
        self.assertEqual(query.global_id, SOURCE_ID)
        self.assertEqual(query.source_version, 4)
        self.assertEqual(query.snapshot_hash, HASH)

    def test_explicit_failed_disposition_is_not_coerced_to_satisfied(self) -> None:
        repository = FakeExactRepository(
            observation(
                disposition=ReadinessSourceState.FAILED,
                reason_code="explicit_failure",
            )
        )

        resolved = resolve_source(exact_request(), context=CONTEXT, repository=repository)

        self.assertIs(resolved.state, ReadinessSourceState.FAILED)
        self.assertEqual(resolved.reason_code, "explicit_failure")

    def test_existence_without_explicit_disposition_fails_closed(self) -> None:
        for disposition in (None, ReadinessSourceState.UNAVAILABLE, "satisfied"):
            with self.subTest(disposition=disposition):
                repository = FakeExactRepository(observation(disposition=disposition))
                with self.assertRaises(RequestValidationFailed):
                    resolve_source(exact_request(), context=CONTEXT, repository=repository)
                self.assertEqual([item[0] for item in repository.calls], ["get", "authorize"])

    def test_missing_malformed_or_drifted_source_fails_closed_without_latest_substitution(self) -> None:
        cases = (
            None,
            {"disposition": "satisfied"},
            observation(tenant_id="tenant-b"),
            observation(project_global_id=OTHER_PROJECT_ID),
            observation(kind=ReadinessSourceKind.RELEASED_DOCUMENT),
            observation(global_id=UUID(int=704)),
            observation(source_version=5),
            observation(snapshot_hash="8" * 64),
        )
        for source in cases:
            with self.subTest(source=source):
                repository = FakeExactRepository(source)
                with self.assertRaises(RequestValidationFailed):
                    resolve_source(exact_request(), context=CONTEXT, repository=repository)
                self.assertEqual([item[0] for item in repository.calls], ["get"])

    def test_exact_source_authorization_failure_is_not_swallowed(self) -> None:
        repository = FakeExactRepository(observation())
        repository.deny = True

        with self.assertRaises(PermissionDenied):
            resolve_source(exact_request(), context=CONTEXT, repository=repository)

        self.assertEqual([item[0] for item in repository.calls], ["get", "authorize"])

    def test_every_formal_external_kind_is_unavailable_without_repository_or_network(self) -> None:
        repository = ExplodingRepository()
        for kind in EXTERNAL_SOURCE_KINDS:
            with self.subTest(kind=kind):
                request = parse_source_request(
                    {"requirementKey": "formal_truth", "kind": kind.value}
                )
                resolved = resolve_source(
                    request,
                    context=CONTEXT,
                    repository=repository,
                )
                self.assertIs(resolved.state, ReadinessSourceState.UNAVAILABLE)
                self.assertIsNone(resolved.global_id)
                self.assertIsNone(resolved.source_version)
                self.assertIsNone(resolved.snapshot_hash)
                self.assertEqual(
                    resolved.reason_code,
                    EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
                )

    def test_resolver_has_no_sql_frappe_erp_or_network_dependency(self) -> None:
        source = Path(
            "apps/npi_core/npi_core/readiness/source_resolver.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "frappe.db",
            "import requests",
            "from requests",
            "import urllib",
            "from urllib",
            "erpnext",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
