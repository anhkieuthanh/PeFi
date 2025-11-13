"""Helper module to standardize imports across different run contexts."""
import sys
from pathlib import Path


def ensure_repo_root():
    """Ensure the repository root is in sys.path for consistent imports."""
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def ensure_src_path():
    """Ensure the src directory is in sys.path."""
    src_path = Path(__file__).resolve().parents[1]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
