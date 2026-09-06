from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import frappe
from frappe.defaults import (
    add_user_default,
    clear_user_default,
    get_defaults_for,
)

from npi_core.inspector_preferences.domain import (
    STORED_PREFERENCE_INVALID,
    USER_DEFAULT_KEY,
    InspectorPreference,
    InspectorPreferenceValidationError,
    decode_stored_preference,
    encode_stored_preference,
)


class InspectorPreferenceStore(Protocol):
    def read(self, *, actor_user_id: str, key: str) -> object | None: ...

    def write(
        self,
        *,
        actor_user_id: str,
        key: str,
        value: str,
    ) -> None: ...

    def invalidate(self, *, actor_user_id: str) -> None: ...


class FrappeUserDefaultInspectorPreferenceStore:
    def read(self, *, actor_user_id: str, key: str) -> object | None:
        return get_defaults_for(parent=actor_user_id).get(key)

    def write(
        self,
        *,
        actor_user_id: str,
        key: str,
        value: str,
    ) -> None:
        # Frappe returns a list when legacy or recreated-user rows contain
        # multiple values for one key. Its normal setter can also return early
        # when the first row already equals the requested value, leaving that
        # ambiguous state untouched, and Frappe v15's setter drops the supplied
        # parent type when it creates the replacement row. An explicit PUT is
        # the controlled repair boundary, so replace every actor/key row inside
        # the request transaction and bind the new row to the User lifecycle.
        clear_user_default(key, user=actor_user_id)
        add_user_default(
            key,
            value,
            user=actor_user_id,
            parenttype="User",
        )

    def invalidate(self, *, actor_user_id: str) -> None:
        frappe.clear_cache(user=actor_user_id)


@dataclass(frozen=True, slots=True)
class InspectorPreferenceLoad:
    preference: InspectorPreference
    recovery_reason: str | None


class FrappeInspectorPreferenceRepository:
    """Persist one fixed inspector layout under the authenticated actor."""

    def __init__(
        self,
        *,
        actor_user_id: str,
        store: InspectorPreferenceStore | None = None,
    ) -> None:
        if not isinstance(actor_user_id, str) or not actor_user_id:
            raise ValueError("The inspector preference actor is invalid.")
        self.actor_user_id = actor_user_id
        self.store = store or FrappeUserDefaultInspectorPreferenceStore()

    def load(self) -> InspectorPreferenceLoad:
        stored_value = self.store.read(
            actor_user_id=self.actor_user_id,
            key=USER_DEFAULT_KEY,
        )
        if stored_value is None:
            return InspectorPreferenceLoad(
                preference=InspectorPreference.default(),
                recovery_reason=None,
            )
        try:
            preference = decode_stored_preference(stored_value)
        except InspectorPreferenceValidationError:
            return InspectorPreferenceLoad(
                preference=InspectorPreference.default(),
                recovery_reason=STORED_PREFERENCE_INVALID,
            )
        return InspectorPreferenceLoad(
            preference=preference,
            recovery_reason=None,
        )

    def save(self, preference: InspectorPreference) -> InspectorPreference:
        encoded = encode_stored_preference(preference)
        try:
            self.store.write(
                actor_user_id=self.actor_user_id,
                key=USER_DEFAULT_KEY,
                value=encoded,
            )
            # Frappe normally clears this cache inside set_user_default. Make
            # the confirmed read independent of that implementation detail.
            self.store.invalidate(actor_user_id=self.actor_user_id)
            confirmed_value = self.store.read(
                actor_user_id=self.actor_user_id,
                key=USER_DEFAULT_KEY,
            )
            confirmed = decode_stored_preference(confirmed_value)
            if confirmed_value != encoded or confirmed != preference:
                raise RuntimeError(
                    "The stored inspector preference could not be confirmed."
                )
        except Exception as storage_error:
            try:
                self.store.invalidate(actor_user_id=self.actor_user_id)
            except Exception as invalidation_error:
                raise ExceptionGroup(
                    "Inspector preference storage and cache recovery failed.",
                    [storage_error, invalidation_error],
                ) from None
            raise
        return preference
