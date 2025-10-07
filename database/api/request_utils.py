from flask import request
import json
from typing import Any, Dict


def parse_json_request() -> Dict[str, Any]:
    """Safely parse JSON payload from Flask request.

    - Tries request.get_json(silent=True)
    - If None, falls back to request.get_data(as_text=True) and json.loads
    - If get_json returns a string, attempts json.loads on it
    - Always returns a dict (empty dict on failure)
    """
    data = request.get_json(silent=True)
    if data is None:
        raw = request.get_data(as_text=True)
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
    elif isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}

    # Ensure we return a dict
    if not isinstance(data, dict):
        return {}
    return data
