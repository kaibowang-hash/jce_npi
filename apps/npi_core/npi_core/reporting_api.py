from __future__ import annotations

import re
from datetime import date
from typing import Any, Protocol

import frappe
from frappe import _

from npi_core.api import frappe_domain_call
from npi_core.foundation.errors import PermissionDenied, RequestValidationFailed
from npi_core.foundation.security import Principal
from npi_core.reporting.domain import (
    PortfolioFilters,
    page_size,
    search_kinds,
    search_term,
)
from npi_core.request_security import (
    authenticated_principal,
    authenticated_user,
    reject_unexpected_request_fields,
    require_reporting_routes_enabled,
    response_request_id,
)


_PORTFOLIO_FIELDS = frozenset(
    {
        "customerReferenceKey",
        "ownerUserId",
        "projectType",
        "factoryReferenceKey",
        "sopMonth",
        "lifecycleState",
        "cursor",
        "limit",
    }
)
_SEARCH_FIELDS = frozenset({"query", "kinds", "cursor", "limit"})
_KPI_FIELDS = frozenset(
    {
        "fromMonth",
        "toMonth",
        "customerReferenceKey",
        "ownerUserId",
        "projectType",
        "factoryReferenceKey",
        "sopMonth",
        "lifecycleState",
    }
)
_CONFIGURATION_FIELDS = frozenset()
_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")


class ReportingRepositoryLike(Protocol):
    def portfolio(self, *, filters: PortfolioFilters, cursor: object | None, limit: int) -> dict[str, object]: ...

    def global_search(self, *, query: str, kinds: tuple, cursor: object | None, limit: int) -> dict[str, object]: ...

    def kpi_trends(self, *, from_month: str, to_month: str, filters: PortfolioFilters) -> dict[str, object]: ...

    def configuration_catalog(self) -> dict[str, object]: ...


def _repository_factory(*, principal: Principal) -> ReportingRepositoryLike:
    from npi_core.reporting.frappe_repository import FrappeReportingRepository

    return FrappeReportingRepository(principal=principal)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_project_portfolio(
    customerReferenceKey: Any = None,
    ownerUserId: Any = None,
    projectType: Any = None,
    factoryReferenceKey: Any = None,
    sopMonth: Any = None,
    lifecycleState: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _read_call(
        _PORTFOLIO_FIELDS,
        request_fields,
        lambda repository: repository.portfolio(
            filters=_filters(
                customerReferenceKey,
                ownerUserId,
                projectType,
                factoryReferenceKey,
                sopMonth,
                lifecycleState,
            ),
            cursor=cursor,
            limit=page_size(_optional_integer(limit)),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def search(
    query: Any = None,
    kinds: Any = None,
    cursor: Any = None,
    limit: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _read_call(
        _SEARCH_FIELDS,
        request_fields,
        lambda repository: repository.global_search(
            query=search_term(query),
            kinds=search_kinds(_kind_values(kinds)),
            cursor=cursor,
            limit=page_size(_optional_integer(limit)),
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_kpi_trends(
    fromMonth: Any = None,
    toMonth: Any = None,
    customerReferenceKey: Any = None,
    ownerUserId: Any = None,
    projectType: Any = None,
    factoryReferenceKey: Any = None,
    sopMonth: Any = None,
    lifecycleState: Any = None,
    **request_fields: Any,
) -> dict[str, Any] | None:
    return _read_call(
        _KPI_FIELDS,
        request_fields,
        lambda repository: _kpi_response(
            repository,
            fromMonth,
            toMonth,
            customerReferenceKey,
            ownerUserId,
            projectType,
            factoryReferenceKey,
            sopMonth,
            lifecycleState,
        ),
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_configuration_catalog(**request_fields: Any) -> dict[str, Any] | None:
    return _read_call(
        _CONFIGURATION_FIELDS,
        request_fields,
        lambda repository: repository.configuration_catalog(),
    )


def _read_call(allowed: frozenset[str], request_fields: dict[str, Any], operation):
    success_headers = {"X-Request-ID": response_request_id()}

    def handle() -> dict[str, Any]:
        require_reporting_routes_enabled()
        actor = authenticated_user()
        principal = authenticated_principal(actor)
        if principal.is_external:
            raise PermissionDenied()
        reject_unexpected_request_fields(allowed, request_fields)
        response = operation(_repository_factory(principal=principal))
        if not isinstance(response, dict):
            raise RuntimeError("The reporting response is invalid.")
        return response

    return frappe_domain_call(
        handle,
        cache_control="private, no-store",
        response_headers=success_headers,
    )


def _filters(customer, owner, project_type, factory, sop_month, lifecycle) -> PortfolioFilters:
    return PortfolioFilters(
        customer_reference_key=_optional_text(customer),
        owner_user_id=_optional_text(owner),
        project_type=_optional_text(project_type),
        factory_reference_key=_optional_text(factory),
        sop_month=_optional_text(sop_month),
        lifecycle_state=_optional_text(lifecycle),
    )


def _optional_text(value: object) -> str | None:
    return None if value is None or value == "" else str(value)


def _optional_integer(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise RequestValidationFailed([{"path": "limit", "message": _("Enter a valid integer.")}])
    try:
        return int(str(value))
    except ValueError:
        raise RequestValidationFailed([{"path": "limit", "message": _("Enter a valid integer.")}]) from None


def _kind_values(value: object | None) -> tuple[str, ...] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return tuple(item for item in value.split(",") if item)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    raise RequestValidationFailed([{"path": "kinds", "message": _("Select supported search object types.")}])


def _kpi_response(repository, start, end, customer, owner, project_type, factory, sop_month, lifecycle):
    from_month, to_month = _month_range(start, end)
    return repository.kpi_trends(
        from_month=from_month,
        to_month=to_month,
        filters=_filters(customer, owner, project_type, factory, sop_month, lifecycle),
    )


def _month_range(start: object, end: object) -> tuple[str, str]:
    if not isinstance(start, str) or _MONTH.fullmatch(start) is None:
        raise RequestValidationFailed([{"path": "fromMonth", "message": _("Enter a month in YYYY-MM format.")}])
    if not isinstance(end, str) or _MONTH.fullmatch(end) is None:
        raise RequestValidationFailed([{"path": "toMonth", "message": _("Enter a month in YYYY-MM format.")}])
    start_date = date.fromisoformat(start + "-01")
    end_date = date.fromisoformat(end + "-01")
    span = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    if span < 0 or span > 23:
        raise RequestValidationFailed([{"path": "toMonth", "message": _("Select a range of no more than 24 months.")}])
    return start, end
