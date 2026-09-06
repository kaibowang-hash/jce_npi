from __future__ import annotations

from .errors import VersionConflict


def next_version(current_version: int, expected_version: int) -> int:
    if current_version < 0 or expected_version < 0:
        raise ValueError("Version cannot be negative.")
    if current_version != expected_version:
        raise VersionConflict()
    return current_version + 1


def make_etag(global_id: str, version: int) -> str:
    if version < 0:
        raise ValueError("Version cannot be negative.")
    return f'W/"{global_id}:{version}"'
