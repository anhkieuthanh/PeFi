#!/usr/bin/env python3
"""Smoke import checker for key project modules.

This script adds the repo root to sys.path and attempts to import a list of modules,
printing a short pass/fail and the exception traceback for failures.
"""
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

modules = [
    "src.config",
    "src.utils.text_processor",
    "src.utils.telegram_handlers",
    "database.database",
]

print(f"Repo root: {REPO_ROOT}")

for m in modules:
    print(f"\nImporting {m}...")
    try:
        __import__(m, fromlist=["*"])
        print(f"✔ {m} imported OK")
    except Exception as e:
        print(f"✖ {m} import FAILED: {e}")
        traceback.print_exc()

print("\nSmoke import check complete.")
