from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from npi_core.foundation.localization import (
    CatalogConfigurationError,
    load_runtime_catalog,
)
from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    deny_controlled_history_delete,
    ensure_uuid,
    throw_domain_validation,
)
from npi_core.project_work.domain import (
    DomainWorkItemKind,
    KindLifecycle,
    LifecycleDefinition,
    LifecycleState,
    PolicyPublicationState,
    ProjectWorkPolicyVersion,
)
from npi_core.project_work.policy_labels import POLICY_LABEL_SOURCES


class NPIProjectWorkPolicyVersion(Document):
    """Administrative policy definition; published versions are immutable."""

    _IDENTITY_FIELDS = (
        "global_id",
        "policy_global_id",
        "policy_key",
        "policy_version",
        "version_key",
    )

    def autoname(self) -> None:
        self._normalize()
        self.name = self.version_key

    def before_validate(self) -> None:
        self._normalize()

    def on_trash(self) -> None:
        if self.publication_state == "published":
            deny_controlled_history_delete()

    def validate(self) -> None:
        previous = self.get_doc_before_save()
        if previous is not None and previous.publication_state == "published":
            frappe.throw(
                _("A published Project work policy version cannot be changed."),
                frappe.ValidationError,
            )
        if previous is None:
            self.optimistic_version = 1
        else:
            assert_immutable_fields(self, previous, self._IDENTITY_FIELDS)
            self.optimistic_version = int(previous.optimistic_version) + 1
        policy = self._domain_policy()
        self.title = policy.title
        self.role_keys = json.dumps(
            list(policy.role_keys),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.wbs_states = json.dumps(
            policy.wbs_lifecycle.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.work_item_lifecycles = json.dumps(
            [
                lifecycle.canonical_dict()
                for lifecycle in policy.work_item_lifecycles
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.snapshot_hash = policy.snapshot_hash
        if self.publication_state == "published":
            self._require_translated_labels(policy)
            self.published_at = now_datetime()
        else:
            self.published_at = None

    def _normalize(self) -> None:
        self.policy_global_id = ensure_uuid(
            self.policy_global_id,
            _("Policy Global ID"),
        )
        if type(self.policy_version) is not int or self.policy_version < 1:
            frappe.throw(
                _("Policy Version must be greater than zero."),
                frappe.ValidationError,
            )
        policy = self._domain_policy()
        self.global_id = str(policy.global_id)
        self.version_key = f"{self.policy_global_id}:{self.policy_version}"

    def _domain_policy(self) -> ProjectWorkPolicyVersion:
        try:
            role_keys = tuple(
                str(value)
                for value in _json_value(
                    self.role_keys,
                    expected_type=list,
                    message=_("Project Role Keys must be a JSON array."),
                )
            )
            wbs_lifecycle = _lifecycle(
                _json_value(
                    self.wbs_states,
                    expected_type=dict,
                    message=_("WBS States must define one lifecycle object."),
                )
            )
            lifecycle_values = _json_value(
                self.work_item_lifecycles,
                expected_type=list,
                message=_("Work Item Lifecycles must be a JSON array."),
            )
            lifecycles = tuple(
                KindLifecycle(
                    DomainWorkItemKind(str(value["kind"])),
                    _lifecycle(
                        {
                            "initialStateKey": value["initialStateKey"],
                            "states": value["states"],
                        }
                    ),
                )
                for value in lifecycle_values
            )
            draft = ProjectWorkPolicyVersion.create_draft(
                policy_global_id=UUID(str(self.policy_global_id)),
                policy_key=self.policy_key,
                policy_version=self.policy_version,
                title=self.title,
                role_keys=role_keys,
                wbs_lifecycle=wbs_lifecycle,
                work_item_lifecycles=lifecycles,
            )
            return ProjectWorkPolicyVersion(
                global_id=draft.global_id,
                policy_global_id=draft.policy_global_id,
                policy_key=draft.policy_key,
                policy_version=draft.policy_version,
                version=int(self.optimistic_version or 1),
                title=draft.title,
                publication_state=PolicyPublicationState(
                    self.publication_state or "draft"
                ),
                role_keys=draft.role_keys,
                wbs_lifecycle=draft.wbs_lifecycle,
                work_item_lifecycles=draft.work_item_lifecycles,
            )
        except RequestValidationFailed as error:
            throw_domain_validation(error)
        except (KeyError, TypeError, ValueError):
            frappe.throw(_("Enter a valid Project Work Policy."), frappe.ValidationError)
        raise AssertionError("Frappe validation must raise an exception.")

    @staticmethod
    def _require_translated_labels(policy: ProjectWorkPolicyVersion) -> None:
        policy_label_sources = {
            state.label_source for state in policy.wbs_lifecycle.states
        }
        policy_label_sources.update(
            state.label_source
            for lifecycle in policy.work_item_lifecycles
            for state in lifecycle.lifecycle.states
        )
        if not policy_label_sources.issubset(POLICY_LABEL_SOURCES):
            frappe.throw(
                _("Enter a valid Project Work Policy."),
                frappe.ValidationError,
            )
        translations_directory = Path(
            frappe.get_app_path("npi_core", "translations")
        )
        try:
            catalogs = {
                language: load_runtime_catalog(
                    translations_directory / f"{language}.csv"
                )
                for language in ("zh", "zh-TW")
            }
        except CatalogConfigurationError:
            frappe.throw(
                _("Project Work Policy translations are unavailable."),
                frappe.ValidationError,
            )
        missing = sorted(
            source
            for source in POLICY_LABEL_SOURCES
            if any(source not in catalog for catalog in catalogs.values())
        )
        if missing:
            frappe.throw(
                _(
                    "Every Project Work Policy state label must have Simplified and Traditional Chinese translations."
                ),
                frappe.ValidationError,
            )


def _json_value(
    value: object,
    *,
    expected_type: type[list] | type[dict],
    message: str,
):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, expected_type):
        frappe.throw(message, frappe.ValidationError)
    return parsed


def _lifecycle(value: object) -> LifecycleDefinition:
    if not isinstance(value, dict) or set(value) != {
        "initialStateKey",
        "states",
    }:
        frappe.throw(
            _("Enter a valid lifecycle definition."),
            frappe.ValidationError,
        )
    states = value["states"]
    if not isinstance(states, list) or any(
        not isinstance(state, dict)
        or set(state) != {"key", "labelSource", "terminal"}
        for state in states
    ):
        frappe.throw(
            _("Lifecycle States must be a JSON array."),
            frappe.ValidationError,
        )
    return LifecycleDefinition(
        initial_state_key=str(value["initialStateKey"]),
        states=tuple(
            LifecycleState(
                key=str(state["key"]),
                label_source=str(state["labelSource"]),
                terminal=state["terminal"],
            )
            for state in states
        ),
    )
