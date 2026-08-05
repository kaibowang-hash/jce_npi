from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


EBOM_POLICY_SCHEMA_VERSION = 1
EBOM_REVISION_SCHEMA_VERSION = 1
EBOM_LIFECYCLE_EVENT_SCHEMA_VERSION = 1
MAX_EBOM_NODES = 500
MAX_POLICY_USERS = 100
MAX_POLICY_UOMS = 50
MAX_POLICY_ATTRIBUTES = 50

_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_ATTRIBUTE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_EBOM_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_ENGINEERING_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_LINE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_UOM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,15}$")


def sha256_json(value: object) -> str:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EngineeringBomPolicyState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class EngineeringBomLifecycleState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    RELEASED = "released"


class EngineeringBomReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class EngineeringBomEventType(StrEnum):
    REVIEW_SUBMITTED = "review_submitted"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    RELEASED = "released"


class EngineeringBomChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    QUANTITY = "quantity"
    SUBSTITUTION = "substitution"
    ATTRIBUTE = "attribute"


class EngineeringBomPolicyUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            503,
            "EBOM_POLICY_UNAVAILABLE",
            _("The EBOM policy is unavailable."),
        )


class EngineeringBomAuthorityUnavailable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            403,
            "EBOM_AUTHORITY_UNAVAILABLE",
            _("You are not authorized to perform this EBOM action."),
        )


class EngineeringBomStateConflict(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "EBOM_STATE_CONFLICT",
            _("The EBOM revision changed. Reload it before continuing."),
        )


@dataclass(frozen=True, slots=True)
class EngineeringBomPolicyReference:
    global_id: UUID
    version: int
    snapshot_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "policy.globalId"))
        object.__setattr__(self, "version", _positive(self.version, "policy.version"))
        object.__setattr__(
            self,
            "snapshot_hash",
            _hash(self.snapshot_hash, "policy.snapshotHash"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "version": self.version,
            "snapshotHash": self.snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class EngineeringBomPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    policy_key: str
    policy_version: int
    title: str
    state: EngineeringBomPolicyState
    synthetic_namespace: str
    quantity_scale: int
    maximum_nodes: int
    engineering_uoms: tuple[str, ...]
    attribute_keys: tuple[str, ...]
    creator_user_ids: tuple[str, ...]
    review_submitter_user_ids: tuple[str, ...]
    reviewer_user_ids: tuple[str, ...]
    release_authority_user_ids: tuple[str, ...]
    line_identity_mode: str = "caller_supplied_stable_key"
    require_acyclic_graph: bool = True
    require_closed_alternates: bool = True
    require_effectivity_order: bool = True
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "policy_global_id", "project_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"ebomPolicy.{fieldname}"),
            )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "ebomPolicy.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "policy_key",
            _text(
                self.policy_key,
                "ebomPolicy.key",
                maximum=64,
                pattern=_ATTRIBUTE_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _positive(self.policy_version, "ebomPolicy.version"),
        )
        object.__setattr__(
            self,
            "title",
            _text(self.title, "ebomPolicy.title", maximum=140),
        )
        if not isinstance(self.state, EngineeringBomPolicyState):
            raise _field_problem("ebomPolicy.state", _("Select a supported value."))
        object.__setattr__(
            self,
            "synthetic_namespace",
            _text(
                self.synthetic_namespace,
                "ebomPolicy.syntheticNamespace",
                maximum=32,
                pattern=_ATTRIBUTE_KEY_PATTERN,
            ),
        )
        if not self.synthetic_namespace.startswith("synthetic_"):
            raise _field_problem(
                "ebomPolicy.syntheticNamespace",
                _("Use an explicitly synthetic EBOM namespace."),
            )
        object.__setattr__(
            self,
            "quantity_scale",
            _integer_range(self.quantity_scale, "ebomPolicy.quantityScale", 0, 6),
        )
        object.__setattr__(
            self,
            "maximum_nodes",
            _integer_range(
                self.maximum_nodes,
                "ebomPolicy.maximumNodes",
                1,
                MAX_EBOM_NODES,
            ),
        )
        object.__setattr__(
            self,
            "engineering_uoms",
            _unique_texts(
                self.engineering_uoms,
                "ebomPolicy.engineeringUoms",
                maximum_items=MAX_POLICY_UOMS,
                maximum_text=16,
                pattern=_UOM_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "attribute_keys",
            _unique_texts(
                self.attribute_keys,
                "ebomPolicy.attributeKeys",
                maximum_items=MAX_POLICY_ATTRIBUTES,
                maximum_text=64,
                pattern=_ATTRIBUTE_KEY_PATTERN,
                allow_empty=True,
            ),
        )
        for fieldname in (
            "creator_user_ids",
            "review_submitter_user_ids",
            "reviewer_user_ids",
            "release_authority_user_ids",
        ):
            object.__setattr__(
                self,
                fieldname,
                _unique_texts(
                    getattr(self, fieldname),
                    f"ebomPolicy.{fieldname}",
                    maximum_items=MAX_POLICY_USERS,
                    maximum_text=254,
                    pattern=_ACTOR_PATTERN,
                ),
            )
        if self.line_identity_mode != "caller_supplied_stable_key":
            raise _field_problem(
                "ebomPolicy.lineIdentityMode",
                _("Select the supported stable line identity mode."),
            )
        for fieldname in (
            "require_acyclic_graph",
            "require_closed_alternates",
            "require_effectivity_order",
        ):
            if getattr(self, fieldname) is not True:
                raise _field_problem(
                    f"ebomPolicy.{fieldname}",
                    _("The fail-closed EBOM validation rule is required."),
                )
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "ebomPolicy.snapshotHash",
                _("The EBOM policy snapshot hash does not match its rules."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    @property
    def reference(self) -> EngineeringBomPolicyReference:
        return EngineeringBomPolicyReference(
            self.policy_global_id,
            self.policy_version,
            self.snapshot_hash,
        )

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": EBOM_POLICY_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "policyGlobalId": str(self.policy_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "key": self.policy_key,
            "version": self.policy_version,
            "title": self.title,
            "state": self.state.value,
            "syntheticNamespace": self.synthetic_namespace,
            "lineIdentityMode": self.line_identity_mode,
            "quantityScale": self.quantity_scale,
            "maximumNodes": self.maximum_nodes,
            "engineeringUoms": list(self.engineering_uoms),
            "attributeKeys": list(self.attribute_keys),
            "creatorUserIds": list(self.creator_user_ids),
            "reviewSubmitterUserIds": list(self.review_submitter_user_ids),
            "reviewerUserIds": list(self.reviewer_user_ids),
            "releaseAuthorityUserIds": list(self.release_authority_user_ids),
            "requireAcyclicGraph": self.require_acyclic_graph,
            "requireClosedAlternates": self.require_closed_alternates,
            "requireEffectivityOrder": self.require_effectivity_order,
        }

    def permits(self, action: str, actor: str) -> bool:
        values = {
            "create": self.creator_user_ids,
            "submit_review": self.review_submitter_user_ids,
            "review": self.reviewer_user_ids,
            "release": self.release_authority_user_ids,
        }.get(action, ())
        candidate = actor.casefold()
        return any(value.casefold() == candidate for value in values)


@dataclass(frozen=True, slots=True)
class EngineeringBomLine:
    global_id: UUID
    line_key: str
    parent_line_key: str | None
    engineering_item_id: str
    description: str
    quantity: Decimal
    engineering_uom: str
    alternate_for_line_key: str | None = None
    alternate_group_key: str | None = None
    effectivity_start: date | None = None
    effectivity_end: date | None = None
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "global_id", _uuid(self.global_id, "ebomLine.globalId"))
        object.__setattr__(
            self,
            "line_key",
            _text(
                self.line_key,
                "ebomLine.lineKey",
                maximum=64,
                pattern=_LINE_KEY_PATTERN,
            ),
        )
        for fieldname in (
            "parent_line_key",
            "alternate_for_line_key",
            "alternate_group_key",
        ):
            value = getattr(self, fieldname)
            object.__setattr__(
                self,
                fieldname,
                _optional_text(
                    value,
                    f"ebomLine.{fieldname}",
                    maximum=64,
                    pattern=_LINE_KEY_PATTERN,
                ),
            )
        object.__setattr__(
            self,
            "engineering_item_id",
            _text(
                self.engineering_item_id,
                "ebomLine.engineeringItemId",
                maximum=128,
                pattern=_ENGINEERING_ID_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "description",
            _text(self.description, "ebomLine.description", maximum=280),
        )
        object.__setattr__(
            self,
            "quantity",
            _decimal(self.quantity, "ebomLine.quantity"),
        )
        object.__setattr__(
            self,
            "engineering_uom",
            _text(
                self.engineering_uom,
                "ebomLine.engineeringUom",
                maximum=16,
                pattern=_UOM_PATTERN,
            ),
        )
        for fieldname in ("effectivity_start", "effectivity_end"):
            value = getattr(self, fieldname)
            if value is not None and (not isinstance(value, date) or isinstance(value, datetime)):
                raise _field_problem(
                    f"ebomLine.{fieldname}",
                    _("Enter a valid effectivity date."),
                )
        if (
            self.effectivity_start is not None
            and self.effectivity_end is not None
            and self.effectivity_start > self.effectivity_end
        ):
            raise _field_problem(
                "ebomLine.effectivityEnd",
                _("Effectivity end cannot be before its start."),
            )
        if self.alternate_for_line_key is not None and self.alternate_group_key is None:
            raise _field_problem(
                "ebomLine.alternateForLineKey",
                _("An alternate line requires an alternate group."),
            )
        normalized_attributes = _attributes(self.attributes)
        object.__setattr__(self, "attributes", normalized_attributes)

    def canonical_dict(self, quantity_scale: int) -> dict[str, object]:
        return {
            "globalId": str(self.global_id),
            "lineKey": self.line_key,
            "parentLineKey": self.parent_line_key,
            "engineeringItemId": self.engineering_item_id,
            "description": self.description,
            "quantity": _decimal_text(self.quantity, quantity_scale),
            "engineeringUom": self.engineering_uom,
            "alternateForLineKey": self.alternate_for_line_key,
            "alternateGroupKey": self.alternate_group_key,
            "effectivityStart": (
                self.effectivity_start.isoformat()
                if self.effectivity_start is not None
                else None
            ),
            "effectivityEnd": (
                self.effectivity_end.isoformat()
                if self.effectivity_end is not None
                else None
            ),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class EngineeringBomRevision:
    global_id: UUID
    ebom_global_id: UUID
    tenant_id: str
    project_global_id: UUID
    engineering_bom_key: str
    revision_number: int
    predecessor_global_id: UUID | None
    predecessor_snapshot_hash: str | None
    reason: str
    effectivity_note: str | None
    policy_ref: EngineeringBomPolicyReference
    quantity_scale: int
    lines: tuple[EngineeringBomLine, ...]
    created_by_user_id: str
    created_at: datetime
    request_id: str
    trace_id: str
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "ebom_global_id", "project_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"ebomRevision.{fieldname}"),
            )
        object.__setattr__(
            self,
            "tenant_id",
            _text(
                self.tenant_id,
                "ebomRevision.tenantId",
                maximum=128,
                pattern=_TENANT_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "engineering_bom_key",
            _text(
                self.engineering_bom_key,
                "ebomRevision.key",
                maximum=64,
                pattern=_EBOM_KEY_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "revision_number",
            _positive(self.revision_number, "ebomRevision.revisionNumber"),
        )
        predecessor = self.predecessor_global_id
        if predecessor is not None:
            predecessor = _uuid(predecessor, "ebomRevision.predecessorGlobalId")
        object.__setattr__(self, "predecessor_global_id", predecessor)
        predecessor_hash = self.predecessor_snapshot_hash
        if predecessor_hash is not None:
            predecessor_hash = _hash(
                predecessor_hash,
                "ebomRevision.predecessorSnapshotHash",
            )
        object.__setattr__(self, "predecessor_snapshot_hash", predecessor_hash)
        if (predecessor is None) != (predecessor_hash is None):
            raise _field_problem(
                "ebomRevision.predecessorGlobalId",
                _("Predecessor identity and snapshot hash must be supplied together."),
            )
        if self.revision_number == 1 and predecessor is not None:
            raise _field_problem(
                "ebomRevision.predecessorGlobalId",
                _("The first EBOM revision cannot have a predecessor."),
            )
        if self.revision_number > 1 and predecessor is None:
            raise _field_problem(
                "ebomRevision.predecessorGlobalId",
                _("A successor EBOM revision requires an exact predecessor."),
            )
        object.__setattr__(
            self,
            "reason",
            _text(self.reason, "ebomRevision.reason", maximum=280),
        )
        object.__setattr__(
            self,
            "effectivity_note",
            _optional_text(
                self.effectivity_note,
                "ebomRevision.effectivityNote",
                maximum=280,
            ),
        )
        if not isinstance(self.policy_ref, EngineeringBomPolicyReference):
            raise _field_problem(
                "ebomRevision.policyRef",
                _("Select an exact EBOM policy version."),
            )
        object.__setattr__(
            self,
            "quantity_scale",
            _integer_range(self.quantity_scale, "ebomRevision.quantityScale", 0, 6),
        )
        if (
            isinstance(self.lines, (str, bytes))
            or not isinstance(self.lines, Sequence)
            or not self.lines
            or len(self.lines) > MAX_EBOM_NODES
            or not all(isinstance(value, EngineeringBomLine) for value in self.lines)
        ):
            raise _field_problem(
                "ebomRevision.lines",
                _("Enter a bounded EBOM line list."),
            )
        ordered = tuple(sorted(self.lines, key=lambda value: value.line_key))
        if len({value.global_id for value in ordered}) != len(ordered) or len(
            {value.line_key.casefold() for value in ordered}
        ) != len(ordered):
            raise _field_problem(
                "ebomRevision.lines",
                _("EBOM line identities and keys must be unique."),
            )
        object.__setattr__(self, "lines", ordered)
        _validate_graph(ordered)
        object.__setattr__(
            self,
            "created_by_user_id",
            _text(
                self.created_by_user_id,
                "ebomRevision.createdByUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _utc_datetime(self.created_at, "ebomRevision.createdAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "ebomRevision.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "ebomRevision.traceId", maximum=128),
        )
        expected = sha256_json(self.snapshot_payload())
        if self.snapshot_hash and self.snapshot_hash != expected:
            raise _field_problem(
                "ebomRevision.snapshotHash",
                _("The EBOM revision snapshot hash does not match its lines."),
            )
        object.__setattr__(self, "snapshot_hash", expected)

    def snapshot_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": EBOM_REVISION_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "ebomGlobalId": str(self.ebom_global_id),
            "tenantId": self.tenant_id,
            "projectGlobalId": str(self.project_global_id),
            "engineeringBomKey": self.engineering_bom_key,
            "revisionNumber": self.revision_number,
            "predecessorGlobalId": (
                str(self.predecessor_global_id)
                if self.predecessor_global_id is not None
                else None
            ),
            "predecessorSnapshotHash": self.predecessor_snapshot_hash,
            "reason": self.reason,
            "effectivityNote": self.effectivity_note,
            "policyRef": self.policy_ref.canonical_dict(),
            "quantityScale": self.quantity_scale,
            "lines": [
                value.canonical_dict(self.quantity_scale) for value in self.lines
            ],
            "createdByUserId": self.created_by_user_id,
            "createdAt": _timestamp(self.created_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


def create_engineering_bom_revision(
    *,
    global_id: UUID,
    ebom_global_id: UUID,
    tenant_id: str,
    project_global_id: UUID,
    engineering_bom_key: str,
    revision_number: int,
    predecessor: EngineeringBomRevision | None,
    reason: str,
    effectivity_note: str | None,
    policy: EngineeringBomPolicyVersion,
    lines: Sequence[EngineeringBomLine],
    actor: str,
    now: datetime,
    request_id: str,
    trace_id: str,
) -> EngineeringBomRevision:
    if (
        policy.state is not EngineeringBomPolicyState.PUBLISHED
        or policy.tenant_id != tenant_id
        or policy.project_global_id != project_global_id
    ):
        raise EngineeringBomPolicyUnavailable()
    if not policy.permits("create", actor):
        raise EngineeringBomAuthorityUnavailable()
    if predecessor is None:
        if revision_number != 1:
            raise _field_problem(
                "ebomRevision.revisionNumber",
                _("The first EBOM revision must use revision number 1."),
            )
        predecessor_global_id = None
        predecessor_snapshot_hash = None
    else:
        if (
            predecessor.ebom_global_id != ebom_global_id
            or predecessor.tenant_id != tenant_id
            or predecessor.project_global_id != project_global_id
            or predecessor.engineering_bom_key != engineering_bom_key
            or revision_number != predecessor.revision_number + 1
        ):
            raise _field_problem(
                "ebomRevision.predecessorGlobalId",
                _("Select the exact current EBOM predecessor."),
            )
        predecessor_global_id = predecessor.global_id
        predecessor_snapshot_hash = predecessor.snapshot_hash
    prepared = tuple(lines)
    revision = EngineeringBomRevision(
        global_id=global_id,
        ebom_global_id=ebom_global_id,
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        engineering_bom_key=engineering_bom_key,
        revision_number=revision_number,
        predecessor_global_id=predecessor_global_id,
        predecessor_snapshot_hash=predecessor_snapshot_hash,
        reason=reason,
        effectivity_note=effectivity_note,
        policy_ref=policy.reference,
        quantity_scale=policy.quantity_scale,
        lines=prepared,
        created_by_user_id=actor,
        created_at=now,
        request_id=request_id,
        trace_id=trace_id,
    )
    validate_revision_against_policy(revision, policy)
    return revision


def validate_revision_against_policy(
    revision: EngineeringBomRevision,
    policy: EngineeringBomPolicyVersion,
) -> None:
    if (
        policy.state is not EngineeringBomPolicyState.PUBLISHED
        or revision.tenant_id != policy.tenant_id
        or revision.project_global_id != policy.project_global_id
        or revision.policy_ref != policy.reference
        or revision.quantity_scale != policy.quantity_scale
    ):
        raise EngineeringBomPolicyUnavailable()
    if not revision.engineering_bom_key.startswith(
        f"{policy.synthetic_namespace}-"
    ):
        raise _field_problem(
            "ebomRevision.engineeringBomKey",
            _("The EBOM key does not match the selected synthetic policy."),
        )
    if len(revision.lines) > policy.maximum_nodes:
        raise _field_problem(
            "ebomRevision.lines",
            _("The EBOM contains more lines than the selected policy allows."),
        )
    allowed_uoms = {value.casefold() for value in policy.engineering_uoms}
    allowed_attributes = set(policy.attribute_keys)
    for index, line in enumerate(revision.lines):
        if line.engineering_uom.casefold() not in allowed_uoms:
            raise _field_problem(
                f"ebomRevision.lines[{index}].engineeringUom",
                _("Select an engineering UOM allowed by the EBOM policy."),
            )
        if any(key not in allowed_attributes for key, _value in line.attributes):
            raise _field_problem(
                f"ebomRevision.lines[{index}].attributes",
                _("Use only attributes allowed by the EBOM policy."),
            )
        if _decimal_scale(line.quantity) > policy.quantity_scale:
            raise _field_problem(
                f"ebomRevision.lines[{index}].quantity",
                _("Quantity precision exceeds the EBOM policy."),
            )


@dataclass(frozen=True, slots=True)
class EngineeringBomRevisionLifecycle:
    revision_global_id: UUID
    revision_snapshot_hash: str
    current_state: EngineeringBomLifecycleState
    lifecycle_version: int
    last_event_global_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "revision_global_id",
            _uuid(self.revision_global_id, "ebomLifecycle.revisionGlobalId"),
        )
        object.__setattr__(
            self,
            "revision_snapshot_hash",
            _hash(
                self.revision_snapshot_hash,
                "ebomLifecycle.revisionSnapshotHash",
            ),
        )
        if not isinstance(self.current_state, EngineeringBomLifecycleState):
            raise _field_problem(
                "ebomLifecycle.currentState",
                _("Select a supported EBOM lifecycle state."),
            )
        object.__setattr__(
            self,
            "lifecycle_version",
            _positive(self.lifecycle_version, "ebomLifecycle.lifecycleVersion"),
        )
        if self.last_event_global_id is not None:
            object.__setattr__(
                self,
                "last_event_global_id",
                _uuid(
                    self.last_event_global_id,
                    "ebomLifecycle.lastEventGlobalId",
                ),
            )


@dataclass(frozen=True, slots=True)
class EngineeringBomLifecycleEvent:
    global_id: UUID
    revision_global_id: UUID
    revision_snapshot_hash: str
    policy_ref: EngineeringBomPolicyReference
    event_type: EngineeringBomEventType
    from_state: EngineeringBomLifecycleState
    to_state: EngineeringBomLifecycleState
    from_version: int
    to_version: int
    actor_user_id: str
    authority_action: str
    decision: EngineeringBomReviewDecision | None
    reason: str | None
    confirmation_intent: str | None
    occurred_at: datetime
    request_id: str
    trace_id: str
    event_hash: str = ""

    def __post_init__(self) -> None:
        for fieldname in ("global_id", "revision_global_id"):
            object.__setattr__(
                self,
                fieldname,
                _uuid(getattr(self, fieldname), f"ebomEvent.{fieldname}"),
            )
        object.__setattr__(
            self,
            "revision_snapshot_hash",
            _hash(self.revision_snapshot_hash, "ebomEvent.revisionSnapshotHash"),
        )
        if not isinstance(self.policy_ref, EngineeringBomPolicyReference):
            raise _field_problem(
                "ebomEvent.policyRef",
                _("Select an exact EBOM policy version."),
            )
        if not isinstance(self.event_type, EngineeringBomEventType):
            raise _field_problem(
                "ebomEvent.eventType",
                _("Select a supported EBOM lifecycle event."),
            )
        if not isinstance(self.from_state, EngineeringBomLifecycleState) or not isinstance(
            self.to_state, EngineeringBomLifecycleState
        ):
            raise _field_problem(
                "ebomEvent.state",
                _("Select supported EBOM lifecycle states."),
            )
        object.__setattr__(
            self,
            "from_version",
            _positive(self.from_version, "ebomEvent.fromVersion"),
        )
        object.__setattr__(
            self,
            "to_version",
            _positive(self.to_version, "ebomEvent.toVersion"),
        )
        if self.to_version != self.from_version + 1:
            raise _field_problem(
                "ebomEvent.toVersion",
                _("The EBOM lifecycle version must advance exactly once."),
            )
        object.__setattr__(
            self,
            "actor_user_id",
            _text(
                self.actor_user_id,
                "ebomEvent.actorUserId",
                maximum=254,
                pattern=_ACTOR_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "authority_action",
            _text(
                self.authority_action,
                "ebomEvent.authorityAction",
                maximum=32,
                pattern=_ATTRIBUTE_KEY_PATTERN,
            ),
        )
        if self.decision is not None and not isinstance(
            self.decision, EngineeringBomReviewDecision
        ):
            raise _field_problem(
                "ebomEvent.decision",
                _("Select a supported EBOM review decision."),
            )
        object.__setattr__(
            self,
            "reason",
            _optional_text(self.reason, "ebomEvent.reason", maximum=280),
        )
        object.__setattr__(
            self,
            "confirmation_intent",
            _optional_text(
                self.confirmation_intent,
                "ebomEvent.confirmationIntent",
                maximum=64,
                pattern=_ATTRIBUTE_KEY_PATTERN,
            ),
        )
        expected_transition = {
            EngineeringBomEventType.REVIEW_SUBMITTED: (
                EngineeringBomLifecycleState.DRAFT,
                EngineeringBomLifecycleState.IN_REVIEW,
                "submit_review",
                None,
            ),
            EngineeringBomEventType.REVIEW_APPROVED: (
                EngineeringBomLifecycleState.IN_REVIEW,
                EngineeringBomLifecycleState.APPROVED,
                "review",
                EngineeringBomReviewDecision.APPROVE,
            ),
            EngineeringBomEventType.REVIEW_REJECTED: (
                EngineeringBomLifecycleState.IN_REVIEW,
                EngineeringBomLifecycleState.DRAFT,
                "review",
                EngineeringBomReviewDecision.REJECT,
            ),
            EngineeringBomEventType.RELEASED: (
                EngineeringBomLifecycleState.APPROVED,
                EngineeringBomLifecycleState.RELEASED,
                "release",
                None,
            ),
        }[self.event_type]
        if (
            self.from_state,
            self.to_state,
            self.authority_action,
            self.decision,
        ) != expected_transition:
            raise _field_problem(
                "ebomEvent.eventType",
                _("The EBOM lifecycle event does not match its exact transition."),
            )
        if (
            self.event_type is EngineeringBomEventType.REVIEW_REJECTED
            and self.reason is None
        ):
            raise _field_problem(
                "ebomEvent.reason",
                _("Enter a reason for rejecting the EBOM revision."),
            )
        if self.event_type is EngineeringBomEventType.RELEASED:
            if self.confirmation_intent != "release_exact_ebom_revision":
                raise _field_problem(
                    "ebomEvent.confirmationIntent",
                    _("Confirm release of the exact EBOM revision."),
                )
        elif self.confirmation_intent is not None:
            raise _field_problem(
                "ebomEvent.confirmationIntent",
                _("Confirmation intent is only valid for EBOM release."),
            )
        object.__setattr__(
            self,
            "occurred_at",
            _utc_datetime(self.occurred_at, "ebomEvent.occurredAt"),
        )
        object.__setattr__(
            self,
            "request_id",
            _text(self.request_id, "ebomEvent.requestId", maximum=128),
        )
        object.__setattr__(
            self,
            "trace_id",
            _text(self.trace_id, "ebomEvent.traceId", maximum=128),
        )
        expected = sha256_json(self.event_payload())
        if self.event_hash and self.event_hash != expected:
            raise _field_problem(
                "ebomEvent.eventHash",
                _("The EBOM lifecycle event hash does not match its content."),
            )
        object.__setattr__(self, "event_hash", expected)

    def event_payload(self) -> dict[str, object]:
        return {
            "schemaVersion": EBOM_LIFECYCLE_EVENT_SCHEMA_VERSION,
            "globalId": str(self.global_id),
            "revisionGlobalId": str(self.revision_global_id),
            "revisionSnapshotHash": self.revision_snapshot_hash,
            "policyRef": self.policy_ref.canonical_dict(),
            "eventType": self.event_type.value,
            "fromState": self.from_state.value,
            "toState": self.to_state.value,
            "fromVersion": self.from_version,
            "toVersion": self.to_version,
            "actorUserId": self.actor_user_id,
            "authorityAction": self.authority_action,
            "decision": self.decision.value if self.decision is not None else None,
            "reason": self.reason,
            "confirmationIntent": self.confirmation_intent,
            "occurredAt": _timestamp(self.occurred_at),
            "requestId": self.request_id,
            "traceId": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class EngineeringBomTransition:
    lifecycle: EngineeringBomRevisionLifecycle
    event: EngineeringBomLifecycleEvent


def transition_engineering_bom(
    *,
    lifecycle: EngineeringBomRevisionLifecycle,
    policy: EngineeringBomPolicyVersion,
    actor: str,
    event_global_id: UUID,
    now: datetime,
    request_id: str,
    trace_id: str,
    expected_version: int,
    action: str,
    decision: EngineeringBomReviewDecision | None = None,
    reason: str | None = None,
    confirmed: bool = False,
    confirmation_intent: str | None = None,
) -> EngineeringBomTransition:
    if policy.state is not EngineeringBomPolicyState.PUBLISHED:
        raise EngineeringBomPolicyUnavailable()
    if lifecycle.lifecycle_version != expected_version:
        raise EngineeringBomStateConflict()
    if not policy.permits(action, actor):
        raise EngineeringBomAuthorityUnavailable()
    from_state = lifecycle.current_state
    if action == "submit_review" and from_state is EngineeringBomLifecycleState.DRAFT:
        event_type = EngineeringBomEventType.REVIEW_SUBMITTED
        to_state = EngineeringBomLifecycleState.IN_REVIEW
        authority_action = "submit_review"
        decision = None
        confirmation_intent = None
    elif action == "review" and from_state is EngineeringBomLifecycleState.IN_REVIEW:
        authority_action = "review"
        confirmation_intent = None
        if decision is EngineeringBomReviewDecision.APPROVE:
            event_type = EngineeringBomEventType.REVIEW_APPROVED
            to_state = EngineeringBomLifecycleState.APPROVED
        elif decision is EngineeringBomReviewDecision.REJECT:
            event_type = EngineeringBomEventType.REVIEW_REJECTED
            to_state = EngineeringBomLifecycleState.DRAFT
            if reason is None:
                raise _field_problem(
                    "ebomReview.reason",
                    _("Enter a reason for rejecting the EBOM revision."),
                )
        else:
            raise _field_problem(
                "ebomReview.decision",
                _("Select approve or reject."),
            )
    elif action == "release" and from_state is EngineeringBomLifecycleState.APPROVED:
        if confirmed is not True or confirmation_intent != "release_exact_ebom_revision":
            raise _field_problem(
                "ebomRelease.confirmed",
                _("Confirm release of the exact EBOM revision."),
            )
        event_type = EngineeringBomEventType.RELEASED
        to_state = EngineeringBomLifecycleState.RELEASED
        authority_action = "release"
        decision = None
    else:
        raise EngineeringBomStateConflict()
    event = EngineeringBomLifecycleEvent(
        global_id=event_global_id,
        revision_global_id=lifecycle.revision_global_id,
        revision_snapshot_hash=lifecycle.revision_snapshot_hash,
        policy_ref=policy.reference,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        from_version=lifecycle.lifecycle_version,
        to_version=lifecycle.lifecycle_version + 1,
        actor_user_id=actor,
        authority_action=authority_action,
        decision=decision,
        reason=reason,
        confirmation_intent=confirmation_intent,
        occurred_at=now,
        request_id=request_id,
        trace_id=trace_id,
    )
    return EngineeringBomTransition(
        lifecycle=EngineeringBomRevisionLifecycle(
            revision_global_id=lifecycle.revision_global_id,
            revision_snapshot_hash=lifecycle.revision_snapshot_hash,
            current_state=to_state,
            lifecycle_version=lifecycle.lifecycle_version + 1,
            last_event_global_id=event.global_id,
        ),
        event=event,
    )


@dataclass(frozen=True, slots=True)
class EngineeringBomDifference:
    line_key: str
    change_type: EngineeringBomChangeType
    changed_fields: tuple[str, ...]
    before: Mapping[str, object] | None
    after: Mapping[str, object] | None


def compare_engineering_bom_revisions(
    before: EngineeringBomRevision,
    after: EngineeringBomRevision,
) -> tuple[EngineeringBomDifference, ...]:
    if (
        before.ebom_global_id != after.ebom_global_id
        or before.tenant_id != after.tenant_id
        or before.project_global_id != after.project_global_id
    ):
        raise _field_problem(
            "ebomComparison",
            _("Compare exact revisions from the same EBOM."),
        )
    old = {line.line_key: line for line in before.lines}
    new = {line.line_key: line for line in after.lines}
    differences: list[EngineeringBomDifference] = []
    for line_key in sorted(set(old) | set(new), key=str.casefold):
        prior = old.get(line_key)
        current = new.get(line_key)
        if prior is None and current is not None:
            differences.append(
                EngineeringBomDifference(
                    line_key,
                    EngineeringBomChangeType.ADDED,
                    ("line",),
                    None,
                    current.canonical_dict(after.quantity_scale),
                )
            )
            continue
        if prior is not None and current is None:
            differences.append(
                EngineeringBomDifference(
                    line_key,
                    EngineeringBomChangeType.REMOVED,
                    ("line",),
                    prior.canonical_dict(before.quantity_scale),
                    None,
                )
            )
            continue
        assert prior is not None and current is not None
        prior_value = prior.canonical_dict(before.quantity_scale)
        current_value = current.canonical_dict(after.quantity_scale)
        if prior.quantity != current.quantity:
            differences.append(
                EngineeringBomDifference(
                    line_key,
                    EngineeringBomChangeType.QUANTITY,
                    ("quantity",),
                    {"quantity": prior_value["quantity"]},
                    {"quantity": current_value["quantity"]},
                )
            )
        substitution_fields = tuple(
            field
            for field in (
                "engineeringItemId",
                "alternateForLineKey",
                "alternateGroupKey",
            )
            if prior_value[field] != current_value[field]
        )
        if substitution_fields:
            differences.append(
                EngineeringBomDifference(
                    line_key,
                    EngineeringBomChangeType.SUBSTITUTION,
                    substitution_fields,
                    {field: prior_value[field] for field in substitution_fields},
                    {field: current_value[field] for field in substitution_fields},
                )
            )
        attribute_fields = tuple(
            field
            for field in (
                "parentLineKey",
                "description",
                "engineeringUom",
                "effectivityStart",
                "effectivityEnd",
                "attributes",
            )
            if prior_value[field] != current_value[field]
        )
        if attribute_fields:
            differences.append(
                EngineeringBomDifference(
                    line_key,
                    EngineeringBomChangeType.ATTRIBUTE,
                    attribute_fields,
                    {field: prior_value[field] for field in attribute_fields},
                    {field: current_value[field] for field in attribute_fields},
                )
            )
    return tuple(differences)


def _validate_graph(lines: Sequence[EngineeringBomLine]) -> None:
    by_key = {line.line_key: line for line in lines}
    for line in lines:
        if line.parent_line_key is not None:
            parent = by_key.get(line.parent_line_key)
            if parent is None or parent.line_key == line.line_key:
                raise _field_problem(
                    "ebomRevision.lines",
                    _("Every EBOM parent must be another exact line in the revision."),
                )
        if line.alternate_for_line_key is not None:
            target = by_key.get(line.alternate_for_line_key)
            if (
                target is None
                or target.line_key == line.line_key
                or target.alternate_for_line_key is not None
                or target.parent_line_key != line.parent_line_key
                or target.alternate_group_key != line.alternate_group_key
            ):
                raise _field_problem(
                    "ebomRevision.lines",
                    _("Every EBOM alternate must reference one unambiguous sibling line."),
                )
    for start in by_key:
        seen: set[str] = set()
        current = start
        while current is not None:
            if current in seen:
                raise _field_problem(
                    "ebomRevision.lines",
                    _("The EBOM hierarchy cannot contain a cycle."),
                )
            seen.add(current)
            current = by_key[current].parent_line_key


def _field_problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise _field_problem(path, _("Enter a valid global ID."))
    return value


def _text(
    value: object,
    path: str,
    *,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_problem(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        raise _field_problem(path, _("Enter a valid value."))
    return normalized


def _optional_text(
    value: object,
    path: str,
    *,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, path, maximum=maximum, pattern=pattern)


def _hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise _field_problem(path, _("Enter a valid lowercase SHA-256 hash."))
    return value


def _positive(value: object, path: str) -> int:
    if type(value) is not int or value < 1:
        raise _field_problem(path, _("Enter an integer greater than zero."))
    return value


def _integer_range(value: object, path: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise _field_problem(path, _("Enter a whole number within the allowed range."))
    return value


def _decimal(value: object, path: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise _field_problem(path, _("Enter a positive decimal quantity."))
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise _field_problem(path, _("Enter a positive decimal quantity.")) from error
    if not parsed.is_finite() or parsed <= 0:
        raise _field_problem(path, _("Enter a positive decimal quantity."))
    return parsed


def _decimal_scale(value: Decimal) -> int:
    return max(0, -value.normalize().as_tuple().exponent)


def _decimal_text(value: Decimal, scale: int) -> str:
    quantum = Decimal(1).scaleb(-scale)
    return format(value.quantize(quantum), "f")


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _field_problem(path, _("Enter a timezone-aware date and time."))
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _unique_texts(
    values: object,
    path: str,
    *,
    maximum_items: int,
    maximum_text: int,
    pattern: re.Pattern[str],
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or len(values) > maximum_items
        or (not values and not allow_empty)
    ):
        raise _field_problem(path, _("Enter a bounded list of values."))
    normalized = tuple(
        _text(
            value,
            f"{path}[{index}]",
            maximum=maximum_text,
            pattern=pattern,
        )
        for index, value in enumerate(values)
    )
    if len({value.casefold() for value in normalized}) != len(normalized):
        raise _field_problem(path, _("Values must be unique."))
    return tuple(sorted(normalized, key=str.casefold))


def _attributes(values: object) -> tuple[tuple[str, str], ...]:
    if isinstance(values, Mapping):
        pairs = tuple(values.items())
    elif isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        pairs = tuple(values)
    else:
        raise _field_problem("ebomLine.attributes", _("Enter controlled attributes."))
    if len(pairs) > MAX_POLICY_ATTRIBUTES:
        raise _field_problem("ebomLine.attributes", _("Enter controlled attributes."))
    normalized: list[tuple[str, str]] = []
    for index, value in enumerate(pairs):
        if (
            not isinstance(value, Sequence)
            or isinstance(value, (str, bytes))
            or len(value) != 2
        ):
            raise _field_problem(
                f"ebomLine.attributes[{index}]",
                _("Enter a controlled attribute key and value."),
            )
        key = _text(
            value[0],
            f"ebomLine.attributes[{index}].key",
            maximum=64,
            pattern=_ATTRIBUTE_KEY_PATTERN,
        )
        item = _text(
            value[1],
            f"ebomLine.attributes[{index}].value",
            maximum=280,
        )
        normalized.append((key, item))
    if len({key for key, _value in normalized}) != len(normalized):
        raise _field_problem("ebomLine.attributes", _("Attribute keys must be unique."))
    return tuple(sorted(normalized))
