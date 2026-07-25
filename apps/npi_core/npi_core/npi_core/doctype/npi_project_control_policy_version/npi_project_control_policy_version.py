from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

try:
    import frappe
    from frappe import _
    from frappe.model.document import Document
    from frappe.utils import now_datetime
except ImportError:  # Keeps the controller importable in pure unit tests.
    class _FallbackValidationError(Exception):
        pass

    class _FallbackPermissionError(Exception):
        pass

    class _UnavailableDatabase:
        def get_value(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("Frappe database access is unavailable.")

    class _FallbackFrappe:
        ValidationError = _FallbackValidationError
        PermissionError = _FallbackPermissionError
        db = _UnavailableDatabase()

        @staticmethod
        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

    frappe = _FallbackFrappe()

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation

    class Document:
        def __init__(self, values: dict[str, Any] | None = None) -> None:
            for fieldname, value in (values or {}).items():
                setattr(self, fieldname, value)
            self._previous = None

        def get(self, fieldname: str) -> Any:
            return getattr(self, fieldname, None)

        def get_doc_before_save(self) -> Any:
            return self._previous

    def now_datetime() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project_controls.domain import (
    ControlPolicyPublicationState,
    HealthAggregationMode,
    HealthAggregationRule,
    HealthDimension,
    HealthDimensionRule,
    HealthRuleMode,
    PriorPolicyVersionReference,
    ProjectControlAction,
    ProjectControlPolicyVersion,
    ProjectLifecycleState,
    ProjectPrerequisiteKey,
    ProjectTransitionRule,
)


_POLICY_VERSION_NAMESPACE = UUID("479fe5c8-cda3-4a07-ab48-6c649592f95a")
_IDENTITY_FIELDS = (
    "global_id",
    "project_control_policy",
    "policy_global_id",
    "policy_code",
    "policy_version",
    "version_key",
    "prior_version_ref",
)
_PRIOR_FIELDS = [
    "global_id",
    "policy_global_id",
    "policy_code",
    "policy_version",
    "publication_state",
    "snapshot",
    "snapshot_hash",
]


class NPIProjectControlPolicyVersion(Document):
    """Administrative draft whose published policy snapshot is immutable."""

    def autoname(self) -> None:
        self._set_policy_identity()
        self.name = self.version_key

    def before_validate(self) -> None:
        self._set_policy_identity()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            frappe.throw(
                _(
                    "A published Project Control Policy version cannot be changed."
                ),
                frappe.ValidationError,
            )

        self._set_policy_identity()
        prior_reference = self._validated_prior_reference(previous)
        if previous is not None:
            _assert_immutable_fields(self, previous, _IDENTITY_FIELDS)

        try:
            requested_state = ControlPolicyPublicationState(
                self.publication_state
            )
            authority_slots = _authority_slots(self.authority_slots)
            health_rules = _health_rules(self.health_rules)
            aggregation = _aggregation(self.require_all_dimensions)
            transitions = _lifecycle_transitions(
                self.lifecycle_transitions
            )
            base_version = (
                _positive_integer(
                    previous.optimistic_version,
                    _("Optimistic Version"),
                )
                if previous is not None
                else 1
            )
            domain_policy = ProjectControlPolicyVersion(
                global_id=UUID(self.global_id),
                policy_global_id=UUID(self.policy_global_id),
                policy_code=self.policy_code,
                policy_version=self.policy_version,
                version=(
                    base_version
                    if requested_state
                    is ControlPolicyPublicationState.PUBLISHED
                    else base_version + (1 if previous is not None else 0)
                ),
                title=self.title,
                publication_state=ControlPolicyPublicationState.DRAFT,
                prior_version_ref=prior_reference,
                authority_slots=authority_slots,
                health_assessment_slot=self.health_assessment_slot,
                health_rules=health_rules,
                aggregation=aggregation,
                transitions=transitions,
            )
            if requested_state is ControlPolicyPublicationState.PUBLISHED:
                domain_policy = domain_policy.publish(
                    expected_version=base_version,
                )
        except RequestValidationFailed as error:
            _throw_domain_validation(error)
        except (AttributeError, KeyError, TypeError, ValueError):
            frappe.throw(
                _("Enter a valid Project Control Policy version."),
                frappe.ValidationError,
            )
        else:
            self._apply_domain_policy(domain_policy)

    def on_trash(self) -> None:
        if self.publication_state == "published":
            frappe.throw(
                _(
                    "A published Project Control Policy version cannot be deleted."
                ),
                frappe.PermissionError,
            )

    def _set_policy_identity(self) -> None:
        root = frappe.db.get_value(
            "NPI Project Control Policy",
            self.project_control_policy,
            ["global_id", "policy_code", "enabled"],
            as_dict=True,
        )
        if (
            root is None
            or type(root.enabled) not in {bool, int}
            or int(root.enabled) != 1
        ):
            frappe.throw(
                _("Select an enabled Project Control Policy."),
                frappe.ValidationError,
            )
        root_global_id = _uuid(
            root.global_id,
            _("Policy Global ID"),
        )
        linked_global_id = _uuid(
            self.project_control_policy,
            _("Project Control Policy"),
        )
        if linked_global_id != root_global_id:
            _invalid_policy_identity()
        root_policy_code = _required_text(
            root.policy_code,
            _("Project Control Policy Code"),
            maximum=64,
        )
        if self.policy_global_id and (
            _uuid(self.policy_global_id, _("Policy Global ID"))
            != root_global_id
        ):
            _invalid_policy_identity()
        if self.policy_code and self.policy_code != root_policy_code:
            _invalid_policy_identity()

        policy_version = _positive_integer(
            self.policy_version,
            _("Policy Version"),
        )
        expected_global_id = uuid5(
            _POLICY_VERSION_NAMESPACE,
            f"{root_global_id}:{policy_version}",
        )
        if self.global_id and (
            _uuid(self.global_id, _("Global ID"))
            != str(expected_global_id)
        ):
            _invalid_policy_identity()
        expected_version_key = f"{root_global_id}:{policy_version}"
        if self.version_key and self.version_key != expected_version_key:
            _invalid_policy_identity()

        self.project_control_policy = root_global_id
        self.policy_global_id = root_global_id
        self.policy_code = root_policy_code
        self.policy_version = policy_version
        self.global_id = str(expected_global_id)
        self.version_key = expected_version_key

    def _validated_prior_reference(
        self,
        previous: object | None,
    ) -> PriorPolicyVersionReference | None:
        supplied = _optional_prior_reference(self.prior_version_ref)
        if self.policy_version == 1:
            if supplied is not None:
                frappe.throw(
                    _(
                        "The first Project Control Policy version cannot have a prior version."
                    ),
                    frappe.ValidationError,
                )
            if previous is None:
                existing = frappe.db.get_value(
                    "NPI Project Control Policy Version",
                    {"policy_global_id": self.policy_global_id},
                    ["name"],
                    as_dict=True,
                )
                if existing is not None:
                    _invalid_version_sequence()
            return None

        prior_key = (
            f"{self.policy_global_id}:{self.policy_version - 1}"
        )
        prior = frappe.db.get_value(
            "NPI Project Control Policy Version",
            prior_key,
            _PRIOR_FIELDS,
            as_dict=True,
        )
        if prior is None or prior.publication_state != "published":
            _invalid_version_sequence()
        try:
            prior_snapshot = _json_value(
                prior.snapshot,
                expected_type=dict,
                label=_("Prior Policy Snapshot"),
            )
            prior_snapshot_hash = _snapshot_hash(prior_snapshot)
            reference = PriorPolicyVersionReference(
                global_id=UUID(str(prior.global_id)),
                policy_version=prior.policy_version,
                snapshot_hash=prior.snapshot_hash,
            )
        except RequestValidationFailed as error:
            _throw_domain_validation(error)
        except (AttributeError, TypeError, ValueError):
            _invalid_version_sequence()

        if (
            str(prior.policy_global_id) != self.policy_global_id
            or prior.policy_code != self.policy_code
            or prior.policy_version != self.policy_version - 1
            or prior_snapshot.get("schemaVersion") != 1
            or prior_snapshot.get("globalId") != str(prior.global_id)
            or prior_snapshot.get("policyGlobalId")
            != str(prior.policy_global_id)
            or prior_snapshot.get("policyCode") != prior.policy_code
            or prior_snapshot.get("policyVersion")
            != prior.policy_version
            or prior_snapshot_hash != reference.snapshot_hash
        ):
            _invalid_version_sequence()
        if supplied is not None and supplied != reference:
            frappe.throw(
                _(
                    "The prior Project Control Policy version reference does not match the published predecessor."
                ),
                frappe.ValidationError,
            )
        if previous is not None and supplied is None:
            frappe.throw(
                _(
                    "The prior Project Control Policy version reference is required."
                ),
                frappe.ValidationError,
            )
        return reference

    def _apply_domain_policy(
        self,
        policy: ProjectControlPolicyVersion,
    ) -> None:
        snapshot = policy.canonical_dict()
        self.global_id = str(policy.global_id)
        self.policy_global_id = str(policy.policy_global_id)
        self.policy_code = policy.policy_code
        self.policy_version = policy.policy_version
        self.version_key = (
            f"{policy.policy_global_id}:{policy.policy_version}"
        )
        self.optimistic_version = policy.version
        self.title = policy.title
        self.publication_state = policy.publication_state.value
        self.prior_version_ref = (
            _canonical(policy.prior_version_ref.canonical_dict())
            if policy.prior_version_ref is not None
            else None
        )
        self.authority_slots = _canonical(list(policy.authority_slots))
        self.health_assessment_slot = policy.health_assessment_slot
        self.health_rules = _canonical(snapshot["healthRules"])
        self.require_all_dimensions = int(
            policy.aggregation.require_all
        )
        self.lifecycle_transitions = _canonical(
            snapshot["transitions"]
        )
        self.snapshot = _canonical(snapshot)
        self.snapshot_hash = policy.snapshot_hash
        self.published_at = (
            now_datetime()
            if policy.publication_state
            is ControlPolicyPublicationState.PUBLISHED
            else None
        )


def _authority_slots(value: object) -> tuple[str, ...]:
    parsed = _json_value(
        value,
        expected_type=list,
        label=_("Project Control Authority Slots"),
    )
    if any(type(item) is not str for item in parsed):
        frappe.throw(
            _(
                "Project Control Authority Slots contains an unsupported value."
            ),
            frappe.ValidationError,
        )
    return tuple(parsed)


def _health_rules(value: object) -> tuple[HealthDimensionRule, ...]:
    parsed = _json_value(
        value,
        expected_type=list,
        label=_("Project Health Rules"),
    )
    expected_fields = {
        "dimension",
        "mode",
        "greenThreshold",
        "yellowThreshold",
    }
    if any(
        type(item) is not dict or set(item) != expected_fields
        for item in parsed
    ):
        frappe.throw(
            _("Project Health Rules contains an unsupported field."),
            frappe.ValidationError,
        )
    try:
        return tuple(
            HealthDimensionRule(
                dimension=HealthDimension(item["dimension"]),
                mode=HealthRuleMode(item["mode"]),
                green_threshold=item["greenThreshold"],
                yellow_threshold=item["yellowThreshold"],
            )
            for item in parsed
        )
    except RequestValidationFailed as error:
        _throw_domain_validation(error)
    except (TypeError, ValueError):
        frappe.throw(
            _("Project Health Rules contains an unsupported value."),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def _aggregation(value: object) -> HealthAggregationRule:
    if type(value) not in {bool, int} or int(value) not in {0, 1}:
        frappe.throw(
            _(
                "Require All Health Dimensions must be a valid true or false value."
            ),
            frappe.ValidationError,
        )
    return HealthAggregationRule(
        mode=HealthAggregationMode.WORST_STATUS,
        require_all=bool(value),
    )


def _lifecycle_transitions(
    value: object,
) -> tuple[ProjectTransitionRule, ...]:
    parsed = _json_value(
        value,
        expected_type=list,
        label=_("Project Lifecycle Transitions"),
    )
    expected_fields = {
        "sourceState",
        "action",
        "targetState",
        "authoritySlot",
        "prerequisites",
    }
    if any(
        type(item) is not dict
        or set(item) != expected_fields
        or type(item["prerequisites"]) is not list
        or any(
            type(prerequisite) is not str
            for prerequisite in item["prerequisites"]
        )
        for item in parsed
    ):
        frappe.throw(
            _(
                "Project Lifecycle Transitions contains an unsupported field."
            ),
            frappe.ValidationError,
        )
    try:
        return tuple(
            ProjectTransitionRule(
                source_state=ProjectLifecycleState(item["sourceState"]),
                action=ProjectControlAction(item["action"]),
                target_state=ProjectLifecycleState(item["targetState"]),
                authority_slot=item["authoritySlot"],
                prerequisites=tuple(
                    ProjectPrerequisiteKey(prerequisite)
                    for prerequisite in item["prerequisites"]
                ),
            )
            for item in parsed
        )
    except RequestValidationFailed as error:
        _throw_domain_validation(error)
    except (TypeError, ValueError):
        frappe.throw(
            _(
                "Project Lifecycle Transitions contains an unsupported value."
            ),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def _optional_prior_reference(
    value: object,
) -> PriorPolicyVersionReference | None:
    if value in (None, ""):
        return None
    parsed = _json_value(
        value,
        expected_type=dict,
        label=_("Prior Policy Version Reference"),
    )
    if set(parsed) != {"globalId", "version", "snapshotHash"}:
        frappe.throw(
            _(
                "Prior Policy Version Reference contains an unsupported field."
            ),
            frappe.ValidationError,
        )
    try:
        return PriorPolicyVersionReference(
            global_id=UUID(str(parsed["globalId"])),
            policy_version=parsed["version"],
            snapshot_hash=parsed["snapshotHash"],
        )
    except RequestValidationFailed as error:
        _throw_domain_validation(error)
    except (TypeError, ValueError):
        frappe.throw(
            _("Enter a valid Prior Policy Version Reference."),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def _json_value(
    value: object,
    *,
    expected_type: type[list] | type[dict],
    label: str,
) -> list[Any] | dict[str, Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if type(parsed) is not expected_type:
        frappe.throw(
            _("{field} must contain valid JSON.").format(field=label),
            frappe.ValidationError,
        )
    return parsed


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _snapshot_hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        frappe.throw(
            _("{field} must be greater than zero.").format(field=label),
            frappe.ValidationError,
        )
    return value


def _uuid(value: object, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        frappe.throw(
            _("{field} must be a valid UUID.").format(field=label),
            frappe.ValidationError,
        )
    raise AssertionError("Frappe validation must raise an exception.")


def _required_text(
    value: object,
    label: str,
    *,
    maximum: int,
) -> str:
    if not isinstance(value, str):
        frappe.throw(
            _("{field} must be valid text.").format(field=label),
            frappe.ValidationError,
        )
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        frappe.throw(
            _("{field} must be valid text.").format(field=label),
            frappe.ValidationError,
        )
    return normalized


def _assert_immutable_fields(
    document: object,
    previous: object,
    fields: tuple[str, ...],
) -> None:
    for fieldname in fields:
        if document.get(fieldname) != previous.get(fieldname):
            frappe.throw(
                _("A protected field cannot be changed."),
                frappe.ValidationError,
            )


def _throw_domain_validation(error: RequestValidationFailed) -> None:
    message = (
        error.field_errors[0].get("message")
        if error.field_errors
        else None
    )
    frappe.throw(
        message or _("Enter a valid value."),
        frappe.ValidationError,
    )


def _invalid_policy_identity() -> None:
    frappe.throw(
        _(
            "The Project Control Policy version does not match its policy root."
        ),
        frappe.ValidationError,
    )


def _invalid_version_sequence() -> None:
    frappe.throw(
        _(
            "Publish each Project Control Policy version before creating the next."
        ),
        frappe.ValidationError,
    )
