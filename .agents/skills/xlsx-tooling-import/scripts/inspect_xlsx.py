#!/usr/bin/env python3
"""Compatibility entry point for the product-owned passive XLSX inspector."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
APP_ROOT = REPOSITORY_ROOT / "apps" / "npi_core"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from npi_core.tooling.xlsx_inspector import *  # noqa: F403
from npi_core.tooling.xlsx_inspector import _bounded_anchor_index, main


if __name__ == "__main__":
    raise SystemExit(main())
