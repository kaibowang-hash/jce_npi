from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping

from npi_core.foundation.errors import RequestValidationFailed

try:
    from frappe import _
except ImportError:  # Keeps this domain independently testable.

    def _identity_translation(source: str) -> str:
        return source

    _ = _identity_translation


REPORTING_SCHEMA_VERSION = 1
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
MAX_SEARCH_TERM = 100
MAX_FILTER_VALUE = 128

_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class SearchKind(StrEnum):
    PROJECT = "project"
    CUSTOMER = "customer"
    PART = "part"
    TOOLING = "tooling"
    DOCUMENT = "document"
    TRIAL = "trial"
    DEFECT = "defect"
    CHANGE = "change"
    FILE = "file"


class SourceSystem(StrEnum):
    NPI_ONE = "NPI_ONE"
    ERPNEXT = "ERPNEXT"
    MIXED = "MIXED"


class Availability(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class KpiValueKind(StrEnum):
    PERCENT = "percent"
    DAYS = "days"


def _problem(path: str, message: str) -> RequestValidationFailed:
    return RequestValidationFailed([{"path": path, "message": message}])


def _optional_reference(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid reference."))
    normalized = value.strip()
    if _REFERENCE.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid reference."))
    return normalized


def _optional_email(value: object, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _problem(path, _("Enter a valid user ID."))
    normalized = value.strip().casefold()
    if len(normalized) > 254 or _EMAIL.fullmatch(normalized) is None:
        raise _problem(path, _("Enter a valid user ID."))
    return normalized


def page_size(value: object | None) -> int:
    if value is None:
        return DEFAULT_PAGE_SIZE
    if type(value) is not int or not 1 <= value <= MAX_PAGE_SIZE:
        raise _problem("limit", _("Enter a page size from 1 to 100."))
    return value


def search_term(value: object) -> str:
    if not isinstance(value, str):
        raise _problem("query", _("Enter at least two search characters."))
    normalized = " ".join(value.split())
    if not 2 <= len(normalized) <= MAX_SEARCH_TERM:
        raise _problem("query", _("Enter between 2 and 100 search characters."))
    return normalized


def search_kinds(values: object | None) -> tuple[SearchKind, ...]:
    if values is None:
        return tuple(SearchKind)
    if not isinstance(values, (tuple, list)) or not values:
        raise _problem("kinds", _("Select at least one search object type."))
    try:
        result = tuple(SearchKind(str(value)) for value in values)
    except ValueError:
        raise _problem("kinds", _("Select supported search object types.")) from None
    if len(result) != len(set(result)):
        raise _problem("kinds", _("Search object types must be unique."))
    return tuple(sorted(result, key=str))


@dataclass(frozen=True, slots=True)
class PortfolioFilters:
    customer_reference_key: str | None = None
    owner_user_id: str | None = None
    project_type: str | None = None
    factory_reference_key: str | None = None
    sop_month: str | None = None
    lifecycle_state: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "customer_reference_key",
            _optional_reference(self.customer_reference_key, "customerReferenceKey"),
        )
        object.__setattr__(
            self,
            "factory_reference_key",
            _optional_reference(self.factory_reference_key, "factoryReferenceKey"),
        )
        object.__setattr__(
            self,
            "owner_user_id",
            _optional_email(self.owner_user_id, "ownerUserId"),
        )
        if self.project_type not in {None, "customer_owned_tool", "new_tool", "tool_change"}:
            raise _problem("projectType", _("Select a supported Project type."))
        if self.lifecycle_state not in {
            None,
            "draft",
            "proposed",
            "active",
            "on_hold",
            "completed",
            "cancelled",
        }:
            raise _problem("lifecycleState", _("Select a supported Project state."))
        if self.sop_month is not None and _MONTH.fullmatch(self.sop_month) is None:
            raise _problem("sopMonth", _("Enter a month in YYYY-MM format."))

    def canonical_dict(self) -> dict[str, str | None]:
        return {
            "customerReferenceKey": self.customer_reference_key,
            "factoryReferenceKey": self.factory_reference_key,
            "lifecycleState": self.lifecycle_state,
            "ownerUserId": self.owner_user_id,
            "projectType": self.project_type,
            "sopMonth": self.sop_month,
        }


@dataclass(frozen=True, slots=True)
class KpiDefinition:
    key: str
    label_source: str
    value_kind: KpiValueKind
    numerator_source: str
    denominator_source: str
    source_system: SourceSystem
    time_zone: str = "site"

    def public_dict(self) -> dict[str, str | int]:
        return {
            "schemaVersion": REPORTING_SCHEMA_VERSION,
            "key": self.key,
            "labelSource": self.label_source,
            "valueKind": self.value_kind.value,
            "numeratorSource": self.numerator_source,
            "denominatorSource": self.denominator_source,
            "sourceSystem": self.source_system.value,
            "timeZone": self.time_zone,
        }


KPI_DEFINITIONS = (
    KpiDefinition(
        key="project_sop_on_time_rate",
        label_source="Project SOP on-time rate",
        value_kind=KpiValueKind.PERCENT,
        numerator_source="completed_projects_at_or_before_target_sop",
        denominator_source="completed_projects_with_controlled_completion_date_and_target_sop",
        source_system=SourceSystem.NPI_ONE,
    ),
    KpiDefinition(
        key="project_cycle_time_days",
        label_source="Project cycle time",
        value_kind=KpiValueKind.DAYS,
        numerator_source="sum_controlled_project_completion_date_minus_activation_date_days",
        denominator_source="completed_projects_with_controlled_activation_and_completion_dates",
        source_system=SourceSystem.NPI_ONE,
    ),
    KpiDefinition(
        key="trial_first_pass_rate",
        label_source="Trial first-pass rate",
        value_kind=KpiValueKind.PERCENT,
        numerator_source="accepted_trial_plans_whose_first_completed_round_was_accepted",
        denominator_source="accepted_trial_plans_with_at_least_one_completed_round",
        source_system=SourceSystem.NPI_ONE,
    ),
    KpiDefinition(
        key="project_cost_variance_rate",
        label_source="Project cost variance rate",
        value_kind=KpiValueKind.PERCENT,
        numerator_source="sum_erp_actual_cost_minus_approved_budget",
        denominator_source="sum_approved_budget_for_fresh_erp_project_cost_projections",
        source_system=SourceSystem.MIXED,
    ),
)


CONFIGURATION_CAPABILITIES = (
    {
        "key": "project_templates",
        "labelSource": "Project templates",
        "mode": "versioned_commands",
        "route": "/administration/project-templates",
    },
    {
        "key": "gate_templates",
        "labelSource": "Gate templates",
        "mode": "versioned_commands",
        "route": "/administration/gate-templates",
    },
    {
        "key": "project_work_policies",
        "labelSource": "Project work policies",
        "mode": "versioned_commands",
        "route": "/administration/project-work-policies",
    },
    {
        "key": "readiness_templates",
        "labelSource": "NPI readiness templates",
        "mode": "versioned_commands",
        "route": "/administration/readiness-templates",
    },
    {
        "key": "production_transition_policies",
        "labelSource": "Production transition policies",
        "mode": "versioned_commands",
        "route": "/administration/production-transition-policies",
    },
    {
        "key": "integration_operations",
        "labelSource": "Integration operations",
        "mode": "operation_specific",
        "route": "/administration/integration-operations",
    },
)


def query_fingerprint(scope: str, values: Mapping[str, object]) -> str:
    payload = {
        "schemaVersion": REPORTING_SCHEMA_VERSION,
        "scope": scope,
        "values": dict(values),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class PageCursor:
    query_fingerprint: str
    sort_value: str
    global_id: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", self.query_fingerprint):
            raise ValueError("Cursor query fingerprint is invalid.")
        for value in (self.sort_value, self.global_id):
            if not isinstance(value, str) or not value or len(value) > 280:
                raise ValueError("Cursor position is invalid.")


def encode_cursor(cursor: PageCursor, signing_key: bytes) -> str:
    if not isinstance(cursor, PageCursor) or len(signing_key) < 32:
        raise ValueError("Secure pagination is unavailable.")
    body = json.dumps(
        {
            "globalId": cursor.global_id,
            "queryFingerprint": cursor.query_fingerprint,
            "schemaVersion": REPORTING_SCHEMA_VERSION,
            "sortValue": cursor.sort_value,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    signature = hmac.new(signing_key, body, hashlib.sha256).digest()
    return _b64(body) + "." + _b64(signature)


def decode_cursor(value: object, signing_key: bytes, expected_fingerprint: str) -> PageCursor:
    if not isinstance(value, str) or len(value) > 1024 or value.count(".") != 1:
        raise _problem("cursor", _("Use a valid pagination cursor."))
    if len(signing_key) < 32:
        raise ValueError("Secure pagination is unavailable.")
    body_text, signature_text = value.split(".")
    try:
        body = _unb64(body_text)
        signature = _unb64(signature_text)
        payload = json.loads(body)
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise _problem("cursor", _("Use a valid pagination cursor.")) from None
    if not hmac.compare_digest(signature, hmac.new(signing_key, body, hashlib.sha256).digest()):
        raise _problem("cursor", _("Use a valid pagination cursor."))
    if not isinstance(payload, dict) or set(payload) != {
        "globalId",
        "queryFingerprint",
        "schemaVersion",
        "sortValue",
    } or payload.get("schemaVersion") != REPORTING_SCHEMA_VERSION:
        raise _problem("cursor", _("Use a valid pagination cursor."))
    try:
        cursor = PageCursor(
            query_fingerprint=payload["queryFingerprint"],
            sort_value=payload["sortValue"],
            global_id=payload["globalId"],
        )
    except (TypeError, ValueError):
        raise _problem("cursor", _("Use a valid pagination cursor.")) from None
    if cursor.query_fingerprint != expected_fingerprint:
        raise _problem("cursor", _("The pagination cursor does not match these filters."))
    return cursor


def source_availability(
    values: Iterable[Availability],
) -> Availability:
    materialized = tuple(values)
    if not materialized or all(value is Availability.UNAVAILABLE for value in materialized):
        return Availability.UNAVAILABLE
    if all(value is Availability.AVAILABLE for value in materialized):
        return Availability.AVAILABLE
    if all(value in {Availability.AVAILABLE, Availability.STALE} for value in materialized):
        return Availability.STALE
    return Availability.PARTIAL


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("invalid base64url")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
