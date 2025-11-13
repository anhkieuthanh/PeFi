from pathlib import Path
import sys, json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import config
from utils import text_processor

class DummyResponse:
    def __init__(self, text: str):
        self.text = text

class MockModel:
    def __init__(self, response_text: str):
        self._response_text = response_text
    def generate_content(self, inputs, generation_config=None, request_options=None):
        return DummyResponse(self._response_text)

payload = {
    "intent": "record_transaction",
    "confidence": 0.77,
    "explanation": "Has amount and recipient -> record"
}
resp = "```json\n" + json.dumps(payload) + "\n```"
mock_model = MockModel(resp)

# patch config.get_text_model
config.get_text_model = lambda *a, **k: mock_model

raw = "Mình đã trả 250000 VND cho thực phẩm hôm nay"
out = text_processor.preprocess_and_classify_text(raw)
print(out)
