from __future__ import annotations


def execute() -> None:
    """Rebuild the derived My Work index without creating business defaults."""

    from npi_core.my_work.frappe_repository import rebuild_my_work_projection

    rebuild_my_work_projection()
