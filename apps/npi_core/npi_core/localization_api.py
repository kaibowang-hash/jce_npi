from __future__ import annotations

from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.defaults import get_defaults_for, set_user_default
from frappe.sessions import get_csrf_token
from frappe.translate import get_all_translations, get_user_lang

from .api import frappe_domain_call, record_safe_diagnostic
from .foundation.errors import (
    LocalizationUnavailable,
    PermissionDenied,
    RequestValidationFailed,
)
from .foundation.localization import (
    ALLOWED_LANGUAGE_CODES,
    CANONICAL_CATALOG_LANGUAGE,
    CatalogConfigurationError,
    build_translation_catalog,
    load_runtime_catalog,
    validate_language_code,
)
from .request_security import (
    authenticated_user,
    reject_unexpected_request_fields,
    require_csrf_token,
)

APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY = (
    "npi_one_app_shell_navigation_collapsed"
)
_STORED_BOOLEAN_VALUES = {True: "true", False: "false"}


def _translations_directory() -> Path:
    return Path(frappe.get_app_path("npi_core", "translations"))


def _catalog_for(language: str) -> dict[str, object]:
    translations_directory = _translations_directory()
    try:
        canonical_catalog = load_runtime_catalog(
            translations_directory / f"{CANONICAL_CATALOG_LANGUAGE}.csv"
        )
        direct_catalog = None
        if language != "en":
            direct_catalog = load_runtime_catalog(translations_directory / f"{language}.csv")
        merged_translations = {} if language == "en" else get_all_translations(language)
        return build_translation_catalog(
            language,
            canonical_catalog,
            direct_catalog,
            merged_translations,
        )
    except CatalogConfigurationError as error:
        record_safe_diagnostic(
            code="LOCALIZATION_CONFIGURATION_ERROR",
            title="NPI localization configuration error",
            exception_type=type(error).__name__,
        )
        raise LocalizationUnavailable() from error


def _navigation_collapsed_preference(user_id: str) -> bool:
    stored_value = get_defaults_for(parent=user_id).get(
        APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY
    )
    if stored_value == _STORED_BOOLEAN_VALUES[True]:
        return True
    if stored_value == _STORED_BOOLEAN_VALUES[False]:
        return False
    return False


def _session_bootstrap(
    user_id: str,
    language: str | None = None,
    *,
    navigation_collapsed: bool | None = None,
) -> dict[str, Any]:
    resolved_language = validate_language_code(language or get_user_lang(user_id))
    resolved_navigation_collapsed = (
        _navigation_collapsed_preference(user_id)
        if navigation_collapsed is None
        else navigation_collapsed
    )
    return {
        "userId": user_id,
        "isSystemManager": "System Manager" in frappe.get_roles(user_id),
        "language": resolved_language,
        "allowedLanguages": list(ALLOWED_LANGUAGE_CODES),
        "csrfToken": get_csrf_token(),
        "catalog": _catalog_for(resolved_language),
        "preferences": {
            "navigationCollapsed": resolved_navigation_collapsed,
        },
    }


def _set_current_user_language(user_id: str, language: Any) -> dict[str, Any]:
    if language is None:
        raise RequestValidationFailed(
            [{"path": "language", "message": _("This field is required.")}]
        )
    language = validate_language_code(language)
    bootstrap = _session_bootstrap(user_id, language)
    user = frappe.get_doc("User", user_id)
    previous_language = user.language
    user.language = language
    try:
        user.save()
        frappe.clear_cache(user=user_id)
    except frappe.PermissionError as error:
        user.language = previous_language
        raise PermissionDenied() from error
    except Exception:
        # The request boundary rolls the database transaction back. Restore the
        # in-memory document as well so an error response cannot observe a
        # target locale that was never committed.
        user.language = previous_language
        raise

    # Keep the current request in its original locale until persistence and
    # cache invalidation have both succeeded. This prevents a failed language
    # change from returning an error translated in the uncommitted locale.
    frappe.local.lang = language
    frappe.local.user_lang = language
    return bootstrap


def _set_current_user_navigation_preference(
    user_id: str, collapsed: Any
) -> dict[str, Any]:
    if collapsed is None:
        raise RequestValidationFailed(
            [{"path": "collapsed", "message": _("This field is required.")}]
        )
    if type(collapsed) is not bool:
        raise RequestValidationFailed(
            [
                {
                    "path": "collapsed",
                    "message": _("Select a valid true or false value."),
                }
            ]
        )
    bootstrap = _session_bootstrap(
        user_id,
        navigation_collapsed=collapsed,
    )
    set_user_default(
        APP_SHELL_NAVIGATION_COLLAPSED_DEFAULT_KEY,
        _STORED_BOOLEAN_VALUES[collapsed],
        user=user_id,
    )
    return bootstrap


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_session_bootstrap(**request_fields: Any) -> dict[str, Any] | None:
    """Return the authenticated NPI session locale and its effective catalog."""

    def handle() -> dict[str, Any]:
        user_id = authenticated_user()
        reject_unexpected_request_fields(frozenset(), request_fields)
        return _session_bootstrap(user_id)

    return frappe_domain_call(handle, cache_control="private, no-store")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def logout_current_session(**request_fields: Any) -> dict[str, Any] | None:
    """End only the authenticated Frappe session behind the LaunchFlow BFF."""

    def handle() -> dict[str, Any]:
        authenticated_user()
        require_csrf_token()
        reject_unexpected_request_fields(frozenset(), request_fields)
        frappe.local.login_manager.logout()
        return {"signedOut": True}

    return frappe_domain_call(handle, cache_control="private, no-store")


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_current_user_navigation_preference(
    collapsed: Any = None, **request_fields: Any
) -> dict[str, Any] | None:
    """Persist the authenticated user's explicit App Shell navigation preference."""

    def handle() -> dict[str, Any]:
        user_id = authenticated_user()
        require_csrf_token()
        reject_unexpected_request_fields(
            frozenset({"collapsed"}), request_fields
        )
        return _set_current_user_navigation_preference(user_id, collapsed)

    return frappe_domain_call(handle, cache_control="private, no-store")


@frappe.whitelist(allow_guest=True, methods=["PUT"])
def set_current_user_language(
    language: Any = None, **request_fields: Any
) -> dict[str, Any] | None:
    """Persist the authenticated user's supported Frappe language code."""

    def handle() -> dict[str, Any]:
        user_id = authenticated_user()
        require_csrf_token()
        reject_unexpected_request_fields(
            frozenset({"language"}), request_fields
        )
        return _set_current_user_language(user_id, language)

    return frappe_domain_call(handle, cache_control="private, no-store")
