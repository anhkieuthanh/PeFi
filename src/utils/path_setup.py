"""Utilities to standardize imports across run contexts.

Use setup_project_root() in modules that need to import `src.*` when code may be
executed from different working directories (project root vs src/).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def setup_project_root(current_file: Optional[str] = None) -> None:
    """Ensure the repository root is on sys.path so `from src import ...` works.

    Pass in __file__ from the caller for correct path resolution. Idempotent.
    """
    base = Path(current_file or __file__).resolve()
    # repo root: .../PeFi
    project_root = base.parents[2]
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
