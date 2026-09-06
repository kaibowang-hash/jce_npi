from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from enum import Enum
from uuid import UUID, uuid5

from npi_core.foundation.concurrency import next_version
from npi_core.foundation.errors import NpiProblem, RequestValidationFailed

from .policy_labels import POLICY_LABEL_SOURCES

try:
    from frappe import _
except ImportError:  # Keeps the domain independently testable.
    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


_POLICY_VERSION_NAMESPACE = UUID("c4a35cdd-03f7-43bb-9fc3-24c430c2b1be")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
_ACTOR_PATTERN = re.compile(r"^[^\s\x00-\x1f\x7f]{1,254}$")
_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class PolicyPublicationState(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class DomainWorkItemKind(str, Enum):
    RISK = "risk"
    ISSUE = "issue"
    ACTION = "action"
    DECISION_REQUEST = "decision_request"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RaciResponsibility(str, Enum):
    RESPONSIBLE = "responsible"
    ACCOUNTABLE = "accountable"
    CONSULTED = "consulted"
    INFORMED = "informed"


class RaciContextType(str, Enum):
    PROJECT = "project"
    WBS_ITEM = "wbs_item"
    DOMAIN_WORK_ITEM = "domain_work_item"


class PublishedWorkPolicyImmutable(NpiProblem):
    def __init__(self) -> None:
        super().__init__(
            409,
            "PUBLISHED_WORK_POLICY_IMMUTABLE",
            _("A published Project work policy version cannot be changed."),
        )


def _validation(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _require_enum(value: object, enum_type: type[Enum], path: str) -> None:
    if not isinstance(value, enum_type):
        raise _validation(path, _("Select a supported value."))


def _require_uuid(value: object, path: str) -> UUID:
    if not isinstance(value, UUID):
        raise _validation(path, _("Enter a valid global ID."))
    return value


def _require_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _validation(path, _("Enter a value."))
    normalized = value.strip()
    if len(normalized) > maximum_length or (
        pattern is not None and pattern.fullmatch(normalized) is None
    ):
        raise _validation(path, _("Enter a valid value."))
    return normalized


def _require_key(value: object, path: str) -> str:
    return _require_text(
        value,
        path,
        maximum_length=64,
        pattern=_KEY_PATTERN,
    )


def _require_email(value: object, path: str) -> str:
    return _require_text(
        value,
        path,
        maximum_length=254,
        pattern=_EMAIL_PATTERN,
    ).casefold()


def _require_actor_identity(value: object, path: str) -> str:
    if not isinstance(value, str) or _ACTOR_PATTERN.fullmatch(value) is None:
        raise _validation(path, _("Enter a valid value."))
    return value


def _require_version(value: object, path: str = "version") -> int:
    if type(value) is not int or value < 1:
        raise _validation(path, _("Enter a positive integer."))
    return value


def _require_date(value: object, path: str) -> date:
    if type(value) is not date:
        raise _validation(path, _("Enter a valid date."))
    return value


def _require_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _validation(path, _("Enter a valid date and time."))
    return value.astimezone(UTC)


def _validate_interval(
    start: date,
    end: date | None,
    *,
    start_path: str,
    end_path: str,
) -> None:
    _require_date(start, start_path)
    if end is not None:
        _require_date(end, end_path)
        if end < start:
            raise _validation(
                end_path,
                _("The effective end date cannot be before the start date."),
            )


def _interval_contains(
    outer_start: date,
    outer_end: date | None,
    inner_start: date,
    inner_end: date | None,
) -> bool:
    if inner_start < outer_start:
        return False
    if outer_end is None:
        return True
    return inner_end is not None and inner_end <= outer_end


def _intervals_overlap(
    left_start: date,
    left_end: date | None,
    right_start: date,
    right_end: date | None,
) -> bool:
    return (left_end is None or right_start <= left_end) and (
        right_end is None or left_start <= right_end
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class LifecycleState:
    key: str
    label_source: str
    terminal: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _require_key(self.key, "states.key"))
        label_source = _require_text(
            self.label_source,
            "states.labelSource",
            maximum_length=140,
        )
        if label_source not in POLICY_LABEL_SOURCES:
            raise _validation(
                "states.labelSource",
                _("Select a supported value."),
            )
        object.__setattr__(
            self,
            "label_source",
            label_source,
        )
        if type(self.terminal) is not bool:
            raise _validation("states.terminal", _("Select a valid true or false value."))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "labelSource": self.label_source,
            "terminal": self.terminal,
        }


@dataclass(frozen=True, slots=True)
class LifecycleDefinition:
    initial_state_key: str
    states: tuple[LifecycleState, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "initial_state_key",
            _require_key(self.initial_state_key, "initialStateKey"),
        )
        states = tuple(self.states)
        if not states or any(not isinstance(state, LifecycleState) for state in states):
            raise _validation("states", _("Add at least one valid lifecycle state."))
        states = tuple(sorted(states, key=lambda state: state.key))
        if len({state.key for state in states}) != len(states):
            raise _validation("states", _("Lifecycle state keys must be unique."))
        if self.initial_state_key not in {state.key for state in states}:
            raise _validation(
                "initialStateKey",
                _("Select an initial state defined by this lifecycle."),
            )
        object.__setattr__(self, "states", states)

    @property
    def initial_state(self) -> LifecycleState:
        return self.state(self.initial_state_key)

    def state(self, key: str) -> LifecycleState:
        normalized = _require_key(key, "stateKey")
        for state in self.states:
            if state.key == normalized:
                return state
        raise _validation("stateKey", _("Select a state defined by the work policy."))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "initialStateKey": self.initial_state_key,
            "states": [state.canonical_dict() for state in self.states],
        }


@dataclass(frozen=True, slots=True)
class KindLifecycle:
    kind: DomainWorkItemKind
    lifecycle: LifecycleDefinition

    def __post_init__(self) -> None:
        _require_enum(self.kind, DomainWorkItemKind, "workItemLifecycles.kind")
        if not isinstance(self.lifecycle, LifecycleDefinition):
            raise _validation(
                "workItemLifecycles.lifecycle",
                _("Enter a valid lifecycle."),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            **self.lifecycle.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class ProjectWorkPolicySnapshot:
    policy_global_id: UUID
    policy_key: str
    policy_version: int
    snapshot_hash: str
    role_keys: tuple[str, ...]
    wbs_lifecycle: LifecycleDefinition
    work_item_lifecycles: tuple[KindLifecycle, ...]

    def __post_init__(self) -> None:
        _require_uuid(self.policy_global_id, "workPolicyRef.globalId")
        object.__setattr__(
            self,
            "policy_key",
            _require_key(self.policy_key, "workPolicyRef.policyKey"),
        )
        _require_version(self.policy_version, "workPolicyRef.version")
        if not isinstance(self.snapshot_hash, str) or _HASH_PATTERN.fullmatch(
            self.snapshot_hash
        ) is None:
            raise _validation(
                "workPolicyRef.snapshotHash",
                _("Enter a valid snapshot hash."),
            )
        normalized_roles, normalized_lifecycles = _validate_policy_contents(
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
            publishable=True,
        )
        object.__setattr__(self, "role_keys", normalized_roles)
        object.__setattr__(self, "work_item_lifecycles", normalized_lifecycles)
        if self.snapshot_hash != _policy_snapshot_hash(
            self.policy_global_id,
            self.policy_key,
            self.policy_version,
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
        ):
            raise _validation(
                "workPolicyRef.snapshotHash",
                _("The work policy snapshot hash does not match its contents."),
            )

    def lifecycle_for(self, kind: DomainWorkItemKind) -> LifecycleDefinition:
        _require_enum(kind, DomainWorkItemKind, "kind")
        for definition in self.work_item_lifecycles:
            if definition.kind is kind:
                return definition.lifecycle
        raise _validation(
            "kind",
            _("The work policy does not define this work item kind."),
        )


@dataclass(frozen=True, slots=True)
class ProjectWorkPolicyVersion:
    global_id: UUID
    policy_global_id: UUID
    policy_key: str
    policy_version: int
    version: int
    title: str
    publication_state: PolicyPublicationState
    role_keys: tuple[str, ...]
    wbs_lifecycle: LifecycleDefinition
    work_item_lifecycles: tuple[KindLifecycle, ...]

    def __post_init__(self) -> None:
        _require_uuid(self.global_id, "globalId")
        _require_uuid(self.policy_global_id, "policyGlobalId")
        object.__setattr__(
            self,
            "policy_key",
            _require_key(self.policy_key, "policyKey"),
        )
        _require_version(self.policy_version, "policyVersion")
        _require_version(self.version, "expectedVersion")
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum_length=140),
        )
        _require_enum(
            self.publication_state,
            PolicyPublicationState,
            "publicationState",
        )
        normalized_roles, normalized_lifecycles = _validate_policy_contents(
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
            publishable=self.publication_state is PolicyPublicationState.PUBLISHED,
        )
        object.__setattr__(self, "role_keys", normalized_roles)
        object.__setattr__(self, "work_item_lifecycles", normalized_lifecycles)

    @classmethod
    def create_draft(
        cls,
        *,
        policy_global_id: UUID,
        policy_key: str,
        policy_version: int,
        title: str,
        role_keys: tuple[str, ...] = (),
        wbs_lifecycle: LifecycleDefinition,
        work_item_lifecycles: tuple[KindLifecycle, ...] = (),
    ) -> ProjectWorkPolicyVersion:
        _require_uuid(policy_global_id, "policyGlobalId")
        global_id = uuid5(
            _POLICY_VERSION_NAMESPACE,
            f"{policy_global_id}:{policy_version}",
        )
        return cls(
            global_id=global_id,
            policy_global_id=policy_global_id,
            policy_key=policy_key,
            policy_version=policy_version,
            version=1,
            title=title,
            publication_state=PolicyPublicationState.DRAFT,
            role_keys=role_keys,
            wbs_lifecycle=wbs_lifecycle,
            work_item_lifecycles=work_item_lifecycles,
        )

    def edit_draft(
        self,
        *,
        expected_version: int,
        title: str | None = None,
        role_keys: tuple[str, ...] | None = None,
        wbs_lifecycle: LifecycleDefinition | None = None,
        work_item_lifecycles: tuple[KindLifecycle, ...] | None = None,
    ) -> ProjectWorkPolicyVersion:
        if self.publication_state is PolicyPublicationState.PUBLISHED:
            raise PublishedWorkPolicyImmutable()
        return replace(
            self,
            version=next_version(self.version, expected_version),
            title=self.title if title is None else title,
            role_keys=self.role_keys if role_keys is None else role_keys,
            wbs_lifecycle=(
                self.wbs_lifecycle if wbs_lifecycle is None else wbs_lifecycle
            ),
            work_item_lifecycles=(
                self.work_item_lifecycles
                if work_item_lifecycles is None
                else work_item_lifecycles
            ),
        )

    def publish(self, *, expected_version: int) -> ProjectWorkPolicyVersion:
        if self.publication_state is PolicyPublicationState.PUBLISHED:
            raise PublishedWorkPolicyImmutable()
        _validate_policy_contents(
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
            publishable=True,
        )
        return replace(
            self,
            version=next_version(self.version, expected_version),
            publication_state=PolicyPublicationState.PUBLISHED,
        )

    def next_draft(self) -> ProjectWorkPolicyVersion:
        if self.publication_state is not PolicyPublicationState.PUBLISHED:
            raise _validation(
                "policyVersion",
                _("Publish the current policy before creating a revision."),
            )
        return self.create_draft(
            policy_global_id=self.policy_global_id,
            policy_key=self.policy_key,
            policy_version=self.policy_version + 1,
            title=self.title,
            role_keys=self.role_keys,
            wbs_lifecycle=self.wbs_lifecycle,
            work_item_lifecycles=self.work_item_lifecycles,
        )

    @property
    def snapshot_hash(self) -> str:
        return _policy_snapshot_hash(
            self.policy_global_id,
            self.policy_key,
            self.policy_version,
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
        )

    def snapshot(self) -> ProjectWorkPolicySnapshot:
        if self.publication_state is not PolicyPublicationState.PUBLISHED:
            raise _validation(
                "workPolicyRef",
                _("Select a published Project work policy version."),
            )
        return ProjectWorkPolicySnapshot(
            policy_global_id=self.policy_global_id,
            policy_key=self.policy_key,
            policy_version=self.policy_version,
            snapshot_hash=self.snapshot_hash,
            role_keys=self.role_keys,
            wbs_lifecycle=self.wbs_lifecycle,
            work_item_lifecycles=self.work_item_lifecycles,
        )

    def _snapshot_payload(self) -> dict[str, object]:
        return _policy_snapshot_payload(
            self.policy_global_id,
            self.policy_key,
            self.policy_version,
            self.role_keys,
            self.wbs_lifecycle,
            self.work_item_lifecycles,
        )


def _validate_policy_contents(
    role_keys: tuple[str, ...],
    wbs_lifecycle: LifecycleDefinition,
    work_item_lifecycles: tuple[KindLifecycle, ...],
    *,
    publishable: bool,
) -> tuple[tuple[str, ...], tuple[KindLifecycle, ...]]:
    if not isinstance(wbs_lifecycle, LifecycleDefinition):
        raise _validation("wbsLifecycle", _("Enter a valid WBS lifecycle."))
    normalized_roles = tuple(
        sorted(_require_key(role, "roleKeys") for role in tuple(role_keys))
    )
    if len(set(normalized_roles)) != len(normalized_roles):
        raise _validation("roleKeys", _("Project role keys must be unique."))
    lifecycles = tuple(work_item_lifecycles)
    if any(not isinstance(item, KindLifecycle) for item in lifecycles):
        raise _validation(
            "workItemLifecycles",
            _("Enter valid work item lifecycles."),
        )
    lifecycles = tuple(sorted(lifecycles, key=lambda item: item.kind.value))
    if len({item.kind for item in lifecycles}) != len(lifecycles):
        raise _validation(
            "workItemLifecycles",
            _("Each work item kind must have one lifecycle."),
        )
    if publishable:
        if not normalized_roles:
            raise _validation(
                "roleKeys",
                _("Add at least one Project role before publishing."),
            )
        if {item.kind for item in lifecycles} != set(DomainWorkItemKind):
            raise _validation(
                "workItemLifecycles",
                _("Define a separate lifecycle for every work item kind."),
            )
    return normalized_roles, lifecycles


def _policy_snapshot_payload(
    policy_global_id: UUID,
    policy_key: str,
    policy_version: int,
    role_keys: tuple[str, ...],
    wbs_lifecycle: LifecycleDefinition,
    work_item_lifecycles: tuple[KindLifecycle, ...],
) -> dict[str, object]:
    return {
        "policyGlobalId": str(policy_global_id),
        "policyKey": policy_key,
        "policyVersion": policy_version,
        "roleKeys": list(role_keys),
        "wbsLifecycle": wbs_lifecycle.canonical_dict(),
        "workItemLifecycles": [
            definition.canonical_dict()
            for definition in work_item_lifecycles
        ],
    }


def _policy_snapshot_hash(
    policy_global_id: UUID,
    policy_key: str,
    policy_version: int,
    role_keys: tuple[str, ...],
    wbs_lifecycle: LifecycleDefinition,
    work_item_lifecycles: tuple[KindLifecycle, ...],
) -> str:
    payload = _policy_snapshot_payload(
        policy_global_id,
        policy_key,
        policy_version,
        role_keys,
        wbs_lifecycle,
        work_item_lifecycles,
    )
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProjectMember:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    user_id: str
    effective_from: date
    effective_to: date | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        object.__setattr__(self, "user_id", _require_email(self.user_id, "userId"))
        _validate_interval(
            self.effective_from,
            self.effective_to,
            start_path="effectiveFrom",
            end_path="effectiveTo",
        )
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class ProjectRoleAssignment:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    member_global_id: UUID
    role_key: str
    effective_from: date
    effective_to: date | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_uuid(self.member_global_id, "memberId")
        object.__setattr__(self, "role_key", _require_key(self.role_key, "roleKey"))
        _validate_interval(
            self.effective_from,
            self.effective_to,
            start_path="effectiveFrom",
            end_path="effectiveTo",
        )
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class ProjectSubstitution:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    role_assignment_global_id: UUID
    substitute_member_global_id: UUID
    effective_from: date
    effective_to: date
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_uuid(self.role_assignment_global_id, "roleAssignmentId")
        _require_uuid(self.substitute_member_global_id, "substituteMemberId")
        _validate_interval(
            self.effective_from,
            self.effective_to,
            start_path="effectiveFrom",
            end_path="effectiveTo",
        )
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class ProjectRaciAssignment:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    context_type: RaciContextType
    context_global_id: UUID
    responsibility_key: str
    role_assignment_global_id: UUID
    responsibility: RaciResponsibility
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_enum(self.context_type, RaciContextType, "contextType")
        _require_uuid(self.context_global_id, "contextId")
        object.__setattr__(
            self,
            "responsibility_key",
            _require_key(self.responsibility_key, "responsibilityKey"),
        )
        _require_uuid(self.role_assignment_global_id, "roleAssignmentId")
        _require_enum(self.responsibility, RaciResponsibility, "raci")
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class ProjectTeam:
    tenant_id: str
    project_global_id: UUID
    policy: ProjectWorkPolicySnapshot
    members: tuple[ProjectMember, ...]
    role_assignments: tuple[ProjectRoleAssignment, ...]
    substitutions: tuple[ProjectSubstitution, ...]
    raci_assignments: tuple[ProjectRaciAssignment, ...]

    def __post_init__(self) -> None:
        tenant_id = _require_text(self.tenant_id, "tenantId", maximum_length=128)
        object.__setattr__(self, "tenant_id", tenant_id)
        _require_uuid(self.project_global_id, "projectId")
        if not isinstance(self.policy, ProjectWorkPolicySnapshot):
            raise _validation("workPolicyRef", _("Select a valid work policy."))
        self._validate()

    def validate_contexts(
        self,
        *,
        wbs_item_ids: frozenset[UUID] = frozenset(),
        domain_work_item_ids: frozenset[UUID] = frozenset(),
    ) -> None:
        for assignment in self.raci_assignments:
            if (
                assignment.context_type is RaciContextType.PROJECT
                and assignment.context_global_id != self.project_global_id
            ):
                raise _validation(
                    "raciAssignments.contextId",
                    _("The RACI Project context does not match this Project."),
                )
            if (
                assignment.context_type is RaciContextType.WBS_ITEM
                and assignment.context_global_id not in wbs_item_ids
            ):
                raise _validation(
                    "raciAssignments.contextId",
                    _("Select a WBS item from this Project."),
                )
            if (
                assignment.context_type is RaciContextType.DOMAIN_WORK_ITEM
                and assignment.context_global_id not in domain_work_item_ids
            ):
                raise _validation(
                    "raciAssignments.contextId",
                    _("Select a work item from this Project."),
                )

    def _validate(self) -> None:
        members = tuple(self.members)
        roles = tuple(self.role_assignments)
        substitutions = tuple(self.substitutions)
        raci = tuple(self.raci_assignments)
        _require_unique_ids(members, "members")
        _require_unique_ids(roles, "roleAssignments")
        _require_unique_ids(substitutions, "substitutions")
        _require_unique_ids(raci, "raciAssignments")
        for collection, path in (
            (members, "members"),
            (roles, "roleAssignments"),
            (substitutions, "substitutions"),
            (raci, "raciAssignments"),
        ):
            _require_same_project(
                collection,
                tenant_id=self.tenant_id,
                project_global_id=self.project_global_id,
                path=path,
            )
        member_by_id = {member.global_id: member for member in members}
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                if left.user_id == right.user_id and _intervals_overlap(
                    left.effective_from,
                    left.effective_to,
                    right.effective_from,
                    right.effective_to,
                ):
                    raise _validation(
                        "members",
                        _("Membership periods for one user cannot overlap."),
                    )
        role_by_id = {role.global_id: role for role in roles}
        allowed_roles = set(self.policy.role_keys)
        for role in roles:
            member = member_by_id.get(role.member_global_id)
            if member is None:
                raise _validation(
                    "roleAssignments.memberId",
                    _("Select a member from this Project."),
                )
            if role.role_key not in allowed_roles:
                raise _validation(
                    "roleAssignments.roleKey",
                    _("Select a role defined by the work policy."),
                )
            if not _interval_contains(
                member.effective_from,
                member.effective_to,
                role.effective_from,
                role.effective_to,
            ):
                raise _validation(
                    "roleAssignments",
                    _("A role assignment must remain within its membership period."),
                )
        for index, left in enumerate(roles):
            for right in roles[index + 1 :]:
                if (
                    left.member_global_id == right.member_global_id
                    and left.role_key == right.role_key
                    and _intervals_overlap(
                        left.effective_from,
                        left.effective_to,
                        right.effective_from,
                        right.effective_to,
                    )
                ):
                    raise _validation(
                        "roleAssignments",
                        _("Duplicate role-assignment periods cannot overlap."),
                    )
        for substitution in substitutions:
            role = role_by_id.get(substitution.role_assignment_global_id)
            substitute = member_by_id.get(substitution.substitute_member_global_id)
            if role is None:
                raise _validation(
                    "substitutions.roleAssignmentId",
                    _("Select a role assignment from this Project."),
                )
            if substitute is None:
                raise _validation(
                    "substitutions.substituteMemberId",
                    _("Select a substitute member from this Project."),
                )
            if substitute.global_id == role.member_global_id:
                raise _validation(
                    "substitutions.substituteMemberId",
                    _("A member cannot substitute for the same assignment."),
                )
            if not _interval_contains(
                role.effective_from,
                role.effective_to,
                substitution.effective_from,
                substitution.effective_to,
            ) or not _interval_contains(
                substitute.effective_from,
                substitute.effective_to,
                substitution.effective_from,
                substitution.effective_to,
            ):
                raise _validation(
                    "substitutions",
                    _("A substitution must remain within both assignment periods."),
                )
        for index, left in enumerate(substitutions):
            for right in substitutions[index + 1 :]:
                if (
                    left.role_assignment_global_id
                    == right.role_assignment_global_id
                    and _intervals_overlap(
                        left.effective_from,
                        left.effective_to,
                        right.effective_from,
                        right.effective_to,
                    )
                ):
                    raise _validation(
                        "substitutions",
                        _("Substitution periods for one assignment cannot overlap."),
                    )
        identities: set[tuple[object, ...]] = set()
        for assignment in raci:
            if assignment.role_assignment_global_id not in role_by_id:
                raise _validation(
                    "raciAssignments.roleAssignmentId",
                    _("Select a role assignment from this Project."),
                )
            identity = (
                assignment.context_type,
                assignment.context_global_id,
                assignment.responsibility_key,
                assignment.role_assignment_global_id,
                assignment.responsibility,
            )
            if identity in identities:
                raise _validation(
                    "raciAssignments",
                    _("RACI assignments must be unique."),
                )
            identities.add(identity)


@dataclass(frozen=True, slots=True)
class WbsItem:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    work_policy_global_id: UUID
    work_policy_version: int
    work_policy_snapshot_hash: str
    code: str
    title: str
    planned_start: date
    planned_finish: date
    milestone: bool
    status_key: str
    progress_percent: int
    critical: bool
    plan_revision: int
    parent_global_id: UUID | None = None
    owner_role_assignment_global_id: UUID | None = None
    actual_start: date | None = None
    actual_finish: date | None = None
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_uuid(self.work_policy_global_id, "workPolicyRef.globalId")
        _require_version(self.work_policy_version, "workPolicyRef.version")
        _require_snapshot_hash(
            self.work_policy_snapshot_hash,
            "workPolicyRef.snapshotHash",
        )
        object.__setattr__(
            self,
            "code",
            _require_text(
                self.code,
                "code",
                maximum_length=64,
                pattern=_CODE_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum_length=280),
        )
        _validate_interval(
            self.planned_start,
            self.planned_finish,
            start_path="plannedStart",
            end_path="plannedFinish",
        )
        if self.actual_start is not None:
            _require_date(self.actual_start, "actualStart")
        if self.actual_finish is not None:
            _require_date(self.actual_finish, "actualFinish")
            if self.actual_start is None or self.actual_finish < self.actual_start:
                raise _validation(
                    "actualFinish",
                    _("Actual finish requires an earlier or equal actual start."),
                )
        if type(self.milestone) is not bool:
            raise _validation("milestone", _("Select a valid true or false value."))
        if self.milestone and self.planned_start != self.planned_finish:
            raise _validation(
                "plannedFinish",
                _("A milestone must start and finish on the same planned date."),
            )
        if (
            self.milestone
            and self.actual_start is not None
            and self.actual_finish is not None
            and self.actual_start != self.actual_finish
        ):
            raise _validation(
                "actualFinish",
                _("A milestone must start and finish on the same actual date."),
            )
        object.__setattr__(self, "status_key", _require_key(self.status_key, "statusKey"))
        if type(self.progress_percent) is not int or not 0 <= self.progress_percent <= 100:
            raise _validation(
                "progressPercent",
                _("Enter a progress percentage from 0 to 100."),
            )
        if type(self.critical) is not bool:
            raise _validation("critical", _("Select a valid true or false value."))
        _require_version(self.plan_revision, "planRevision")
        if self.parent_global_id is not None:
            _require_uuid(self.parent_global_id, "parentId")
        if self.owner_role_assignment_global_id is not None:
            _require_uuid(
                self.owner_role_assignment_global_id,
                "ownerRoleAssignmentId",
            )
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class WbsDependency:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    predecessor_global_id: UUID
    successor_global_id: UUID
    plan_revision: int
    active: bool = True
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_uuid(self.predecessor_global_id, "predecessorItemId")
        _require_uuid(self.successor_global_id, "successorItemId")
        if self.predecessor_global_id == self.successor_global_id:
            raise _validation(
                "successorItemId",
                _("A WBS item cannot depend on itself."),
            )
        _require_version(self.plan_revision, "planRevision")
        if type(self.active) is not bool:
            raise _validation("active", _("Select a valid true or false value."))
        _require_version(self.version)


@dataclass(frozen=True, slots=True)
class WbsPlan:
    tenant_id: str
    project_global_id: UUID
    project_version: int
    policy: ProjectWorkPolicySnapshot
    items: tuple[WbsItem, ...]
    dependencies: tuple[WbsDependency, ...]
    role_assignments: tuple[ProjectRoleAssignment, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            _require_text(self.tenant_id, "tenantId", maximum_length=128),
        )
        _require_uuid(self.project_global_id, "projectId")
        _require_version(self.project_version, "projectVersion")
        if not isinstance(self.policy, ProjectWorkPolicySnapshot):
            raise _validation("workPolicyRef", _("Select a valid work policy."))
        self._validate()

    def _validate(self) -> None:
        items = tuple(self.items)
        dependencies = tuple(self.dependencies)
        _require_unique_ids(items, "items")
        _require_unique_ids(dependencies, "dependencies")
        _require_same_project(
            items,
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            path="items",
        )
        _require_same_project(
            dependencies,
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            path="dependencies",
        )
        role_by_id = {role.global_id: role for role in self.role_assignments}
        _require_same_project(
            self.role_assignments,
            tenant_id=self.tenant_id,
            project_global_id=self.project_global_id,
            path="roleAssignments",
        )
        item_by_id = {item.global_id: item for item in items}
        code_keys: set[str] = set()
        expected_policy = (
            self.policy.policy_global_id,
            self.policy.policy_version,
            self.policy.snapshot_hash,
        )
        for item in items:
            policy_ref = (
                item.work_policy_global_id,
                item.work_policy_version,
                item.work_policy_snapshot_hash,
            )
            if policy_ref != expected_policy:
                raise _validation(
                    "items.workPolicyRef",
                    _("Every WBS item must use the selected work policy version."),
                )
            self.policy.wbs_lifecycle.state(item.status_key)
            code_key = item.code.casefold()
            if code_key in code_keys:
                raise _validation("items.code", _("WBS codes must be unique."))
            code_keys.add(code_key)
            if item.parent_global_id is not None:
                if item.parent_global_id == item.global_id:
                    raise _validation(
                        "items.parentId",
                        _("A WBS item cannot be its own parent."),
                    )
                if item.parent_global_id not in item_by_id:
                    raise _validation(
                        "items.parentId",
                        _("Select a parent WBS item from this Project."),
                    )
            if (
                item.owner_role_assignment_global_id is not None
                and item.owner_role_assignment_global_id not in role_by_id
            ):
                raise _validation(
                    "items.ownerRoleAssignmentId",
                    _("Select a role assignment from this Project."),
                )
        parent_edges = {
            item.global_id: (
                (item.parent_global_id,) if item.parent_global_id is not None else ()
            )
            for item in items
        }
        _reject_cycle(parent_edges, "items.parentId")
        dependency_edges: dict[UUID, list[UUID]] = {
            item_id: [] for item_id in item_by_id
        }
        edge_identities: set[tuple[UUID, UUID]] = set()
        for dependency in dependencies:
            if not dependency.active:
                continue
            if (
                dependency.predecessor_global_id not in item_by_id
                or dependency.successor_global_id not in item_by_id
            ):
                raise _validation(
                    "dependencies",
                    _("Every dependency must reference WBS items from this Project."),
                )
            identity = (
                dependency.predecessor_global_id,
                dependency.successor_global_id,
            )
            if identity in edge_identities:
                raise _validation(
                    "dependencies",
                    _("WBS dependencies must be unique."),
                )
            edge_identities.add(identity)
            dependency_edges[dependency.predecessor_global_id].append(
                dependency.successor_global_id
            )
        _reject_cycle(
            {node: tuple(edges) for node, edges in dependency_edges.items()},
            "dependencies",
        )


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    wbs_item_global_id: UUID
    planned_start: date
    planned_finish: date
    critical: bool

    def canonical_dict(self) -> dict[str, object]:
        return {
            "wbsItemId": str(self.wbs_item_global_id),
            "plannedStart": self.planned_start.isoformat(),
            "plannedFinish": self.planned_finish.isoformat(),
            "critical": self.critical,
        }


@dataclass(frozen=True, slots=True)
class WbsPlanBaseline:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    plan_revision: int
    project_version: int
    label: str
    work_policy_global_id: UUID
    work_policy_version: int
    work_policy_snapshot_hash: str
    snapshot_hash: str
    entries: tuple[BaselineEntry, ...]
    captured_at: datetime
    captured_by: str
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_version(self.plan_revision, "planRevision")
        _require_version(self.project_version, "projectVersion")
        object.__setattr__(
            self,
            "label",
            _require_text(self.label, "label", maximum_length=140),
        )
        _require_uuid(self.work_policy_global_id, "workPolicyRef.globalId")
        _require_version(self.work_policy_version, "workPolicyRef.version")
        _require_snapshot_hash(
            self.work_policy_snapshot_hash,
            "workPolicyRef.snapshotHash",
        )
        _require_snapshot_hash(self.snapshot_hash, "snapshotHash")
        entries = tuple(sorted(self.entries, key=lambda entry: str(entry.wbs_item_global_id)))
        if not entries or len({entry.wbs_item_global_id for entry in entries}) != len(
            entries
        ):
            raise _validation(
                "baseline",
                _("A plan baseline requires unique WBS items."),
            )
        object.__setattr__(self, "entries", entries)
        object.__setattr__(
            self,
            "captured_at",
            _require_datetime(self.captured_at, "capturedAt"),
        )
        object.__setattr__(
            self,
            "captured_by",
            _require_actor_identity(self.captured_by, "capturedBy"),
        )
        _require_version(self.version)
        if self.snapshot_hash != _baseline_hash(entries):
            raise _validation(
                "snapshotHash",
                _("The plan baseline snapshot hash does not match its contents."),
            )

    @property
    def snapshot_payload(self) -> dict[str, object]:
        return {"items": [entry.canonical_dict() for entry in self.entries]}


@dataclass(frozen=True, slots=True)
class BaselineComparisonItem:
    wbs_item_global_id: UUID
    baseline_planned_start: date
    baseline_planned_finish: date
    current_planned_start: date
    current_planned_finish: date
    start_variance_days: int
    finish_variance_days: int
    critical: bool


@dataclass(frozen=True, slots=True)
class WbsBaselineComparison:
    baseline_global_id: UUID
    baseline_project_version: int
    current_project_version: int
    items: tuple[BaselineComparisonItem, ...]


def capture_wbs_baseline(
    plan: WbsPlan,
    *,
    global_id: UUID,
    label: str,
    captured_at: datetime,
    captured_by: str,
) -> WbsPlanBaseline:
    if not isinstance(plan, WbsPlan):
        raise _validation("plan", _("Enter a valid WBS plan."))
    entries = tuple(
        BaselineEntry(
            wbs_item_global_id=item.global_id,
            planned_start=item.planned_start,
            planned_finish=item.planned_finish,
            critical=item.critical,
        )
        for item in sorted(plan.items, key=lambda item: str(item.global_id))
    )
    if not entries:
        raise _validation("items", _("Add at least one WBS item before baselining."))
    plan_revision = max(item.plan_revision for item in plan.items)
    return WbsPlanBaseline(
        global_id=global_id,
        tenant_id=plan.tenant_id,
        project_global_id=plan.project_global_id,
        plan_revision=plan_revision,
        project_version=plan.project_version,
        label=label,
        work_policy_global_id=plan.policy.policy_global_id,
        work_policy_version=plan.policy.policy_version,
        work_policy_snapshot_hash=plan.policy.snapshot_hash,
        snapshot_hash=_baseline_hash(entries),
        entries=entries,
        captured_at=captured_at,
        captured_by=captured_by,
    )


def compare_wbs_baseline(
    baseline: WbsPlanBaseline,
    plan: WbsPlan,
) -> WbsBaselineComparison:
    if (
        baseline.tenant_id != plan.tenant_id
        or baseline.project_global_id != plan.project_global_id
    ):
        raise _validation(
            "baseline",
            _("The plan baseline belongs to a different Project."),
        )
    if (
        baseline.work_policy_global_id != plan.policy.policy_global_id
        or baseline.work_policy_version != plan.policy.policy_version
        or baseline.work_policy_snapshot_hash != plan.policy.snapshot_hash
    ):
        raise _validation(
            "workPolicyRef",
            _("The plan baseline uses a different work policy version."),
        )
    current_by_id = {item.global_id: item for item in plan.items}
    comparisons: list[BaselineComparisonItem] = []
    for entry in baseline.entries:
        current = current_by_id.get(entry.wbs_item_global_id)
        if current is None:
            raise _validation(
                "items",
                _("A baselined WBS item cannot be omitted from the current plan."),
            )
        comparisons.append(
            BaselineComparisonItem(
                wbs_item_global_id=entry.wbs_item_global_id,
                baseline_planned_start=entry.planned_start,
                baseline_planned_finish=entry.planned_finish,
                current_planned_start=current.planned_start,
                current_planned_finish=current.planned_finish,
                start_variance_days=(
                    current.planned_start - entry.planned_start
                ).days,
                finish_variance_days=(
                    current.planned_finish - entry.planned_finish
                ).days,
                critical=current.critical,
            )
        )
    return WbsBaselineComparison(
        baseline_global_id=baseline.global_id,
        baseline_project_version=baseline.project_version,
        current_project_version=plan.project_version,
        items=tuple(comparisons),
    )


@dataclass(frozen=True, slots=True)
class DomainWorkItem:
    global_id: UUID
    tenant_id: str
    project_global_id: UUID
    kind: DomainWorkItemKind
    title: str
    owner_user_id: str
    due_at: datetime
    severity: Severity
    blocking: bool
    state_key: str
    state_label_source: str
    state_terminal: bool
    work_policy_global_id: UUID
    work_policy_version: int
    work_policy_snapshot_hash: str
    related_work_item_ids: tuple[UUID, ...]
    detail: str | None = None
    stage_global_id: UUID | None = None
    wbs_item_global_id: UUID | None = None
    evidence_references: tuple[UUID, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        _validate_project_identity(self.global_id, self.tenant_id, self.project_global_id)
        _require_enum(self.kind, DomainWorkItemKind, "kind")
        object.__setattr__(
            self,
            "title",
            _require_text(self.title, "title", maximum_length=280),
        )
        if self.detail is not None:
            normalized_detail = self.detail.strip()
            if len(normalized_detail) > 4000:
                raise _validation("detail", _("Enter no more than 4000 characters."))
            object.__setattr__(
                self,
                "detail",
                normalized_detail if normalized_detail else None,
            )
        object.__setattr__(
            self,
            "owner_user_id",
            _require_email(self.owner_user_id, "ownerUserId"),
        )
        object.__setattr__(self, "due_at", _require_datetime(self.due_at, "dueAt"))
        _require_enum(self.severity, Severity, "severity")
        if type(self.blocking) is not bool:
            raise _validation("blocking", _("Select a valid true or false value."))
        object.__setattr__(self, "state_key", _require_key(self.state_key, "stateKey"))
        object.__setattr__(
            self,
            "state_label_source",
            _require_text(
                self.state_label_source,
                "stateLabelSource",
                maximum_length=140,
            ),
        )
        if type(self.state_terminal) is not bool:
            raise _validation(
                "stateTerminal",
                _("Select a valid true or false value."),
            )
        _require_uuid(self.work_policy_global_id, "workPolicyRef.globalId")
        _require_version(self.work_policy_version, "workPolicyRef.version")
        _require_snapshot_hash(
            self.work_policy_snapshot_hash,
            "workPolicyRef.snapshotHash",
        )
        related = tuple(self.related_work_item_ids)
        if len(related) > 100 or len(set(related)) != len(related):
            raise _validation(
                "relatedWorkItemIds",
                _("Related work item IDs must be unique."),
            )
        for related_id in related:
            _require_uuid(related_id, "relatedWorkItemIds")
            if related_id == self.global_id:
                raise _validation(
                    "relatedWorkItemIds",
                    _("A work item cannot relate to itself."),
                )
        object.__setattr__(
            self,
            "related_work_item_ids",
            tuple(sorted(related, key=str)),
        )
        if self.stage_global_id is not None:
            _require_uuid(self.stage_global_id, "context.stageId")
        if self.wbs_item_global_id is not None:
            _require_uuid(self.wbs_item_global_id, "context.wbsItemId")
        if self.evidence_references:
            raise _validation(
                "evidenceReferences",
                _("Controlled evidence references are not available in this task."),
            )
        _require_version(self.version)

    def is_overdue(self, *, as_of: datetime) -> bool:
        current = _require_datetime(as_of, "asOf")
        return not self.state_terminal and self.due_at < current


def create_domain_work_item(
    *,
    global_id: UUID,
    tenant_id: str,
    project_global_id: UUID,
    policy: ProjectWorkPolicySnapshot,
    kind: DomainWorkItemKind,
    title: str,
    owner_user_id: str,
    due_at: datetime,
    severity: Severity,
    blocking: bool,
    related_work_item_ids: tuple[UUID, ...] = (),
    related_items: tuple[DomainWorkItem, ...] = (),
    detail: str | None = None,
    stage_global_id: UUID | None = None,
    wbs_item_global_id: UUID | None = None,
    known_stage_ids: frozenset[UUID] | None = None,
    known_wbs_item_ids: frozenset[UUID] | None = None,
) -> DomainWorkItem:
    if not isinstance(policy, ProjectWorkPolicySnapshot):
        raise _validation("workPolicyRef", _("Select a valid work policy."))
    _require_enum(kind, DomainWorkItemKind, "kind")
    if stage_global_id is not None and (
        known_stage_ids is None or stage_global_id not in known_stage_ids
    ):
        raise _validation(
            "context.stageId",
            _("Select a stage from this Project."),
        )
    if wbs_item_global_id is not None and (
        known_wbs_item_ids is None or wbs_item_global_id not in known_wbs_item_ids
    ):
        raise _validation(
            "context.wbsItemId",
            _("Select a WBS item from this Project."),
        )
    related_by_id = {item.global_id: item for item in related_items}
    for related_id in related_work_item_ids:
        related = related_by_id.get(related_id)
        if related is None:
            raise _validation(
                "relatedWorkItemIds",
                _("Select related work items from this Project."),
            )
        if (
            related.tenant_id != tenant_id
            or related.project_global_id != project_global_id
        ):
            raise _validation(
                "relatedWorkItemIds",
                _("Select related work items from this Project."),
            )
    initial_state = policy.lifecycle_for(kind).initial_state
    return DomainWorkItem(
        global_id=global_id,
        tenant_id=tenant_id,
        project_global_id=project_global_id,
        kind=kind,
        title=title,
        detail=detail,
        stage_global_id=stage_global_id,
        wbs_item_global_id=wbs_item_global_id,
        owner_user_id=owner_user_id,
        due_at=due_at,
        severity=severity,
        blocking=blocking,
        state_key=initial_state.key,
        state_label_source=initial_state.label_source,
        state_terminal=initial_state.terminal,
        work_policy_global_id=policy.policy_global_id,
        work_policy_version=policy.policy_version,
        work_policy_snapshot_hash=policy.snapshot_hash,
        related_work_item_ids=related_work_item_ids,
    )


def _validate_project_identity(
    global_id: object,
    tenant_id: object,
    project_global_id: object,
) -> None:
    _require_uuid(global_id, "globalId")
    _require_text(tenant_id, "tenantId", maximum_length=128)
    _require_uuid(project_global_id, "projectId")


def _require_snapshot_hash(value: object, path: str) -> str:
    if not isinstance(value, str) or _HASH_PATTERN.fullmatch(value) is None:
        raise _validation(path, _("Enter a valid snapshot hash."))
    return value


def _require_unique_ids(values: tuple[object, ...], path: str) -> None:
    identities = [getattr(value, "global_id", None) for value in values]
    if any(not isinstance(identity, UUID) for identity in identities) or len(
        set(identities)
    ) != len(identities):
        raise _validation(path, _("Global IDs must be unique."))


def _require_same_project(
    values: tuple[object, ...],
    *,
    tenant_id: str,
    project_global_id: UUID,
    path: str,
) -> None:
    for value in values:
        if (
            getattr(value, "tenant_id", None) != tenant_id
            or getattr(value, "project_global_id", None) != project_global_id
        ):
            raise _validation(path, _("Every record must belong to this Project."))


def _reject_cycle(edges: dict[UUID, tuple[UUID, ...]], path: str) -> None:
    unvisited, visiting, visited = 0, 1, 2
    states: dict[UUID, int] = {}

    for start in sorted(edges, key=str):
        if states.get(start, unvisited) != unvisited:
            continue
        states[start] = visiting
        stack: list[tuple[UUID, int]] = [(start, 0)]
        while stack:
            node, successor_index = stack[-1]
            successors = edges.get(node, ())
            if successor_index >= len(successors):
                states[node] = visited
                stack.pop()
                continue

            target = successors[successor_index]
            stack[-1] = (node, successor_index + 1)
            target_state = states.get(target, unvisited)
            if target_state == visiting:
                raise _validation(
                    path,
                    _("The WBS graph cannot contain a cycle."),
                )
            if target_state == unvisited:
                states[target] = visiting
                stack.append((target, 0))


def _baseline_hash(entries: tuple[BaselineEntry, ...]) -> str:
    payload = {
        "items": [
            entry.canonical_dict()
            for entry in sorted(entries, key=lambda entry: str(entry.wbs_item_global_id))
        ]
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
