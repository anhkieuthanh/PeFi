#!/usr/bin/env python3
"""Unit tests for src/utils/text_processor.py

These tests mock the Gemini model returned by `config.get_text_model()` so they run
without network/API access.
"""

import sys
from pathlib import Path
import json

# Add src to path (repo-root/src)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config  # noqa: E402
from utils import text_processor  # noqa: E402


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


class MockModel:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def generate_content(self, inputs, generation_config=None, request_options=None):
        return DummyResponse(self._response_text)


def test_preprocess_and_classify_summarize(monkeypatch):
    # Prepare a JSON response indicating 'summarize_expenses'
    resp = json.dumps({
        "intent": "summarize_expenses",
        "confidence": 0.93,
        "explanation": "User asked for expense summary"
    })
    mock_model = MockModel(resp)

    monkeypatch.setattr(config, "get_text_model", lambda *a, **k: mock_model)

    raw = "\n  Tổng hợp chi tiêu tháng này cho tôi  \n\n"
    out = text_processor.preprocess_and_classify_text(raw)

    assert out["normalized_text"] == "Tổng hợp chi tiêu tháng này cho tôi"
    cls = out["classification"]
    assert cls["intent"] == "summarize_expenses"
    assert cls["confidence"] >= 0.9
    assert "summary" in cls["explanation"].lower()


def test_preprocess_and_classify_record(monkeypatch):
    # Prepare a JSON response indicating 'record_transaction' wrapped in code fences
    payload = {
        "intent": "record_transaction",
        "confidence": 0.77,
        "explanation": "Has amount and recipient -> record"
    }
    resp = "```json\n" + json.dumps(payload) + "\n```"
    mock_model = MockModel(resp)

    monkeypatch.setattr(config, "get_text_model", lambda *a, **k: mock_model)

    raw = "250000 VND cho thực phẩm hôm nay"
    out = text_processor.preprocess_and_classify_text(raw)
    assert out["normalized_text"] == "250000 VND cho thực phẩm hôm nay"
    cls = out["classification"]
    assert cls["intent"] == "record_transaction"
    assert 0.0 <= cls["confidence"] <= 1.0
    assert "record" in cls["explanation"].lower()


def test_heuristic_income_phrase(monkeypatch):
    # No Gemini call should be needed; heuristic should classify as record_transaction
    monkeypatch.setattr(config, "get_text_model", lambda *a, **k: (_ for _ in ()).throw(Exception("Should not be called")))

    raw = "Nhận lương 12 triệu"
    out = text_processor.preprocess_and_classify_text(raw)
    cls = out["classification"]
    assert cls["intent"] == "record_transaction"
    assert cls["confidence"] >= 0.9
    assert "heuristic" in cls["explanation"].lower()


def test_heuristic_expense_phrase(monkeypatch):
    # Expense phrase should also be recognized
    monkeypatch.setattr(config, "get_text_model", lambda *a, **k: (_ for _ in ()).throw(Exception("Should not be called")))

    raw = "Tôi trả 200k cho cafe"
    out = text_processor.preprocess_and_classify_text(raw)
    cls = out["classification"]
    assert cls["intent"] == "record_transaction"
    assert cls["confidence"] >= 0.9
    assert "heuristic" in cls["explanation"].lower()


def _run_as_script():
    """Run tests without pytest by invoking the test functions and printing results.

    This is a convenience for environments without pytest installed.
    """
    passed = 0
    total = 0

    def _run(fn):
        nonlocal passed, total
        total += 1
        try:
            # emulate minimal monkeypatch by passing a simple lambda setter
            class MP:
                def setattr(self, obj, name, val):
                    setattr(obj, name, val)

            fn(MP())
            print(f"✅ {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {fn.__name__}: Assertion failed: {e}")
        except Exception as e:
            print(f"❌ {fn.__name__}: Error: {e}")

    _run(test_preprocess_and_classify_summarize)
    _run(test_preprocess_and_classify_record)

    print(f"\nSummary: {passed}/{total} tests passed")


if __name__ == "__main__":
    _run_as_script()
