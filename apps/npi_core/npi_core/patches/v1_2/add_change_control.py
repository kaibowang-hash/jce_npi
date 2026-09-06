from __future__ import annotations


def execute() -> None:
    """Record the additive schema checkpoint without creating business rows."""

    # The four standard DocTypes are synchronized by Frappe before this
    # post-model-sync patch. P9-01A intentionally has no defaults, fixtures,
    # legacy rewrite or production integration activation.
    return None
