from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Final


_REGISTRY_FILENAME = "policy_label_sources.json"
_REGISTRY_SCHEMA_VERSION = 1


class PolicyLabelRegistryError(RuntimeError):
    """The packaged Project work policy-label registry is unsafe to use."""


def _read_registry_text() -> str:
    try:
        packaged_registry = resources.files(__package__).joinpath(
            _REGISTRY_FILENAME
        )
        return packaged_registry.read_text(encoding="utf-8")
    except (
        FileNotFoundError,
        ModuleNotFoundError,
        OSError,
        TypeError,
        UnicodeError,
    ):
        local_registry = Path(__file__).with_name(_REGISTRY_FILENAME)
        try:
            return local_registry.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise PolicyLabelRegistryError(
                "Project work policy-label registry is unavailable."
            ) from error


def _parse_registry(text: str) -> frozenset[str]:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as error:
        raise PolicyLabelRegistryError(
            "Project work policy-label registry is not valid JSON."
        ) from error

    if (
        not isinstance(payload, dict)
        or set(payload) != {"schemaVersion", "labelSources"}
        or type(payload["schemaVersion"]) is not int
        or payload["schemaVersion"] != _REGISTRY_SCHEMA_VERSION
        or not isinstance(payload["labelSources"], list)
    ):
        raise PolicyLabelRegistryError(
            "Project work policy-label registry has an unsupported shape."
        )

    sources = payload["labelSources"]
    if (
        not sources
        or any(
            not isinstance(source, str)
            or not source
            or source != source.strip()
            or len(source) > 140
            or not source.isascii()
            or not any(character.isalpha() for character in source)
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in source
            )
            for source in sources
        )
        or len(set(sources)) != len(sources)
        or sources != sorted(sources)
    ):
        raise PolicyLabelRegistryError(
            "Project work policy-label registry contains invalid label sources."
        )
    return frozenset(sources)


POLICY_LABEL_SOURCES: Final[frozenset[str]] = _parse_registry(
    _read_registry_text()
)
