from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator


QUALITY_TYPE_ERROR_STAGES = frozenset(
    {
        "P703_QUALITY_API_INVOKE",
        "P703_QUALITY_COMMAND_START",
        "P703_QUALITY_RUNNING_CONTEXT",
        "P703_QUALITY_TOOLING_CONTEXT",
        "P703_QUALITY_SAMPLE_RESOLVE",
        "P703_QUALITY_DEFECT_TIP",
        "P703_QUALITY_MEMBER_RESOLVE",
        "P703_QUALITY_ACTION_RESOLVE",
        "P703_QUALITY_EVIDENCE_RESOLVE",
        "P703_QUALITY_DEFECT_BUILD",
        "P703_QUALITY_DEFECT_SUCCESSOR_VALIDATE",
        "P703_QUALITY_RECEIPT_INSERT",
        "P703_QUALITY_TARGET_INSERT",
        "P703_QUALITY_AUDIT_APPEND",
        "P703_QUALITY_RESPONSE_BUILD",
        "P703_QUALITY_RECEIPT_SEAL",
        "P703_QUALITY_DEFECT_SNAPSHOT_PARSE",
        "P703_QUALITY_DEFECT_RUNNING_ROUND",
        "P703_QUALITY_DEFECT_CONTEXT",
        "P703_QUALITY_DEFECT_RESPONSIBILITY",
        "P703_QUALITY_DEFECT_EVIDENCE",
        "P703_QUALITY_DEFECT_PREDECESSOR",
        "P703_QUALITY_DEFECT_NORMALIZE",
    }
)

_TRACE_PATTERN = re.compile(r"^trace-[a-f0-9]{32}$")


@contextmanager
def quality_type_error_stage(code: str, trace_id: str) -> Iterator[None]:
    """Record a bounded P7-03 stage for an unexpected TypeError and re-raise it."""

    try:
        yield
    except TypeError as error:
        if code in QUALITY_TYPE_ERROR_STAGES and _TRACE_PATTERN.fullmatch(trace_id):
            try:
                from npi_core.api import record_safe_diagnostic

                record_safe_diagnostic(
                    code=code,
                    title="NPI Trial quality type error",
                    exception_type=type(error).__name__,
                    trace_id=trace_id,
                )
            except Exception:
                # Diagnostics are secondary and must not replace the original failure.
                pass
        raise
