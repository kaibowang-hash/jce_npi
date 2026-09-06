from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import UnsupportedLanguage

ALLOWED_LANGUAGE_CODES = ("en", "zh", "zh-TW")
CANONICAL_CATALOG_LANGUAGE = "zh"


class CatalogConfigurationError(ValueError):
    """A runtime catalog cannot safely serve the NPI interface."""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    source: str
    translation: str
    context: str | None = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.context}" if self.context else self.source


def validate_language_code(language: Any) -> str:
    if not isinstance(language, str) or language not in ALLOWED_LANGUAGE_CODES:
        raise UnsupportedLanguage()
    return language


def parse_runtime_catalog(
    rows: Iterable[Sequence[str]], *, source_name: str = "runtime catalog"
) -> dict[str, CatalogEntry]:
    """Parse Frappe's headerless source, translation, optional-context CSV rows."""
    catalog: dict[str, CatalogEntry] = {}

    for line_number, row in enumerate(rows, start=1):
        if not row:
            continue
        if line_number == 1 and tuple(row[:3]) == (
            "source_string",
            "translated_string",
            "context",
        ):
            raise CatalogConfigurationError(f"{source_name} must not contain a header row")
        if len(row) not in (2, 3):
            raise CatalogConfigurationError(
                f"{source_name} line {line_number} must have two or three columns"
            )

        source = row[0].replace("\\n", "\n")
        translation = row[1].replace("\\n", "\n").strip()
        context = row[2] if len(row) == 3 and row[2] else None
        if not source.strip() or not translation:
            raise CatalogConfigurationError(
                f"{source_name} line {line_number} has an empty source or translation"
            )

        entry = CatalogEntry(source=source, translation=translation, context=context)
        if entry.key in catalog:
            raise CatalogConfigurationError(
                f"{source_name} line {line_number} duplicates key {entry.key!r}"
            )
        catalog[entry.key] = entry

    if not catalog:
        raise CatalogConfigurationError(f"{source_name} is empty")
    return catalog


def load_runtime_catalog(path: Path) -> dict[str, CatalogEntry]:
    try:
        with path.open(encoding="utf-8", newline="") as catalog_file:
            return parse_runtime_catalog(csv.reader(catalog_file), source_name=str(path))
    except OSError as error:
        raise CatalogConfigurationError(f"Unable to read runtime catalog {path}") from error


def build_translation_catalog(
    language: str,
    canonical_catalog: Mapping[str, CatalogEntry],
    direct_catalog: Mapping[str, CatalogEntry] | None,
    merged_translations: Mapping[str, str],
) -> dict[str, object]:
    """Filter Frappe's effective catalog to canonical NPI keys.

    Non-English locales must also contain every key in their direct app CSV.
    This keeps Frappe's parent-locale fallback from hiding missing zh-TW rows.
    """
    language = validate_language_code(language)
    if not canonical_catalog:
        raise CatalogConfigurationError("The canonical runtime catalog is empty")

    if language == "en":
        messages = {key: entry.source for key, entry in canonical_catalog.items()}
    else:
        if direct_catalog is None:
            raise CatalogConfigurationError(f"The direct {language} runtime catalog is missing")
        missing_direct = sorted(set(canonical_catalog).difference(direct_catalog))
        if missing_direct:
            raise CatalogConfigurationError(
                f"The direct {language} runtime catalog is missing "
                f"{len(missing_direct)} canonical keys"
            )

        messages: dict[str, str] = {}
        missing_effective: list[str] = []
        for key in canonical_catalog:
            translated = merged_translations.get(key)
            if not isinstance(translated, str) or not translated.strip():
                missing_effective.append(key)
                continue
            messages[key] = translated
        if missing_effective:
            raise CatalogConfigurationError(
                f"The effective {language} catalog is missing "
                f"{len(missing_effective)} canonical keys"
            )

    encoded = json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    version = hashlib.sha256(f"{language}\n{encoded}".encode()).hexdigest()
    return {"language": language, "version": version, "messages": messages}
