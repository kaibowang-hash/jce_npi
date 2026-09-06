from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID


sys.path.insert(0, "apps/npi_core")

from npi_core.my_work.domain import (
    AvailableMyWorkCount,
    DomainWorkItemKind,
    DomainWorkItemTarget,
    GateReviewTarget,
    InvalidMyWorkCursor,
    MyWorkCategory,
    MyWorkCountAvailability,
    MyWorkCounts,
    MyWorkCursorCodec,
    MyWorkDueState,
    MyWorkItem,
    MyWorkPriority,
    MyWorkPriorityScheme,
    MyWorkQuery,
    MyWorkSortTuple,
    MyWorkSourceReference,
    MyWorkSourceType,
    MyWorkStatus,
    MyWorkUnavailableReason,
    MyWorkValidationError,
    MyWorkView,
    UnavailableMyWorkCount,
    calculate_my_work_counts,
    filter_my_work_items,
    my_work_due_state,
    my_work_query_fingerprint,
    sort_my_work_items,
)


PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_PROJECT_ID = UUID("99999999-9999-4999-8999-999999999999")
WORK_ID = UUID("22222222-2222-4222-8222-222222222222")
GATE_ID = UUID("33333333-3333-4333-8333-333333333333")
AS_OF = datetime(2026, 7, 25, 12, tzinfo=UTC)
SIGNING_KEY = b"synthetic-my-work-test-signing-key-0001"


def domain_item(
    *,
    item_id: UUID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    project_id: UUID = PROJECT_ID,
    source_id: UUID = WORK_ID,
    kind: DomainWorkItemKind = DomainWorkItemKind.RISK,
    category: MyWorkCategory = MyWorkCategory.RISK,
    status: MyWorkStatus = MyWorkStatus.READY,
    due_at: datetime | None = AS_OF - timedelta(hours=1),
    priority: MyWorkPriority | None = MyWorkPriority(
        MyWorkPriorityScheme.DOMAIN_SEVERITY,
        "high",
    ),
    blocking: bool = False,
    target: object | None = None,
) -> MyWorkItem:
    return MyWorkItem(
        id=item_id,
        project_global_id=project_id,
        source=MyWorkSourceReference(
            MyWorkSourceType.DOMAIN_WORK_ITEM,
            source_id,
            4,
        ),
        domain_kind=kind,
        category=category,
        status=status,
        due_at=due_at,
        priority=priority,
        blocking=blocking,
        target=(
            DomainWorkItemTarget(source_id)
            if target is None
            else target  # type: ignore[arg-type]
        ),
    )


def gate_item(
    *,
    item_id: UUID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
    project_id: UUID = PROJECT_ID,
    gate_id: UUID = GATE_ID,
    source_type: MyWorkSourceType = MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
    category: MyWorkCategory = MyWorkCategory.APPROVAL,
    status: MyWorkStatus = MyWorkStatus.WAITING,
    due_at: datetime | None = AS_OF,
    priority: MyWorkPriority | None = MyWorkPriority(
        MyWorkPriorityScheme.GATE_REQUIREMENT_PRIORITY,
        "P0",
    ),
    blocking: bool = False,
    target: object | None = None,
) -> MyWorkItem:
    return MyWorkItem(
        id=item_id,
        project_global_id=project_id,
        source=MyWorkSourceReference(source_type, gate_id, 7),
        domain_kind=None,
        category=category,
        status=status,
        due_at=due_at,
        priority=priority,
        blocking=blocking,
        target=(
            GateReviewTarget(project_id, gate_id)
            if target is None
            else target  # type: ignore[arg-type]
        ),
    )


class MyWorkStrictTypeTests(unittest.TestCase):
    def test_values_are_frozen_and_normalize_instants_to_utc(self) -> None:
        local_due = datetime(
            2026,
            7,
            25,
            20,
            tzinfo=timezone(timedelta(hours=8)),
        )
        item = domain_item(due_at=local_due)
        self.assertEqual(item.due_at, datetime(2026, 7, 25, 12, tzinfo=UTC))
        for value, attribute, replacement_value in (
            (item, "blocking", True),
            (item.source, "version", 5),
            (item.priority, "value", "critical"),
            (item.target, "work_item_id", GATE_ID),
            (MyWorkQuery(MyWorkView.ALL), "limit", 1),
        ):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, attribute, replacement_value)

    def test_due_state_uses_the_fixed_clock_and_actor_time_zone(self) -> None:
        self.assertEqual(
            my_work_due_state(
                domain_item(due_at=None),
                as_of=AS_OF,
                time_zone="UTC",
            ),
            MyWorkDueState.UNSCHEDULED,
        )
        self.assertEqual(
            my_work_due_state(
                domain_item(due_at=AS_OF - timedelta(microseconds=1)),
                as_of=AS_OF,
                time_zone="UTC",
            ),
            MyWorkDueState.OVERDUE,
        )
        self.assertEqual(
            my_work_due_state(
                domain_item(due_at=AS_OF + timedelta(hours=1)),
                as_of=AS_OF,
                time_zone="America/Los_Angeles",
            ),
            MyWorkDueState.TODAY,
        )
        self.assertEqual(
            my_work_due_state(
                domain_item(due_at=AS_OF + timedelta(days=1)),
                as_of=AS_OF,
                time_zone="UTC",
            ),
            MyWorkDueState.UPCOMING,
        )

    def test_enums_booleans_ids_instants_and_limit_are_strict(self) -> None:
        with self.assertRaises(MyWorkValidationError):
            MyWorkSourceReference(
                "domain_work_item",  # type: ignore[arg-type]
                WORK_ID,
                1,
            )
        with self.assertRaises(MyWorkValidationError):
            MyWorkSourceReference(
                MyWorkSourceType.DOMAIN_WORK_ITEM,
                UUID(int=0),
                1,
            )
        with self.assertRaises(MyWorkValidationError):
            domain_item(due_at=datetime(2026, 7, 25, 12))
        with self.assertRaises(MyWorkValidationError):
            domain_item(blocking=1)  # type: ignore[arg-type]
        for limit in (True, 0, 101):
            with self.subTest(limit=limit):
                with self.assertRaises(MyWorkValidationError):
                    MyWorkQuery(MyWorkView.ALL, limit=limit)
        self.assertEqual(MyWorkQuery(MyWorkView.ALL, limit=1).limit, 1)
        self.assertEqual(MyWorkQuery(MyWorkView.ALL, limit=100).limit, 100)

    def test_priority_is_an_exact_validated_pair_without_cross_source_mapping(
        self,
    ) -> None:
        domain_priority = MyWorkPriority(
            MyWorkPriorityScheme.DOMAIN_SEVERITY,
            "high",
        )
        gate_priority = MyWorkPriority(
            MyWorkPriorityScheme.GATE_REQUIREMENT_PRIORITY,
            "P0",
        )
        self.assertNotEqual(domain_priority, gate_priority)
        with self.assertRaises(MyWorkValidationError):
            MyWorkPriority(MyWorkPriorityScheme.DOMAIN_SEVERITY, "P0")
        with self.assertRaises(MyWorkValidationError):
            MyWorkPriority(
                MyWorkPriorityScheme.GATE_REQUIREMENT_PRIORITY,
                "high",
            )
        with self.assertRaises(MyWorkValidationError):
            replace(domain_item(), priority=gate_priority)
        with self.assertRaises(MyWorkValidationError):
            replace(gate_item(), priority=domain_priority)

    def test_domain_kind_has_one_explicit_projection_category(self) -> None:
        cases = (
            (DomainWorkItemKind.ACTION, MyWorkCategory.TASK),
            (DomainWorkItemKind.RISK, MyWorkCategory.RISK),
            (DomainWorkItemKind.ISSUE, MyWorkCategory.ISSUE),
            (DomainWorkItemKind.DECISION_REQUEST, MyWorkCategory.DECISION),
        )
        for kind, category in cases:
            with self.subTest(kind=kind):
                self.assertEqual(
                    domain_item(kind=kind, category=category).category,
                    category,
                )
                wrong = (
                    MyWorkCategory.ISSUE
                    if category is not MyWorkCategory.ISSUE
                    else MyWorkCategory.TASK
                )
                with self.assertRaises(MyWorkValidationError):
                    domain_item(kind=kind, category=wrong)

    def test_gate_sources_enforce_approval_and_blocker_contracts(self) -> None:
        self.assertEqual(gate_item().category, MyWorkCategory.APPROVAL)
        invalidation = gate_item(
            source_type=MyWorkSourceType.GATE_REVIEW_INVALIDATION,
            category=MyWorkCategory.BLOCKER,
            blocking=True,
        )
        self.assertEqual(invalidation.category, MyWorkCategory.BLOCKER)
        for source_type, category, blocking in (
            (
                MyWorkSourceType.GATE_REVIEW_ASSIGNMENT,
                MyWorkCategory.BLOCKER,
                True,
            ),
            (
                MyWorkSourceType.GATE_REVIEW_INVALIDATION,
                MyWorkCategory.BLOCKER,
                False,
            ),
            (
                MyWorkSourceType.GATE_REVIEW_INVALIDATION,
                MyWorkCategory.APPROVAL,
                True,
            ),
        ):
            with self.subTest(source_type=source_type, category=category):
                with self.assertRaises(MyWorkValidationError):
                    gate_item(
                        source_type=source_type,
                        category=category,
                        blocking=blocking,
                    )

    def test_target_is_typed_and_bound_to_exact_source_identity(self) -> None:
        with self.assertRaises(MyWorkValidationError):
            domain_item(target={"path": f"/work/{WORK_ID}"})
        with self.assertRaises(MyWorkValidationError):
            domain_item(target=DomainWorkItemTarget(GATE_ID))
        with self.assertRaises(MyWorkValidationError):
            gate_item(target=GateReviewTarget(OTHER_PROJECT_ID, GATE_ID))
        with self.assertRaises(MyWorkValidationError):
            gate_item(target=GateReviewTarget(PROJECT_ID, WORK_ID))
        self.assertFalse(hasattr(DomainWorkItemTarget(WORK_ID), "path"))
        self.assertFalse(hasattr(GateReviewTarget(PROJECT_ID, GATE_ID), "path"))


class MyWorkQueryTests(unittest.TestCase):
    def test_canonical_sort_puts_due_items_first_then_due_and_id(self) -> None:
        early_id = UUID("20000000-0000-4000-8000-000000000000")
        tied_low_id = UUID("10000000-0000-4000-8000-000000000000")
        tied_high_id = UUID("f0000000-0000-4000-8000-000000000000")
        null_low_id = UUID("30000000-0000-4000-8000-000000000000")
        null_high_id = UUID("e0000000-0000-4000-8000-000000000000")
        values = (
            domain_item(item_id=null_high_id, due_at=None),
            domain_item(
                item_id=tied_high_id,
                due_at=AS_OF - timedelta(hours=2),
            ),
            domain_item(item_id=null_low_id, due_at=None),
            domain_item(
                item_id=tied_low_id,
                due_at=AS_OF - timedelta(hours=2),
            ),
            domain_item(
                item_id=early_id,
                due_at=AS_OF - timedelta(hours=3),
            ),
        )
        ordered = sort_my_work_items(values)
        self.assertEqual(
            tuple(item.id for item in ordered),
            (
                early_id,
                tied_low_id,
                tied_high_id,
                null_low_id,
                null_high_id,
            ),
        )
        self.assertEqual(
            tuple(item.due_at is None for item in ordered),
            (False,) * 3 + (True,) * 2,
        )

    def test_today_uses_response_timezone_local_date(self) -> None:
        fixed = datetime(2026, 7, 25, 0, 30, tzinfo=UTC)
        prior_utc_day_same_local_day = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
            due_at=datetime(2026, 7, 24, 23, 30, tzinfo=UTC),
        )
        next_local_day = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000002"),
            due_at=datetime(2026, 7, 25, 7, 30, tzinfo=UTC),
        )
        selected = filter_my_work_items(
            (prior_utc_day_same_local_day, next_local_day),
            MyWorkQuery(MyWorkView.TODAY),
            as_of=fixed,
            time_zone="America/Los_Angeles",
        )
        self.assertEqual(selected, (prior_utc_day_same_local_day,))

    def test_overdue_is_strict_instant_comparison_against_fixed_as_of(self) -> None:
        overdue = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
            due_at=AS_OF - timedelta(microseconds=1),
        )
        equal = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000002"),
            due_at=AS_OF,
        )
        undated = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000003"),
            due_at=None,
        )
        selected = filter_my_work_items(
            (equal, undated, overdue),
            MyWorkQuery(MyWorkView.OVERDUE),
            as_of=AS_OF,
            time_zone="Asia/Shanghai",
        )
        self.assertEqual(selected, (overdue,))

    def test_views_use_category_blocking_and_status_without_inference(self) -> None:
        approval = gate_item(due_at=AS_OF + timedelta(days=1))
        blocking_risk = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
            blocking=True,
            status=MyWorkStatus.READY,
        )
        waiting_task = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000002"),
            kind=DomainWorkItemKind.ACTION,
            category=MyWorkCategory.TASK,
            blocking=False,
            status=MyWorkStatus.WAITING,
        )
        values = (approval, blocking_risk, waiting_task)

        def selected(view: MyWorkView) -> tuple[MyWorkItem, ...]:
            return filter_my_work_items(
                values,
                MyWorkQuery(view),
                as_of=AS_OF,
                time_zone="UTC",
            )

        self.assertEqual(selected(MyWorkView.APPROVALS), (approval,))
        self.assertEqual(selected(MyWorkView.BLOCKERS), (blocking_risk,))
        self.assertEqual(selected(MyWorkView.WAITING), (waiting_task, approval))
        self.assertEqual(selected(MyWorkView.INTEGRATION), ())

    def test_project_priority_and_limit_filters_are_exact(self) -> None:
        high = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
        )
        critical = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000002"),
            priority=MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "critical",
            ),
        )
        other_project = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000003"),
            project_id=OTHER_PROJECT_ID,
        )
        selected = filter_my_work_items(
            (other_project, critical, high),
            MyWorkQuery(
                MyWorkView.ALL,
                project_global_id=PROJECT_ID,
                priority=MyWorkPriority(
                    MyWorkPriorityScheme.DOMAIN_SEVERITY,
                    "high",
                ),
                limit=1,
            ),
            as_of=AS_OF,
            time_zone="UTC",
        )
        self.assertEqual(selected, (high,))

    def test_keyset_seek_uses_the_same_canonical_sort_tuple(self) -> None:
        first = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000001"),
        )
        second = domain_item(
            item_id=UUID("10000000-0000-4000-8000-000000000002"),
        )
        page = filter_my_work_items(
            (second, first),
            MyWorkQuery(MyWorkView.ALL, limit=1),
            as_of=AS_OF,
            time_zone="UTC",
            after=first.sort_tuple,
        )
        self.assertEqual(page, (second,))

    def test_counts_expose_availability_and_never_fake_integration_zero(self) -> None:
        values = (
            domain_item(blocking=True, status=MyWorkStatus.READY),
            gate_item(),
            gate_item(
                item_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
                source_type=MyWorkSourceType.GATE_REVIEW_INVALIDATION,
                category=MyWorkCategory.BLOCKER,
                blocking=True,
                due_at=None,
                priority=None,
                status=MyWorkStatus.BLOCKED,
            ),
        )
        counts = calculate_my_work_counts(
            values,
            as_of=AS_OF,
            time_zone="UTC",
        )
        self.assertEqual(counts.all.value, 3)
        self.assertEqual(counts.today.value, 2)
        self.assertEqual(counts.overdue.value, 1)
        self.assertEqual(counts.approvals.value, 1)
        self.assertEqual(counts.blockers.value, 2)
        self.assertEqual(counts.waiting.value, 1)
        self.assertIs(
            counts.integration.availability,
            MyWorkCountAvailability.UNAVAILABLE,
        )
        self.assertIs(
            counts.integration.reason,
            MyWorkUnavailableReason.SOURCE_NOT_AVAILABLE,
        )
        with self.assertRaises(AttributeError):
            getattr(counts.integration, "value")
        with self.assertRaises(MyWorkValidationError):
            MyWorkCounts(
                all=AvailableMyWorkCount(1),
                today=AvailableMyWorkCount(2),
                overdue=AvailableMyWorkCount(0),
                approvals=AvailableMyWorkCount(0),
                blockers=AvailableMyWorkCount(0),
                waiting=AvailableMyWorkCount(0),
                integration=UnavailableMyWorkCount(),
            )


class MyWorkCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = MyWorkCursorCodec(SIGNING_KEY)
        self.query = MyWorkQuery(
            MyWorkView.BLOCKERS,
            project_global_id=PROJECT_ID,
            priority=MyWorkPriority(
                MyWorkPriorityScheme.DOMAIN_SEVERITY,
                "high",
            ),
            limit=20,
        )
        self.last = domain_item(due_at=None).sort_tuple

    def test_signed_cursor_round_trips_fixed_query_time_and_last_tuple(self) -> None:
        token = self.codec.encode(
            query=self.query,
            as_of=AS_OF,
            time_zone="Asia/Shanghai",
            last=self.last,
        )
        decoded = self.codec.decode(
            token,
            query=replace(self.query, limit=5),
            expected_time_zone="Asia/Shanghai",
            expected_as_of=AS_OF,
        )
        self.assertEqual(decoded.as_of, AS_OF)
        self.assertEqual(decoded.time_zone, "Asia/Shanghai")
        self.assertEqual(
            decoded.query_fingerprint,
            my_work_query_fingerprint(self.query),
        )
        self.assertEqual(decoded.last, self.last)
        self.assertLessEqual(len(token), 500)

    def test_tampering_and_public_payload_forgery_fail_closed(self) -> None:
        token = self.codec.encode(
            query=self.query,
            as_of=AS_OF,
            time_zone="UTC",
            last=self.last,
        )
        replacement = "A" if token[-1] != "A" else "B"
        tampered = token[:-1] + replacement
        payload, signature = token.split(".")
        forged = ("A" if payload[0] != "A" else "B") + payload[1:] + "." + signature
        for candidate in (tampered, forged, "not.a.valid.cursor"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(InvalidMyWorkCursor):
                    self.codec.decode(
                        candidate,
                        query=self.query,
                        expected_time_zone="UTC",
                    )

    def test_query_timezone_and_as_of_mismatch_fail_closed(self) -> None:
        token = self.codec.encode(
            query=self.query,
            as_of=AS_OF,
            time_zone="UTC",
            last=self.last,
        )
        mismatches = (
            {
                "query": replace(self.query, view=MyWorkView.ALL),
                "expected_time_zone": "UTC",
            },
            {
                "query": self.query,
                "expected_time_zone": "Asia/Shanghai",
            },
            {
                "query": self.query,
                "expected_time_zone": "UTC",
                "expected_as_of": AS_OF + timedelta(microseconds=1),
            },
        )
        for mismatch in mismatches:
            with self.subTest(mismatch=mismatch):
                with self.assertRaises(InvalidMyWorkCursor):
                    self.codec.decode(token, **mismatch)

    def test_cursor_context_is_cryptographically_independent(self) -> None:
        token = self.codec.encode(
            query=self.query,
            as_of=AS_OF,
            time_zone="UTC",
            last=MyWorkSortTuple(AS_OF, WORK_ID),
        )
        other_context = MyWorkCursorCodec(
            SIGNING_KEY,
            context=b"npi-one:another-projection:cursor:v1",
        )
        with self.assertRaises(InvalidMyWorkCursor):
            other_context.decode(
                token,
                query=self.query,
                expected_time_zone="UTC",
            )

    def test_cursor_key_and_context_configuration_are_strict(self) -> None:
        for key in (b"short", bytearray(SIGNING_KEY)):
            with self.subTest(key=type(key).__name__):
                with self.assertRaises(MyWorkValidationError):
                    MyWorkCursorCodec(key)  # type: ignore[arg-type]
        with self.assertRaises(MyWorkValidationError):
            MyWorkCursorCodec(SIGNING_KEY, context=b"")


if __name__ == "__main__":
    unittest.main()
